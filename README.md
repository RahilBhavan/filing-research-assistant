# Filing research: answers from SEC filings that quote the source or abstain

[![CI](https://github.com/RahilBhavan/filing-research-assistant/actions/workflows/ci.yml/badge.svg)](https://github.com/RahilBhavan/filing-research-assistant/actions/workflows/ci.yml) [![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

![The local web app answers "How many bitcoins did Strategy hold as of July 24, 2026?" with a verbatim quote from Strategy's 10-Q, its accession number and an Inspect source button](docs/images/checked-answer.png)

*Screenshot of the local app with no API key, so the model-free extractive writer produced this answer.*

Filing research answers questions about six SEC filings from Strategy (MSTR), BitMine (BMNR) and Coinbase (COIN). It retrieves five passages from one filing and asks an LLM to answer with exact quotes from them. A deterministic checker turns any answer with a non-verbatim quote or an unquoted number into an abstention. The earlier v2 tool, which calls no LLM, still answers over four Docusign and Albany International filings with extractive passages.

## Results

Held-out results for v3: 40 questions about the six treasury-company filings, 30 answerable and 10 unanswerable, frozen before any writer ran. The source is [`evaluation/treasury/REPORT.md`](evaluation/treasury/REPORT.md).

| Writer | Correct (judge) | Unanswerable abstained | False abstentions | p50 latency | Cost per question |
|---|---|---|---|---|---|
| Claude Haiku 5.5, through the Claude Code CLI | 26/30 | 10/10 | 4/30 | 2.31 s | ≈$0.0003 at API list price |
| Extractive fallback, no model | 16/30 | 7/10 | 6/30 | <0.1 s | $0 |
| qwen2.5:0.5b, local through Ollama | 7/30 | 10/10 | 22/30 | 1.15 s | $0 |

- Every served quote is verbatim, because the checker runs before display. Haiku attempted 27 answers and 26 passed the checker (`evaluation/treasury/runs/heldout-haiku-cli.jsonl`).
- bge-small embeddings fused with BM25 put a gold passage first for 27/30 answerable questions (MRR@5 0.900). BM25 alone did so for 23/30 (MRR@5 0.811). Source: `evaluation/treasury/heldout-retrieval.json`.
- Claude Sonnet, a different model from the writer, judged the served answers. It agreed with the author labels on 57 of 58 items across the three writers.
- The v2 tool over Docusign and Albany calls no LLM. On its 30-question held-out set, BM25 returned complete gold evidence for 18/20 answerable questions, abstained on 10/10 unsupported ones, had 0 false abstentions and quoted 24/24 excerpts exactly. Source: `evaluation/real/heldout-v2-results.json`.

The Claude Code agent that built the system also wrote the questions, gold passages and correctness labels. No human reviewed them. See [Scope and limits](#scope-and-limits).

## How it works

1. The question names one company ticker and one filing accession.
2. `filing_assistant/cited.py` ranks the narrative passages in that filing. By default it fuses bge-small-en-v1.5 embeddings (`dense.py`) with BM25 (`retrieval.py`) by reciprocal-rank fusion and keeps the top 5.
3. One writer from `providers.py` sees only those 5 passages: `anthropic` (default model `claude-haiku-5-5`), `claude-cli`, `ollama` or `extractive`. It must return JSON with one sentence of at most 40 words and exact quotes, or abstain. Without `ANTHROPIC_API_KEY`, the default writer is `extractive`.
4. `cited.check` accepts the answer only if every cited passage was retrieved, every quote is a substring of its passage and every multi-digit number in the sentence appears in a quote.

`webapp.py` serves this flow at `/api/answer`. It serves the v2 flow (`engine.py`, `research.py`) at `/api/ask`, which uses BM25 and hand-written evidence gates and calls no model.

## Run it

You need Python 3.9 or newer. CI tests 3.9 and 3.12. The base package uses only the standard library. The `embed` extra (fastembed) is needed for the default v3 retrieval, and the `llm` extra (anthropic) for the Anthropic writer.

```sh
python3 -m venv .venv && .venv/bin/pip install -e ".[embed,llm]"
python3 -m unittest discover -s tests -q
```

The test suite ran 108 tests, all passing, on Python 3.14.

Ask one question from the command line. This uses the extractive writer unless `ANTHROPIC_API_KEY` is set. The Anthropic writer bills that key.

```sh
.venv/bin/python -m filing_assistant --corpus corpora/treasury answer \
	"How many bitcoins did Strategy hold as of July 24, 2026?" --company MSTR --accession 0001050446-26-000044
```

Start the web app at `http://127.0.0.1:8765`. Tick **Write a checked, cited answer** to use the v3 flow.

```sh
.venv/bin/python -m filing_assistant --corpus corpora/treasury serve
docker build -t filing-research . && docker run --rm -p 8765:8765 -e ANTHROPIC_API_KEY filing-research
```

Without `--corpus`, `serve` opens the v2 Docusign and Albany corpus. Run the CLI from a checkout, because the corpora are not in the installed package.

Reproduce the evaluations with the commands below. Retrieval and the v2 runs are deterministic, and they leave tracked files unchanged unless you pass `--write`. `generate` calls the writer you name. `judge` calls Claude Sonnet through a logged-in Claude Code CLI.

```sh
.venv/bin/python -m filing_assistant.treasury_eval retrieval --split heldout
.venv/bin/python -m filing_assistant.treasury_eval generate --run my-run --provider extractive   # or anthropic, claude-cli, ollama
.venv/bin/python -m filing_assistant.treasury_eval judge --run my-run
.venv/bin/python -m filing_assistant.treasury_eval score --run my-run
python3 -m filing_assistant.real_eval heldout-v2
```

## Repository layout

- `filing_assistant/`: the package: parser, retrievers, writers, checker, evaluation runners, web server and `static/` interface.
- `corpora/treasury/`: v3 corpus. Six raw filings, the passage index, pinned dense vectors and the LSA model.
- `corpora/sec/`: v2 corpus. Four Docusign and Albany filings and their index.
- `data/`: the fictional Northstar and Harbor fixture corpus, kept for regression tests.
- `evaluation/`: frozen questions, runs, results and reports. `treasury/` is v3, `real/` is v2 and the top level is the synthetic fixture set.
- `tests/`: unit tests (`unittest`).
- `work/`: scripts that wrote the questions, built the reports and checked the web app.
- `baselines/`: the first engine and its documentation, preserved.
- `docs/`: deployment notes and the README screenshot.
- `.github/workflows/`: CI and a manual SEC refresh workflow.

## Documentation

- [`docs/DEPLOY-AZURE.md`](docs/DEPLOY-AZURE.md): untested steps to run the container on Azure Container Apps, and what it costs.
- [`evaluation/treasury/REPORT.md`](evaluation/treasury/REPORT.md): v3 retrieval and answer metrics, their definitions and every Haiku miss.
- [`evaluation/real/REPORT.md`](evaluation/real/REPORT.md): v2 protocol, results and failure list.
- [`evaluation/HUMAN-REVIEW.md`](evaluation/HUMAN-REVIEW.md): the independent citation review, which has not been done.
- [`VALIDATION.md`](VALIDATION.md): the v2 validation record from September 2026.
- [`WALKTHROUGH.md`](WALKTHROUGH.md): one answer traced through the synthetic fixture engine.
- [`CONTRIBUTING.md`](CONTRIBUTING.md): local checks and the rules for changing a corpus.
- [`SECURITY.md`](SECURITY.md): what the server checks and where it must not run.

## Sources

All filings come from SEC EDGAR.

| Company | Form | Report period | Filed | Corpus |
|---|---|---|---|---|
| Strategy (MSTR) | 10-K, 10-Q | 2025-12-31, 2026-06-30 | 2026-02-19, 2026-08-03 | v3 |
| BitMine (BMNR) | 10-K, 10-Q | 2025-08-31, 2026-05-31 | 2025-11-21, 2026-07-14 | v3 |
| Coinbase (COIN) | 10-K, 10-Q | 2025-12-31, 2026-06-30 | 2026-02-12, 2026-07-30 | v3 |
| Docusign (DOCU) | 10-K, 10-Q | 2026-01-31, 2026-07-31 | 2026-03-18, 2026-09-04 | v2 |
| Albany International (AIN) | 10-K, 10-Q | 2025-12-31, 2026-06-30 | 2026-02-27, 2026-08-04 | v2 |

- The v3 corpus holds the latest 10-K and the following 10-Q for each company as of 2026-10-21. `fetch-sec` downloaded the original HTTP bytes. `corpora/treasury/data/manifest.json` pins each file by SHA-256. The index has 2,534 narrative passages.
- The v2 corpus holds browser DOM captures of the official SEC pages, not original HTTP bytes. `corpora/sec/data/manifest.json` records their hashes. The index has 1,309 passages. Twenty passages were checked against the rendered SEC source, and all 20 matched.
- Only Business, MD&A and Risk Factors are indexed. Tables are excluded.

## Scope and limits

- Independent portfolio project. It is not affiliated with Strategy, BitMine, Coinbase, Docusign, Albany International or Anthropic.
- The v3 evaluation is small: 40 held-out questions and one run per writer. One question moves a rate by about 3 points.
- The agent that built the system wrote all questions, gold passages and labels. No human has reviewed them.
- The Haiku run used the Claude Code CLI (`claude -p --model haiku`), because no Anthropic API key was available. The `anthropic` provider is covered by unit tests only.
- The checker verifies quotes and digits. It does not check entities, counts written as words or relevance. A verbatim quote can still give a wrong answer.
- v2 is a known-test rerun, not a blind benchmark. Its evidence gates are regex rules tuned to its 60 questions. The v1 held-out result cannot be reproduced.
- Not deployed. The container builds and runs locally. The Azure steps have not been run.
- Not investment advice. Facts that appear only in tables or notes are out of scope.

## License

MIT for the code; see [`LICENSE`](LICENSE). The SEC filing text under `corpora/` is public-record material from EDGAR and is not covered by the license.

Part of [Rahil Bhavan's projects](https://github.com/RahilBhavan).
