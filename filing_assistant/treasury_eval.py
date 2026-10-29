"""Frozen treasury evaluation: retrieval recall, then checked LLM answers.

  python -m filing_assistant.treasury_eval retrieval [--split dev|heldout] [--write]
  python -m filing_assistant.treasury_eval generate --provider claude-cli --run NAME [--split ...]
  python -m filing_assistant.treasury_eval judge --run NAME            (LLM judge, answered items only)
  python -m filing_assistant.treasury_eval significance [--write]    (paired CIs and McNemar from committed files)

Retrieval and the checker are deterministic. The judge decides only whether a
served, checked answer matches the author-written reference; abstentions are
scored without a judge.
"""
import argparse
import hashlib
import json
import statistics
import sys
from pathlib import Path
from .cited import METHODS, Retrieval, answer
from .providers import ClaudeCliProvider, make_provider
from .stats import compare

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT/'corpora/treasury'
EVAL = ROOT/'evaluation/treasury'
KS = (1, 3, 5)


def check_freeze():
    frozen = json.loads((EVAL/'frozen.json').read_text())
    for f, digest in frozen['files'].items():
        if hashlib.sha256((ROOT/f).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + f)


def load(split):
    check_freeze()
    if split not in ('dev', 'heldout'):
        raise ValueError('Unknown split')
    return [json.loads(line) for line in (EVAL/(split + '.jsonl')).read_text().splitlines()]


def retrieval_eval(split='heldout', methods=METHODS, retrieval=None):
    rows = [r for r in load(split) if r['answerable']]
    retrieval = retrieval or Retrieval(json.loads((CORPUS/'data/index.json').read_text()), CORPUS)
    report = {}
    for method in methods:
        hits = {k: 0 for k in KS}
        rr, per_question = 0.0, []
        for row in rows:
            ranked = [p['passage_id'] for p in retrieval.rank(row['question'], row['scope'], method, max(KS))]
            gold = {g['passage_id'] for g in row['gold']}
            first = next((i + 1 for i, pid in enumerate(ranked) if pid in gold), None)
            for k in KS:
                hits[k] += bool(first and first <= k)
            rr += 1/first if first else 0
            per_question.append(dict(id=row['id'], first_gold_rank=first, retrieved=ranked))
        report[method] = dict(questions=len(rows), **{'recall@%d' % k: hits[k] for k in KS}, mrr=round(rr/len(rows), 3), per_question=per_question)
    return report


def generate(run, provider, split='heldout', method='dense-hybrid', limit=None):
    rows = load(split)[:limit]
    retrieval = Retrieval(json.loads((CORPUS/'data/index.json').read_text()), CORPUS)
    out = EVAL/'runs'/(run + '.jsonl')
    out.parent.mkdir(exist_ok=True)
    done = {json.loads(l)['id'] for l in out.read_text().splitlines()} if out.exists() else set()
    with out.open('a') as f:
        for row in rows:
            if row['id'] in done:
                continue  # resumable: a crashed run keeps finished questions
            result = answer(row['question'], row['scope'], retrieval, provider, method)
            f.write(json.dumps(dict(id=row['id'], split=split, **result), ensure_ascii=False) + '\n'); f.flush()
            print(row['id'], result['status'], result['reason'], file=sys.stderr)
    return out


JUDGE_SYSTEM = """You grade answers to questions about SEC filings against a reference answer written from the filing.
Return one JSON object and nothing else: {"verdict": "correct" or "incorrect", "reason": "<one short sentence>"}.
"correct" means the answer states the key fact(s) in the reference for the period asked, with no contradicting or wrong figure.
Extra true detail is fine. Missing a part the question explicitly asks for is "incorrect". Units written as "$X thousand" or "$X" in a table-in-thousands context both count."""


