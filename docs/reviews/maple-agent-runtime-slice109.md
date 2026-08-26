# Code Review - durable parallel-branch retries @ d388b51

**Code Reviewer** - **Date:** 2026-08-26  
**Scope:** `WorkflowCheckpoint`, `WorkflowRun`, `Workflow._execute`, parallel
branch waves, workflow regressions, ADR/API/README/parity documentation

## Review checklist

| Area | Review result | Evidence |
|---|---|---|
| Checkpoint schema | Pass | New branch retry maps are JSON-safe, identifier/count/timestamp validated, backward-compatible when absent, and copied into public run views |
| Retry bounds | Pass | Existing `RetryPolicy` caps retries and delay; branch scheduling uses the same policy and cannot retry after exhaustion |
| Wave execution | Pass | Only pending branches enter the next bounded `ThreadPoolExecutor` wave; successful branch outputs are retained for deterministic declaration-order merge |
| Retry context | Pass | Each branch receives its persisted retry count through `WorkflowContext.retry_count` |
| Persistence/CAS | Pass | Every schedule uses `expected_version`; terminal failure and pause paths reload the latest checkpoint after intermediate branch saves |
| Error handling | Pass | Invalid branch results remain typed; policy exhaustion is `NODE_RETRY_EXHAUSTED`; existing no-policy errors remain unchanged |
| Pause/recovery | Pass | Branch retry metadata survives interruption/recovery, due times are honored before pending waves, and group boundary clearing remains atomic |
| Side-effect boundary | Pass | Documentation explicitly retains at-least-once semantics and avoids exactly-once or distributed scheduler claims |
| Test coverage | Pass | Flaky retry, persisted schedule/due time, typed exhaustion, existing fan-out, pause/resume, replay, and full tracked regression are covered |
| Scope/dependencies | Pass | One runtime module, one regression module, docs, and ADR; no new dependency or remote surface |

## Findings and disposition

The focused regression initially exposed a stale checkpoint-version path when a
branch exhausted its policy after an earlier schedule save. The implementation
now reloads the latest durable checkpoint before terminal failure or interruption
commit, and the exhaustion regression protects that behavior. No open
implementation finding remains for this slice.

## Gate summary

- Focused workflow/replay regression: `24 passed in 0.32s`.
- Tracked application regression: `1267 passed, 1 skipped in 256.93s`.
- Black, Ruff, changed-boundary mypy, compileall, diff, and network-free doctor
  pass.
- Dependency governance remains a separate release veto because the host
  environment reports `383` known vulnerabilities in `77` packages via
  `pip-audit`; `gitleaks` is unavailable.
- Clean archive package candidate `afa57d0`: build and both Twine checks pass,
  sdist contains `513` entries, required public files are `5/5`, Slice 109 ADR
  and QA/review files are present, and the workspace-only audit is `0`.

**Review verdict:** pass for the Slice 109 implementation and package boundary;
dependency governance remains open and no publication was performed.
