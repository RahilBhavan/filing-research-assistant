"""Scope first, BM25 second, conservative extractive evidence last."""
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import List, Optional

STOP = set('a an and are as at be been because between by can caused causes cause compare company could did do does during ended explains for from generally how in into is it its many more most of on or per reported report period quarter quarterly annual year than that the their these this those to two was were what when which who why with would filings filing primarily percentage percent people'.split())
STOP.update({'driver', 'drivers', 'drove', 'driven', 'long'})
# Small explicit normalization vocabulary. This is not semantic search.
NORMAL = {'grew':'growth','grow':'growth','growing':'growth', 'increased':'increase','higher':'increase','rose':'increase', 'decreased':'decrease','lower':'decrease','fell':'decrease','fall':'decrease', 'declined':'decline','weaker':'decline', 'improved':'improve','costs':'cost','expenses':'cost','expense':'cost', 'sales':'revenue', 'employees':'employee','employed':'employ', 'housing':'housings','vendor':'supplier','buyers':'customer','generation':'flow','drivers':'driver','worked':'employ'}
NORMAL.update({'employ':'employee', 'employed':'employee', 'worked':'employee', 'represented':'represent', 'interruption':'interrupt', 'interruptions':'interrupt', 'interrupted':'interrupt'})
NORMAL.update({
    'accounted':'account', 'accounting':'account',
    'activities':'activity',
    'alternative':'alternate', 'alternatives':'alternate',
    'compared':'compare', 'comparing':'compare',
    'currencies':'currency',
    'strengthened':'strengthen', 'strengthening':'strengthen',
    'unavailable':'availability',
})


def tokens(text):
    words = re.findall(r'[a-z]+|\d+(?:\.\d+)?', text.lower())
    out = []
    for word in words:
        if word in STOP or re.fullmatch(r'\d{4}', word):
            continue
        word = NORMAL.get(word, word)
        if len(word) > 4 and word.endswith('ies'):
            word = word[:-3] + 'y'
        elif len(word) > 4 and word.endswith('s') and not word.endswith('ss'):
            word = word[:-1]
        out.append(word)
    return out


@dataclass
class Scope:
    company: str
    accessions: List[str] = field(default_factory=list)
    form: Optional[str] = None
    period: Optional[str] = None
    section: Optional[str] = None


