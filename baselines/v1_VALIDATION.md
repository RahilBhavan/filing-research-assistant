# Validation and implementation record

Implemented September 21, 2026. The original planning document one directory above remains unchanged. The project lives entirely in `outputs/filing-assistant`. No app was deployed or published, and no external messages were sent.

## Delivered behavior

Four immutable synthetic HTML documents represent two fictional companies with different fiscal year ends, each with an annual and subsequent quarterly report. They produce 39 narrative passages. The corpus includes similar terms across periods and sections, changes in narrative explanations, annual versus quarterly percentages, hidden content, and unsupported tables. Every query displays a source notice. Synthetic documents have no SEC CIK, SEC accession number or remote source URL.

The implementation provides local ingestion with hash validation, visible narrative extraction, company/form/period/accession/section filtering, BM25 ranking, exact quoted answers, conservative abstention, paired comparison extracts, an offline CLI, an optional separate SEC downloader, and a frozen 30-question evaluation with gold annotations and per-question traces.

## Verification commands and outcomes

Run these from the project directory. Exact command arrays, exit codes, captured output and Python version are saved in `evaluation/verification.json`; the demo transcript is in `evaluation/demo-output.txt`.

| Command | Exit | Meaningful result |
| --- | --- | --- |
| `python3 -m unittest discover -s tests -v` | 0 | 41 tests pass, covering scope conflicts, hidden content, omitted tables, quote provenance, hash changes, missing evidence, comparisons and SEC selection/access errors |
| `python3 -m filing_assistant ingest` | 0 | Four documents validated; 39 passages; one table omitted per document |
| `python3 -m filing_assistant list` | 0 | Four synthetic filings listed with exact period, filing date and accession |
| Direct-answer demo in README | 0 | Quotes the annual subscription growth passage with fixture provenance |
| Period-sensitive demo in README | 0 | Selects the quarterly 27 percent distributor figure, not the annual 24 percent |
| Comparison demo in README | 0 | Returns annual and quarterly hosting-cost excerpts with separate citations |
| Unsupported-question demo in README | 0 | Abstains; no answer excerpt |
| `python3 -m filing_assistant evaluate` | 0 | All frozen hashes match; report includes all 30 outcomes |

## Measured counts

| Check | Result |
| --- | --- |
| At least one gold passage in top five | 25/26 answerable questions, 96.15% |
| All required gold passages in top five | 25/26, 96.15% |
| All gold passages cited in the extractive answer | 24/26, 92.31% |
| Correct abstention | 4/4 unanswerable questions, 100% |
| False abstention | 2/26 answerable questions, 7.69% |
| Exact returned quote equals its stored passage | 28/28 excerpts, 100% |
| Returned passage matches an agent-authored gold ID | 28/28 excerpts, 100% |
| Wrong-scope citations | 0/30 questions |
| Complete comparison answers | 4/4 comparisons |
| Human-verified semantic citation support | Not measured |

The latency figure in `evaluation/REPORT.md` is a warm in-process median over one run per question. It excludes parsing and process startup. Source labels and questions were authored by the same agent that wrote the implementation. Development rules were refined after the first evaluation, so these are development metrics, not independent test results. A low denominator, especially four negative cases, prevents broad conclusions about abstention.

## Failure investigations

| Case | What happened | Resolution or remaining limit |
| --- | --- | --- |
| Dollar-denominated subscription revenue probe | The first engine returned a growth explanation without a dollar amount | Added an unmatched-term guard and a currency-evidence check; regression test passes |
| Revenue growth "on Mars" probe | The first engine ignored an unsupported qualifier and quoted a related passage | Added a guard against substantive query terms missing from retrieved scope; regression test passes |
| Employee wording in q21 | `employees` and `worked` normalized inconsistently, causing false abstention | Unified inflections; q21 now returns the 240-person annual excerpt |
| q17, cast housing vendor paraphrase | Correct supplier passage is retrieved, but only a minority of query terms overlap | Remains an explicit false abstention; no guessed answer |
| q18, buyers and sales channels paraphrase | The business passage falls outside the top five | Remains a retrieval failure and abstention; raw candidates are retained |
| Real SEC HTML download | Public submissions JSON returned HTTP 200; selected annual filing HTML returned HTTP 403 | Shipped synthetic fixtures and an optional downloader; no claim of real-data parser validation |

The frozen evaluation file and corpus were not rewritten to remove failures. The amendment case asks for an unavailable hypothetical amendment; there is no actual amendment in the fixture corpus. This exercises scope rejection, not amendment interpretation.

## SEC access evidence

The initial sandbox request could not resolve `data.sec.gov`, exit 6. A subsequent approved network request to `https://data.sec.gov/submissions/CIK0001261333.json` returned HTTP 200, curl exit 0. The selected source `https://www.sec.gov/Archives/edgar/data/1261333/000126133326000021/docu-20260131.htm` returned HTTP 403, curl exit 0. Curl's transport exit 0 did not mean the filing was accessible. The failed HTTP response was not treated as filing content. The development probe used an application identifier without a contact email, so this observation does not prove the SEC would reject a fully declared client. The optional downloader requires the user to configure a real contact address.

## Deviations and limits

- Real SEC filings were replaced with synthetic equivalents after the HTML access failure, as permitted by the implementation request. The corpus cutoff and invented dates are fixed in the manifest. These files are not actual financial evidence.
- Tables and numerical totals are excluded. Narrative counts and percentages retain their original text and periods. No XBRL calculation or table extraction is claimed.
- Comparison answers juxtapose excerpts. They do not infer net changes, compute percentages, or establish that a risk is new unless the text explicitly states it.
- Human support review and true answer-accuracy grading remain outstanding. The original 90% semantic citation-support target is unverified. Gold passage agreement is not a substitute.
- Lexical overlap is an imperfect answerability test. Familiar words can have the wrong relationship; an irrelevant exact quote remains possible. The unmatched-term guard reduces some false positives but also increases abstention on unfamiliar phrasing. Known company names and explicit dates receive checks; arbitrary entities, relative dates and fiscal-year language are not fully understood.
- Real HTML often has tables used for layout, sections in differently styled spans, repeated contents pages and complex footnotes. The parser excludes whole tables and may omit valid text. A live corpus requires manual coverage inspection and new gold labels.
- The optional SEC downloader's selection and error handling have offline tests. A successful end-to-end real filing download was not run because source HTML was blocked and a real contact configuration was unavailable. It handles recent submission metadata only and stops on access errors.
- No embeddings or generative model were added. A future enhancement must keep this deterministic baseline and use separate evaluation labels.
