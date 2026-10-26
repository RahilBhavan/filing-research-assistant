# Independent citation review

This is the remaining human release gate. The implementer cannot satisfy an
independent review by reviewing their own labels.

1. Combine or select a frozen question file before running a new system build.
2. Generate the worksheet with `python3 work/create_review_sheet.py QUESTIONS.jsonl review.csv`.
3. Give the reviewer only the questions and original SEC source links first.
4. The reviewer records answerability, then receives the system citation and
   scores support: 0 unsupported, 1 partial, 2 complete.
5. Report agreement, complete support, partial support, unsupported answers,
   false abstentions, and scope errors. Keep disagreements rather than silently
   changing labels.

The reviewer must be someone other than the person who implemented retrieval.
Until completed, documentation must state that human semantic support is
unmeasured.


## Fresh set awaiting a human grade (v3, v2 tool)

Status: **pending**. Nobody has graded these answers yet.

`evaluation/human-grade-v3/` holds 30 new questions over the four Docusign and Albany filings (20 answerable, 10 unsupported), written and hashed before the system ran (`frozen.json`). Each answerable question has a gold answer and an exact quote with its passage ID, filing, section, character range and SEC URL.

1. Open `grading-sheet.html` in a browser. Each card shows the question, the system answer, its cited passage and the gold answer. Pick a grade for each: `correct`, `partial`, `wrong` for an answer; `correct-refusal`, `wrong-refusal` for an abstention. Add a note if useful. Choices save in the browser.
2. Click Download completed CSV. (Or fill `rahil_grade` and `note` in `grading-sheet.csv` directly.)
3. Run `python3 -m filing_assistant.human_grade score --sheet grading-sheet-completed.csv`. It rejects unknown grades and grades that contradict the system output (for example `correct` on an abstention), and writes `human-report.md` and `human-report.json`. A partly filled sheet is scored and marked incomplete.

To rebuild from scratch: `python3 -m filing_assistant.human_grade run`, then `sheet`. `run` refuses to start if the frozen questions or corpus changed.
