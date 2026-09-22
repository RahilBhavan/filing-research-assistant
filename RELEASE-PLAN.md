# Completion and release plan

Started September 22, 2026.

## 1. Correctness

- Reject exact quantity questions when evidence has no quantity or discloses only an approximate basis.
- Normalize common SEC question variants such as activities/activity, currencies/currency, strengthening/strengthened, and alternative/alternate.
- Remove instruction words that should not be required in evidence, such as "section," "reason," and "rate."
- Recover the six answerable held-out cases identified in the first audit without weakening the unsupported-question checks.
- Add regression tests for every observed failure and for boundary cases involving dates, quantities, causes, scope, and comparisons.

## 2. Evaluation

- Preserve the original frozen development and held-out results as version 1 evidence.
- Create a version 2 regression report that clearly states the original held-out set is now a known test set.
- Add a reviewer worksheet and annotation guide so an independent person can score citation support and answerability without seeing system output first.
- Do not claim independent semantic accuracy until that worksheet is completed by someone other than the implementer.

## 3. Release engineering

- Add Python package metadata, supported Python versions, console entry point, license, and contributor guidance.
- Add continuous integration for unit tests, syntax checks, package building, and security-sensitive API tests.
- Add a scheduled/manual SEC refresh workflow that uses a repository secret for the SEC contact identity and publishes a reviewable corpus artifact.
- Add structured operational logging that excludes questions and filing text.
- Add repeatable load, accessibility, and responsive-layout checks.

## 4. GitHub publication

- Initialize a Git repository, review the complete diff, and commit a reproducible release candidate.
- Create a private GitHub repository by default to avoid unexpectedly publishing the bundled filing captures.
- Push the default branch and report the repository URL and any remaining human release gate.

## Completion criteria

- All automated checks pass from a clean checkout.
- Version 2 regression results contain no unsupported answers for the known suite and document false abstentions separately.
- The local interface answers, compares, cites, and abstains correctly in browser checks.
- The GitHub repository contains no credentials, local environment files, or user questions.
- Independent human review remains explicitly pending until another person completes it.
