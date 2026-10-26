"""Human-graded answer check for the v2 tool: run, make a grading sheet, score it.

Subcommands:
  run    run the frozen v3 questions and save outputs plus automatic metrics
  sheet  write grading-sheet.csv and grading-sheet.html from the saved outputs
  score  read a completed sheet and write the human-graded report

Automatic metrics compare cited passage IDs with agent-authored gold. They are
not human judgement. Only `score` reports human grades, and only for rows that
have been graded.
"""
import argparse
import csv
import hashlib
import html
import json
from collections import Counter
from pathlib import Path

from .engine import Scope

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / 'evaluation/human-grade-v3'
GRADES = ('correct', 'partial', 'wrong', 'correct-refusal', 'wrong-refusal')
ANSWER_GRADES = ('correct', 'partial', 'wrong')
REFUSAL_GRADES = ('correct-refusal', 'wrong-refusal')
COLUMNS = ['id', 'question', 'expected', 'system_status', 'system_answer', 'cited_passage',
           'gold_answer', 'gold_quote', 'gold_location', 'rahil_grade', 'note']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_questions(directory=DIR):
    return [json.loads(line) for line in (Path(directory) / 'questions.jsonl').read_text().splitlines()]


def check_freeze(directory=DIR):
    frozen = json.loads((Path(directory) / 'frozen.json').read_text())
    for name, digest in frozen['files'].items():
        if sha(ROOT / name) != digest:
            raise ValueError('Frozen input changed: ' + name)
    return frozen


def automatic_outcome(row, result):
    """Classify one result against the agent-authored gold passage."""
    cited = {a['citation']['passage_id'] for a in result['answer']}
    answered = result['status'] == 'answered'
    if not row['answerable']:
        return 'correct_abstention' if not answered else 'answered_unsupported'
    if not answered:
        return 'false_abstention'
    return 'gold_cited' if row['gold']['passage_id'] in cited else 'answer_not_gold'


def run(directory=DIR, write=True):
    from .research import ResearchEngine
    frozen = check_freeze(directory)
    index = json.loads((ROOT / 'corpora/sec/data/index.json').read_text())
    engine = ResearchEngine(index, ROOT / 'corpora/sec/data/semantic.json.gz', 'bm25')
    by_id = {p['passage_id']: p for p in index['passages']}
    results = []
    counts = Counter()
    for row in load_questions(directory):
        result = engine.ask(row['question'], Scope(**row['scope']), row['compare'])
        outcome = automatic_outcome(row, result)
        counts[outcome] += 1
        counts['answerable' if row['answerable'] else 'unsupported'] += 1
        for a in result['answer']:
            counts['excerpts'] += 1
            counts['exact_excerpts'] += a['excerpt'] == by_id[a['citation']['passage_id']]['text']
            counts['wrong_scope'] += a['citation']['accession'] not in row['scope']['accessions']
        results.append(dict(id=row['id'], question=row['question'], answerable=row['answerable'],
                            automatic_outcome=outcome, result=result))
    metrics = dict(
        label='automatic',
        method='bm25 (default of the v2 tool)',
        frozen_at=frozen['frozen_at'],
        code_commit=frozen['code_commit'],
        questions=len(results),
        answerable=counts['answerable'],
        unsupported=counts['unsupported'],
        gold_passage_cited=counts['gold_cited'],
        answered_cited_other_passage=counts['answer_not_gold'],
        false_abstentions=counts['false_abstention'],
        unsupported_abstained=counts['correct_abstention'],
        unsupported_answered=counts['answered_unsupported'],
        excerpts=counts['excerpts'],
        exact_excerpts=counts['exact_excerpts'],
        excerpts_outside_scope=counts['wrong_scope'],
        note='Automatic: compares cited passage IDs with agent-authored gold. It does not judge whether an answer is right. Human grade pending.',
    )
    if write:
        (Path(directory) / 'outputs.json').write_text(json.dumps(dict(metrics=metrics, results=results), indent=2, ensure_ascii=False) + '\n')
    return metrics


