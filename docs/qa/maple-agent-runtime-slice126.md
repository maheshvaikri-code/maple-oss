# MAPLE Agent Runtime Slice 126 QA Report

**Date:** 2026-08-27
**Scope:** bounded durable approval-outcome replay
**Implementation commit:** `8ea5b6d`

## Acceptance evidence

| Criterion | Evidence | Pass |
|---|---|---|
| Built-in stores persist a bounded terminal outcome | In-memory and file approval stores validate a JSON-safe `{content, is_error}` result, cap content at `131,072` UTF-8 bytes, write atomically, and preserve the first recorded value idempotently. | Yes |
| Repeated execution does not invoke the handler again | Direct approved-tool execution replays a stored result for consumed approvals; sync and async durable resume replay the stored result after a checkpoint-save crash. Regression tests assert the handler is called once. | Yes |
| Crash windows fail closed | A consumed request without a recorded result returns `APPROVAL_OUTCOME_UNAVAILABLE` with `effect_uncertain: true`; recording failures return `APPROVAL_OUTCOME_SAVE_ERROR` with the same uncertainty and do not retry the handler. | Yes |
| Custom-store compatibility is bounded | Stores without the optional `record_execution` capability retain their prior single-use behavior; the built-in stores implement the durable recorder. | Yes |
| Existing behavior remains green | Focused approval/run/agent suite: `66 passed in 0.43s`; full autonomy suite: `359 passed in 15.24s`; exact tracked manifest: `1321 passed, 1 skipped in 231.38s` across `108` tracked Python test files. | Yes |
| Public contract is documented | ADR-072, API reference, README, parity ledger, changelog, and this QA/review evidence describe the bounded replay contract and at-least-once side-effect limitation. | Yes |

## Static and security evidence

- isort: changed imports pass.
- Black: `5 files would be left unchanged`.
- Ruff: `All checks passed!`.
- Changed-boundary mypy: `Success: no issues found in 2 source files` with
  `--follow-imports=skip`.
- Compile gate: `python -m compileall -q maple` passed.
- Diff check: passed; Git emitted only LF-to-CRLF normalization warnings for
  modified files.
- Declared-project pip-audit: `No known vulnerabilities found`; no runtime
  dependency was added.
- Narrow changed-surface secret scan: no matches.
- The environment-wide pip-audit remains a release-governance veto at the
  previously observed `384` known vulnerabilities across `77` installed
  packages.

## Package evidence

- `git archive HEAD` clean checkout plus `python -m build --wheel --sdist`:
  `Successfully built maple_oss-1.1.3-py3-none-any.whl and
  maple_oss-1.1.3.tar.gz`; exit `0`.
- Twine checks: wheel and sdist both `PASSED`; exit `0`.
- Artifact shape: wheel `104` entries and clean sdist `564` entries; the
  clean sdist contains zero workspace-only Doctrine files.
- Isolated wheel smoke: `clean archive no-dependency approval replay export
  smoke passed`; exit `0`.

## QA verdict

**Pass for Slice 126 behavior and repository gates.** The implementation is
provider-neutral and does not claim distributed transactions, exactly-once
effects, automatic retries, or durable external-effect reconciliation.
Publication, deployment, cloud action, and website changes were not performed.