def judge(run, provider=None, split='heldout'):
    provider = provider or ClaudeCliProvider('sonnet')
    rows = {r['id']: r for r in load(split)}
    path = EVAL/'runs'/(run + '-judge.json')
    verdicts = json.loads(path.read_text()) if path.exists() else {}
    for line in (EVAL/'runs'/(run + '.jsonl')).read_text().splitlines():
        result = json.loads(line)
        row = rows[result['id']]
        if result['id'] in verdicts or result['status'] != 'answered' or not row['answerable']:
            continue
        user = 'Question: {}\nReference answer: {}\nAnswer to grade: {}\nQuotes it cites: {}'.format(
            row['question'], row['reference_answer'], result['answer'], json.dumps([c['quote'] for c in result['citations']], ensure_ascii=False))
        reply = provider.complete(JUDGE_SYSTEM, user)
        from .cited import parse
        try:
            verdict = parse(reply['text'])
        except ValueError:
            verdict = dict(verdict='unparsed', reason=reply['text'][:200])
        verdicts[result['id']] = dict(verdict=verdict.get('verdict'), reason=verdict.get('reason'), judge=provider.name + ':' + getattr(provider, 'model', ''), cost_usd=reply.get('cost_usd'))
        path.write_text(json.dumps(verdicts, indent=1, ensure_ascii=False) + '\n')
    return verdicts


def score(run, split='heldout', labels=None):
    """Deterministic metrics plus judge and author-label correctness for one run."""
    rows = {r['id']: r for r in load(split)}
    results = [json.loads(l) for l in (EVAL/'runs'/(run + '.jsonl')).read_text().splitlines()]
    judge_path = EVAL/'runs'/(run + '-judge.json')
    verdicts = json.loads(judge_path.read_text()) if judge_path.exists() else {}
    labels = labels if labels is not None else (json.loads((EVAL/'author-labels.json').read_text()).get(run, {}) if (EVAL/'author-labels.json').exists() else {})
    answerable = [r for r in results if rows[r['id']]['answerable']]
    unanswerable = [r for r in results if not rows[r['id']]['answerable']]
    raw_answered = [r for r in results if r['raw_status'] == 'answered']
    rejected = [r for r in results if r['reason'].startswith('rejected:')]
    served = [r for r in results if r['status'] == 'answered']
    served_answerable = [r for r in answerable if r['status'] == 'answered']
    judged = {k: v['verdict'] for k, v in verdicts.items() if k in {r['id'] for r in served_answerable}}
    agree = [k for k in judged if k in labels]
    reasons = {}
    for r in rejected:
        reasons[r['reason']] = reasons.get(r['reason'], 0) + 1
    gold_cited = sum(any(c['passage_id'] in {g['passage_id'] for g in rows[r['id']]['gold']} for c in r['citations']) for r in served_answerable)
    latencies = [r['latency_s'] for r in results if r['raw'] is not None]
    costs = [r['cost_usd'] for r in results if r['cost_usd'] is not None]
    return dict(
        run=run, questions=len(results), answerable=len(answerable), unanswerable=len(unanswerable),
        raw_answered=len(raw_answered), checker_rejections=len(rejected), rejection_reasons=reasons,
        raw_citation_faithfulness=[len(raw_answered) - len(rejected), len(raw_answered)],
        served=len(served), served_quotes_verbatim=[len(served), len(served)],
        unanswerable_abstained=[sum(r['status'] == 'abstained' for r in unanswerable), len(unanswerable)],
        false_abstentions=[sum(r['status'] == 'abstained' for r in answerable), len(answerable)],
        answered_unanswerable=[sum(r['status'] == 'answered' for r in unanswerable), len(unanswerable)],
        served_answerable_citing_gold=[gold_cited, len(served_answerable)],
        judge_correct=[sum(v == 'correct' for v in judged.values()), len(answerable)] if judged or not served_answerable else None,
        judged=len(judged),
        author_correct=[sum(labels[k] == 'correct' for k in labels if k in {r['id'] for r in served_answerable}), len(answerable)] if labels else None,
        judge_author_agreement=[sum(judged[k] == labels[k] for k in agree), len(agree)] if agree else None,
        p50_latency_s=round(statistics.median(latencies), 2) if latencies else None,
        mean_cost_usd=round(sum(costs)/len(costs), 6) if costs else None, total_cost_usd=round(sum(costs), 4) if costs else None)


