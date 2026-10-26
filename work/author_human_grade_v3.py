"""Write the frozen human-grade v3 question file.

The questions, gold answers and quoted evidence below were written by the agent
from the filing text before the system was run on them. Every quote is checked
as an exact substring of its indexed passage, and the passage location is copied
from the index. Run: python3 work/author_human_grade_v3.py
"""
import datetime
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'evaluation/human-grade-v3/questions.jsonl'

# (doc id, section, question, gold answer, passage id, exact quote)
ANSWERABLE = [
    ('docu-k', 'business', 'What percentage of Docusign\'s revenue came from subscriptions in the year ended January 31, 2026?',
     '98%', 'docu-k-3-0', 'subscriptions, which accounted for 98% of our revenue in the year ended January 31, 2026'),
    ('docu-k', 'mda', 'How many Docusign customers had more than $300,000 in annualized contract value at the end of fiscal 2026?',
     '1,205 customers as of January 31, 2026 (1,131 a year earlier)', 'docu-k-408-0',
     'The number of our customers with greater than $300,000 in annualized contract value was 1,205 as of January 31, 2026 compared to 1,131 as of January 31, 2025.'),
    ('docu-k', 'mda', 'How much did Docusign\'s subscription revenue grow in fiscal 2026 and what drove it?',
     'It increased $249.2 million, or 9%, mainly from expansion of revenue from commercial and enterprise accounts and the digital channel.', 'docu-k-435-0',
     'Subscription revenue increased $249.2 million, or 9%, in the year ended January 31, 2026. The increase was primarily due to the expansion of revenue from our commercial and enterprise accounts, as well as our digital channel.'),
    ('docu-k', 'mda', 'Why did Docusign\'s research and development expenses go up in fiscal 2026?',
     'They rose $76.5 million, or 13%, mainly from investment in the workforce for product innovation, including expansion from the Lexion acquisition in fiscal 2025.', 'docu-k-444-0',
     'Research and development expenses increased $76.5 million, or 13%, in the year ended January 31, 2026, primarily due to investments in our workforce to support product innovation, including expansion due to our acquisition of Lexion in fiscal 2025.'),
    ('docu-k', 'mda', 'What was Docusign\'s annual recurring revenue at January 31, 2026?',
     '$3,272 million (ARR), up from $3,030 million a year earlier', 'docu-k-489-0',
     'ARR was $3,272 million as of January 31, 2026, $3,030 million as of January 31, 2025'),
    ('docu-k', 'business', 'How many hours have Docusign employees volunteered through the company\'s giving programs?',
     'More than 140,000 hours collectively', 'docu-k-74-0', 'employees have volunteered more than 140,000 hours collectively'),
    ('docu-k', 'mda', 'How many shares did Docusign buy back in fiscal 2026 and what did that cost?',
     '11.8 million shares for $869.1 million', 'docu-k-457-0',
     'we repurchased and settled 11.8 million shares of common stock for $869.1 million through our stock repurchase program'),
    ('docu-k', 'mda', 'What drove the cash Docusign used in investing activities during fiscal 2026?',
     'Net cash used in investing was $126.8 million, mainly $106.4 million of property and equipment purchases (capitalized software, data centers) plus a $19.6 million net purchase of marketable securities.', 'docu-k-461-0',
     'net cash used in investing activities of $126.8 million was primarily driven by $106.4 million in purchases of property and equipment'),
    ('docu-q', 'mda', 'How many of its own shares did Docusign repurchase in the first six months of fiscal 2027, and for how much?',
     '13.3 million shares for $624.0 million', 'docu-q-56-0',
     'During the six months ended July 31, 2026, we repurchased 13.3 million shares of common stock for $624.0 million'),
    ('docu-q', 'mda', 'How much cash did Docusign\'s operations provide in the six months ended July 31, 2026?',
     '$656.2 million', 'docu-q-58-0', 'Cash provided by operating activities was $656.2 million in the six months ended July 31, 2026.'),
    ('docu-q', 'mda', 'What explains the lower research and development spending in the three months ended July 31, 2026?',
     'R&D expenses fell $6.0 million, or 4%, primarily from lower personnel costs, including stock-based compensation.', 'docu-q-41-0',
     'The decrease in both the three months and six months ended July 31, 2026 primarily consisted of personnel costs, including stock-based compensation.'),
    ('docu-q', 'mda', 'Why did Docusign\'s income tax provision rise in the quarter ended July 31, 2026?',
     'It rose $33.8 million, or 250%, mainly from higher profit before taxes and more tax expense from stock-compensation shortfalls in fiscal 2027 versus windfalls in fiscal 2026.', 'docu-q-48-0',
     'primarily attributable to higher profit before taxes and an increase in tax expense related to shortfalls from stock-based compensation in fiscal 2027 compared to windfalls in fiscal 2026'),
    ('ain-k', 'mda', 'How much was drawn on Albany\'s unsecured credit agreement at the end of 2025?',
     '$455.7 million outstanding under the $800 million agreement', 'ain-k-295-0',
     'Under our $800 million unsecured credit agreement, $455.7 million of borrowings were outstanding as of December 31, 2025.'),
    ('ain-k', 'mda', 'What share of Albany\'s 2025 consolidated net revenues came from sales to SAFRAN?',
     'Approximately 15%', 'ain-k-247-0',
     'accounted for approximately 15% of the Company’s consolidated Net revenues in 2025'),
    ('ain-k', 'business', 'Roughly how many people does Albany International employ?',
     'Approximately 5,700 people', 'ain-k-29-0', 'we are proud to employ approximately 5,700 people'),
    ('ain-k', 'mda', 'How many of its own shares did Albany repurchase in 2025, and what did they cost?',
     '2,841,036 shares for $187.9 million', 'ain-k-298-0',
     'the Company repurchased 2,841,036 shares in 2025 for a total cost of $187.9 million'),
    ('ain-k', 'mda', 'What is Albany doing with its headquarters, and how many employees does it affect?',
     'It decided in Q1 2025 to consolidate headquarters in Portsmouth, NH, affecting approximately 100 employees through the first half of 2026.', 'ain-k-260-0',
     'the Company decided to consolidate headquarters in Portsmouth, NH. This change impacts approximately 100 employees'),
    ('ain-q', 'mda', 'What caused Albany\'s gross profit to rise in the three months ended June 30, 2026?',
     'Gross profit rose $10.4 million, primarily driven by increased sales volume; margin rose to 32.7% from 31.3%.', 'ain-q-45-0',
     'The increase in gross profit of $10.4 million for the three months ended June 30, 2026, as compared to the three months ended June 30, 2025, was primarily driven by the increased sales volume.'),
    ('ain-q', 'mda', 'How did net revenues at Albany Engineered Composites change in the three months ended June 30, 2026?',
     'Increased 15.6%, driven by higher activity on programs including LEAP platforms, B787 Frames and Boeing Tanks, and lower unfavorable long-term contract adjustments.', 'ain-q-71-0',
     'Net revenues for the three months ended June 30, 2026 increased 15.6%, primarily driven by higher activity levels on various programs including LEAP platforms, B787 Frames, and Boeing Tanks'),
    ('ain-q', 'mda', 'In how many countries outside the United States does Albany have a taxable presence?',
     '22 countries', 'ain-q-58-0', 'taxable presence in 22 countries outside of the United States'),
]

