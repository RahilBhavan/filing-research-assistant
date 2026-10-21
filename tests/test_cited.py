import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from filing_assistant.cited import Retrieval, answer, check, numbers, parse, prompt
from filing_assistant.dense import DenseRetriever, build_dense, fuse
from filing_assistant.providers import AnthropicProvider, ClaudeCliProvider, ExtractiveProvider, OllamaProvider, make_provider

ROOT = Path(__file__).resolve().parents[1]
P1 = dict(passage_id='a1', text='As of May 31, 2026, the Company held 5,416,945 ETH with a fair value of $10.9 billion.')
P2 = dict(passage_id='a2', text='Revenue from leasing was $0. The machine lease agreements expired on December 31, 2025 and were not renewed.')


def reply(obj):
    return json.dumps(obj)


class HashEncoder:
    """Deterministic bag-of-words vectors: lets dense tests run without the model."""
    model = 'test-hash'

    def encode(self, texts):
        out = []
        for text in texts:
            v = [0.0]*16
            for word in text.lower().split():
                v[int(hashlib.md5(word.strip('.,?').encode()).hexdigest(), 16) % 16] += 1
            out.append(v)
        return out


def mini_index():
    base = dict(company='Test Co', ticker='TST', cik='1', form='10-Q', report_period='2026-05-31', filing_date='2026-07-01', section='mda', source_kind='sec', source_url='https://www.sec.gov/x', local_path='x', sha256='0', start_char=0, end_char=1, anchor=None, id='t')
    texts = ['bitcoin holdings rose sharply this quarter', 'employee headcount was stable', 'ether staking revenue increased', 'the lease agreements expired']
    return dict(schema_version=1, notice='n', passages=[dict(base, passage_id='p%d' % i, accession='A' if i < 3 else 'B', text=t) for i, t in enumerate(texts)])


class CheckerTests(unittest.TestCase):
    def test_verbatim_quote_with_supported_numbers_is_served(self):
        out = dict(status='answered', answer='It held 5,416,945 ETH worth $10.9 billion.', citations=[dict(passage_id='a1', quote='the Company held 5,416,945 ETH with a fair value of $10.9 billion')])
        self.assertEqual(check(out, [P1, P2])[:2], ('answered', 'checked_quotes'))

    def test_paraphrased_quote_is_rejected(self):
        out = dict(status='answered', answer='It held 5,416,945 ETH.', citations=[dict(passage_id='a1', quote='the company held 5,416,945 ETH')])
        self.assertEqual(check(out, [P1])[:2], ('abstained', 'rejected:quote_not_verbatim'))

    def test_quote_from_wrong_passage_is_rejected(self):
        out = dict(status='answered', answer='Leases expired.', citations=[dict(passage_id='a1', quote='The machine lease agreements expired')])
        self.assertEqual(check(out, [P1, P2])[1], 'rejected:quote_not_verbatim')

    def test_unretrieved_citation_is_rejected(self):
        out = dict(status='answered', answer='x', citations=[dict(passage_id='zzz', quote='The machine lease agreements expired')])
        self.assertEqual(check(out, [P1])[1], 'rejected:citation_not_retrieved')

    def test_number_absent_from_quotes_is_rejected(self):
        out = dict(status='answered', answer='Average cost was $2,012 per ETH.', citations=[dict(passage_id='a1', quote='the Company held 5,416,945 ETH')])
        self.assertEqual(check(out, [P1])[1], 'rejected:number_not_in_quotes')

    def test_abstention_and_malformed_output(self):
        self.assertEqual(check(dict(status='abstained', answer='', citations=[]), [P1])[1], 'model_abstained')
        self.assertEqual(check(None, [P1])[1], 'rejected:malformed_output')
        self.assertEqual(check(dict(status='answered', answer='x', citations=[]), [P1])[1], 'rejected:missing_answer_or_citation')
        self.assertEqual(check(dict(status='answered', answer='x', citations=[dict(passage_id='a1', quote='As of')]), [P1])[1], 'rejected:quote_too_short')

    def test_numbers_ignore_single_digits_and_commas(self):
        self.assertEqual(numbers('Q2 had 5,416,945 ETH, $10.9 billion and 85%.'), {'5416945', '10.9', '85'})

    def test_parse_accepts_fenced_json_and_rejects_prose(self):
        self.assertEqual(parse('```json\n{"status": "abstained"}\n```')['status'], 'abstained')
        with self.assertRaises(ValueError):
            parse('I cannot answer that.')


