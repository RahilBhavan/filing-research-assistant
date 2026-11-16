import unittest
from pathlib import Path
from filing_assistant import penalty_rescore as pr

ROOT = Path(__file__).resolve().parents[1]


class RuleTests(unittest.TestCase):
    def test_rule_on_tiny_fixture(self):
        answerable = {'a1': True, 'a2': True, 'a3': True, 'a4': True, 'u1': False, 'u2': False}
        statuses = {'a1': 'answered', 'a2': 'answered', 'a3': 'abstained', 'a4': 'rejected',
                    'u1': 'answered', 'u2': 'abstained'}
        verdicts = {'a1': 'correct', 'a2': 'incorrect', 'a3': 'correct', 'a4': 'correct', 'u1': 'correct'}
        # +1 (a1) -4 (a2 wrong) -4 (u1 served); abstain and rejected score 0
        self.assertEqual(pr.score(answerable, statuses, verdicts),
                         {'correct': 1, 'wrong': 1, 'unanswerable_served': 1, 'score': -7})

    def test_all_abstain_scores_zero(self):
        self.assertEqual(pr.score({'a': True, 'u': False}, {'a': 'abstained', 'u': 'abstained'}, {})['score'], 0)


class CommittedRunTests(unittest.TestCase):
    def test_committed_runs_reproduce_published_scores(self):
        r = pr.rescore(ROOT / 'evaluation/treasury')
        self.assertEqual(r['heldout-haiku-cli']['judge']['score'], 26)
        self.assertEqual(r['heldout-extractive']['judge']['score'], -28)
        self.assertEqual(r['heldout-extractive']['judge'],
                         {'correct': 16, 'wrong': 8, 'unanswerable_served': 3, 'score': -28})
        self.assertEqual(r['heldout-ollama-qwen0.5b']['judge']['score'], 3)
        self.assertEqual(r['heldout-ollama-qwen0.5b']['author']['score'], -2)


if __name__ == '__main__':
    unittest.main()
