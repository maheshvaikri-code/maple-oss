# QA + Security Report - MAPLE Agent Runtime Slice 119 @ cafff3c

**QA Engineer / Security Reviewer · Date:** 2026-08-27  
**Build under test:** `cafff3c` (bounded authenticated handoff transport)

## Acceptance criteria verification

| # | Criterion | Evidence (real output) | Pass |
|---|---|---|---|
| 1 | A host can expose its existing handoff store through authenticated HTTP. | Focused server suite: `16 passed in 6.24s`; create, inspect, list, accept, complete, and unauthorized paths are covered. | Yes |
| 2 | Existing store ownership and terminal-state semantics remain authoritative. | The transport delegates to `HandoffStore`; wrong target returns `HANDOFF_OWNER_ERROR`, and accepted records complete back to source ownership. | Yes |
| 3 | The transport is digest-only and bounded. | `HandoffRecord.to_dict()` is the payload; raw task/context are not sent. Record parsing uses the store's bounded identifiers, SHA-256, finite timestamp, and state validation; list limits are capped at 100. | Yes |
| 4 | Missing stores and malformed/unauthorized requests fail closed. | No configured store returns `HANDOFF_STORE_UNAVAILABLE`; invalid records/limits are typed; bearer auth is required when configured. | Yes |
| 5 | Existing application behavior remains green. | Full autonomy suite: `340 passed in 9.27s`. Exact tracked manifest: `1302 passed, 1 skipped in 214.52s (0:03:34)` across `108` tracked test files. | Yes |
| 6 | Public/runtime surfaces are documented and statically valid. | Black: `97 files would be left unchanged`; Ruff: `All checks passed!`; changed-boundary mypy: `Success: no issues found in 3 source files`; doctor: `ready: true`, all eight checks true, `network: false`; compile and diff checks exit `0`. | Yes |
| 7 | The exact feature commit produces a clean package candidate. | `python -m build --wheel --sdist`: exit `0`; Twine wheel/sdist: both `PASSED`; sdist `541` members; wheel `104` members; required public files `6/6`; fresh `--no-deps` install printed `handoff transport exports ok`. | Yes |

## Contract and adversarial matrix

| Scenario | Expected | Observed | Pass |
|---|---|---|---|
| Handoff store attached without bearer token | Refuse construction | `ValueError: auth_token is required when handoff_store is configured` | Yes |
| Missing or wrong bearer token | Do not access store | Typed `UNAUTHORIZED` | Yes |
| No configured store | Fail closed | Typed `HANDOFF_STORE_UNAVAILABLE`, HTTP `503` | Yes |
| Invalid record payload | Reject before store mutation | `HANDOFF_RECORD_INVALID`, HTTP `400` | Yes |
| Invalid open-list limit | Reject before store access | `HANDOFF_LIMIT_INVALID` | Yes |
| Wrong target agent | Preserve ownership boundary | `HANDOFF_OWNER_ERROR`, HTTP `409` | Yes |
| Repeated terminal transition | Preserve one-time state machine | Existing `HANDOFF_STATE_CONFLICT` behavior is returned unchanged | Yes |
| Record inspection | Do not expose raw task/context | Response contains digests and state fields only | Yes |
| Cross-process file store | Keep fencing/atomic semantics | Transport delegates to the already-tested `FileHandoffStore`; no alternate persistence path added | Yes |

## Regression evidence

```text
16 passed in 6.24s
340 passed in 9.27s
tracked_test_files=108
1302 passed, 1 skipped in 214.52s (0:03:34)
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
- No new runtime dependency was added. The implementation reuses the
  existing `HandoffStore` contract and standard-library transport.
- Task/context contents are not accepted by this transport; only validated
  digest-only records cross the HTTP boundary. Store ownership, validation,
  file fencing, and terminal transitions remain authoritative.
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

**QA verdict:** pass for Slice 119 behavior, bounds, authentication,
store-delegation, static checks, regression coverage, and clean package
evidence. Remote payload delivery, principal scopes, notifications, retries,
scheduling, cancellation, and exactly-once effects remain outside the
contract.
