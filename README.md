# Filing research

Question answering over SEC 10-K and 10-Q filings that cites exact source passages or abstains. Version 3 adds Strategy (MSTR), BitMine (BMNR) and Coinbase (COIN) filings, a pretrained embedding retriever, and an LLM answer layer whose every quote is checked against the source before it is shown.

## Results

- **Checked LLM answers:** with Claude Haiku 5.5 as the writer, 26/30 answerable held-out questions answered correctly and 10/10 unanswerable ones abstained; every served quote is verbatim from its cited passage because the checker runs before display.
- **Retrieval:** bge-small embeddings fused with BM25 put a gold passage first for 27/30 held-out questions (MRR@5 0.900), against 23/30 for BM25 alone.
- **Corpus:** 2,534 narrative passages from the latest 10-K and following 10-Q of Strategy, BitMine and Coinbase, fetched from EDGAR and pinned by SHA-256.
- **No-key fallback:** the extractive writer answers 16/30 correctly at $0; the v2 extractive tool over Docusign and Albany filings returns complete gold evidence for 18/20 answerable questions and abstains on 10/10 unsupported ones.
- **Limits:** 40 held-out questions, one run per writer, and questions and labels written by the Claude Code agent that built the system, not reviewed by a human.

**How it works:** scope to one filing, retrieve the top 5 passages, make one LLM call that must return quotes from those passages or abstain, then a deterministic checker rejects any quote that is not verbatim and any number that is not quoted.

**Run the tests:** `python3 -m unittest discover -s tests -q` (108 tests, standard library only)

## Evaluation detail (v3, held-out)

40 questions about the six treasury-company filings (30 answerable, 10 unanswerable), frozen before any generator run. **Questions, gold passages, reference answers and correctness labels are author-written by the Claude Code agent that built this; none were reviewed by a human.** Full tables, definitions and every failure: [evaluation/treasury/REPORT.md](evaluation/treasury/REPORT.md).

**Retrieval** (30 answerable; a hit is any gold passage in the top k):

| Method | Recall@1 | Recall@5 | MRR@5 |
|---|---|---|---|
| BM25 | 23/30 | 26/30 | 0.811 |
| LSA, 64-dim corpus-fitted | 16/30 | 23/30 | 0.626 |
| LSA + BM25 (RRF) | 19/30 | 26/30 | 0.729 |
| bge-small-en-v1.5 embeddings (new) | 22/30 | **28/30** | 0.825 |
| bge-small + BM25 (RRF, new; used for answers) | **27/30** | 27/30 | **0.900** |

**Checked answers** (dense+BM25 hybrid, top 5 passages):

| Writer | Correct (LLM judge) | Correct (author labels) | Judge–author agreement | Unanswerable abstained | False abstentions | Raw citation faithfulness | p50 latency | Cost / question |
|---|---|---|---|---|---|---|---|---|
| Claude Haiku 5.5, via Claude Code CLI adapter | **26/30** | 26/30 | 26/26 | **10/10** | 4/30 | 26/27 | 2.3 s | ≈$0.0003 API list price ($0.0007 as CLI-reported) |
| Extractive fallback, no model | 16/30 | 16/30 | 24/24 | 7/10 | 6/30 | 27/27 | <0.1 s | $0 |
| qwen2.5:0.5b, local via Ollama | 7/30 | 6/30 | 7/8 | 10/10 | 22/30 | 6/38 | 1.2 s | $0 |

Every served quote is verbatim by construction: the checker runs before display. *Raw citation faithfulness* is the share of the model's attempted answers that passed the checker. The judge is Claude Sonnet, a different model from the writer, and sees only served answers. Author labels were committed before the judge ran. Across all three writers the judge agreed with the author labels on 57 of 58 items. That figure is weak evidence for the judge, because Haiku had no incorrect served answers; of the 10 author-incorrect items from the other two writers, the judge agreed on 9.

### Known failures

