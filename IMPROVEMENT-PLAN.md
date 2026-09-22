# Improvement plan

Started September 21, 2026. Implement all five requested improvements while preserving the original fixture corpus and its regression tests.

1. Capture four real SEC filings for two companies, with original filing URLs, metadata, capture timestamps and hashes. Audit at least 20 passages against source content. Fix demonstrated parsing errors before changing retrieval.
2. Author 60 questions from source evidence before implementing new retrieval rules. Include 40 answerable and 20 unsupported or misleading questions. Freeze a 30-question development split and a 30-question held-out split. Keep paired paraphrases and evidence families in one split to reduce leakage. Labels are agent-authored; this does not constitute independent human review.
3. Add evidence checks for requested amounts, dates, causes and comparisons. Measure incorrect answers and false abstention separately. Preserve the original engine as an executable baseline.
4. Compare BM25, a local latent-semantic retrieval model, and a hybrid. Fit semantic representations only to source passages, never question labels. Select settings using development results, freeze the implementation, then run the held-out split without further tuning. Keep every failed question in the report.
5. Add a localhost-only interface with company and filing selectors, side-by-side comparisons, highlighted passage text, original filing links and explicit abstention reasons. Verify real browser interactions and source inspection.

The default app must continue to run without a paid API. A corpus-fitted latent semantic model is an experiment, not a pretrained language model. NumPy from the existing bundled runtime may be used only to build its static model artifact; querying uses the standard library. No new production dependency is needed.

Acceptance evidence: reproducible commands, source audit, frozen data hashes, baseline/development/held-out raw counts, adversarial regression tests, browser checks, and a short failure-to-fix narrative. Human semantic-support scores remain unmeasured unless a human supplies actual annotations.

Status: all five implementation stages completed; measured limitations are recorded below.

## Completed September 21, 2026

- [x] Four real SEC filings captured, hashed and indexed; 20 original-source passage/anchor checks passed. Fixed section bleed and source-anchor loss.
- [x] 60 questions frozen before new retrieval: 40 answerable, 20 unsupported; family-separated 30/30 splits.
- [x] Quantity, date, cause and paired-comparison evidence gates implemented and tested. Heuristic limitations remain; see held-out failure r51.
- [x] Post-fix v2 regression removes the known unsupported employee-count answer and the six false-abstention cases; 18/20 gold-complete, 10/10 unsupported abstentions, 0/20 false abstentions.
- [x] Original engine, BM25, LSA and hybrid measured. BM25 selected on development results; implementation frozen before held-out evaluation.
- [x] Local interface delivered and verified: scoped questions, highlighted original-source context, provenance, side-by-side comparisons and abstention.
- [x] Packaging, CI, SEC refresh workflow, local load smoke test, security guidance, accessibility checks, and independent-review worksheet added.

Verification: 67 unit/regression tests passed; localhost API checks and browser interactions passed; package wheel and CI/refresh artifacts are present. See `VALIDATION.md` and `evaluation/real/REPORT.md`. The measured outcome is an implemented research prototype with documented errors, not a claim of production-grade financial answer accuracy. No independent human semantic-support score is claimed until the worksheet in `evaluation/HUMAN-REVIEW.md` is completed by another person.
