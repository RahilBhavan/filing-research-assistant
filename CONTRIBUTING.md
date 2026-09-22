# Contributing

## Local checks

Use Python 3.9 or newer:

```sh
python3 -m unittest discover -s tests -q
python3 -m compileall -q -b filing_assistant tests
python3 -m pip wheel . --no-deps -w dist
```

Delete generated adjacent `.pyc` files after the compile check if running it
outside CI. The repository ignores them.

## Corpus changes

Treat source data, the parser, the semantic model, frozen evaluations, and
selection hashes as one versioned unit. A corpus change requires a rebuilt
index, a rebuilt semantic artifact, and a new evaluation version. Never edit a
frozen evaluation to improve a score.

## Review standard

Any change to answer selection needs tests for supported answers, unsupported
answers, scope, quantities, dates, causes, and comparisons. Record false
abstentions separately from unsupported answers.

Independent citation review uses `work/create_review_sheet.py`. The reviewer
must inspect the original filing before seeing system output and must not be the
person implementing the retrieval change.