- **3 of 4 Haiku misses are retrieval misses.** For t10 (BitMine ETH held), t17 (Strategy Q2 BTC Yield) and t21 (Coinbase headcount), the gold passage was not in the top 5, and Haiku correctly abstained instead of guessing.
- **The checker is strict and once rejected a correct answer.** In t02, Haiku restated "August 31, 2025", which was not inside its quote, so the number check rejected a right answer. This was not fixed after seeing the held-out result.
- **Verbatim does not mean correct or relevant.** qwen2.5:0.5b answered "15%" for Strategy's Q2 BTC Yield by quoting a worked example from the metric's definition. The quote was verbatim, so the answer was served.
- **Words are not checked.** The checker verifies quotes and digits. It does not check entities ("KULR" in Haiku t08) or counts written as words (qwen t01, whose quotes do not support its answer).
- **Small and self-labelled.** 40 questions, a single run per writer, and labels by the builder. One question moves a rate by about 3 points.
- **Measurement path.** No Anthropic API key was available on the build machine. The Haiku run used the Claude Code CLI in headless mode (`claude -p --model haiku`, tools and settings off) as a backend adapter. Its latency includes CLI start-up. The "≈API" cost reprices the same token counts at Haiku 5.5 list price ($0.10/$0.50 per million tokens); the CLI's own figure adds a prompt-cache write premium. The `anthropic` provider is covered by unit tests only.
- **Not deployed.** The container builds and runs locally. Azure steps are documented in [docs/DEPLOY-AZURE.md](docs/DEPLOY-AZURE.md) but need an account.

## How the answer layer works

1. **Scope:** company ticker plus one filing accession.
2. **Retrieve:** bge-small embeddings fused with BM25, top 5 narrative passages. Deterministic.
3. **Write:** one LLM call. It sees only those 5 passages and must return JSON with a sentence of at most 40 words and quotes copied exactly from cited passage IDs, or abstain. It has no tools and does no calculation.
4. **Check:** deterministic. Reject unless every cited ID was retrieved, every quote is a verbatim substring of its passage, and every multi-digit number in the sentence appears in a quote. A rejection is served as an abstention. The raw output is kept in evaluation runs and stripped from API responses.

Providers (`filing_assistant/providers.py`): `anthropic` (Messages API, default `claude-haiku-5-5`, needs `ANTHROPIC_API_KEY`), `claude-cli` (the headless adapter above), `ollama` (local model), `extractive` (no model). Without a key, the default is `extractive`.

## Run v3

```sh
python3 -m venv .venv && .venv/bin/pip install -e ".[embed,llm]"   # embeddings + Anthropic SDK
.venv/bin/python -m filing_assistant --corpus corpora/treasury answer \
  "How many bitcoins did Strategy hold as of July 24, 2026?" --company MSTR --accession 0001050446-26-000044
.venv/bin/python -m filing_assistant --corpus corpora/treasury serve       # http://127.0.0.1:8765, tick "Write a checked, cited answer"

docker build -t filing-research . && docker run --rm -p 8765:8765 -e ANTHROPIC_API_KEY filing-research
```

Reproduce the evaluation. Retrieval is deterministic; generation calls a model and costs money:

```sh
.venv/bin/python -m filing_assistant.treasury_eval retrieval --split heldout
.venv/bin/python -m filing_assistant.treasury_eval generate --run my-run --provider anthropic   # or claude-cli / ollama / extractive
.venv/bin/python -m filing_assistant.treasury_eval judge --run my-run
.venv/bin/python -m filing_assistant.treasury_eval score --run my-run
.venv/bin/python work/build_treasury_report.py
```

Treasury corpus: the latest 10-K and the following 10-Q for each company as of 2026-10-21, fetched from EDGAR with `fetch-sec` (User-Agent with contact email, at most one request per 1.1 s) and pinned by SHA-256 in `corpora/treasury/data/manifest.json`. These are original HTTP bytes, not browser captures. 2,534 narrative passages; tables are excluded. Dense vectors (`dense.f32`) and the LSA model are pinned to the index digest. The 40 held-out and 9 dev questions are in `evaluation/treasury/`. They were written in `work/author_treasury_questions.py` by reading passages directly, not retriever output. The retrieval method used for answers was chosen on the dev split (`selection.json`).

---

## v2: Docusign and Albany (extractive, no LLM)

The original v2 tool: a local, extractive research assistant for four real SEC filings (Docusign, Albany International). Choose a company and filing, ask a question, inspect highlighted source context, or compare two reporting periods side by side. Runs with Python's standard library; no API key or paid service.

### Run

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

### What is included