def sheet_rows(directory=DIR):
    outputs = {r['id']: r for r in json.loads((Path(directory) / 'outputs.json').read_text())['results']}
    rows = []
    for q in load_questions(directory):
        res = outputs[q['id']]['result']
        if res['status'] == 'answered':
            answer = '\n\n'.join(a['excerpt'] for a in res['answer'])
            cited = '\n'.join('%s (%s %s, chars %s-%s) %s' % (
                a['citation']['passage_id'], a['citation']['form'], a['citation']['section'],
                a['citation']['start_char'], a['citation']['end_char'], a['citation']['source_url']) for a in res['answer'])
        else:
            answer = 'ABSTAINED (' + str(res['reason']) + ')'
            cited = ''
        g = q['gold']
        rows.append({
            'id': q['id'], 'question': q['question'],
            'expected': 'answerable' if q['answerable'] else 'unsupported (no answer in the filings)',
            'system_status': res['status'], 'system_answer': answer, 'cited_passage': cited,
            'gold_answer': q['gold_answer'] if q['answerable'] else 'None. ' + q['why_unsupported'],
            'gold_quote': g['quote'] if g else '',
            'gold_location': '%s (%s %s, chars %s-%s) %s' % (g['passage_id'], g['form'], g['section'], g['start_char'], g['end_char'], g['source_url']) if g else '',
            'rahil_grade': '', 'note': ''})
    return rows


def write_sheet(directory=DIR):
    directory = Path(directory)
    rows = sheet_rows(directory)
    with (directory / 'grading-sheet.csv').open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    (directory / 'grading-sheet.html').write_text(render_html(rows), encoding='utf-8')
    return rows


