import json
import tempfile
import unittest
from pathlib import Path
from filing_assistant.corpus import NarrativeParser, build_index
from filing_assistant.sec import fetch_corpus
ROOT=Path(__file__).resolve().parents[1]
TREASURY=ROOT/'corpora/treasury'

class TreasuryCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index=build_index(TREASURY)
    def test_index_rebuilds_from_hashed_sources(self):
        self.assertEqual(self.index,json.loads((TREASURY/'data/index.json').read_text()))
    def test_three_companies_each_have_a_10k_and_10q(self):
        filings={(p['ticker'],p['form']) for p in self.index['passages']}
        self.assertEqual(filings,{(t,f) for t in ('MSTR','BMNR','COIN') for f in ('10-K','10-Q')})
        for p in self.index['passages']:
            self.assertEqual(p['source_kind'],'sec');self.assertTrue(p['source_url'].startswith('https://www.sec.gov/Archives/edgar/data/'))
    def test_every_filing_has_risk_factors(self):
        self.assertEqual({p['accession'] for p in self.index['passages'] if p['section']=='risks'},{p['accession'] for p in self.index['passages']})
    def test_heading_with_trailing_period_starts_section(self):
        p=NarrativeParser();p.feed('<p><b>Item 1A. Risk Factors.</b></p><p>Our ether holdings could decline sharply in value at any time.</p>');p.flush()
        self.assertEqual([b['section'] for b in p.blocks],['risks'])
    def test_fetch_accepts_three_ciks_but_rejects_duplicates(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError,'distinct'):
                fetch_corpus(Path(temp)/'new',['1050446','1829311','0001050446'],'2026-10-21')
            with self.assertRaisesRegex(ValueError,'one to five'):
                fetch_corpus(Path(temp)/'new',[],'2026-10-21')

if __name__=='__main__':unittest.main()
