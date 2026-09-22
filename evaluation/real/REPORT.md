# Real filing evaluation

Evaluated September 21, 2026. All labels are agent-authored from source text, not independently human-reviewed. The held-out split was not used for retrieval tuning, but the author also built the system; this is not a blind external benchmark.

## Protocol

Four real filings; 1,309 passages. Sixty questions: 40 answerable and 20 unsupported. Each split has 20 answerable and 10 unsupported questions. Positive evidence families and paired paraphrases stay in one split. Questions and source index were hashed before new retrieval development. Training for LSA uses only source passages.

The original engine is preserved in `baselines/v1_engine.py` and evaluated against the same corrected real corpus. Thus these engine comparisons do not measure the separate parser improvement. BM25 was selected on development results, and implementation hashes were frozen before running held-out evaluation. No implementation changes followed held-out inspection.

Development changes: remove question filler, normalize the supply inflection, reject wrong financial measures, require currency evidence for monetary requests, check exact requested numbers and event-specific date precision, require explicit causal language, and require evidence from both selected filings. All methods share these gates. Retrieval budget is five passages total, distributed across both documents for comparisons.

## Results

Gold-complete means every annotated passage ID was cited. Alternate relevant passages count as misses. An exact quote is evidence of textual fidelity, not proof that it answers a question.

| Split | Engine | Gold retrieved /20 | Gold-complete answers /20 | Unsupported abstentions /10 | False abstentions /20 | Answered but not gold-complete | Complete comparisons |
|---|---|---:|---:|---:|---:|---:|---:|
| dev | baseline | 19 | 12 | 9 | 6 | 3 | 0/2 |
| dev | bm25 | 20 | 19 | 10 | 0 | 1 | 2/2 |
| dev | semantic | 16 | 12 | 10 | 4 | 4 | 0/2 |
| dev | hybrid | 19 | 16 | 10 | 1 | 3 | 1/2 |
| heldout | baseline | 19 | 11 | 10 | 7 | 2 | 1/4 |
| heldout | bm25 | 19 | 13 | 9 | 6 | 2 | 2/4 |
| heldout | semantic | 15 | 11 | 9 | 7 | 3 | 0/4 |
| heldout | hybrid | 17 | 11 | 9 | 6 | 4 | 0/4 |

BM25 is the default because it led on development gold coverage. The corpus-fitted, 64-dimensional LSA model and reciprocal-rank hybrid did not improve the measured results. This experiment does not establish how a pretrained embedding model would perform.

## Post-fix v2 result

The first audit exposed one unsafe quantity answer and six false abstentions. The fixes add quantity-intent detection, plural and tense normalization, and a distinction between factual-event causes and explicitly hypothetical risk questions. The original version 1 result remains frozen. A known-test v2 rerun gives BM25 18/20 gold-complete answers, 10/10 unsupported abstentions, 0/20 false abstentions, and 24/24 exact excerpts. Two questions remain strict gold misses because the system cited alternate relevant paragraphs: partner integrations and international revenue growth. See `heldout-v2-results.json` and `selection-v2.json`.

The v2 rerun is not a new blind benchmark: it uses the same question set after the implementer saw the v1 failures. Independent human citation review remains pending; follow `evaluation/HUMAN-REVIEW.md`.

Selected BM25 held-out results: 17/17 excerpts exactly matched their source passages and 0 excerpts crossed the selected company/filing scope. Human-verified semantic support remains **unmeasured**.

## Every selected-engine failure

### dev

- **r37 — What sales channels does Docusign use?** Outcome: `answer_not_gold_complete`; reason: `extractive_evidence`. Gold: docu-k-49-0. Cited: docu-k-55-0.
### heldout

- **r03 — How many active partner integrations does Docusign offer?** Outcome: `answer_not_gold_complete`; reason: `extractive_evidence`. Gold: docu-k-1-0. Cited: docu-k-10-0.
- **r04 — Did any single customer account for more than 10% of total revenue?** Outcome: `false_abstention`; reason: `question_details_not_supported`. Gold: docu-k-1-0. Cited: none.
- **r07 — Compare the disclosed international revenue growth rates between the filings.** Outcome: `false_abstention`; reason: `question_details_not_supported`. Gold: docu-k-24-0, docu-q-16-0. Cited: none.
- **r23 — Compare the disclosed reasons for the decrease in cash provided by operating activities.** Outcome: `false_abstention`; reason: `question_details_not_supported`. Gold: ain-k-291-0, ain-q-79-0. Cited: none.
- **r32 — What does the quarterly risk factors section say about changes?** Outcome: `false_abstention`; reason: `question_details_not_supported`. Gold: i14dbd90247bd4fc9b423fff1380bd4ce_127. Cited: none.
- **r36 — Which currencies strengthened compared with the U.S. dollar?** Outcome: `false_abstention`; reason: `insufficient_topic_support`. Gold: docu-q-47-0. Cited: none.
- **r40 — Why might alternative raw material suppliers be unavailable to AEC?** Outcome: `false_abstention`; reason: `question_details_not_supported`. Gold: ain-k-25-0. Cited: none.
- **r51 — What was the exact number of employees based in the U.S.?** Outcome: `answer_not_gold_complete`; reason: `extractive_evidence`. Gold: unsupported. Cited: docu-k-237-0.

### Interpretation

- Development r37 cites another paragraph that mentions digital channels, direct sales and partners. It remains a strict gold miss; the frozen label was not expanded after seeing the result.
- Held-out r03 cites another developer-ecosystem passage rather than the annotated integrations passage. This also remains a strict miss.
- Six answerable held-out questions abstained. Morphological differences, additional question words, and required topic coverage make the gate overly conservative in these cases.
- **Held-out r51 is an actual unsupported answer:** an exact U.S. headcount question received a generic employee-recruiting risk bullet. The quantity check does not recognize that question formulation, while token filtering drops geographic initials. This is a known correctness limitation, not a successful answer. It is preserved in the frozen report and has not been tuned away.

## Source audit

Twenty passages, five per filing, were compared in the browser against complete normalized text in the official SEC rendered page. All 20 excerpts matched exactly and all 20 source anchors existed. See `source-audit.json` for full quotes, source URLs, hashes and observations. This is a selected agent audit, not exhaustive or human-certified extraction validation.

The original parser produced 2,215 passages on these documents, including later sections incorrectly labeled as MD&A or risks. Fixes recognize plain-div Item headings as boundaries, prevent prose references from changing sections, remove recurring Docusign page headers, and retain the nearest real source anchor. Corrected output: 1,309 passages. Tables remain deliberately excluded. Some long or page-split paragraphs retain incomplete surrounding context; source inspection is necessary.

## Artifacts and reproduction

- `frozen.json`: question and corpus hashes.
- `selection.json`: selected method, rationale and pre-held-out implementation hashes.
- `dev-results.json`, `heldout-results.json`: every question, retrieval result, excerpt and outcome for every engine.
- `source-audit.json`: complete twenty-passage source comparison.
- `web-verification.json`: API and browser evidence.
- `../../VALIDATION.md`: commands and exit statuses.

From the project directory: `python3 -m filing_assistant.real_eval dev` and `python3 -m filing_assistant.real_eval heldout`. Repeating held-out evaluation reproduces a known result; it does not create a fresh test set. Do not regenerate questions or source index to improve a score.
