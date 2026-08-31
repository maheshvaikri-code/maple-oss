# MAPLE Agent Runtime Slice 125 QA Report

**Date:** 2026-08-27
**Scope:** bounded document connector and ingestion contract
**Implementation commit:** `0ea1084`

## Acceptance evidence

| Criterion | Evidence | Pass |
|---|---|---|
| Connector and sink are host-owned | `DocumentConnector.fetch(...)` supplies bounded cursor pages and `DocumentIngestor.add_document(...)` is the explicit sink; MAPLE selects no provider and makes no network call. | Yes |
| Pages and progress are bounded | Page size is capped at `100`; ingestion validates document, batch, and total-document quotas and returns bounded progress plus a resume cursor. | Yes |
| Documents are validated before sink mutation | Document/source validation, duplicate IDs, empty advancing pages, stalled cursors, and over-limit pages fail before the affected page is written. | Yes |
| Failures are typed and redacted | Connector and sink exceptions/errors return typed retrieval errors without provider exception text or secrets. | Yes |
| Existing behavior remains green | Focused retrieval suite: `18 passed in 0.07s`; full autonomy suite: `355 passed in 16.97s`; exact tracked manifest: `1317 passed, 1 skipped in 229.72s` across `108` tracked Python test files. | Yes |
| Public surface is exported and documented | Root/autonomy exports, README, API reference, parity ledger, changelog, ADR-071, and this QA/review evidence are updated. | Yes |

## Static and package evidence

- isort: changed import surfaces pass.
- Black: `4 files would be left unchanged` for the changed Python files.
- Ruff: `All checks passed!`.
- Changed-boundary mypy: `Success: no issues found in 1 source file`.
- Compile gate: passed for changed Python files.
- Diff check: passed; Git emitted only LF-to-CRLF normalization warnings for
  the modified plan file.
- Declared-project pip-audit: `No known vulnerabilities found`; no runtime
  dependency was added.
- Package build: `Successfully built maple_oss-1.1.3-py3-none-any.whl and
  maple_oss-1.1.3.tar.gz`; exit `0`.
- Twine: both wheel and sdist checks returned `PASSED`.
- Artifact shape: wheel `104` entries; sdist `568` entries.
- Isolated wheel smoke: `wheel no-dependency document connector export smoke
  passed`.

## Security disposition

- The changed surface introduces no secret literal, executable deserialization,
  shell invocation, or new dangerous construct. `gitleaks` and `bandit` are
  unavailable in this environment.
- The environment-wide pip-audit remains a release-governance veto:
  `384` known vulnerabilities across `77` installed packages. This must be
  dispositioned before publication.
- The connector is a bounded callback contract only. Durable cursors, managed
  stores, rate limits, retries, transactions, rollback, provider
  authentication, and sandboxing remain host-owned or separate capabilities.

## QA verdict

**Pass for Slice125 behavior and repository gates.** Publication remains
blocked by the environment-wide dependency-governance veto and still
requires the human-controlled release/publish decision. No publication,
deployment, cloud action, or website change was performed.