def render_html(rows):
    cards = []
    for r in rows:
        grades = ANSWER_GRADES if r['system_status'] == 'answered' else REFUSAL_GRADES
        options = '<option value="">(not graded)</option>' + ''.join('<option>%s</option>' % g for g in GRADES)
        cards.append(
            '<section class="card" data-id="%(id)s"><h2>%(id)s. %(question)s</h2>'
            '<p class="meta">Expected: %(expected)s. System: %(system_status)s. Fits this row: %(fits)s.</p>'
            '<div class="cols"><div><h3>System answer</h3><pre>%(system_answer)s</pre><p class="src">%(cited_passage)s</p></div>'
            '<div><h3>Gold answer</h3><p><b>%(gold_answer)s</b></p><pre>%(gold_quote)s</pre><p class="src">%(gold_location)s</p></div></div>'
            '<label>Grade <select class="grade">%(options)s</select></label> '
            '<label class="n">Note <input class="note" type="text"></label></section>' % dict(
                {k: html.escape(v) for k, v in r.items()}, options=options, fits=html.escape(', '.join(grades))))
    return PAGE.replace('__CARDS__', '\n'.join(cards)).replace('__COLUMNS__', json.dumps(COLUMNS)).replace('__ROWS__', json.dumps(rows).replace('</', '<\\/'))


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Filing research: human grading sheet (v3)</title>
<style>
body{font:16px/1.5 system-ui,sans-serif;max-width:1100px;margin:0 auto;padding:16px;color:#1a1a1a}
.card{border:1px solid #bbb;border-radius:6px;padding:12px 16px;margin:16px 0}
.card.done{border-color:#2a7a2a}
h2{font-size:1.05rem;margin:0 0 4px}h3{font-size:.85rem;margin:8px 0 2px;text-transform:uppercase;color:#555}
.meta,.src{font-size:.8rem;color:#555;word-break:break-all}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:16px}@media(max-width:800px){.cols{grid-template-columns:1fr}}
pre{white-space:pre-wrap;background:#f5f5f5;padding:8px;border-radius:4px;font:inherit;font-size:.9rem;margin:0}
label{font-size:.9rem}.n{display:inline-block;width:60%}.note{width:80%}
#bar{position:sticky;top:0;background:#fff;padding:8px 0;border-bottom:1px solid #ccc}
</style></head><body>
<div id="bar"><b>Human grading sheet, v3.</b> The human grade is pending until you fill this in.
<span id="count"></span> <button id="dl">Download completed CSV</button></div>
<p>Grades: correct, partial, wrong (for answers); correct-refusal, wrong-refusal (for abstentions). Choices save in this browser. Download the CSV, then run
<code>python3 -m filing_assistant.human_grade score --sheet grading-sheet-completed.csv</code>.</p>
__CARDS__
<script>
const COLUMNS=__COLUMNS__, ROWS=__ROWS__, KEY='filing-grade-v3';
const saved=JSON.parse(localStorage.getItem(KEY)||'{}');
function refresh(){const n=document.querySelectorAll('.grade').length;let d=0;
 document.querySelectorAll('.card').forEach(c=>{const g=c.querySelector('.grade').value;c.classList.toggle('done',!!g);if(g)d++});
 document.getElementById('count').textContent=' Graded '+d+' of '+n+'.'}
document.querySelectorAll('.card').forEach(c=>{const id=c.dataset.id,s=saved[id]||{},g=c.querySelector('.grade'),t=c.querySelector('.note');
 g.value=s.grade||'';t.value=s.note||'';
 const save=()=>{saved[id]={grade:g.value,note:t.value};localStorage.setItem(KEY,JSON.stringify(saved));refresh()};
 g.addEventListener('change',save);t.addEventListener('input',save)});
function esc(v){v=String(v);return /[",\\n\\r]/.test(v)?'"'+v.replace(/"/g,'""')+'"':v}
document.getElementById('dl').addEventListener('click',()=>{
 const lines=[COLUMNS.join(',')];
 ROWS.forEach(r=>{const s=saved[r.id]||{};lines.push(COLUMNS.map(k=>esc(k==='rahil_grade'?(s.grade||''):k==='note'?(s.note||''):r[k])).join(','))});
 const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([lines.join('\\r\\n')+'\\r\\n'],{type:'text/csv'}));
 a.download='grading-sheet-completed.csv';a.click()});
refresh();
</script></body></html>
"""


def read_grades(sheet):
    with Path(sheet).open(newline='', encoding='utf-8') as handle:
        return {row['id']: row for row in csv.DictReader(handle)}


def score(sheet, directory=DIR, out=None):
    """Score a completed sheet. Raises ValueError on grades that are invalid or contradict the system output."""
    directory = Path(directory)
    questions = {q['id']: q for q in load_questions(directory)}
    outputs = {r['id']: r for r in json.loads((directory / 'outputs.json').read_text())['results']}
    graded = read_grades(sheet)
    unknown = sorted(set(graded) - set(questions))
    if unknown:
        raise ValueError('Sheet has unknown ids: ' + ', '.join(unknown))
    problems, rows = [], []
    for qid, q in questions.items():
        raw = (graded.get(qid, {}).get('rahil_grade') or '').strip().lower()
        status = outputs[qid]['result']['status']
        if raw and raw not in GRADES:
            problems.append('%s: unknown grade %r' % (qid, raw))
            continue
        if raw and (raw in ANSWER_GRADES) != (status == 'answered'):
            problems.append('%s: grade %r contradicts system status %r' % (qid, raw, status))
            continue
        rows.append(dict(id=qid, answerable=q['answerable'], status=status, grade=raw or None,
                         auto=outputs[qid]['automatic_outcome'], note=' '.join((graded.get(qid, {}).get('note') or '').split())))
    if problems:
        raise ValueError('Sheet problems:\n' + '\n'.join(problems))
    summary = summarize(rows)
    report = render_report(summary, rows, questions)
    out = Path(out) if out else directory
    (out / 'human-report.json').write_text(json.dumps(dict(summary=summary, rows=rows), indent=2) + '\n')
    (out / 'human-report.md').write_text(report)
    return summary


def pct(n, d):
    return 'n/a' if not d else '%d/%d (%.0f%%)' % (n, d, 100.0 * n / d)


def summarize(rows):
    done = [r for r in rows if r['grade']]
    count = lambda pred: sum(1 for r in done if pred(r))  # noqa: E731
    ans = [r for r in done if r['answerable']]
    uns = [r for r in done if not r['answerable']]
    answered = [r for r in done if r['status'] == 'answered']
    # Automatic gold hit versus the human verdict, on rows with a grade.
    auto_hit = [r for r in ans if r['auto'] == 'gold_cited']
    return dict(
        total=len(rows), graded=len(done), complete=len(done) == len(rows),
        grade_counts={g: count(lambda r, g=g: r['grade'] == g) for g in GRADES},
        answerable_graded=len(ans), unsupported_graded=len(uns),
        answerable_correct=sum(r['grade'] == 'correct' for r in ans),
        answerable_partial=sum(r['grade'] == 'partial' for r in ans),
        answerable_wrong=sum(r['grade'] == 'wrong' for r in ans),
        answerable_wrong_refusal=sum(r['grade'] == 'wrong-refusal' for r in ans),
        unsupported_correct_refusal=sum(r['grade'] == 'correct-refusal' for r in uns),
        unsupported_answered_wrong=sum(r['grade'] == 'wrong' for r in uns),
        answered_graded=len(answered),
        answered_correct=sum(r['grade'] == 'correct' for r in answered),
        acceptable=sum(r['grade'] in ('correct', 'correct-refusal') for r in done),
        auto_gold_cited_graded=len(auto_hit),
        auto_gold_cited_human_correct=sum(r['grade'] == 'correct' for r in auto_hit),
    )


def render_report(s, rows, questions):
    status = ('All %d questions are graded.' % s['total']) if s['complete'] else \
        ('INCOMPLETE: %d of %d questions are graded. Figures below cover graded rows only.' % (s['graded'], s['total']))
    if not s['graded']:
        status = 'The human grade is pending: no question has been graded yet.'
    lines = ['# Human-graded results, v3 (v2 tool, BM25)', '', status, '',
             'These grades are Rahil\'s judgement of the system answer against the filing text. They are separate from the automatic metrics in `outputs.json`.', '',
             '| Measure | Result |', '|---|---|',
             '| Answerable, answered correctly | %s |' % pct(s['answerable_correct'], s['answerable_graded']),
             '| Answerable, partially correct | %s |' % pct(s['answerable_partial'], s['answerable_graded']),
             '| Answerable, answered wrongly | %s |' % pct(s['answerable_wrong'], s['answerable_graded']),
             '| Answerable, wrongly refused | %s |' % pct(s['answerable_wrong_refusal'], s['answerable_graded']),
             '| Unsupported, correctly refused | %s |' % pct(s['unsupported_correct_refusal'], s['unsupported_graded']),
             '| Unsupported, answered anyway | %s |' % pct(s['unsupported_answered_wrong'], s['unsupported_graded']),
             '| Answered questions that were correct | %s |' % pct(s['answered_correct'], s['answered_graded']),
             '| Correct or correct-refusal, all graded | %s |' % pct(s['acceptable'], s['graded']),
             '| Automatic gold-passage hits that a human graded correct | %s |' % pct(s['auto_gold_cited_human_correct'], s['auto_gold_cited_graded']),
             '', 'One question moves a rate by about 3 points. Labels, gold answers and questions were written by the agent that built the system; the grade is the only human input.', '']
    notes = [r for r in rows if r['grade'] in ('partial', 'wrong', 'wrong-refusal')]
    if notes:
        lines += ['## Questions graded partial, wrong or wrongly refused', '']
        for r in notes:
            lines.append('- %s (%s): %s. %s%s' % (r['id'], r['grade'], questions[r['id']]['question'], 'Auto: ' + r['auto'] + '.', (' Note: ' + r['note']) if r['note'] else ''))
        lines.append('')
    return '\n'.join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='command', required=True)
    sub.add_parser('run')
    sub.add_parser('sheet')
    sp = sub.add_parser('score')
    sp.add_argument('--sheet', required=True, type=Path, help='Completed grading sheet CSV')
    sp.add_argument('--out', type=Path, help='Folder for human-report.md and .json (default: the v3 folder)')
    args = p.parse_args(argv)
    if args.command == 'run':
        print(json.dumps(run(), indent=2))
    elif args.command == 'sheet':
        print('wrote %d rows to %s' % (len(write_sheet()), DIR))
    else:
        print(json.dumps(score(args.sheet, out=args.out), indent=2))


if __name__ == '__main__':
    main()