# (doc id, question, why the filings cannot answer it)
UNSUPPORTED = [
    ('docu-k', 'How many patents has Docusign been granted?',
     'The 10-K discusses patents in general terms only and gives no count.'),
    ('docu-k', 'Who is the chief financial officer of Docusign?',
     'The indexed 10-K narrative does not name Docusign officers.'),
    ('docu-q', 'What were Docusign\'s diluted earnings per share for the three months ended July 31, 2026?',
     'Per-share results appear only in financial tables, which are not indexed.'),
    ('ain-k', 'What dividend per share did Albany declare in 2025?',
     'The 10-K narrative gives total dividends ($32.5 million) but no per-share figure.'),
    ('docu-k', 'How many Docusign customers are in India?',
     'No country-level customer counts for India appear in the 10-K narrative.'),
    ('ain-k', 'How many people does Albany employ in Brazil?',
     'Brazil appears only as a plant location; there is no per-country headcount.'),
    ('ain-q', 'What will Albany\'s net revenues be for full year 2027?',
     'Asks for a forecast; the filing gives none.'),
    ('docu-q', 'Why did Docusign\'s revenue decrease in the three months ended July 31, 2026?',
     'False premise: revenue increased $75.1 million, or 9%, in that quarter. A good answer corrects the premise or refuses.'),
    ('ain-k', 'What purchase price did Albany pay to acquire Heimbach?',
     'The 10-K narrative mentions the August 2023 acquisition but gives no price.'),
    ('docu-q', 'What is Docusign\'s customer churn rate?',
     'No churn or retention rate appears in the 10-Q narrative.'),
]

