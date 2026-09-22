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

