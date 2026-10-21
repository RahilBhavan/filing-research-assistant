import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from filing_assistant import treasury_eval
from filing_assistant.cited import Retrieval

ROOT = Path(__file__).resolve().parents[1]


class FrozenSetTests(unittest.TestCase):
    def test_heldout_is_forty_questions_with_ten_unanswerable(self):
        rows = treasury_eval.load('heldout')
        self.assertEqual((len(rows), sum(not r['answerable'] for r in rows)), (40, 10))
        self.assertEqual({r['scope']['company'] for r in rows}, {'MSTR', 'BMNR', 'COIN'})
        self.assertFalse({r['id'] for r in rows} & {r['id'] for r in treasury_eval.load('dev')})

    def test_gold_quotes_are_verbatim_and_in_scope(self):
        passages = {p['passage_id']: p for p in json.loads((ROOT/'corpora/treasury/data/index.json').read_text())['passages']}
        for row in treasury_eval.load('heldout'):
            for g in row['gold']:
                self.assertIn(g['quote'], passages[g['passage_id']]['text'])
                self.assertIn(passages[g['passage_id']]['accession'], row['scope']['accessions'])

    def test_changed_question_file_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            shutil.copytree(ROOT/'evaluation/treasury', Path(temp)/'evaluation/treasury')
            shutil.copytree(ROOT/'corpora/treasury/data', Path(temp)/'corpora/treasury/data', ignore=shutil.ignore_patterns('raw'))
            with (Path(temp)/'evaluation/treasury/heldout.jsonl').open('a') as f:
                f.write('\n')
            with patch.object(treasury_eval, 'ROOT', Path(temp)), patch.object(treasury_eval, 'EVAL', Path(temp)/'evaluation/treasury'):
                with self.assertRaisesRegex(ValueError, 'Frozen input changed'):
                    treasury_eval.load('heldout')


class ScoringTests(unittest.TestCase):
    def test_bm25_retrieval_scores_any_gold_hit(self):
        index = json.loads((ROOT/'corpora/treasury/data/index.json').read_text())
        report = treasury_eval.retrieval_eval('dev', ('bm25',), Retrieval(index))
        self.assertEqual(report['bm25']['questions'], 6)
        self.assertLessEqual(report['bm25']['recall@1'], report['bm25']['recall@5'])

    def test_score_separates_rejections_abstentions_and_labels(self):
        rows = treasury_eval.load('heldout')
        answerable = [r for r in rows if r['answerable']]
        unanswerable = [r for r in rows if not r['answerable']]
        results = []
        for i, r in enumerate(answerable):
            if i == 0:  # model answered but checker rejected
                results.append(dict(id=r['id'], status='abstained', reason='rejected:quote_not_verbatim', raw_status='answered', citations=[], latency_s=2.0, cost_usd=0.001, raw='x'))
            else:
                results.append(dict(id=r['id'], status='answered', reason='checked_quotes', raw_status='answered', citations=[dict(passage_id=r['gold'][0]['passage_id'], quote='q')], latency_s=1.0, cost_usd=0.001, raw='x', answer='a'))
        for i, r in enumerate(unanswerable):
            served = i == 0
            results.append(dict(id=r['id'], status='answered' if served else 'abstained', reason='checked_quotes' if served else 'model_abstained', raw_status='answered' if served else 'abstained', citations=[], latency_s=3.0, cost_usd=0.001, raw='x', answer='a'))
        with tempfile.TemporaryDirectory() as temp:
            runs = Path(temp)/'runs'; runs.mkdir()
            (runs/'t.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in results))
            judged = {r['id']: dict(verdict='correct') for r in answerable[1:]}
            judged[answerable[1]['id']] = dict(verdict='incorrect')
            (runs/'t-judge.json').write_text(json.dumps(judged))
            labels = {r['id']: 'correct' for r in answerable[1:]}
            for name in ('frozen.json', 'heldout.jsonl', 'dev.jsonl'):
                shutil.copy(ROOT/'evaluation/treasury'/name, Path(temp)/name)
            with patch.object(treasury_eval, 'EVAL', Path(temp)):
                s = treasury_eval.score('t', labels=labels)
        self.assertEqual(s['raw_citation_faithfulness'], [30, 31])
        self.assertEqual(s['false_abstentions'], [1, 30])
        self.assertEqual(s['unanswerable_abstained'], [9, 10])
        self.assertEqual(s['judge_correct'], [28, 30])
        self.assertEqual(s['author_correct'], [29, 30])
        self.assertEqual(s['judge_author_agreement'], [28, 29])
        self.assertEqual(s['served_answerable_citing_gold'], [29, 29])
        self.assertEqual(s['p50_latency_s'], 1.0)


if __name__ == '__main__':
    unittest.main()
