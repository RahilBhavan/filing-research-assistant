import json
import unittest
from pathlib import Path
from filing_assistant.corpus import NarrativeParser, build_index
from filing_assistant.engine import Scope
from filing_assistant.research import ResearchEngine,evidence_error
from filing_assistant.real_eval import check_freeze
from filing_assistant.retrieval import Retriever
ROOT=Path(__file__).resolve().parents[1]
class RealCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index=build_index(ROOT/'corpora/sec');cls.engine=ResearchEngine(cls.index);cls.docs={p['id']:p for p in cls.index['passages']}
    def ask(self,q,doc='docu-q',compare=False,others=()):
        p=self.docs[doc]
        return self.engine.ask(q,Scope(p['ticker'],[p['accession']]+[self.docs[d]['accession'] for d in others]),compare)
    def test_sources_and_frozen_index_match_rebuild(self):
        check_freeze();self.assertEqual(self.index,json.loads((ROOT/'corpora/sec/data/index.json').read_text()));self.assertEqual(len(self.docs),4)
        for p in self.docs.values():self.assertEqual(p['source_kind'],'sec')
    def test_source_audit_has_twenty_verified_passages(self):
        audit=json.loads((ROOT/'evaluation/real/source-audit.json').read_text());self.assertEqual(audit['count'],20)
        for p in audit['results']:
            self.assertTrue(p['exact_visible_text']);self.assertTrue(p['anchor_exists']);self.assertFalse(p['human_reviewed'])
    def test_div_item_heading_stops_section_bleed(self):
        p=NarrativeParser();p.feed('<div id="a">Item 2. Management’s Discussion and Analysis</div><div>Our operating costs increased due to new hiring.</div><div>Item 3. Market Risk</div><div>These market risk disclosures are outside the supported section.</div>');p.flush()
        self.assertEqual(len(p.blocks),1);self.assertEqual(p.blocks[0]['anchor'],'a')
    def test_prose_reference_does_not_switch_section(self):
        p=NarrativeParser();p.feed('<h2>Business</h2><p>See our risk factors for additional information about our business.</p><p>We manufacture products that serve paper mill customers worldwide.</p>');p.flush()
        self.assertEqual([b['section'] for b in p.blocks],['business','business'])
    def test_risk_update_is_not_followed_by_exhibits(self):
        rows=[p for p in self.index['passages'] if p['id']=='ain-q' and p['section']=='risks'];self.assertEqual(len(rows),1);self.assertIn('no material changes',rows[0]['text'])
    def test_no_page_headers_in_evidence(self):
        self.assertFalse(any('| 2026 Form 10-K |' in p['text'] for p in self.index['passages']))
    def test_false_currency_number_abstains(self):
        r=self.ask('Was cash provided by operating activities exactly $12345 million?');self.assertEqual(r['status'],'abstained');self.assertEqual(r['answer'],[])
    def test_partial_numeric_match_rejected(self):
        self.assertEqual(evidence_error('Was the total $12?', 'The total was $123.',{'total'},1),'requested_number_not_supported')
    def test_cause_requires_causal_statement(self):
        self.assertEqual(evidence_error('Why did cash decrease?', 'Cash decreased $3 million.',{'cash','decrease'},1),'no_explicit_causal_evidence')
    def test_hypothetical_cause_not_realized(self):
        self.assertEqual(evidence_error('Why did revenue decrease?', 'Revenue could decrease due to a fire.',{'revenue','decrease'},1),'hypothetical_risk_not_realized_cause')
    def test_exact_day_not_borrowed_from_balance_date(self):
        self.assertEqual(evidence_error('What exact day does the facility mature?', 'As of July 31, 2026, no borrowings were outstanding. The facility matures in May 2030.',{'facility','mature'},1),'requested_date_precision_not_disclosed')
    def test_currency_requires_currency_not_percentage(self):
        self.assertEqual(evidence_error('How much revenue in dollars?', 'Revenue increased 12%.',{'revenue'},1),'no_currency_amount_in_evidence')
    def test_wrong_company_alias_rejected(self):
        self.assertEqual(self.ask('What is Albany revenue?')['reason'],'question_company_conflicts_with_scope')
    def test_unavailable_section_abstains(self):
        p=self.docs['ain-q'];r=self.engine.ask('What are the products?',Scope('AIN',[p['accession']],section='business'));self.assertEqual(r['status'],'abstained');self.assertEqual(r['retrieved'],[])
    def test_comparison_requires_both_filings(self):
        r=self.ask('Compare total liquidity disclosed in the two filings.','ain-k',True,('ain-q',));self.assertEqual(r['status'],'answered');self.assertEqual(len({a['citation']['accession'] for a in r['answer']}),2)
    def test_incomplete_comparison_no_partial_answer(self):
        r=self.ask('Compare global employee headcounts.','docu-k',True,('docu-q',));self.assertEqual(r['status'],'abstained');self.assertEqual(r['answer'],[])
    def test_exact_scoped_excerpts(self):
        r=self.ask('Why did revenue increase?');self.assertEqual(r['status'],'answered')
        for a in r['answer']:
            p=next(p for p in self.index['passages'] if p['passage_id']==a['citation']['passage_id']);self.assertEqual(a['excerpt'],p['text']);self.assertEqual(p['id'],'docu-q')
    def test_semantic_model_pinned_to_index(self):
        with self.assertRaisesRegex(ValueError,'does not match'):Retriever(dict(self.index,notice='changed'),ROOT/'corpora/sec/data/semantic.json.gz')
    def test_split_positive_families_disjoint(self):
        families=[]
        for split in ['dev','heldout']:
            rows=[json.loads(s) for s in (ROOT/f'evaluation/real/{split}.jsonl').read_text().splitlines()];self.assertEqual(len(rows),30);self.assertEqual(sum(r['answerable'] for r in rows),20);families.append({r['family'] for r in rows if r['answerable']})
        self.assertFalse(families[0]&families[1])
    def test_exact_us_employee_count_abstains(self):
        r=self.ask('What was the exact number of employees based in the U.S.?','docu-k')
        self.assertEqual(r['status'],'abstained');self.assertEqual(r['answer'],[])
    def test_known_answerable_language_variants(self):
        cases=[
            ('Did any single customer account for more than 10% of total revenue?','docu-k',False,()),
            ('Compare the disclosed international revenue growth rates between the filings.','docu-k',True,('docu-q',)),
            ('Compare the disclosed reasons for the decrease in cash provided by operating activities.','ain-k',True,('ain-q',)),
            ('What does the quarterly risk factors section say about changes?','ain-q',False,()),
            ('Which currencies strengthened compared with the U.S. dollar?','docu-q',False,()),
            ('Why might alternative raw material suppliers be unavailable to AEC?','ain-k',False,()),
        ]
        for question,doc,compare,others in cases:
            with self.subTest(question=question):
                self.assertEqual(self.ask(question,doc,compare,others)['status'],'answered')
if __name__=='__main__':unittest.main()
