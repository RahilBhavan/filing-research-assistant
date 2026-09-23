"""Frozen, agent-authored development evaluation. Not human support grading."""
import hashlib
import json
import statistics
import time
from pathlib import Path
from .corpus import build_index
from .engine import Engine, Scope


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def evaluate(root,write=False):
    root = Path(root)
    frozen = json.loads((root/'evaluation/frozen.json').read_text())
    for path, expected in frozen['sha256'].items():
        if digest(root/path) != expected:
            raise ValueError('Frozen evaluation input changed: ' + path)
    records = [json.loads(line) for line in (root/'evaluation/questions.jsonl').read_text().splitlines() if line.strip()]
    index = build_index(root)
    engine = Engine(index)
    source = {p['passage_id']:p for p in index['passages']}
    rows, latencies = [], []
    counts = dict(answerable=0,unanswerable=0,retrieval_any=0,retrieval_all=0,answer_gold_complete=0,correct_abstention=0,false_abstention=0,answered=0,exact_quotes=0,quotes=0,gold_aligned_quotes=0,wrong_scope_questions=0,comparisons=0,comparison_complete=0)
    for row in records:
        scope = Scope(**row['scope'])
        gold = set(row['gold_passage_ids'])
        for pid in gold:
            if pid not in source or source[pid]['accession'] not in scope.accessions:
                raise ValueError('Invalid gold annotation: ' + row['id'])
        if bool(gold) != row['answerable']:
            raise ValueError('Gold answerability mismatch')
        started = time.perf_counter()
        result = engine.ask(row['question'], scope, row['compare'])
        ms = (time.perf_counter()-started)*1000
        latencies.append(ms)
        retrieved = {h['passage_id'] for h in result['retrieved']}
        cited = {h['citation']['passage_id'] for h in result['answer']}
        complete = bool(gold) and gold.issubset(cited)
        counts['answered'] += result['status'] == 'answered'
        if row['answerable']:
            counts['answerable'] += 1
            counts['retrieval_any'] += bool(gold & retrieved)
            counts['retrieval_all'] += gold.issubset(retrieved)
            counts['answer_gold_complete'] += complete
            counts['false_abstention'] += result['status'] == 'abstained'
        else:
            counts['unanswerable'] += 1
            counts['correct_abstention'] += result['status'] == 'abstained'
        if row['compare']:
            counts['comparisons'] += 1
            counts['comparison_complete'] += complete
        bad_scope = False
        for item in result['answer']:
            citation = item['citation']
            passage = source.get(citation['passage_id'])
            counts['quotes'] += 1
            counts['exact_quotes'] += bool(passage and item['excerpt'] == passage['text'])
            counts['gold_aligned_quotes'] += citation['passage_id'] in gold
            bad_scope |= citation['accession'] not in scope.accessions
            bad_scope |= not passage or citation['ticker'].lower() != scope.company.lower()
            if scope.period:
                bad_scope |= citation['report_period'] != scope.period
            if scope.form:
                bad_scope |= citation['form'] != scope.form
        counts['wrong_scope_questions'] += bool(bad_scope)
        rows.append(dict(row, result=result, retrieval_any=bool(gold & retrieved), retrieval_all=bool(gold) and gold.issubset(retrieved), gold_complete_answer=complete, latency_ms=round(ms,3)))
    def rate(n,d):
        return {'numerator':n,'denominator':d,'percent':round(100*n/d,2) if d else None}
    metrics = {
        'retrieval_hit_at_5':rate(counts['retrieval_any'],counts['answerable']),
        'all_gold_evidence_at_5':rate(counts['retrieval_all'],counts['answerable']),
        'gold_complete_extractive_answer':rate(counts['answer_gold_complete'],counts['answerable']),
        'correct_abstention':rate(counts['correct_abstention'],counts['unanswerable']),
        'false_abstention':rate(counts['false_abstention'],counts['answerable']),
        'exact_quote_integrity':rate(counts['exact_quotes'],counts['quotes']),
        'agent_gold_passage_alignment':rate(counts['gold_aligned_quotes'],counts['quotes']),
        'wrong_scope_questions':rate(counts['wrong_scope_questions'],len(records)),
        'complete_comparison_answers':rate(counts['comparison_complete'],counts['comparisons']),
        'median_query_latency_ms':round(statistics.median(latencies),3),
        'human_verified_citation_support':None,
    }
    report = {'dataset_size':len(records),'dataset_notice':frozen['notice'],'corpus_notice':index['notice'],'counts':counts,'metrics':metrics,'latency_scope':'Warm in-process query only; excludes corpus parsing and disk I/O. One run per question.','results':rows}
    if write:(root/'evaluation/results.json').write_text(json.dumps(report,indent=2)+'\n')
    lines=['# Evaluation results','',index['notice'],'',frozen['notice'],'','This is an agent-authored development set. No human or independent reviewer has verified semantic citation support. Literal quote equality and gold passage alignment are distinct mechanical checks.','', '| Metric | Raw count | Percent |','| --- | --- | --- |']
    for name,value in metrics.items():
        if isinstance(value,dict):
            lines.append('| {} | {}/{} | {}% |'.format(name,value['numerator'],value['denominator'],value['percent']))
    lines += ['', 'Median warm query latency: {} ms. Excludes parsing and disk I/O; one measured query per question.'.format(metrics['median_query_latency_ms']), '', 'Human-verified citation support: **not measured**. The original 90% semantic-support target remains unverified.', '', '## Per-question outcomes', '', '| ID | Category | Status | All gold retrieved | Complete gold cited | Reason |', '| --- | --- | --- | --- | --- | --- |']
    for row in rows:
        lines.append('| {} | {} | {} | {} | {} | {} |'.format(row['id'],row['category'],row['result']['status'],row['retrieval_all'] if row['answerable'] else 'N/A',row['gold_complete_answer'] if row['answerable'] else 'N/A',row['result']['reason']))
    lines += ['', '## Failures and limits','']
    failures = [r for r in rows if (r['answerable'] and not r['gold_complete_answer']) or (not r['answerable'] and r['result']['status']!='abstained')]
    if not failures:
        lines.append('No failed cases in this small development set. This does not establish performance on real filings or unseen questions.')
    for row in failures:
        lines += ['- {}: {} Expected passages: {}. Retrieved: {}. Outcome: {}. Inspect the raw result before changing retrieval.'.format(row['id'],row['question'],', '.join(row['gold_passage_ids']),', '.join(h['passage_id'] for h in row['result']['retrieved']),row['result']['reason'])]
    lines += ['', 'Further limits: synthetic narrative data, no table answers, no learned embeddings, only explicit scope checks, and heuristic lexical abstention. An exact quote can still be irrelevant to a question. Comparison output juxtaposes passages and does not establish causal or numerical change. See VALIDATION.md for adversarial cases and verification commands.','']
    if write:(root/'evaluation/REPORT.md').write_text('\n'.join(lines))
    return report
