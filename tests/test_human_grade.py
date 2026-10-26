import csv
import json
import tempfile
import unittest
from pathlib import Path

from filing_assistant import human_grade as hg


def question(qid, answerable):
    return dict(id=qid, question='Q ' + qid, answerable=answerable, scope={}, compare=False,
                gold_answer='A' if answerable else None, why_unsupported=None if answerable else 'none',
                gold=dict(passage_id='p1', form='10-K', section='mda', start_char=0, end_char=9, source_url='u', quote='q') if answerable else None)


def output(qid, answerable, status, cited=(), auto='x'):
    answer = [dict(excerpt='text ' + c, citation=dict(passage_id=c, form='10-K', section='mda', start_char=0, end_char=9, source_url='u', accession='a')) for c in cited]
    return dict(id=qid, answerable=answerable, automatic_outcome=auto, result=dict(status=status, reason='r', answer=answer))


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        # a1 answered right, a2 answered wrong, a3 refused wrongly, u1 refused rightly, u2 answered anyway
        qs = [question('a1', True), question('a2', True), question('a3', True), question('u1', False), question('u2', False)]
        outs = [output('a1', True, 'answered', ['p1'], 'gold_cited'), output('a2', True, 'answered', ['p9'], 'answer_not_gold'),
                output('a3', True, 'abstained', auto='false_abstention'), output('u1', False, 'abstained', auto='correct_abstention'),
                output('u2', False, 'answered', ['p5'], 'answered_unsupported')]
        (self.dir / 'questions.jsonl').write_text(''.join(json.dumps(q) + '\n' for q in qs))
        (self.dir / 'outputs.json').write_text(json.dumps(dict(metrics={}, results=outs)))

    def tearDown(self):
        self.tmp.cleanup()

    def sheet(self, grades, notes=None):
        path = self.dir / 'done.csv'
        with path.open('w', newline='') as handle:
            w = csv.DictWriter(handle, fieldnames=hg.COLUMNS)
            w.writeheader()
            for qid in ['a1', 'a2', 'a3', 'u1', 'u2']:
                w.writerow({'id': qid, 'rahil_grade': grades.get(qid, ''), 'note': (notes or {}).get(qid, '')})
        return path

    def score(self, grades, notes=None):
        return hg.score(self.sheet(grades, notes), self.dir)


class ScoreTests(Fixture):
    def test_full_sheet_counts(self):
        s = self.score(dict(a1='correct', a2='wrong', a3='wrong-refusal', u1='correct-refusal', u2='wrong'))
        self.assertTrue(s['complete'])
        self.assertEqual((s['answerable_correct'], s['answerable_wrong'], s['answerable_wrong_refusal']), (1, 1, 1))
        self.assertEqual((s['unsupported_correct_refusal'], s['unsupported_answered_wrong']), (1, 1))
        self.assertEqual((s['answered_graded'], s['answered_correct']), (3, 1))
        self.assertEqual(s['acceptable'], 2)
        self.assertEqual((s['auto_gold_cited_graded'], s['auto_gold_cited_human_correct']), (1, 1))

    def test_partial_is_counted_separately_from_correct(self):
        s = self.score(dict(a1='partial'))
        self.assertEqual((s['answerable_partial'], s['answerable_correct']), (1, 0))
        self.assertEqual(s['acceptable'], 0)

    def test_blank_sheet_reports_pending_and_no_rates(self):
        s = self.score({})
        self.assertEqual((s['graded'], s['complete']), (0, False))
        report = (self.dir / 'human-report.md').read_text()
        self.assertIn('human grade is pending', report)
        self.assertIn('n/a', report)

    def test_incomplete_sheet_is_labelled_incomplete(self):
        self.score(dict(a1='correct'))
        report = (self.dir / 'human-report.md').read_text()
        self.assertIn('INCOMPLETE: 1 of 5', report)

    def test_grades_are_case_and_space_insensitive(self):
        s = self.score({'a1': ' Correct ', 'u1': 'CORRECT-REFUSAL'})
        self.assertEqual(s['grade_counts']['correct'], 1)
        self.assertEqual(s['grade_counts']['correct-refusal'], 1)

    def test_unknown_grade_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'unknown grade'):
            self.score(dict(a1='mostly right'))

    def test_grade_contradicting_system_output_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'contradicts'):
            self.score(dict(a3='correct'))  # a3 was a refusal
        with self.assertRaisesRegex(ValueError, 'contradicts'):
            self.score(dict(a1='correct-refusal'))  # a1 was an answer

    def test_unknown_id_is_rejected(self):
        path = self.sheet({})
        path.write_text(path.read_text() + 'zz9,,,,,,,,,correct,\n')
        with self.assertRaisesRegex(ValueError, 'unknown ids'):
            hg.score(path, self.dir)

    def test_rescoring_overwrites_report_and_notes_are_one_line(self):
        self.score(dict(a2='wrong'), notes=dict(a2='line one\nline two'))
        report = (self.dir / 'human-report.md').read_text()
        self.assertIn('Note: line one line two', report)
        self.score(dict(a2='partial'))
        data = json.loads((self.dir / 'human-report.json').read_text())
        self.assertEqual(data['summary']['grade_counts']['wrong'], 0)

    def test_pct_handles_zero_denominator(self):
        self.assertEqual(hg.pct(0, 0), 'n/a')
        self.assertEqual(hg.pct(1, 4), '1/4 (25%)')


