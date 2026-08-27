# MAPLE Agent Runtime Slice 127 QA Report

**Date:** 2026-08-27
**Scope:** authenticated bounded remote approval control transport
**Implementation commit:** `3b0121c`

## Acceptance evidence

| Criterion | Evidence | Pass |
|---|---|---|
| Remote approval control is authenticated | Configuring `RunServer(approval_store=...)` requires a bearer token; unauthorized `RunClient` calls return `UNAUTHORIZED`. | Yes |
| Transport operations are bounded | `RunServer` and `RunClient` expose bounded pending-list, inspection, and decision routes with existing path/body/response limits and an approval list cap of `100`. | Yes |
| Store authority and decision semantics are preserved | The server delegates list/get/decide to the configured `ApprovalStore`; optional edited arguments are validated before mutation, and store conflicts remain typed. | Yes |
| Remote control cannot consume or execute tools | Slice 127 adds no remote consume/execute route. The local agent remains responsible for consumption, handler invocation, terminal-outcome replay, and side-effect uncertainty. | Yes |
| Existing behavior remains green | Focused server suite: `26 passed in 11.38s`; full autonomy suite: `362 passed in 14.29s`; exact tracked manifest: `1324 passed, 1 skipped in 253.70s` across `108` tracked Python test files. | Yes |
| Public contract is documented | ADR-073, API reference, README, parity ledger, changelog, and this QA/review evidence describe the authenticated control-plane boundary and its non-claims. | Yes |

## Static and security evidence

- isort: changed imports pass.
- Black: `2 files would be left unchanged`.
- Ruff: `All checks passed!`.
- Changed-boundary mypy: `Success: no issues found in 1 source file` with
  `--follow-imports=skip`.
- Compile gate: `python -m compileall -q maple` passed.
- Diff check: passed for the implementation/public-doc changes.
- Narrow changed-surface secret scan: no matches.
- No runtime dependency was added. The declared-project dependency audit and
  clean package evidence are recorded in the Slice 127 closure below.

## QA verdict

**Behavioral pass for Slice 127.** The package gate is completed in the final
release closure after the QA and review records are included in the tracked
archive. Publication, deployment, cloud action, and website changes were not
performed.