class FakeProvider:
    name = 'fake'

    def __init__(self, text):
        self.text, self.seen = text, None

    def complete(self, system, user):
        self.seen = user
        return dict(text=self.text, latency_s=0.01, cost_usd=0.0001, usage={})


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.index = mini_index()
        self.retrieval = Retrieval(self.index)

    def test_scope_limits_passages_the_model_sees(self):
        provider = FakeProvider(reply(dict(status='abstained', answer='', citations=[])))
        result = answer('bitcoin lease agreements expired', dict(company='TST', accessions=['A']), self.retrieval, provider, 'bm25')
        self.assertNotIn('p3', result['retrieved'])
        self.assertNotIn('lease agreements expired', provider.seen.split('Passages:')[1])

    def test_invented_quote_becomes_abstention_with_raw_kept(self):
        bad = reply(dict(status='answered', answer='Leases ended in 2025.', citations=[dict(passage_id='p3', quote='the leases ended in 2025')]))
        result = answer('lease agreements expired', dict(company='TST', accessions=['B']), self.retrieval, FakeProvider(bad), 'bm25')
        self.assertEqual((result['status'], result['reason'], result['raw_status']), ('abstained', 'rejected:quote_not_verbatim', 'answered'))
        self.assertEqual(result['raw'], bad)

    def test_served_citation_carries_provenance(self):
        good = reply(dict(status='answered', answer='The lease agreements expired.', citations=[dict(passage_id='p3', quote='the lease agreements expired')]))
        result = answer('lease agreements expired', dict(company='TST', accessions=['B']), self.retrieval, FakeProvider(good), 'bm25')
        self.assertEqual(result['status'], 'answered')
        self.assertEqual(result['citations'][0]['accession'], 'B')
        self.assertEqual(result['citations'][0]['source_url'], 'https://www.sec.gov/x')

    def test_unknown_company_and_foreign_accession_raise(self):
        with self.assertRaises(ValueError):
            self.retrieval.rank('q', dict(company='NOPE'), 'bm25')
        with self.assertRaises(ValueError):
            self.retrieval.rank('q', dict(company='TST', accessions=['Z']), 'bm25')

    def test_methods_without_models_are_refused(self):
        for method in ('lsa', 'dense', 'dense-hybrid'):
            with self.assertRaises(ValueError):
                self.retrieval.rank('bitcoin', dict(company='TST'), method)

    def test_prompt_lists_passage_ids(self):
        self.assertIn('[passage_id: a1]', prompt('q', [dict(P1, company='C', form='10-Q', report_period='r', section='mda')]))


class DenseTests(unittest.TestCase):
    def test_build_rank_and_hybrid_with_pinned_vectors(self):
        index = mini_index()
        with tempfile.TemporaryDirectory() as temp:
            data = Path(temp)/'data'; data.mkdir()
            self.assertEqual(build_dense(index, data, HashEncoder())['dimensions'], 16)
            dense = DenseRetriever(index, data, HashEncoder())
            ranked = dense.rank(index['passages'], 'ether staking revenue')
            self.assertEqual(ranked[0]['passage']['passage_id'], 'p2')
            retrieval = Retrieval(index, Path(temp), HashEncoder())
            self.assertEqual(retrieval.rank('ether staking revenue', dict(company='TST'), 'dense-hybrid', 1)[0]['passage_id'], 'p2')

    def test_vectors_refuse_a_changed_index_or_file(self):
        index = mini_index()
        with tempfile.TemporaryDirectory() as temp:
            build_dense(index, temp, HashEncoder())
            with self.assertRaisesRegex(ValueError, 'do not match'):
                DenseRetriever(dict(index, notice='changed'), temp, HashEncoder())
            with (Path(temp)/'dense.f32').open('ab') as f:
                f.write(b'\0\0\0\0')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                DenseRetriever(index, temp, HashEncoder())

    def test_fusion_rewards_agreement(self):
        a, b, c = (dict(passage=dict(passage_id=x)) for x in 'abc')
        self.assertEqual(fuse([a, b, c], [b, a, c])[2]['passage']['passage_id'], 'c')

    def test_treasury_vectors_match_committed_index(self):
        index = json.loads((ROOT/'corpora/treasury/data/index.json').read_text())
        dense = DenseRetriever(index, ROOT/'corpora/treasury/data', HashEncoder())
        self.assertEqual(len(dense.vectors), len(index['passages']))
        self.assertEqual(dense.meta['model'], 'BAAI/bge-small-en-v1.5')


