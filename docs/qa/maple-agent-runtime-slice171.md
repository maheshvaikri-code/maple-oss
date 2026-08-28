# QA + Security Report - bounded remote agent invocation idempotency

**QA Engineer** / **Security Reviewer** / **Date:** 2026-08-28
**Code candidate:** `1c19544` plus public-contract documentation closure
**Design baseline:** [ADR-116](../adr/116-bounded-agent-invocation-idempotency.md)

## Acceptance criteria verification

| # | Criterion | Evidence | Pass |
|---|---|---|---|
| 1 | Optional bounded key with absent-key compatibility | `normalize_agent_idempotency_key` validates the 256-byte key boundary; raw client methods emit the field only when supplied; unkeyed server calls retain the legacy registry path | Yes |
| 2 | Concurrent in-memory duplicate suppression and replay | `tests/autonomy/test_invocations.py` covers one pending claim, in-progress conflict, completed detached replay, and handler suppression; transport regressions pass | Yes |
| 3 | Target/request conflict immutability | Canonical SHA-256 fingerprinting binds target, task, context, session, and run fields; same-key conflict tests verify no handler call and no completed-record mutation | Yes |
| 4 | Atomic file restart state and bounded persistence | File-store tests cover restart replay, malformed/oversized state, expiry/capacity, fencing, atomic writes, and absence of raw task/context in serialized state | Yes |
| 5 | Fail-closed invalid/configuration/storage behavior | Typed errors cover missing store, invalid key/digest/response, claim races, clock, lease, load/save, capacity, and response-size failures; keyed requests claim before handlers | Yes |
| 6 | Raw/typed and capability-route compatibility | Named and capability-routed raw/typed client regressions pass; selected capability identity is retained; existing named-agent tests remain green | Yes |
| 7 | Public contract and validation gates | API reference, README, parity ledger, changelog, review, QA, and release-plan artifacts are filed; final package gate is recorded below after the closure commit | Pending final archive gate |

## Regression evidence

```text
python -m pytest tests/autonomy/test_invocations.py tests/autonomy/test_invocation_transport.py -q --no-cov
21 passed in 4.46s

python -m pytest -q --no-cov
1670 passed, 1 skipped in 259.19s
```

The full run collected 1,671 tests. The single skip is pre-existing
test-environment coverage; no test was deleted, skipped, weakened, or retried
to obtain this result.

## Static and security gates

```text
black_exit=0
isort_exit=0
ruff_exit=0
mypy_exit=0
compile_exit=0
slice171_secret_scan=passed
slice171_danger_scan=passed
```

The exact command output is recorded in the code-review artifact. `gitleaks`
and Bandit are unavailable in this environment. No runtime dependency was
added. The established environment-wide `python -m pip_audit --local` result
of `384 known vulnerabilities in 77 packages` remains a separate,
pre-existing release-governance veto; the declared MAPLE project dependency
set was not changed by this slice.

## Package gate

Pending the final closure commit so that the clean archive includes the
completed QA and release artifacts. No publication or upload is authorized by
this report.

## Security verdict

Pass for Slice-171-specific behavior under the bounded local contract. The
feature is authenticated, scope-checked, finite, canonicalized, detached, and
fail-closed. It does not claim distributed coordination, caller/tenant
identity binding, automatic retry, failover, resume/cancel idempotency, or
exactly-once external effects.
