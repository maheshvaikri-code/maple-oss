# Code Review - opt-in remote handoff invocation idempotency

**Role:** Code Reviewer
**Date:** 2026-08-28
**Implementation:** `RemoteHandoffTarget` plus adapter regressions
**Design baseline:** [ADR-117](../adr/117-remote-handoff-idempotency-binding.md)

## Findings

No critical or high-severity findings were identified in the Slice 172
implementation. The new behavior is explicitly disabled by default, so
existing adapter callers—including clients whose `run_agent` implementation
does not accept an idempotency keyword—retain their prior invocation shape.

When enabled, the adapter requires the caller-owned bounded `handoff_id`
before making an HTTP call and passes it as both `run_id` and
`idempotency_key`. The existing Slice 171 receiver performs canonical request
fingerprinting, claim-before-handler execution, detached replay, and typed
conflict handling. The async methods use the same synchronous path, so the
binding cannot drift between sync and async behavior.

The adapter continues to sanitize remote failures, check cancellation before
and after the request, and avoid retrying or waiting for in-flight work. The
feature does not broaden authentication, authorization, persistence, or
exactly-once claims.

## Verification

```text
python -m pytest tests/autonomy/test_remote_handoff_idempotency.py tests/autonomy/test_server.py -q --no-cov
54 passed in 21.77s

python -m black --check maple/autonomy/server.py tests/autonomy/test_remote_handoff_idempotency.py
2 files would be left unchanged.

python -m isort --check-only maple/autonomy/server.py tests/autonomy/test_remote_handoff_idempotency.py
isort_exit=0

python -m ruff check maple/autonomy/server.py tests/autonomy/test_remote_handoff_idempotency.py
All checks passed!

python -m mypy --follow-imports=skip maple/autonomy/server.py
Success: no issues found in 1 source file

python -m compileall -q maple/autonomy/server.py tests/autonomy/test_remote_handoff_idempotency.py
compile_exit=0

slice172_secret_scan=passed
slice172_danger_scan=passed
```

An independent fresh-session verifier was not available in this execution
environment; that required governance step remains open and is not claimed by
this review. `gitleaks` and Bandit are unavailable here. No dependency was
added.

## Disposition

Acceptable for the explicitly opt-in, local/host-owned retry-suppression
contract. Publication, deployment, cloud action, registry write, and website
update remain outside this review.
