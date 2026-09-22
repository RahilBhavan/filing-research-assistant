# Evaluation results

SYNTHETIC LEARNING FIXTURES. Fictional companies and invented disclosures. Not SEC filings or investment evidence.

Frozen 30-question, agent-authored development set created before the first evaluation run. Gold labels are not independent human judgments. Do not edit inputs to improve reported scores; version a new dataset instead.

This is an agent-authored development set. No human or independent reviewer has verified semantic citation support. Literal quote equality and gold passage alignment are distinct mechanical checks.

| Metric | Raw count | Percent |
| --- | --- | --- |
| retrieval_hit_at_5 | 25/26 | 96.15% |
| all_gold_evidence_at_5 | 25/26 | 96.15% |
| gold_complete_extractive_answer | 24/26 | 92.31% |
| correct_abstention | 4/4 | 100.0% |
| false_abstention | 2/26 | 7.69% |
| exact_quote_integrity | 28/28 | 100.0% |
| agent_gold_passage_alignment | 28/28 | 100.0% |
| wrong_scope_questions | 0/30 | 0.0% |
| complete_comparison_answers | 4/4 | 100.0% |

Median warm query latency: 0.093 ms. Excludes parsing and disk I/O; one measured query per question.

Human-verified citation support: **not measured**. The original 90% semantic-support target remains unverified.

## Per-question outcomes

| ID | Category | Status | All gold retrieved | Complete gold cited | Reason |
| --- | --- | --- | --- | --- | --- |
| q01 | direct | answered | True | True | extractive_evidence |
| q02 | direct | answered | True | True | extractive_evidence |
| q03 | direct | answered | True | True | extractive_evidence |
| q04 | direct | answered | True | True | extractive_evidence |
| q05 | direct | answered | True | True | extractive_evidence |
| q06 | direct | answered | True | True | extractive_evidence |
| q07 | direct | answered | True | True | extractive_evidence |
| q08 | direct | answered | True | True | extractive_evidence |
| q09 | direct | answered | True | True | extractive_evidence |
| q10 | direct | answered | True | True | extractive_evidence |
| q11 | direct | answered | True | True | extractive_evidence |
| q12 | direct | answered | True | True | extractive_evidence |
| q13 | paraphrase | answered | True | True | extractive_evidence |
| q14 | paraphrase | answered | True | True | extractive_evidence |
| q15 | paraphrase | answered | True | True | extractive_evidence |
| q16 | paraphrase | answered | True | True | extractive_evidence |
| q17 | paraphrase | abstained | True | False | insufficient_lexical_evidence |
| q18 | paraphrase | abstained | False | False | insufficient_lexical_evidence |
| q19 | period | answered | True | True | extractive_evidence |
| q20 | period | answered | True | True | extractive_evidence |
| q21 | period | answered | True | True | extractive_evidence |
| q22 | period | answered | True | True | extractive_evidence |
| q23 | comparison | answered | True | True | paired_extracts_not_a_calculated_change |
| q24 | comparison | answered | True | True | paired_extracts_not_a_calculated_change |
| q25 | comparison | answered | True | True | paired_extracts_not_a_calculated_change |
| q26 | comparison | answered | True | True | paired_extracts_not_a_calculated_change |
| q27 | unsupported | abstained | N/A | N/A | insufficient_lexical_evidence |
| q28 | unsupported | abstained | N/A | N/A | question_period_conflicts_with_scope |
| q29 | unsupported | abstained | N/A | N/A | question_company_conflicts_with_scope |
| q30 | unsupported | abstained | N/A | N/A | question_form_conflicts_with_scope |

## Failures and limits

- q17: What exposure arises from depending on one cast housing vendor? Expected passages: hbrm-k-supplier. Retrieved: hbrm-k-supplier, hbrm-k-cash. Outcome: insufficient_lexical_evidence. Inspect the raw result before changing retrieval.
- q18: Which buyers and sales channels does the pump business serve? Expected passages: hbrm-k-business. Retrieved: hbrm-k-concentration, hbrm-k-revenue, hbrm-k-contracts, hbrm-k-warranty, hbrm-k-demand. Outcome: insufficient_lexical_evidence. Inspect the raw result before changing retrieval.

Further limits: synthetic narrative data, no table answers, no learned embeddings, only explicit scope checks, and heuristic lexical abstention. An exact quote can still be irrelevant to a question. Comparison output juxtaposes passages and does not establish causal or numerical change. See VALIDATION.md for adversarial cases and verification commands.
