# QA + Security Report — MAPLE Agent Runtime Slice 196 @ 69c5fb6

**QA Engineer:** QA gate · **Security Reviewer:** Security gate · **Date:** 2026-08-29  
**Build under test:** `69c5fb6` (`fix(llm): reject malformed fallback results`)

## Acceptance criteria verification

| # | Criterion | How executed | Evidence (real output) | Pass |
|---|---|---|---|---|
| 1 | Default router compatibility; deterministic opt-in initialization; at most eight providers | Focused LLM tests plus adversarial bound matrix | `31 passed in 5.62s`; `QA_FAILOVER_MATRIX=PASS` | Yes |
| 2 | Sync/async exact transient failover, raised-exception classification, and non-retryable fail-fast | Focused LLM tests and adversarial unknown-exception/cancellation checks | `tests\\llm\\test_capabilities.py ...............`; `tests\\llm\\test_provider.py ................`; `31 passed`; `QA_FAILOVER_MATRIX=PASS` | Yes |
| 3 | Unchanged successful response, wrapper usage, bounded sanitized exhaustion metadata | Focused success/usage/exhaustion tests and eight-provider exhaustion matrix | `31 passed`; `QA_FAILOVER_MATRIX=PASS` | Yes |
| 4 | Typed streaming rejection before provider construction | Focused router/wrapper streaming test | `31 passed`; streaming rejection assertion passed | Yes |
| 5 | Public exports, runnable API surface, tests, and no new dependency | Public import smoke, full suite, static checks, dependency manifest diff | `public API example: PASS`; `1775 passed, 1 skipped`; Black/isort/Ruff/mypy clean; no dependency manifest changed | Yes |

## Adversarial & edge matrix

| Input/scenario | Expected | Observed | Pass |
|---|---|---|---|
| Empty message list | Provider contract remains callable | Completion tests and matrix completed | Yes |
| One provider | No unnecessary child attempt | Focused wrapper tests passed | Yes |
| Eight providers | Bounded construction and one attempt per child | Exhaustion metadata listed eight providers; each child called once | Yes |
| Nine providers | Reject the configured bound | `ValueError` from direct wrapper construction; typed router limit error in focused tests | Yes |
| Unicode provider label | Metadata remains bounded and serializable | `attemptedProviders` preserved `東京` | Yes |
| Raised timeout | Classify as `LLM_TIMEOUT`, then advance | Backup succeeded; focused test passed | Yes |
| Raised unknown/non-transient exception | Fail fast; do not call backup | `LLM_COMPLETION_ERROR`; backup call count remained zero | Yes |
| Non-retryable typed result | Fail fast; do not call backup | `LLM_AUTHENTICATION_ERROR`; focused test passed | Yes |
| Malformed result and malformed successful payload | Typed invalid-result error; do not call backup | `LLM_PROVIDER_RESULT_INVALID`; focused regression tests passed | Yes |
| Invalid failover factory output | Fail closed as provider selection failure | `PROVIDER_SELECTION_FAILED`; focused regression test passed | Yes |
| Cancellation/interruption | Do not swallow cancellation | `QA_FAILOVER_MATRIX=PASS`; `asyncio.CancelledError` propagated | Yes |
| Native streaming | Reject rather than imply stream continuity | `PROVIDER_FAILOVER_STREAM_UNSUPPORTED` | Yes |
| Concurrent async calls | Per-call attempt state remains isolated | `QA_CONCURRENT_CALLS=PASS` | Yes |

The first ad-hoc matrix attempt contained an invalid assertion that expected
provider calls during lazy construction; it was corrected and rerun. No
product failure was involved.

## Regression

Focused command:

```text
============================= test session starts ==============================
collected 31 items
tests\\llm\\test_capabilities.py ...............                           [ 48%]
tests\\llm\\test_provider.py ................                              [100%]
============================== 31 passed in 5.62s ==============================
```

Final dirty-tree command: `python -m pytest -q`

```text
================= 1775 passed, 1 skipped in 348.08s (0:05:48) =================
EXIT_CODE=0
```

Static checks:

```text
All done! ✨ 🍰 ✨
2 files left unchanged.
All checks passed!
Success: no issues found in 3 source files
```

Flakes: none observed. The full suite log is retained at:
`C:\Users\mahes_h9w44qg\AppData\Local\Temp\maple-slice196-full-final-20260829-033415.log`.

## Bugs found

No new product bugs were found by QA. The code-review findings and regression
tests are recorded in [the Slice 196 review](../reviews/maple-agent-runtime-slice196.md).

## Security sweep (per `skills/security.md`)

- Secrets scan: scoped outgoing diff scan clean (`SECRET_DIFF_SCAN=clean`).
- Injection review: no SQL, shell, path, template, deserialization, or network
  construction was added; provider labels, exception names, retry types, and
  attempted-provider metadata are bounded and sanitized.
- Dependency audit: `python -m pip_audit --progress-spinner off --strict .`
  returned `No known vulnerabilities found`.
- Dangerous constructs: scoped source scan clean
  (`DANGEROUS_CONSTRUCT_SCAN=clean`). `gitleaks` and `bandit` are unavailable in
  this environment; their absence is disclosed, not treated as a clean tool
  result.
- Bounds/fail-closed: maximum eight children, one attempt per child, exact
  retryable types, typed malformed-result errors, cancellation propagation,
  and explicit streaming rejection were executed above.

**Security verdict:** SIGN-OFF for the scoped Slice 196 change. The overall
repository release remains CONDITIONAL / NOT PUBLISH-READY because the
standing shared-environment audit/tooling gate and the separately gated hosted
identity, distributed scheduling/liveness, and side-effect contracts remain
open. Human override: n/a.

**QA verdict:** pass for the scoped local contract.
