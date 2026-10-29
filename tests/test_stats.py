import json
import unittest
from pathlib import Path
from filing_assistant import stats, treasury_eval

ROOT = Path(__file__).resolve().parents[1]


class McNemarTests(unittest.TestCase):
    def test_no_discordant_pairs_gives_p_one(self):
        self.assertEqual(stats.mcnemar_exact(0, 0), 1.0)

    def test_balanced_discordance_caps_at_one(self):
        self.assertEqual(stats.mcnemar_exact(3, 3), 1.0)

    def test_known_tables(self):
        # two-sided p = 2 * P(X <= min) with X ~ Binomial(n, 1/2)
        self.assertEqual(stats.mcnemar_exact(0, 5), 2/32)
        self.assertEqual(stats.mcnemar_exact(1, 6), 2*(1 + 7)/128)
        self.assertEqual(stats.mcnemar_exact(8, 2), 2*(1 + 10 + 45)/1024)

    def test_symmetric_in_its_arguments(self):
        self.assertEqual(stats.mcnemar_exact(2, 9), stats.mcnemar_exact(9, 2))


class BootstrapTests(unittest.TestCase):
    def test_identical_runs_give_zero_difference_and_p_one(self):
        scores = [1, 0, 1, 1, 0, 1, 0, 0, 1, 1]
        out = stats.compare(scores, list(scores))
        self.assertEqual((out['diff'], out['ci_low'], out['ci_high'], out['mcnemar_p']), (0, 0, 0, 1.0))
        self.assertTrue(out['interval_includes_zero'])

    def test_constant_difference_has_a_degenerate_interval(self):
        out = stats.compare([1.0]*8, [0.5]*8)
        self.assertEqual((out['diff'], out['ci_low'], out['ci_high']), (0.5, 0.5, 0.5))
        self.assertFalse(out['interval_includes_zero'])
        self.assertNotIn('mcnemar_p', out)  # graded scores get no McNemar test

    def test_discordant_counts_and_difference(self):
        a = [1, 1, 1, 0, 0, 1]
        b = [1, 0, 0, 0, 1, 1]
        out = stats.compare(a, b)
        self.assertEqual((out['a_only'], out['b_only']), (2, 1))
        self.assertAlmostEqual(out['diff'], 1/6)
        self.assertEqual(out['mcnemar_p'], 1.0)

    def test_interval_brackets_the_difference_and_is_reproducible(self):
        a = [1]*24 + [0]*6
        b = [1]*18 + [0]*12
        first, second = stats.compare(a, b), stats.compare(a, b)
        self.assertEqual(first, second)
        self.assertLessEqual(first['ci_low'], first['diff'])
        self.assertGreaterEqual(first['ci_high'], first['diff'])
        self.assertGreater(first['ci_low'], 0)  # 6 of 6 discordant pairs favour a

    def test_different_seed_changes_the_draws_not_the_difference(self):
        a, b = [1, 0, 1, 1, 0, 1, 0, 1], [0, 0, 1, 0, 0, 1, 1, 0]
        self.assertEqual(stats.compare(a, b, seed=1)['diff'], stats.compare(a, b, seed=2)['diff'])

    def test_rejects_unpaired_input(self):
        with self.assertRaises(ValueError):
            stats.paired_bootstrap_ci([1, 0], [1])
        with self.assertRaises(ValueError):
            stats.paired_bootstrap_ci([], [])


class CommittedRunTests(unittest.TestCase):
    def test_writer_vectors_match_the_reported_judge_counts(self):
        for run, expected in (('heldout-haiku-cli', 26), ('heldout-extractive', 16), ('heldout-ollama-qwen0.5b', 7)):
            vector = treasury_eval.writer_correct(run)
            self.assertEqual((len(vector), sum(vector.values())), (30, expected))
            self.assertEqual(treasury_eval.score(run)['judge_correct'], [expected, 30])

    def test_significance_means_match_the_retrieval_report(self):
        report = treasury_eval.significance()
        retrieval = json.loads((ROOT/'evaluation/treasury/heldout-retrieval.json').read_text())
        row = report['retrieval']['dense-hybrid vs bm25']
        self.assertEqual(round(row['top1']['mean_a']*30), retrieval['dense-hybrid']['recall@1'])
        self.assertEqual(round(row['top1']['mean_b']*30), retrieval['bm25']['recall@1'])
        self.assertEqual(round(row['mrr5']['mean_a'], 3), retrieval['dense-hybrid']['mrr'])
        self.assertEqual(round(row['mrr5']['mean_b'], 3), retrieval['bm25']['mrr'])

    def test_committed_significance_file_is_current(self):
        committed = json.loads((ROOT/'evaluation/treasury/heldout-significance.json').read_text())
        self.assertEqual(committed, json.loads(json.dumps(treasury_eval.significance())))


if __name__ == '__main__':
    unittest.main()