# Interleave the two kinds so the order carries no pattern a reader could learn.
ORDER = [
    'a0', 'a1', 'u0', 'a2', 'a3', 'u1', 'a4', 'a5', 'a6', 'u2', 'a7', 'a8', 'u3', 'a9', 'a10',
    'u4', 'a11', 'a12', 'u5', 'a13', 'a14', 'u6', 'a15', 'a16', 'u7', 'a17', 'a18', 'u8', 'a19', 'u9',
]


def main():
    index = json.loads((ROOT / 'corpora/sec/data/index.json').read_text())
    passages = {p['passage_id']: p for p in index['passages']}
    docs = {p['id']: p for p in index['passages']}
    assert len(ANSWERABLE) == 20 and len(UNSUPPORTED) == 10 and len(set(ORDER)) == 30
    # Do not reuse any earlier question text.
    old = set()
    for f in ('dev', 'heldout'):
        for line in (ROOT / 'evaluation/real' / (f + '.jsonl')).read_text().splitlines():
            old.add(json.loads(line)['question'].lower())
    rows = []
    for n, key in enumerate(ORDER, 1):
        kind, i = key[0], int(key[1:])
        if kind == 'a':
            doc, section, question, answer, pid, quote = ANSWERABLE[i]
            p = passages[pid]
            assert p['id'] == doc and p['section'] == section, pid
            assert quote in p['text'], (pid, quote)
            gold = dict(passage_id=pid, accession=p['accession'], form=p['form'], section=p['section'],
                        start_char=p['start_char'], end_char=p['end_char'], anchor=p['anchor'],
                        source_url=p['source_url'], filing_sha256=p['sha256'], quote=quote)
            extra = dict(answerable=True, gold_answer=answer, gold=gold)
        else:
            doc, question, why = UNSUPPORTED[i]
            section = None
            extra = dict(answerable=False, gold_answer=None, gold=None, why_unsupported=why)
        assert question.lower() not in old, question
        d = docs[doc]
        scope = dict(company=d['ticker'], accessions=[d['accession']])
        if section:
            scope['section'] = section
        rows.append(dict(id='v3-%02d' % n, split='human-grade-v3', question=question, scope=scope, compare=False, **extra))
    OUT.write_text(''.join(json.dumps(r, ensure_ascii=False, sort_keys=True) + '\n' for r in rows))
    print('wrote', len(rows), 'questions to', OUT)
    freeze()


def sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def freeze():
    """Record when and against which code and corpus the questions were fixed."""
    files = ['evaluation/human-grade-v3/questions.jsonl', 'corpora/sec/data/index.json', 'corpora/sec/data/manifest.json']
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    frozen = dict(
        frozen_at=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
        note='Questions, gold answers and evidence were written and hashed before the system was run on them. '
             'The system code is pinned by code_commit. Labels are agent-authored; a human grade is pending.',
        code_commit=head,
        label_origin='agent authored from the filing text before any run',
        human_independent=False,
        files={f: sha(f) for f in files},
    )
    (ROOT / 'evaluation/human-grade-v3/frozen.json').write_text(json.dumps(frozen, indent=2) + '\n')
    print('froze', frozen['frozen_at'])


if __name__ == '__main__':
    main()
