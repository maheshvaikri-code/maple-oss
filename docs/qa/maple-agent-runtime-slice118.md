# QA + Security Report - MAPLE Agent Runtime Slice 118 @ a6e3575

**QA Engineer / Security Reviewer · Date:** 2026-08-27  
**Build under test:** `a6e3575` (bounded authenticated agent-run transport)

## Acceptance criteria verification

| # | Criterion | Evidence (real output) | Pass |
|---|---|---|---|
| 1 | A host can register a named agent handler and invoke it through the public HTTP client/server contract. | Focused server suite: `14 passed in 5.68s`; authenticated round-trip and public exports covered. | Yes |
| 2 | Task, identifiers, and context are bounded before handler execution. | Focused tests cover invalid task/context and the implementation enforces task, identifier, item, depth, string, and serialized-byte limits. | Yes |
| 3 | Authentication and failure boundaries are fail-closed. | Agent registry configuration without `auth_token` raises `ValueError`; unauthorized invocation returns typed `UNAUTHORIZED`; unknown agents return `AGENT_NOT_FOUND`; handler exceptions return generic `AGENT_HANDLER_ERROR`. | Yes |
| 4 | Handler results are typed, identity-bound, and JSON-safe. | Tests reject wrong agent identity, non-JSON results, and malformed handler errors with `AGENT_RESULT_INVALID`; valid envelopes preserve agent/run correlation. | Yes |
| 5 | Existing application behavior remains green. | Full autonomy suite: `338 passed in 7.52s`. Exact tracked manifest: `1300 passed, 1 skipped in 212.14s (0:03:32)` across `108` tracked test files. | Yes |
| 6 | Public/runtime surfaces are documented and statically valid. | Black: `97 files would be left unchanged`; Ruff: `All checks passed!`; changed-boundary mypy: `Success: no issues found in 3 source files`; doctor: `ready: true`, all eight checks true, `network: false`; compile and diff checks exit `0`. | Yes |
| 7 | The exact feature commit produces a clean package candidate. | `python -m build --wheel --sdist`: exit `0`; Twine wheel/sdist: both `PASSED`; sdist `538` members; wheel `104` members; required public files `6/6`; fresh `--no-deps` install printed `agent transport exports ok`. | Yes |

## Contract and adversarial matrix

| Scenario | Expected | Observed | Pass |
|---|---|---|---|
| Agent registry attached without a bearer token | Refuse construction | `ValueError: auth_token is required when agent_registry is configured` | Yes |
| Missing or wrong bearer token | Do not invoke handler | Typed `UNAUTHORIZED`; handler call list remains unchanged in the authenticated round-trip test | Yes |
| Unknown agent ID | 404 typed error | `AGENT_NOT_FOUND` | Yes |
| Blank or oversized task | 400 typed error | `AGENT_TASK_INVALID` | Yes |
| Non-object context | 400 typed error | `AGENT_CONTEXT_INVALID` | Yes |
| Handler raises an exception | No private exception text over transport | `AGENT_HANDLER_ERROR`; test secret text is absent from the response | Yes |
| Handler returns mismatched identity/status/non-JSON data | Reject result | `AGENT_RESULT_INVALID` | Yes |
| Missing run ID | Supply a correlation ID | Registry generates a bounded UUID and passes it to the handler | Yes |
| Client timeout/transport loss | No retry or duplicate suppression claim | Existing `TRANSPORT_ERROR` and no-retry client behavior remain in force | Yes |

## Regression evidence

```text
14 passed in 5.68s
338 passed in 7.52s
tracked_test_files=108
1300 passed, 1 skipped in 212.14s (0:03:32)
```

The skipped test is the existing NATS dependency-gated test. No retry-until-
lucky behavior was used.

## Security sweep

- Manual secret-pattern scan on the changed source/test/ADR surface: `no
  matches`.
- Dangerous-construct scan for `eval(`, `exec(`, `pickle`, `subprocess`,
  `os.system`, `shell=True`, and `yaml.load(`: `no matches`.
- `gitleaks`: unavailable in the environment.
- `bandit`: unavailable in the environment.
- No new runtime dependency was added. The implementation uses standard
  library HTTP primitives and existing `Result` contracts.
- The handler boundary copies and bounds JSON values, rejects non-finite
  numbers and unsupported values, does not expose exception text, and binds
  returned agent/run IDs to the request.
- Declared-project audit: `python -m pip_audit --progress-spinner off --format
  json .` returned `No known vulnerabilities found` with exit `0` across `13`
  resolved runtime packages.
- Separate environment-wide audit remains a governance veto: the prior
  `python -m pip_audit --progress-spinner off` run found `383` known
  vulnerabilities in `77` packages. This is not silently represented as a
  clean project-runtime result.

**Security verdict:** pass for the changed declared runtime surface; **VETO**
for final repository publication until the environment-wide dependency
findings are dispositioned under release policy.

**QA verdict:** pass for Slice 118 behavior, bounds, authentication, static
checks, regression coverage, and clean package evidence. The transport is
invocation-only; remote persistence, scheduling, cancellation, resume,
retries, and exactly-once effects remain outside the contract.
