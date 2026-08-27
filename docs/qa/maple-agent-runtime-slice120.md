# QA + Security Report - MAPLE Agent Runtime Slice 120 @ 9d1d7aa

**QA Engineer / Security Reviewer · Date:** 2026-08-27  
**Build under test:** `9d1d7aa` (bounded authenticated durable agent-run transport)

## Acceptance criteria verification

| # | Criterion | Evidence (real output) | Pass |
|---|---|---|---|
| 1 | A host can expose an existing durable agent-run store for remote inspection. | Focused server suite: `18 passed in 10.19s`; inspection returns a checkpoint summary and rejects cross-agent access. | Yes |
| 2 | Remote resume requires an explicit host-owned callback. | `AgentRegistry.register(..., resume_handler=...)` and `RunClient.resume_agent_run(...)` are covered; a missing callback returns typed `AGENT_RESUME_UNAVAILABLE`. | Yes |
| 3 | Inspection avoids transcript leakage. | The response includes bounded identity/status/counters/pending IDs/session/usage/result/error/version/timestamps and omits `messages` and `reasoning_steps`. | Yes |
| 4 | Authentication and failure paths fail closed. | Configured agent registry/store require a bearer token; unauthorized calls return `UNAUTHORIZED`; missing stores return `503`; missing/cross-agent runs return `404`; callback failures are redacted. | Yes |
| 5 | Existing application behavior remains green. | Full autonomy suite: `342 passed in 14.06s`. Exact tracked manifest: `1304 passed, 1 skipped in 224.03s (0:03:44)` across `108` tracked test files. | Yes |
| 6 | Public/runtime surfaces are documented and statically valid. | Black: `4 files would be left unchanged`; Ruff: `All checks passed!`; changed-boundary mypy: `Success: no issues found in 3 source files`; doctor reports all eight checks true, `ready: true`, `network: false`; compile and diff checks pass. | Yes |
| 7 | The exact feature commit produces a clean package candidate. | Clean archive `9d1d7aa`: build exit `0`; Twine wheel/sdist exit `0`; sdist `505` members; wheel `104` members; required public files `6/6`; no-dependency smoke printed `durable agent transport exports ok`. | Yes |

## Contract and adversarial matrix

| Scenario | Expected | Observed | Pass |
|---|---|---|---|
| Durable run store attached without a bearer token | Refuse construction | `ValueError: auth_token is required when agent_run_store is configured` | Yes |
| Missing or wrong bearer token | Do not inspect or resume | Typed `UNAUTHORIZED` | Yes |
| Missing run store | Fail closed | `AGENT_RUN_STORE_UNAVAILABLE`, HTTP `503` | Yes |
| Missing or cross-agent run | Avoid disclosure | `AGENT_RUN_NOT_FOUND`, HTTP `404` | Yes |
| Persisted transcript and reasoning trace | Keep off-wire | Response omits `messages` and `reasoning_steps` | Yes |
| No resume callback | Do not reinvoke the original handler | `AGENT_RESUME_UNAVAILABLE`, HTTP `501` | Yes |
| Explicit resume callback | Invoke exactly the host callback | Callback receives the validated `run_id`; result is identity-bound and normalized | Yes |
| Malformed callback result | Reject result | Existing `AGENT_RESULT_INVALID` boundary is shared with new invocation | Yes |
| Store-owned durable state | Preserve authority | Transport calls `AgentRunStore.load`; it does not bypass checkpoint validation or fencing | Yes |

## Regression evidence

```text
18 passed in 10.19s
342 passed in 14.06s
tracked_test_files=108
1304 passed, 1 skipped in 224.03s (0:03:44)
```

One earlier full-autonomy attempt showed a transient Windows socket abort in an
existing oversized-body test and a transport-level race in the new unsupported
resume assertion; both passed in isolation, and the clean rerun above passed.
The final tracked manifest completed without either failure. No test was
weakened or removed.

## Security sweep

- Manual credential-pattern scan on the changed source/test/ADR surface:
  `secret_scan=no matches`.
- Dangerous-construct scan for `eval(`, `exec(`, `pickle`, `subprocess`,
  `os.system`, `shell=True`, and `yaml.load(`):
  `dangerous_construct_scan=no matches`.
- No new runtime dependency was added; the implementation reuses the existing
  `AgentRunStore` and standard-library HTTP transport.
- The transport does not expose persisted messages or reasoning steps, and a
  checkpoint for another agent is intentionally indistinguishable from a
  missing run at the route boundary.
- Declared-project audit: `python -m pip_audit --progress-spinner off --format
  json .` returned `No known vulnerabilities found` with exit `0` across `13`
  resolved runtime packages.
- `gitleaks` and `bandit` are unavailable in the environment.
- Separate environment-wide audit remains a governance veto: the recorded
  prior `pip_audit` run found `383` known vulnerabilities in `77` packages.
  This is not silently represented as a clean project-runtime result.

**Security verdict:** pass for the changed declared runtime surface; **VETO**
for final repository publication until the environment-wide dependency
findings are dispositioned under release policy.

**QA verdict:** pass for Slice 120 behavior, bounds, authentication, redacted
inspection, explicit resume ownership, static checks, regression coverage, and
clean package evidence. Scheduling, cancellation, retries, principal scopes,
remote event aggregation, and exactly-once effects remain outside the contract.
