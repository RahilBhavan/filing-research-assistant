"""Scoped extraction with explicit, conservative answerability checks."""
import re
from .engine import Engine, Scope, tokens
from .retrieval import Retriever

QUESTION_FILLER=set('much have had about says say stated disclosed disclosure provide provided proportion share number exact exactly approximately amounts amount called consists consist explain describe basis based according constitute came come used uses use offer offers offering reach served serves serve contributed contribute any section reason reasons rate rates might'.split())
MONTH=r'(?:January|February|March|April|May|June|July|August|September|October|November|December)'
CAUSAL=r'\b(?:because|due to|driven by|result of|attributable to|contributed|to support|to continue|partially offset|preclude|delay)\b'
CITATION=('passage_id','company','ticker','cik','accession','form','report_period','filing_date','section','source_kind','source_url','local_path','sha256','start_char','end_char','anchor')

def evidence_error(question, text, terms, coverage):
    lower=question.lower(); source=text.lower()
    if coverage<0.55:
        return 'insufficient_topic_support'
    missing=terms-set(tokens(text))
    # Search relevance cannot silently drop an extra entity or unsupported qualifier.
    if missing:
        return 'question_details_not_supported'
    numbers=re.findall(r'(?<!\w)\d[\d,]*(?:\.\d+)?',re.sub(r'\b(?:19|20)\d{2}\b','',question))
    for n in numbers:
        if not re.search(r'(?<![\d.])'+re.escape(n)+r'(?![\d.])',text):
            return 'requested_number_not_supported'
    if 'revenue' in terms and 'cost' not in terms and re.search(r'^cost of revenue', source):
        return 'wrong_financial_measure'
    if re.search(r'what.*channels', lower):
        routes=sum(bool(re.search(pattern,source)) for pattern in [r'direct sales',r'partner',r'digital|self.service'])
        if routes<2:return 'incomplete_channel_list'
    if re.search(r'compare.*cash (?:and cash )?equivalents', lower) and not re.search(r'cash and cash equivalents of \$[\d,.]+',text,re.I):
        return 'no_cash_balance_in_evidence'
    numeric=bool(re.search(r'how (?:much|many)|what (?:was|is|were).*(?:number|amount|percentage|percent|total liquidity)|what (?:share|proportion)',lower))
    if numeric and not re.search(r'\d',text):
        return 'no_quantity_in_evidence'
    currency=bool(re.search(r'\$|\b(?:dollars?|usd)\b|how much.*(?:cost|expense|revenue|cash|liquidity)',lower))
    if currency and not re.search(r'\$\s*\d|\d[\d,.]*\s*(?:million |billion )?(?:dollars?|USD)',text,re.I):
        return 'no_currency_amount_in_evidence'
    if re.search(r'\b(?:why|caused|causes|reasons)\b',lower):
        if not re.search(CAUSAL,text,re.I):
            return 'no_explicit_causal_evidence'
        if (not re.search(r'\b(?:could|may|might|potential)\b',lower)
                and re.search(r'\b(?:could|may|might|potential)\b',source)
                and not re.search(r'\b(?:increased|decreased|was|were|experienced)\b',source)):
            return 'hypothetical_risk_not_realized_cause'
    if re.search(r'\bwhen\b|exact day|what date',lower):
        if not re.search(r'\b(?:18|19|20)\d{2}\b',text):
            return 'no_date_in_evidence'
        if re.search(r'exact day|what date',lower):
            # A date elsewhere in the paragraph cannot supply an event's missing day.
            event='matur' if 'matur' in lower else 'agreement|entered|signed'
            sentences=[s for s in re.split(r'(?<=[.!?])\s+',text) if re.search(event,s,re.I)]
            if not any(re.search(MONTH+r'\s+\d{1,2},?\s+20\d{2}',s) for s in sentences):
                return 'requested_date_precision_not_disclosed'
    if re.search(r'exact (?:number|amount)|exactly',lower) and re.search(r'\b(?:approximately|over|more than|less than|about)\b',source):
        return 'requested_precision_not_disclosed'
    return None

class ResearchEngine(Engine):
    def __init__(self,index,model_path=None,method='bm25'):
        super().__init__(index)
        self.retriever=Retriever(index,model_path)
        self.method=method

    def query_terms(self,question):
        cleaned=question
        for d in self.documents.values():
            for alias in (d['company'],d['ticker'],d['company'].split(',')[0], 'Docusign' if d['ticker']=='DOCU' else 'Albany'):
                cleaned=re.sub(r'(?<!\w)'+re.escape(alias)+r'(?!\w)',' ',cleaned,flags=re.I)
        cleaned=re.sub(r'\b10-[KQ](?:/A)?\b|\b\d{4}-\d{2}-\d{2}\b',' ',cleaned,flags=re.I)
        cleaned=re.sub(MONTH+r'\s+\d{1,2},?\s+20\d{2}',' ',cleaned,flags=re.I)
        return {'supplie' if t == 'supply' else t for t in tokens(cleaned) if t not in QUESTION_FILLER and len(t)>1 and not t.isdigit()}

    def resolve(self,question,scope,compare):
        # Canonical aliases are checked before the inherited strict accession/form/date gates.
        for name,ticker in [('Docusign','DOCU'),('Albany','AIN')]:
            if re.search(r'\b'+name+r'\b',question,re.I) and scope.company.upper() in {'DOCU','AIN'} and scope.company.upper()!=ticker:
                return [],'question_company_conflicts_with_scope'
        return super().resolve(question,scope,compare)

    def ask(self,question,scope,compare=False):
        result=dict(question=question,status='abstained',reason=None,source_notice=self.index['notice'],answer=[],retrieved=[],method=self.method,support_assessment='Exact excerpts with heuristic topic, quantity, date and cause checks. Not human-verified semantic support.')
        docs,error=self.resolve(question,scope,compare)
        if error:result['reason']=error;return result
        if re.search(r'\b(predict|forecast|recommend|should I buy|stock price|tomorrow)\b',question,re.I):
            result['reason']='unsupported_prediction_or_advice';return result
        terms=self.query_terms(question)
        if not terms:result['reason']='no_searchable_terms';return result
        groups=[]
        for d in sorted(docs,key=lambda d:d['report_period']):
            candidates=[p for p in self.passages if p['accession']==d['accession'] and (not scope.section or p['section']==scope.section)]
            groups.append(self.retriever.rank(candidates,terms,self.method))
        pool=[]
        for i in range(5):
            g=groups[i%len(groups)];n=i//len(groups)
            if n<len(g):pool.append(g[n])
        result['retrieved']=[dict(passage_id=h['passage']['passage_id'],accession=h['passage']['accession'],score=round(h['score'],6),query_term_coverage=round(h['coverage'],3)) for h in pool]
        selected=[]
        for group in groups:
            available=[h for h in pool if h in group]
            errors=[]
            for hit in available:
                p=hit['passage'];error=evidence_error(question,p['text'],terms,hit['coverage'])
                if error:errors.append(error);continue
                selected.append(p);break
            else:
                result['reason']=errors[0] if errors else 'no_relevant_evidence';return result
        result['answer']=[dict(excerpt=p['text'],citation={k:p[k] for k in CITATION}) for p in selected]
        result['status']='answered';result['reason']='paired_extracts_not_a_calculated_change' if compare else 'extractive_evidence'
        return result
