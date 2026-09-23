# Filing research

A local, extractive research assistant for four real SEC filings. Choose a company and filing, ask a question, inspect highlighted source context, or compare two reporting periods side by side. Runs with Python's standard library; no API key or paid service.

## Run

From this directory:

```sh
python3 -m filing_assistant serve
```

Open **http://127.0.0.1:8765/**. Stop with Ctrl-C. The server binds only to the local machine.

Try:

- Docusign → quarterly filing → “Why did revenue increase?”
- Albany → compare both filings → “Compare total liquidity disclosed in the two filings.”
- “Predict next quarter operating cash flow.” → explicit abstention.

**Inspect source** shows the exact cited passage highlighted beside nearby narrative, source accession, reporting and filing dates, capture hash, and the original SEC link. Anchors sometimes locate a section rather than the exact paragraph. Comparisons do not calculate changes between periods of different durations.

## What is included

| Company | Form | Report period | Filed |
|---|---|---|---|
| Docusign | 10-K | 2026-01-31 | 2026-03-18 |
| Docusign | 10-Q | 2026-07-31 | 2026-09-04 |
| Albany International | 10-K | 2025-12-31 | 2026-02-27 |
| Albany International | 10-Q | 2026-06-30 | 2026-08-04 |

Real source files and hashes live in `corpora/sec/data/`. These are serialized browser DOM captures from official SEC URLs, not original HTTP bytes. Browser serialization may include injected browser markup. Raw HTML is never served by the app. The parser excludes scripts, hidden XBRL, tables, navigation and unsupported filing sections.

Supported sections: Business, Management Discussion and Analysis, and Risk Factors. There are **1,309 passages**. Twenty selected passages were checked against the original rendered SEC sources; every checked excerpt and anchor matched.

The original fictional Northstar/Harbor corpus remains under `data/` for regression testing. Its original 30-question evaluation remains under `evaluation/`. The new real-source evaluation lives separately under `evaluation/real/`.

## Measured results and limitations

Sixty source-authored questions were frozen before retrieval development: 30 development and 30 held-out, with 20 unsupported questions overall. BM25, corpus-fitted latent semantic analysis and hybrid retrieval were compared; BM25 won the development comparison and is the default.

The original frozen held-out result is preserved as version 1, which is archival: its selection hashes match no commit in this repository, so it cannot be rerun. After correctness fixes, version 2 returns complete gold evidence for **18/20 answerable questions**, correctly abstains on **10/10 unsupported questions**, and has **0/20 false abstentions**. The two remaining misses are alternate relevant passages. Version 2 is a known-test rerun, not an independent blind benchmark.

Quantity/date/cause checks remain heuristic. Exact quotation does not guarantee answer relevance, and human semantic-support validation has not been performed. The original frozen results remain unchanged; post-fix results are recorded separately as `heldout-v2-results.json`.

The evidence gates are hand-tuned regex heuristics fitted to this 60-question set. Expect misses and wrong abstentions on other question wording.

[Read the full benchmark and failure list](evaluation/real/REPORT.md). [See the completed plan](IMPROVEMENT-PLAN.md).

## CLI and verification

Legacy CLI defaults to the synthetic fixture corpus. Select the real corpus explicitly:

```sh
python3 -m filing_assistant --corpus corpora/sec list
python3 -m filing_assistant --corpus corpora/sec ask 'Why did revenue increase?' --company DOCU --form 10-Q --json
python3 -m filing_assistant --corpus corpora/sec ask 'Compare total liquidity disclosed in the two filings.' --company AIN --compare --json
python3 -m unittest discover -s tests -q
python3 -m filing_assistant.real_eval dev
python3 -m filing_assistant.real_eval heldout-v2
```

Evaluation runs print counts to stdout and leave tracked results untouched. Add `--write` (for example `python3 -m filing_assistant.real_eval heldout-v2 --write` or `python3 -m filing_assistant --corpus . evaluate --write`) only when intentionally regenerating the tracked JSON and reports. `real_eval heldout` (v1) prints an archival notice and exits 1.

Add `--method semantic` or `--method hybrid` to a real-corpus CLI question to compare retrieval. All methods share the evidence gates. Semantic search here is 64-dimensional LSA fitted to these passages, not a pretrained embedding service. Its static model requires no numerical library at query time.

To rebuild that model, use a Python environment with NumPy already installed:

```sh
python3 -c "import json; from filing_assistant.retrieval import build_semantic; print(build_semantic(json.load(open('corpora/sec/data/index.json')), 'corpora/sec/data/semantic.json.gz'))"
```

Rebuilding can change model bytes and invalidate the selected implementation hash. Preserve the supplied artifacts for benchmark reproduction. Changing corpus data requires a new model and a new benchmark version.

Optional future SEC ingestion still requires a valid `SEC_USER_AGENT` with contact details; see `python3 -m filing_assistant fetch-sec --help`. No future refresh or monitor is scheduled.

## Structure

- `filing_assistant/corpus.py`: parser, boundaries, provenance and source hashing.
- `filing_assistant/research.py`: scope and evidence checks.
- `filing_assistant/retrieval.py`: BM25, LSA and reciprocal-rank fusion.
- `filing_assistant/webapp.py`, `static/`: localhost API and interface.
- `filing_assistant/real_eval.py`: frozen evaluation runner.
- `baselines/`: preserved first engine and documentation.
- `evaluation/real/`: questions, freezes, source audit, raw results and report.
- `evaluation/HUMAN-REVIEW.md`: independent citation-review process and worksheet instructions.

The interface renders source content as text, applies a restrictive Content Security Policy, rejects nonlocal Host and cross-origin requests, and exposes no filesystem browsing or raw filing HTML route.