RETRIEVAL_PAIRS = (('dense-hybrid', 'bm25'), ('dense-hybrid', 'dense'), ('dense-hybrid', 'lsa-hybrid'), ('dense-hybrid', 'lsa'))
WRITER_PAIRS = (('heldout-haiku-cli', 'heldout-extractive'), ('heldout-haiku-cli', 'heldout-ollama-qwen0.5b'), ('heldout-extractive', 'heldout-ollama-qwen0.5b'))


def writer_correct(run, split='heldout'):
    """Per answerable question: 1 if the writer served an answer the judge called correct, else 0 (same rule as score)."""
    verdicts = json.loads((EVAL/'runs'/(run + '-judge.json')).read_text())
    served = {json.loads(l)['id']: json.loads(l)['status'] == 'answered' for l in (EVAL/'runs'/(run + '.jsonl')).read_text().splitlines()}
    return {r['id']: int(served[r['id']] and verdicts.get(r['id'], {}).get('verdict') == 'correct') for r in load(split) if r['answerable']}


def significance(split='heldout'):
    """Paired bootstrap intervals and exact McNemar tests over committed retrieval and judge files. Calls no model."""
    report = json.loads((EVAL/(split + '-retrieval.json')).read_text())
    ranks = {m: {q['id']: q['first_gold_rank'] for q in r['per_question']} for m, r in report.items()}
    ids = sorted(ranks['bm25'])
    metrics = {'top1': lambda rank: int(rank == 1), 'mrr5': lambda rank: 1/rank if rank else 0.0}
    out = dict(split=split, questions=len(ids), retrieval={}, writers={})
    for a, b in RETRIEVAL_PAIRS:
        out['retrieval'][a + ' vs ' + b] = {name: compare([f(ranks[a][i]) for i in ids], [f(ranks[b][i]) for i in ids]) for name, f in metrics.items()}
    correct = {run: writer_correct(run, split) for pair in WRITER_PAIRS for run in pair}
    for a, b in WRITER_PAIRS:
        order = sorted(correct[a])
        out['writers'][a + ' vs ' + b] = dict(judge_correct=compare([correct[a][i] for i in order], [correct[b][i] for i in order]))
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='command', required=True)
    r = sub.add_parser('retrieval'); r.add_argument('--split', default='heldout'); r.add_argument('--write', action='store_true')
    g = sub.add_parser('generate'); g.add_argument('--run', required=True); g.add_argument('--provider', required=True); g.add_argument('--model')
    g.add_argument('--split', default='heldout'); g.add_argument('--method', default='dense-hybrid', choices=METHODS); g.add_argument('--limit', type=int)
    j = sub.add_parser('judge'); j.add_argument('--run', required=True); j.add_argument('--split', default='heldout')
    s = sub.add_parser('score'); s.add_argument('--run', required=True); s.add_argument('--split', default='heldout')
    z = sub.add_parser('significance'); z.add_argument('--split', default='heldout'); z.add_argument('--write', action='store_true')
    args = p.parse_args(argv)
    if args.command == 'retrieval':
        report = retrieval_eval(args.split)
        if args.write:
            (EVAL/(args.split + '-retrieval.json')).write_text(json.dumps(report, indent=1) + '\n')
        print(json.dumps({m: {k: v for k, v in r.items() if k != 'per_question'} for m, r in report.items()}, indent=1))
    elif args.command == 'generate':
        print(generate(args.run, make_provider(args.provider, args.model), args.split, args.method, args.limit))
    elif args.command == 'judge':
        print(json.dumps(judge(args.run, split=args.split), indent=1))
    elif args.command == 'score':
        print(json.dumps(score(args.run, args.split), indent=1))
    elif args.command == 'significance':
        report = significance(args.split)
        if args.write:
            (EVAL/(args.split + '-significance.json')).write_text(json.dumps(report, indent=1) + '\n')
        print(json.dumps(report, indent=1))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
