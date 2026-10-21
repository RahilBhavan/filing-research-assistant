import json
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path
from filing_assistant.webapp import Server, make_handler

ROOT = Path(__file__).resolve().parents[1]
GOOD = {'status': 'answered', 'answer': 'Strategy held about 843,775 bitcoins.', 'citations': [{'passage_id': None, 'quote': 'we held approximately 843,775 bitcoins'}]}


class QuoteFirstRetrieved:
    """Fake writer: quotes the 843,775 sentence if it was retrieved, else abstains."""
    name = 'fake'

    def complete(self, system, user):
        pid = next((line.split(']')[0][len('[passage_id: '):] for line in user.splitlines() if line.startswith('[passage_id: ') and '843,775' in user.split(line, 1)[1].split('[passage_id: ')[0]), None)
        out = dict(GOOD, citations=[dict(GOOD['citations'][0], passage_id=pid)]) if pid else {'status': 'abstained', 'answer': '', 'citations': []}
        return dict(text=json.dumps(out), latency_s=0.0, cost_usd=0.0, usage={})


class AnswerApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        handler = make_handler(ROOT/'corpora/treasury', allowed_hosts=['filings.example.test'], provider=QuoteFirstRetrieved(), answers_per_minute=2)
        cls.server = Server(('127.0.0.1', 0), handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.port = cls.server.server_port

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close()

    def post(self, body, host=None):
        c = HTTPConnection('127.0.0.1', self.port, timeout=30)
        c.request('POST', '/api/answer', json.dumps(body), {'Content-Type': 'application/json', 'Host': host or '127.0.0.1:%d' % self.port})
        r = c.getresponse(); return r.status, json.loads(r.read())

    def test_answer_is_checked_cited_and_raw_output_hidden(self):
        status, r = self.post({'question': 'How many bitcoins did Strategy hold as of July 24, 2026?', 'scope': {'company': 'MSTR', 'accessions': ['0001050446-26-000044']}})
        self.assertEqual(status, 200)
        self.assertEqual(r['status'], 'answered', r)
        self.assertEqual(r['citations'][0]['accession'], '0001050446-26-000044')
        self.assertNotIn('raw', r)

    def test_configured_public_host_is_accepted_and_others_refused(self):
        body = {'question': 'What is the bitcoin custody arrangement?', 'scope': {'company': 'MSTR', 'accessions': ['0001050446-26-000020']}}
        self.assertNotEqual(self.post(body, 'filings.example.test')[0], 403)
        self.assertEqual(self.post(body, 'evil.example')[0], 403)

    def test_comparisons_and_sections_are_rejected(self):
        status, r = self.post({'question': 'x y z', 'scope': {'company': 'MSTR', 'accessions': ['0001050446-26-000020', '0001050446-26-000044']}})
        self.assertEqual(status, 400)

    def test_rate_cap_returns_429(self):
        body = {'question': 'How many employees?', 'scope': {'company': 'COIN', 'accessions': ['0001679788-26-000015']}}
        codes = [self.post(body)[0] for _ in range(4)]
        self.assertIn(429, codes)


if __name__ == '__main__':
    unittest.main()