class Engine:
    def __init__(self, index):
        self.index = index
        self.passages = index['passages']
        self.documents = {p['accession']: p for p in self.passages}
        self.term_counts = {p['passage_id']: Counter(tokens(p['text'])) for p in self.passages}

    def resolve(self, question, scope, compare):
        known = {}
        for p in self.documents.values():
            known[p['ticker'].lower()] = p['ticker']
            known[p['company'].lower()] = p['ticker']
            if p.get('cik'):
                known[p['cik']] = p['ticker']
        ticker = known.get(scope.company.lower())
        if not ticker:
            return [], 'unknown_company'
        for alias, candidate in known.items():
            if re.search(r'(?<!\w)' + re.escape(alias) + r'(?!\w)', question.lower()) and candidate != ticker:
                return [], 'question_company_conflicts_with_scope'
        docs = [p for p in self.documents.values() if p['ticker'] == ticker]
        if scope.accessions:
            if len(set(scope.accessions)) != len(scope.accessions):
                return [], 'duplicate_accessions'
            if any(a not in {d['accession'] for d in docs} for a in scope.accessions):
                return [], 'accession_outside_company_or_missing'
            docs = [d for d in docs if d['accession'] in scope.accessions]
        if scope.form:
            docs = [d for d in docs if d['form'] == scope.form]
        if scope.period:
            docs = [d for d in docs if d['report_period'] == scope.period]
        forms = set(re.findall(r'\b10-[KQ](?:/A)?\b', question.upper()))
        if forms and any(d['form'] not in forms for d in docs):
            return [], 'question_form_conflicts_with_scope'
        periods = set(re.findall(r'\b\d{4}-\d{2}-\d{2}\b', question))
        if periods and not periods.issubset({d['report_period'] for d in docs}):
            return [], 'question_period_conflicts_with_scope'
        years = set(re.findall(r'\b(?:19|20)\d{2}\b', question)) if not periods else set()
        if years and not years.issubset({d['report_period'][:4] for d in docs}):
            return [], 'question_year_conflicts_with_scope'
        if not docs:
            return [], 'no_filings_in_scope'
        if len(docs) != (2 if compare else 1):
            return [], 'comparison_requires_exactly_two_filings' if compare else 'select_one_filing_or_use_compare'
        if scope.section and scope.section not in {'business','mda','risks'}:
            return [], 'unsupported_section'
        return docs, None

    def query_terms(self, question):
        cleaned = re.sub(r'\b\d{4}-\d{2}-\d{2}\b', ' ', question)
        cleaned = re.sub(r'\b10-[KQ](?:/A)?\b', ' ', cleaned, flags=re.I)
        for d in self.documents.values():
            for alias in (d['company'], d['ticker']):
                cleaned = re.sub(r'(?<!\w)' + re.escape(alias) + r'(?!\w)', ' ', cleaned, flags=re.I)
        return set(tokens(cleaned))

    def rank(self, candidates, terms):
        if not candidates or not terms:
            return []
        counts = [self.term_counts[p['passage_id']] for p in candidates]
        mean_length = sum(sum(c.values()) for c in counts) / len(counts)
        frequencies = {term:sum(term in c for c in counts) for term in terms}
        ranked = []
        for p, counts in zip(candidates, counts):
            score = 0.0
            matched = terms.intersection(counts)
            for term in matched:
                tf = counts[term]
                idf = math.log(1 + (len(candidates) - frequencies[term] + 0.5)/(frequencies[term] + 0.5))
                score += idf * tf * 2.5 / (tf + 1.5 * (0.25 + 0.75 * sum(counts.values()) / mean_length))
            if score:
                ranked.append({'passage':p,'score':round(score,6),'coverage':len(matched)/len(terms),'matched_terms':sorted(matched)})
        return sorted(ranked, key=lambda x:(-x['score'],x['passage']['passage_id']))

    def ask(self, question, scope, compare=False):
        result = {'question':question,'status':'abstained','reason':None,'source_notice':self.index['notice'],'answer':[], 'retrieved':[], 'support_assessment':'Exact extract only; lexical relevance is heuristic, not human-verified semantic support.'}
        docs, error = self.resolve(question, scope, compare)
        if error:
            result['reason'] = error
            return result
        terms = self.query_terms(question)
        if not terms:
            result['reason'] = 'no_searchable_terms'
            return result
        if re.search(r'\b(predict|forecast|recommend|should I buy|stock price|tomorrow)\b', question, re.I):
            result['reason'] = 'unsupported_prediction_or_advice'
            return result
        groups = []
        for doc in sorted(docs, key=lambda d:d['report_period']):
            candidates = [p for p in self.passages if p['accession'] == doc['accession'] and (not scope.section or p['section'] == scope.section)]
            groups.append(self.rank(candidates, terms))
        # Fair allocation across both filings: total retrieval budget stays five.
        pool = []
        if compare:
            for position in range(5):
                group = groups[position % 2]
                index = position // 2
                if index < len(group):
                    pool.append(group[index])
        else:
            pool = groups[0][:5]
        result['retrieved'] = [{'passage_id':h['passage']['passage_id'],'accession':h['passage']['accession'],'score':h['score'],'query_term_coverage':round(h['coverage'],3)} for h in pool]
        # Gates use observable lexical overlap, never a claim of model confidence.
        selected = []
        for group in groups:
            if not group or group[0]['coverage'] < 0.55 or len(group[0]['matched_terms']) < min(2,len(terms)):
                result['reason'] = 'insufficient_lexical_evidence'
                return result
            vocabulary = set().union(*(self.term_counts[h['passage']['passage_id']] for h in group))
            if terms - vocabulary:
                result['reason'] = 'unmatched_query_terms'
                return result
            if re.search(r'\b(dollars?|USD)\b|\$', question, re.I) and not re.search(r'\$\s*\d|\b\d[\d,.]*\s*(?:million\s+|billion\s+)?(?:dollars?|USD)\b', group[0]['passage']['text'], re.I):
                result['reason'] = 'no_currency_amount_in_evidence'
                return result
            selected.append(group[0]['passage'])
        for p in selected:
            citation = {k:p[k] for k in ('passage_id','company','ticker','cik','accession','form','report_period','filing_date','section','source_kind','source_url','local_path','sha256','start_char','end_char','anchor')}
            result['answer'].append({'excerpt':p['text'],'citation':citation})
        result['status'] = 'answered'
        result['reason'] = 'paired_extracts_not_a_calculated_change' if compare else 'extractive_evidence'
        return result
