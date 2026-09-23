# Validation — September 21, 2026

All commands below ran from the project directory unless stated otherwise. The real evaluation is separate from the preserved synthetic benchmark.

| Check | Command / action | Exit | Result |
|---|---|---:|---|
| Regression and evidence tests | `python3 -m unittest discover -s tests -q` | 0 | 67 tests passed, including original 41 |
| Source/index integrity | Covered by `test_sources_and_frozen_index_match_rebuild` | 0 | Raw hashes, frozen questions, and rebuilt index match |
| Development comparison | `python3 -m filing_assistant.real_eval dev` | 0 | Baseline plus BM25, LSA and hybrid measured on 30 questions; prints only, `--write` rewrites `dev-results.json` |
| Held-out comparison (v1, archival) | `python3 -m filing_assistant.real_eval heldout` | 1 | Prints "v1 frozen results are archival and cannot be reproduced from this repo; run heldout-v2". The v1 selection hashes match no commit, so `heldout-results.json` is kept only as a record |
| Post-fix held-out comparison | `python3 -m filing_assistant.real_eval heldout-v2` | 0 | 18/20 gold-complete, 10/10 unsupported abstentions, 0/20 false abstentions; two alternate-passage misses; prints only, `--write` rewrites `heldout-v2-results.json` |
| Real CLI answer | `python3 -m filing_assistant --corpus corpora/sec ask 'Why did revenue increase?' --company DOCU --form 10-Q --json` | 0 | Exact `docu-q-31-0` excerpt with accession, dates, hash and source anchor |
| JavaScript syntax | Bundled Node: `node --check filing_assistant/static/app.js` | 0 | No syntax errors |
| Package build | `python3 -m pip wheel --no-build-isolation . --no-deps -w /tmp/filing-wheel2` | 0 | `filing_research_assistant-1.0.0-py3-none-any.whl` with entry point metadata |
| Review worksheet | `python3 work/create_review_sheet.py evaluation/real/dev.jsonl /tmp/filing-review.csv` | 0 | 30-row blind-review worksheet generated |
| Local API | `python3 work/verify_web.py` with server on port 8765 | 0 | 11 assertions/checks passed; results in `evaluation/real/web-verification.json` |
| Browser source audit | 20 complete excerpts checked against normalized official SEC DOM text, plus anchor lookup | n/a | 20/20 text matches; 20/20 anchors exist |
| Browser interface | Real answer, source dialog, comparison, prediction abstention | n/a | Expected content visible; no console errors observed |
| Visual review | Desktop comparison screenshot | n/a | Two readable source cards shown side by side |

The local API check required network sandbox permission to contact localhost. The server required permission to bind its localhost port. The first isolated package build could not download `setuptools` because this environment has no PyPI network access; the compatibility fallback using installed setuptools then built successfully. No external publishing occurred yet.

## Measured limitations

Original selected BM25 on held-out data: gold retrieval 19/20; complete gold answers 13/20; correct unsupported abstention 9/10; false abstention 6/20. Post-fix v2: gold retrieval 19/20; complete gold answers 18/20; correct unsupported abstention 10/10; false abstention 0/20; exact excerpts 24/24; cross-scope excerpts 0. The two remaining misses cite alternate relevant passages. Details are in `evaluation/real/REPORT.md` and `heldout-v2-results.json`.

Independent human semantic-support review was **not performed**. No accuracy claim is based solely on exact string matches. Tables are intentionally excluded. Twenty selected source checks do not establish exhaustive parser accuracy. No paid/pretrained embedding provider was benchmarked: the semantic experiment is local corpus-fitted LSA. The load-test script, SEC refresh workflow, packaging, CI, accessibility checks, and responsive layout checks are now included; CI and live SEC refresh require GitHub execution with network access and a configured `SEC_USER_AGENT` secret.

The original fixture validation remains in `baselines/v1_VALIDATION.md`.
