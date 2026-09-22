> Legacy synthetic-fixture walkthrough. For the completed real SEC interface, start with [README.md](README.md) and [the real-source report](evaluation/real/REPORT.md).

# Learn by tracing one answer

Start with this question:

```sh
python3 -m filing_assistant ask 'What caused subscription revenue growth?' --company NSTR --form 10-K --json
```

The correct fixture passage says additional seats and new customer sales caused growth. This is an invented disclosure. Read it in `data/raw/nstr-k.html`, then find its `nstr-k-revenue` ID in the JSON answer. The displayed citation includes the synthetic accession, form, report period, filing date, section, raw file path, source hash, and character offsets.

## Read the code in this order

1. Open `data/manifest.json`. A document's report period is the date its disclosure covers; its filing date is when it was submitted. In the fixture, Northstar's annual period ends December 31, 2025, while its fictional filing date is February 20, 2026. These are different fields and cannot substitute for each other.
2. Read `corpus.py`. `NarrativeParser` keeps visible narrative blocks beneath supported section headings. It omits scripts, navigation, hidden inline XBRL and tables. Visible inline XBRL text survives. `build_index` verifies source SHA-256 hashes and attaches document metadata to each passage. The offsets refer to a normalized text stream built by joining narrative blocks with newline characters. They are not HTML byte offsets.
3. Read `Engine.resolve` in `engine.py`. It selects the company and filing before ranking. An unavailable period, wrong company, missing amendment or contradictory form causes abstention. Known company names and explicit date strings in a question receive extra consistency checks. This is not general natural-language entity resolution.
4. Read `tokens`, `query_terms` and `rank`. Tokenization turns text into words. A small normalization table joins forms such as `grew` and `growth`; stop words remove common question grammar. BM25 favors matching terms that occur in fewer candidate passages and accounts for passage length. Scores are only used to rank within each selected document. They are not probabilities and are not compared as calibrated scores across filings.
5. Read `Engine.ask`. It gathers at most five candidate passages. A comparison shares that budget across two filings. It requires a strong enough word overlap and rejects unmatched query terms; a missing side causes complete abstention. The reply copies the selected passage exactly. No language model writes an explanation.
6. Read `evaluate.py`. It first checks frozen hashes. It compares retrieved and cited IDs to the supplied gold IDs, then checks exact quote equality and scope. A two-source question only receives a complete-answer mark if both gold passages are cited. Human semantic support is recorded as `null`, because no human review occurred.

## First exercise, 30 to 45 minutes

Run the question above, then change `--form 10-K` to `--form 10-Q`. Write down the two different revenue explanations and their report periods. Open both HTML files and locate the quoted passages.

Next, ask the annual filing about `2024-12-31`. Explain why it abstains even though it contains words about revenue. Finally, ask about cryptocurrency compensation and examine the candidate IDs in JSON. Relevant-looking words do not establish an answer.

Create a separate exercise note with four fields: question, selected accession, excerpt ID, and why that excerpt answers the question. Do not modify the frozen evaluation to add your answers. Finish by explaining aloud why exact quote equality is weaker than proving that the quote supports the requested conclusion.

## Second exercise: inspect a real failure

The development question `q18` asks about buyers and sales channels. Its gold passage is `hbrm-k-business`, but lexical retrieval misses it in the top five. Compare the query vocabulary to that paragraph. Terms such as "independent distributors" express the answer without repeating all the question's wording.

Design an improvement on paper first: a synonym rule, a section preference, or an embedding retriever. Decide what new held-out questions would show that the improvement works. Keep those new questions separate from the existing 30 and record both gains and regressions. Do not present this development set as a blind test.

## Suggested interview demonstration

Show a direct answer, a period-sensitive answer, a comparison, and an abstention. Open a citation's local HTML file. Explain the documented SEC access failure and why fixture CIKs and source URLs are null. Describe the failed paraphrases and show their raw retrieval results. You can discuss architecture and evaluation honestly without claiming the prototype has been validated for real financial research.
