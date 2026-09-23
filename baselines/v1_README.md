# Filing evidence assistant

A small Python CLI that finds narrative passages, quotes them with provenance, and abstains when its scope or evidence checks fail. It uses deterministic BM25 retrieval and Python's standard library. No model, API key, package installation, or network connection is needed for the bundled demo. Tested with Python 3.9.6.

**The bundled corpus is synthetic.** Northstar Software and Harbor Manufacturing are fictional companies. Their four HTML documents contain invented disclosures in a 10-K/10-Q-like structure. The app displays this notice in every answer. Fixture CIKs and SEC URLs are null; accession identifiers start with `fixture-`. These are programming examples, not SEC facts.

## Run it

Open a terminal in this project folder:

```sh
cd <project-dir>
python3 -m filing_assistant ingest
python3 -m filing_assistant list
python3 -m filing_assistant ask 'What caused subscription revenue growth?' --company NSTR --form 10-K
python3 -m filing_assistant ask 'For the report period 2025-12-31, what percentage of quarterly revenue did the largest distributor represent?' --company HBRM --form 10-Q
python3 -m filing_assistant ask 'Compare hosting costs between the filings.' --company NSTR --compare
python3 -m filing_assistant ask 'What was the CEO compensation in cryptocurrency?' --company NSTR --form 10-K
python3 -m filing_assistant evaluate
python3 -m unittest discover -s tests -v
```

The folder is portable. After copying it elsewhere, change `cd` to that path. `ingest` checks source hashes and writes `data/index.json`. Queries rebuild and validate the small corpus in memory, so they cannot accidentally use a stale saved index. Add `--json` to `ask` for machine-readable output. Normal answers and abstentions exit 0; invalid files or command arguments exit 2.

Use `--accession fixture-nstr-k` for a precise document, `--period 2025-12-31` for an exact report period, or `--section business`, `mda`, or `risks`. Company accepts an exact ticker or full company name; real SEC corpora also accept CIK. Scope filters intersect. Without a unique filing, a normal question abstains rather than choosing an unstated date. `--compare` requires exactly two filings for the same company and returns one excerpt from each. Repeat `--accession` to choose the pair.

## What is included

| File or directory | Purpose |
| --- | --- |
| `data/manifest.json` | All document metadata, fixture notice and source hashes |
| `data/raw/` | Four frozen synthetic HTML documents |
| `filing_assistant/corpus.py` | Visible narrative parsing, source validation and stable passage IDs |
| `filing_assistant/engine.py` | Scope checks, lexical normalization, BM25, extraction and abstention |
| `filing_assistant/sec.py` | Optional downloader for a separate real SEC corpus |
| `evaluation/questions.jsonl` | Frozen 30-question development set with gold evidence IDs |
| `evaluation/frozen.json` | Hashes guarding the dataset and fixture corpus |
| `evaluation/REPORT.md` | Measured results, per-question outcomes and failures |
| `evaluation/results.json` | Full retrieved IDs, answers, citations and per-query timings |
| `tests/test_assistant.py` | Offline behavioral, parser, integrity and downloader tests |
| `WALKTHROUGH.md` | Code reading order and a concrete first exercise |
| `VALIDATION.md` | Verification, design deviations, failures and remaining risks |

## Measured result

On the 30-question synthetic development set, retrieval found gold evidence in its top five for **25/26** answerable questions. The assistant cited all required gold passages for **24/26**, correctly abstained on **4/4** unanswerable questions, and returned both gold passages for **4/4** comparisons. All **28/28** returned excerpts exactly matched their stored passage. There were **0/30** questions with citations outside their selected scope.

These figures are mechanical comparisons against agent-authored labels. They are not human-verified citation support or a test of generalization to real financial filings. The two answerable failures remain visible in the report. The evaluator records latency separately; it excludes file parsing and is not end-to-end CLI latency.

## Optional real SEC corpus

A metadata request succeeded during development, but the selected SEC filing HTML returned HTTP 403. No real filing text was incorporated into the fixtures. The optional downloader is provided for a later environment where access works. It needs network access and a real contact address in the `SEC_USER_AGENT` environment variable. Keep that address in your shell environment, not in source control.

```sh
# Set SEC_USER_AGENT locally to your application name and contact email first.
python3 -m filing_assistant fetch-sec --cik 1261333 --cik 819793 --as-of 2026-09-21 --destination sec-corpus
python3 -m filing_assistant --corpus sec-corpus list
```

The command selects the latest 10-K by cutoff and latest subsequent 10-Q per company from recent submission metadata. It downloads at most one request per 1.1 seconds, stops on access errors, writes hashes and original URLs, and refuses to overwrite any destination. It validates that supported narrative sections exist before finalizing the output directory. It does not support older submission pagination, amendments, 20-Fs, or PDFs. A downloaded document must still be inspected for parser accuracy. The fixture evaluation cannot be reused to score a different corpus.

The SEC documents [public JSON APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces), [declared User-Agent headers](https://www.sec.gov/about/webmaster-frequently-asked-questions), and [fair access limits](https://www.sec.gov/about/developer-resources). Review current guidance before downloading. SEC narrative HTML layouts are more varied than these fixtures; successful download does not establish complete parsing.

## Limits and next steps

Answers are literal evidence excerpts. Comparisons display two excerpts without calculating changes or claiming a causal relationship. Tables are omitted to avoid separating values from their headers and units. This prototype does not train or call a language model. Its word normalization and overlap thresholds are explicit heuristics; related text can still fail to answer a question, and unfamiliar paraphrases can cause false abstentions.

Next, have a person label questions and verify each cited excerpt, then evaluate on real filings with different layouts. Add embedding retrieval as a separate measured experiment against this baseline. Keep model-generated answers behind a separate interface and evaluate semantic support before using them in the default path.
