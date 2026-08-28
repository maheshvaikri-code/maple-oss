# Code Review - bounded remote agent invocation idempotency

**Role:** Code Reviewer
**Date:** 2026-08-28
**Commits reviewed:** `d824940`, `1c19544`
**Design baseline:** [ADR-116](../adr/116-bounded-agent-invocation-idempotency.md)

## Review scope

- Bounded memory and file-backed claim/complete/abort stores.
- Canonical target/request fingerprinting and detached response replay.
- Authenticated named-agent and capability-routed HTTP integration.
- Raw/typed client compatibility and public package exports.
- Resource bounds, malformed-state handling, fencing, and fail-closed errors.

## Findings

No critical or high-severity findings were identified in the reviewed diff.

The implementation keeps the important ordering explicit: authentication and
input validation precede the claim, the claim precedes handler execution, and
completion follows the existing normalized response boundary. A reused key is
bound to both a target and a canonical SHA-256 digest, so a key cannot replay a
response for different request content. Responses are copied through bounded
JSON validation before memory or file retention.

The file store uses a local durable lease and atomic replacement. It persists
only target/key/digest/expiry/response fields, rejects malformed or oversized
state, and does not retain raw task or context. The server preserves the
legacy registry call path when the optional key is absent. The authenticated
route and existing `agent:invoke` scope remain the transport boundary.

Accepted limitations are intentional and documented: local host ownership,
TTL/eviction, crash windows, no automatic waiting/retry, no distributed
coordination, and no exactly-once external-effect guarantee. Resume/cancel
routes are not made idempotent by this slice.

## Verification

```text
python -m pytest tests/autonomy/test_invocations.py tests/autonomy/test_invocation_transport.py -q --no-cov
21 passed in 4.46s

python -m pytest -q --no-cov
1670 passed, 1 skipped in 259.19s

python -m black --check maple/autonomy/invocations.py maple/autonomy/server.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_invocations.py tests/autonomy/test_invocation_transport.py
All done! ✨ U0001f370 ✨
6 files would be left unchanged.

python -m isort --check-only maple/autonomy/invocations.py maple/autonomy/server.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_invocations.py tests/autonomy/test_invocation_transport.py
isort_exit=0

python -m ruff check maple/autonomy/invocations.py maple/autonomy/server.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_invocations.py tests/autonomy/test_invocation_transport.py
All checks passed!

python -m mypy --follow-imports=skip maple/autonomy/invocations.py maple/autonomy/server.py maple/autonomy/__init__.py maple/__init__.py
Success: no issues found in 4 source files

python -m compileall -q maple/autonomy/invocations.py maple/autonomy/server.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_invocations.py tests/autonomy/test_invocation_transport.py
compile_exit=0

slice171_secret_scan=passed
slice171_danger_scan=passed
```

An independent fresh-session verifier was not available in this execution
environment; the required independent review remains a release-governance
follow-up. This document is the author's bounded code-review record, not a
claim that the fresh-session verifier ran. `gitleaks` and Bandit are also
unavailable here. No dependency was added.

## Disposition

The implementation is acceptable for the bounded local/host-owned contract.
Publication, deployment, cloud action, registry write, and website update
remain outside this review.
