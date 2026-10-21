"""Cited answers: deterministic retrieval, a narrow LLM step, a deterministic checker.

The model sees only the top-k passages in scope. It may quote them and write
one short sentence built from those quotes, or abstain. The checker then
rejects (and abstains on) any answer that cites a passage it was not given,
quotes text that is not verbatim in the cited passage, or states a number that
appears in none of its quotes. Nothing the model writes is served unchecked.
"""
import importlib.util
import json
import re
import time
from pathlib import Path
from .dense import DenseRetriever, fuse
from .engine import Engine
from .retrieval import Retriever

METHODS = ('bm25', 'lsa', 'lsa-hybrid', 'dense', 'dense-hybrid')
TOP_K = 5
SYSTEM = """You answer questions about SEC filings using only the numbered passages you are given.
Return one JSON object and nothing else:
{"status": "answered", "answer": "<one sentence, at most 40 words>", "citations": [{"passage_id": "<id>", "quote": "<text copied exactly from that passage>"}]}
or, when the passages do not state the answer:
{"status": "abstained", "answer": "", "citations": []}
Rules:
- Each quote must be copied character for character from the passage with that passage_id. Do not paraphrase, fix, trim inside, or join quotes.
- Every number in the answer must appear in one of your quotes.
- Answer only what the passages state. Do not calculate, estimate, forecast or use outside knowledge.
- If the question asks for a period, date or entity the passages do not cover, abstain."""


class Retrieval:
    """Scope first (company + accessions), then one of five rankers."""
    def __init__(self, index, corpus=None, dense_encoder=None):
        self.index = index
        self.engine = Engine(index)
        corpus = Path(corpus) if corpus else None
        lsa = corpus/'data/semantic.json.gz' if corpus else None
        self.lsa = Retriever(index, lsa) if lsa and lsa.exists() else None
        # Dense needs the embedding package at query time; without it, fall back to BM25/LSA.
        usable = dense_encoder is not None or importlib.util.find_spec('fastembed') is not None
        self.dense = DenseRetriever(index, corpus/'data', dense_encoder) if usable and corpus and (corpus/'data/dense.json').exists() else None

    def scoped(self, scope):
        tickers = {p['ticker'] for p in self.index['passages']}
        if scope['company'] not in tickers:
            raise ValueError('Unknown company')
        accessions = set(scope.get('accessions') or [])
        passages = [p for p in self.index['passages'] if p['ticker'] == scope['company'] and (not accessions or p['accession'] in accessions)]
        if accessions and accessions - {p['accession'] for p in passages}:
            raise ValueError('Accession outside company or missing')
        return passages

    def rank(self, question, scope, method, k=TOP_K):
        if method not in METHODS:
            raise ValueError('Unknown retrieval method')
        candidates = self.scoped(scope)
        terms = self.engine.query_terms(question)
        if method in ('bm25', 'lsa-hybrid', 'dense-hybrid'):
            bm = self.engine.rank(candidates, terms)
        if method in ('lsa', 'lsa-hybrid'):
            if not self.lsa:
                raise ValueError('No LSA model for this corpus')
            ranked = self.lsa.rank(candidates, terms, 'semantic' if method == 'lsa' else 'hybrid')
        elif method in ('dense', 'dense-hybrid'):
            if not self.dense:
                raise ValueError('No dense vectors for this corpus')
            dense = self.dense.rank(candidates, question)
            ranked = dense if method == 'dense' else fuse(bm, dense)
        else:
            ranked = bm
        return [h['passage'] for h in ranked[:k]]


def prompt(question, passages):
    blocks = '\n\n'.join('[passage_id: {}] ({} {} {}, {})\n{}'.format(p['passage_id'], p['company'], p['form'], p['report_period'], p['section'], p['text']) for p in passages)
    return 'Question: {}\n\nPassages:\n\n{}'.format(question, blocks)


def parse(raw):
    text = raw.strip()
    fenced = re.match(r'^```(?:json)?\s*(.*?)\s*```$', text, re.S)
    if fenced:
        text = fenced.group(1)
    start, end = text.find('{'), text.rfind('}')
    if start < 0 or end < start:
        raise ValueError('no JSON object')
    value = json.loads(text[start:end+1])
    if not isinstance(value, dict):
        raise ValueError('not an object')
    return value


NUMBER = re.compile(r'\d[\d,]*(?:\.\d+)?')


def numbers(text):
    """Numbers as digit strings; single bare digits are ignored ("Q2", "3 months")."""
    return {n.replace(',', '').rstrip('.') for n in NUMBER.findall(text) if len(n) > 1}


def check(output, passages):
    """Deterministic gate. Returns (status, reason, answer, citations)."""
    given = {p['passage_id']: p['text'] for p in passages}
    if not isinstance(output, dict) or output.get('status') not in ('answered', 'abstained'):
        return 'abstained', 'rejected:malformed_output', '', []
    if output['status'] == 'abstained':
        return 'abstained', 'model_abstained', '', []
    answer, citations = output.get('answer'), output.get('citations')
    if not isinstance(answer, str) or not answer.strip() or not isinstance(citations, list) or not citations:
        return 'abstained', 'rejected:missing_answer_or_citation', '', []
    clean = []
    for c in citations:
        if not isinstance(c, dict) or not isinstance(c.get('passage_id'), str) or not isinstance(c.get('quote'), str):
            return 'abstained', 'rejected:malformed_citation', '', []
        if c['passage_id'] not in given:
            return 'abstained', 'rejected:citation_not_retrieved', '', []
        quote = c['quote'].strip()
        if len(quote) < 8:
            return 'abstained', 'rejected:quote_too_short', '', []
        if quote not in given[c['passage_id']]:
            return 'abstained', 'rejected:quote_not_verbatim', '', []
        clean.append(dict(passage_id=c['passage_id'], quote=quote))
    quoted = set().union(*(numbers(c['quote']) for c in clean))
    if numbers(answer) - quoted:
        return 'abstained', 'rejected:number_not_in_quotes', '', []
    return 'answered', 'checked_quotes', answer.strip(), clean


def answer(question, scope, retrieval, provider, method='dense-hybrid', k=TOP_K):
    passages = retrieval.rank(question, scope, method, k)
    record = dict(question=question, method=method, provider=provider.name, retrieved=[p['passage_id'] for p in passages])
    if not passages:
        return dict(record, status='abstained', reason='no_passages_in_scope', answer='', citations=[], raw=None, raw_status=None, latency_s=0.0, cost_usd=0.0, usage={})
    started = time.monotonic()
    reply = provider.complete(SYSTEM, prompt(question, passages))
    latency = reply.get('latency_s', time.monotonic() - started)
    try:
        output = parse(reply['text'])
    except (ValueError, json.JSONDecodeError):
        output = None
    status, reason, text, citations = check(output, passages)
    by_id = {p['passage_id']: p for p in passages}
    for c in citations:
        p = by_id[c['passage_id']]
        c.update(company=p['company'], ticker=p['ticker'], form=p['form'], accession=p['accession'], report_period=p['report_period'], section=p['section'], source_url=p['source_url'], sha256=p['sha256'])
    return dict(record, status=status, reason=reason, answer=text, citations=citations, raw=reply['text'],
                raw_status=output.get('status') if isinstance(output, dict) else None,
                latency_s=round(latency, 3), cost_usd=reply.get('cost_usd'), usage=reply.get('usage', {}))