class AutomaticOutcomeTests(unittest.TestCase):
    def test_outcomes(self):
        a, u = question('a', True), question('u', False)
        self.assertEqual(hg.automatic_outcome(a, output('a', True, 'answered', ['p1'])['result']), 'gold_cited')
        self.assertEqual(hg.automatic_outcome(a, output('a', True, 'answered', ['p2'])['result']), 'answer_not_gold')
        self.assertEqual(hg.automatic_outcome(a, output('a', True, 'abstained')['result']), 'false_abstention')
        self.assertEqual(hg.automatic_outcome(u, output('u', False, 'abstained')['result']), 'correct_abstention')
        self.assertEqual(hg.automatic_outcome(u, output('u', False, 'answered', ['p1'])['result']), 'answered_unsupported')


class SheetTests(Fixture):
    def test_sheet_has_blank_grade_columns_and_html_matches(self):
        rows = hg.write_sheet(self.dir)
        with (self.dir / 'grading-sheet.csv').open(newline='') as handle:
            read = list(csv.DictReader(handle))
        self.assertEqual(len(read), 5)
        self.assertEqual(list(read[0]), hg.COLUMNS)
        self.assertTrue(all(r['rahil_grade'] == '' and r['note'] == '' for r in read))
        self.assertEqual(read[2]['system_status'], 'abstained')
        self.assertTrue(read[2]['system_answer'].startswith('ABSTAINED'))
        page = (self.dir / 'grading-sheet.html').read_text()
        self.assertIn('pending until you fill', page)
        self.assertEqual(page.count('class="card"'), len(rows))

    def test_blank_sheet_scores_as_pending(self):
        hg.write_sheet(self.dir)
        s = hg.score(self.dir / 'grading-sheet.csv', self.dir)
        self.assertEqual(s['graded'], 0)


class FrozenSetTests(unittest.TestCase):
    """Checks on the committed v3 files, not fixtures."""

    def test_freeze_hashes_match(self):
        frozen = hg.check_freeze()
        self.assertIn('frozen_at', frozen)

    def test_question_mix_and_gold_quotes(self):
        qs = hg.load_questions()
        self.assertEqual(len(qs), 30)
        self.assertEqual(sum(q['answerable'] for q in qs), 20)
        index = json.loads((hg.ROOT / 'corpora/sec/data/index.json').read_text())
        text = {p['passage_id']: p['text'] for p in index['passages']}
        for q in qs:
            if q['answerable']:
                self.assertIn(q['gold']['quote'], text[q['gold']['passage_id']], q['id'])

    def test_no_overlap_with_dev_or_heldout_questions(self):
        old = set()
        for name in ('dev', 'heldout'):
            for line in (hg.ROOT / 'evaluation/real' / (name + '.jsonl')).read_text().splitlines():
                old.add(json.loads(line)['question'].lower())
        self.assertFalse(old & {q['question'].lower() for q in hg.load_questions()})

    def test_committed_sheet_is_ungraded(self):
        with (hg.DIR / 'grading-sheet.csv').open(newline='') as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 30)
        self.assertTrue(all(r['rahil_grade'] == '' for r in rows))

    def test_saved_outputs_match_a_fresh_run(self):
        saved = json.loads((hg.DIR / 'outputs.json').read_text())['metrics']
        self.assertEqual(hg.run(write=False), saved)


if __name__ == '__main__':
    unittest.main()