class ProviderTests(unittest.TestCase):
    def test_anthropic_provider_uses_low_effort_and_prices_haiku(self):
        calls = []
        message = SimpleNamespace(stop_reason='end_turn', content=[SimpleNamespace(type='thinking'), SimpleNamespace(type='text', text='{"status": "abstained"}')],
                                  usage=SimpleNamespace(input_tokens=1000, output_tokens=100))
        client = SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: calls.append(kw) or message))
        out = AnthropicProvider(client=client).complete('sys', 'user')
        self.assertEqual(calls[0]['model'], 'claude-haiku-5-5')
        self.assertEqual(calls[0]['output_config'], {'effort': 'low'})
        self.assertNotIn('temperature', calls[0])
        self.assertEqual(out['text'], '{"status": "abstained"}')
        self.assertAlmostEqual(out['cost_usd'], (1000*0.10 + 100*0.50)/1e6)

    def test_anthropic_refusal_becomes_abstention(self):
        message = SimpleNamespace(stop_reason='refusal', content=[], usage=SimpleNamespace(input_tokens=1, output_tokens=0))
        client = SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: message))
        self.assertEqual(json.loads(AnthropicProvider(client=client).complete('s', 'u')['text'])['status'], 'abstained')

    def test_cli_adapter_disables_tools_and_reads_cost(self):
        seen = {}
        def runner(command, **kw):
            seen['command'], seen['input'] = command, kw['input']
            return SimpleNamespace(returncode=0, stdout=json.dumps(dict(result='{"status": "abstained"}', total_cost_usd=0.0007, usage={'input_tokens': 5}, modelUsage={'claude-haiku-5-5': {}}, is_error=False)), stderr='')
        out = ClaudeCliProvider(runner=runner).complete('SYS', 'USER')
        self.assertEqual(seen['command'][seen['command'].index('--tools') + 1], '')
        self.assertIn('--no-session-persistence', seen['command'])
        self.assertEqual(seen['command'][seen['command'].index('--system-prompt') + 1], 'SYS')
        self.assertEqual(seen['input'], 'USER')
        self.assertEqual((out['cost_usd'], out['usage']['models']), (0.0007, ['claude-haiku-5-5']))

    def test_cli_error_raises(self):
        runner = lambda command, **kw: SimpleNamespace(returncode=1, stdout='', stderr='not logged in')
        with self.assertRaisesRegex(RuntimeError, 'not logged in'):
            ClaudeCliProvider(runner=runner).complete('s', 'u')

    def test_ollama_posts_json_mode_chat(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return json.dumps(dict(message=dict(content='{"status": "abstained"}'), prompt_eval_count=9, eval_count=3)).encode()
        requests = []
        out = OllamaProvider(opener=lambda req, timeout: requests.append(json.loads(req.data)) or Response()).complete('s', 'u')
        self.assertEqual((requests[0]['format'], requests[0]['model']), ('json', 'qwen2.5:0.5b'))
        self.assertEqual(out['usage']['output_tokens'], 3)

    def test_extractive_fallback_quotes_or_abstains(self):
        user = prompt('When did the machine lease agreements expire?', [dict(P2, company='C', form='10-Q', report_period='r', section='mda')])
        out = json.loads(ExtractiveProvider().complete('s', user)['text'])
        self.assertEqual(out['citations'][0]['quote'], 'The machine lease agreements expired on December 31, 2025 and were not renewed.')
        self.assertEqual(check(out, [P2])[0], 'answered')
        user = prompt('What is the dividend policy for preferred shares?', [dict(P2, company='C', form='10-Q', report_period='r', section='mda')])
        self.assertEqual(json.loads(ExtractiveProvider().complete('s', user)['text'])['status'], 'abstained')

    def test_default_provider_without_key_is_offline(self):
        import os
        from unittest.mock import patch
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(make_provider().name, 'extractive')
            with self.assertRaisesRegex(ValueError, 'ANTHROPIC_API_KEY'):
                make_provider('anthropic')


if __name__ == '__main__':
    unittest.main()
