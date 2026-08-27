# MAPLE Agent Runtime Slice 123 QA Report

**Date:** 2026-08-27
**Scope:** authenticated host-owned cooperative cancellation for remote agent
runs
**Commit:** `8ec56bb`

## Acceptance evidence

| Criterion | Evidence | Pass |
|---|---|---|
| Host callback is explicit and bounded | `AgentRegistry.register(..., cancel_handler=...)` validates the callback; `AgentRegistry.cancel(...)` validates agent/run IDs and normalizes the result. | Yes |
| Cancellation result is unambiguous | A cancel callback must return a JSON-safe `AgentRun` with status `cancelled`; other statuses fail closed. | Yes |
| HTTP transport is authenticated | `POST /v1/agents/<agent_id>/runs/<run_id>/cancel` uses the existing bearer-auth boundary and remains loopback-only by default. | Yes |
| Failure behavior is typed and redacted | Missing callback returns `AGENT_CANCEL_UNAVAILABLE`/`501`; callback exceptions return `AGENT_CANCEL_HANDLER_ERROR` without exception text; malformed status returns `AGENT_CANCEL_RESULT_INVALID`. | Yes |
| Existing behavior remains green | Focused server suite: `23 passed in 9.94s`; full autonomy suite: `347 passed in 16.99s`; exact tracked manifest: `1309 passed, 1 skipped in 236.70s` across `108` tracked Python test files. | Yes |
| Public surface is exported and documented | Root/autonomy exports, README, API reference, parity ledger, changelog, ADR-069, and this QA/review evidence are updated. | Yes |

## Static and package evidence

- Black: `2 files would be left unchanged` for the changed Python files.
- isort: changed import surfaces pass after formatting.
- Ruff: `All checks passed!`.
- Changed-boundary mypy: `Success: no issues found in 1 source file` with
  `--follow-imports skip`.
- Compile gate: passed for changed Python files.
- Diff check: passed; Git emitted only existing LF-to-CRLF normalization
  warnings for modified text files.
- Package build: `python -m build --wheel --sdist` exited `0`.
- Twine: both wheel and sdist checks returned `PASSED`.
- Artifact shape: sdist `560` entries; wheel `104` entries.
- Declared-project pip-audit: `No known vulnerabilities found` across `13`
  declared runtime dependencies.

## Security disposition

- The changed surface introduces no secret literal, executable deserialization,
  shell invocation, or new dangerous construct. `gitleaks` and `bandit` are
  unavailable in this environment.
- The environment-wide pip-audit is not a project-runtime result and remains a
  release veto: `384` known vulnerabilities across `77` installed packages.
  This must be dispositioned before publication.
- The cancellation endpoint is cooperative. It does not force-kill threads,
  guarantee checkpoint mutation, or claim exactly-once external effects.

## QA verdict

**Pass for Slice123 behavior and repository gates.** **Publication remains
blocked** by the environment-wide dependency-governance veto and still
requires the human-controlled release/publish decision. No publication,
deployment, cloud action, or website change was performed.