| Company | Form | Report period | Filed |
|---|---|---|---|
| Docusign | 10-K | 2026-01-31 | 2026-03-18 |
| Docusign | 10-Q | 2026-07-31 | 2026-09-04 |
| Albany International | 10-K | 2025-12-31 | 2026-02-27 |
| Albany International | 10-Q | 2026-06-30 | 2026-08-04 |

Real source files and hashes live in `corpora/sec/data/`. These are serialized browser DOM captures from official SEC URLs, not original HTTP bytes. Browser serialization may include injected browser markup. Raw HTML is never served by the app. The parser excludes scripts, hidden XBRL, tables, navigation and unsupported filing sections.

Supported sections: Business, Management Discussion and Analysis, and Risk Factors. There are **1,309 passages**. Twenty selected passages were checked against the original rendered SEC sources; every checked excerpt and anchor matched.

The original fictional Northstar/Harbor corpus remains under `data/` for regression testing. Its original 30-question evaluation remains under `evaluation/`. The new real-source evaluation lives separately under `evaluation/real/`.

### Measured results and limitations

Sixty source-authored questions were frozen before retrieval development: 30 development and 30 held-out, with 20 unsupported questions overall. BM25, corpus-fitted latent semantic analysis and hybrid retrieval were compared; BM25 won the development comparison and is the default.

The original frozen held-out result is preserved as version 1, which is archival: its selection hashes match no commit in this repository, so it cannot be rerun. After correctness fixes, version 2 returns complete gold evidence for **18/20 answerable questions**, correctly abstains on **10/10 unsupported questions**, and has **0/20 false abstentions**. The two remaining misses are alternate relevant passages. Version 2 is a known-test rerun, not an independent blind benchmark. The v2 fixes also caused one development regression: dev r22 ("Homer facility ... monofilament share") now abstains with `question_details_not_supported`, so selected BM25 dev is 18/20, not the 19/20 cited in `selection.json`. The v1 dev artifact behind that 19/20 is no longer in the repository. `semantic.json.gz` was rebuilt for v2.

Quantity/date/cause checks remain heuristic. Exact quotation does not guarantee answer relevance, and human semantic-support validation has not been performed. The original frozen results remain unchanged; post-fix results are recorded separately as `heldout-v2-results.json`.

The evidence gates are hand-tuned regex heuristics fitted to this 60-question set. Expect misses and wrong abstentions on other question wording.

[Read the full benchmark and failure list](evaluation/real/REPORT.md). [See the completed plan](IMPROVEMENT-PLAN.md).

### CLI and verification

Run the CLI from a checkout of this repository: the corpora live in the repo, not in the installed package. The installed `filing-research` command reads the current directory unless you pass `--corpus`, and exits with an error if no corpus is there.

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

### Structure

- `filing_assistant/corpus.py`: parser, boundaries, provenance and source hashing.
- `filing_assistant/research.py`: scope and evidence checks.
- `filing_assistant/retrieval.py`: BM25, LSA and reciprocal-rank fusion.
- `filing_assistant/webapp.py`, `static/`: localhost API and interface.
- `filing_assistant/dense.py`: bge-small embeddings, pinned vectors, reciprocal-rank fusion (v3).
- `filing_assistant/cited.py`: scoped retrieval, the answer prompt and the deterministic quote/number checker (v3).
- `filing_assistant/providers.py`: Anthropic, Claude Code CLI adapter, Ollama and extractive writers (v3).
- `filing_assistant/treasury_eval.py`: frozen treasury evaluation: retrieval, generation, judge, scoring (v3).
- `evaluation/treasury/`: frozen questions, runs, judge verdicts, author labels and report (v3).
- `Dockerfile`, `docs/DEPLOY-AZURE.md`: container and undeployed Azure Container Apps steps (v3).
- `filing_assistant/real_eval.py`: frozen evaluation runner.
- `baselines/`: preserved first engine and documentation.
- `evaluation/real/`: questions, freezes, source audit, raw results and report.
- `evaluation/HUMAN-REVIEW.md`: independent citation-review process and worksheet instructions.

The interface renders source content as text, applies a restrictive Content Security Policy, rejects nonlocal Host and cross-origin requests, and exposes no filesystem browsing or raw filing HTML route.

## License

MIT for the code. The SEC filing text under `corpora/` is public-record material from SEC EDGAR and is not covered by the MIT license.
