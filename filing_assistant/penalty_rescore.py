"""Penalty rescoring of the held-out treasury runs from committed files (no model calls).

Rule: a served answer to an answerable question scores +1 if judged correct and -4 if not;
any served answer to an unanswerable question scores -4; abstaining or a checker-rejected
answer (status other than 'answered') scores 0.

Usage: python -m filing_assistant.penalty_rescore [evaluation/treasury]
"""
import json
import sys
from pathlib import Path

RUNS = ('heldout-haiku-cli', 'heldout-extractive', 'heldout-ollama-qwen0.5b')
CORRECT, WRONG = 1, -4


def score(answerable, statuses, verdicts):
    """answerable: id -> bool; statuses: id -> run status; verdicts: id -> 'correct'/other."""
    correct = wrong = unanswerable_served = 0
    for qid, status in statuses.items():
        if status != 'answered':
            continue
        if not answerable[qid]:
            unanswerable_served += 1
        elif verdicts[qid] == 'correct':
            correct += 1
        else:
            wrong += 1
    return {'correct': correct, 'wrong': wrong, 'unanswerable_served': unanswerable_served,
            'score': CORRECT * correct + WRONG * (wrong + unanswerable_served)}


def _jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def rescore(root):
    root = Path(root)
    answerable = {r['id']: r['answerable'] for r in _jsonl(root / 'heldout.jsonl')}
    labels = json.loads((root / 'author-labels.json').read_text())
    out = {}
    for run in RUNS:
        statuses = {r['id']: r['status'] for r in _jsonl(root / 'runs' / f'{run}.jsonl')}
        judge = json.loads((root / 'runs' / f'{run}-judge.json').read_text())
        out[run] = {
            'judge': score(answerable, statuses, {i: judge[i]['verdict'] for i in statuses if i in judge}),
            'author': score(answerable, statuses, labels[run]),
        }
    return out


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    root = argv[0] if argv else Path(__file__).resolve().parents[1] / 'evaluation' / 'treasury'
    for run, by in rescore(root).items():
        for who, s in by.items():
            print(run, who, 'correct', s['correct'], 'wrong', s['wrong'],
                  'unanswerable_served', s['unanswerable_served'], 'score', s['score'])


if __name__ == '__main__':
    main()
