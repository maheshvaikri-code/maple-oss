# QA + Security Report - MAPLE Agent Runtime Slice 122 @ 3642805

**QA Engineer / Security Reviewer · Date:** 2026-08-27  
**Build under test:** `3642805` (bounded authenticated event inspection by
cursor)

## Acceptance criteria verification

| # | Criterion | Evidence (real output) | Pass |
|---|---|---|---|
| 1 | A host can expose authenticated cursor-based inspection of its event stream. | Combined event/server suite: `37 passed in 10.68s`; the route reads the existing host-owned stream. | Yes |
| 2 | Remote reads preserve stream authority and redaction. | Cursor pagination returns the existing batch envelope, receiver-assigned sequence/timestamps, and redacted payloads. | Yes |
| 3 | Retention gaps are explicit. | An evicted cursor returns typed `EVENT_CURSOR_EXPIRED` with HTTP `409`; no silent skipping occurs. | Yes |
| 4 | Query validation is strict and bounded. | Unknown/duplicate/malformed/negative/over-bound query values fail with typed `400` errors; remote batch limit is capped at `1,000`. | Yes |
| 5 | Authentication and absent-stream paths fail closed. | Missing or wrong bearer token returns `UNAUTHORIZED`; absent stream returns `EVENT_STREAM_UNAVAILABLE`/`503`. | Yes |
| 6 | Existing application behavior remains green. | Full autonomy suite: `346 passed in 12.57s`. Exact tracked manifest: `1308 passed, 1 skipped in 226.26s` across `108` tracked Python files. | Yes |
| 7 | Public/runtime surfaces are documented and statically valid. | Black: `2 files would be left unchanged`; Ruff: `All checks passed!`; changed-boundary mypy: `Success: no issues found in 1 source file`; compile and diff checks pass. | Yes |
| 8 | The exact feature commit produces a clean package candidate. | Clean archive `3642805`: build exit `0`; both Twine checks `PASSED`; sdist `550` members; wheel `104` members; required public files `6/6`; no-dependency wheel smoke printed `event inspection exports ok`. | Yes |

## Contract and adversarial matrix

| Scenario | Expected | Observed | Pass |
|---|---|---|---|
| Read with `after=1&limit=1` | Return the next bounded page | Batch contains sequence `2`, with next cursor `2` | Yes |
| Read after the retained window | Do not silently skip history | `EVENT_CURSOR_EXPIRED`, HTTP `409` | Yes |
| Unknown or invalid query | Reject before stream read | `EVENT_QUERY_INVALID`, HTTP `400` | Yes |
| More than one `after` or `limit` | Reject ambiguous state | Strict duplicate-query rejection | Yes |
| Limit above remote bound | Keep response bounded | `EVENT_QUERY_INVALID`, `max_limit=1000` | Yes |
| Returned sensitive payload field | Preserve redaction boundary | `[REDACTED]` in remote batch | Yes |
| Missing or wrong token | Do not inspect stream | Typed `UNAUTHORIZED` | Yes |
| Event stream absent | Fail closed | Typed `EVENT_STREAM_UNAVAILABLE`, HTTP `503` | Yes |

## Regression evidence

```text
37 passed in 10.68s
346 passed in 12.57s
tracked_python_files=108
1308 passed, 1 skipped in 226.26s (0:03:46)
```

One initial full-manifest attempt encountered an unrelated existing subprocess
timeout in `tests/resources/test_file_lease.py`; that exact test passed in
isolation (`1 passed in 10.35s`) and the clean final 108-file rerun above passed.
No resource code or test was modified, weakened, skipped, or removed.

## Static, package, and security evidence

- Manual credential-pattern scan on the changed source/test/ADR surface:
  `secret_scan=no matches`.
- Dangerous-construct scan for `eval(`, `exec(`, `pickle`, `subprocess`,
  `os.system`, `shell=True`, and `yaml.load(`):
  `dangerous_construct_scan=no matches`.
- `python -m pip_audit --progress-spinner off --format json .` returned
  `No known vulnerabilities found` with exit `0` across the `13` declared
  runtime packages.
- `gitleaks` and `bandit` are unavailable in the environment.
- The separate environment-wide audit remains a governance veto: the recorded
  prior audit found `383` known vulnerabilities across `77` packages. This is
  not silently represented as a clean project-runtime result.
- Clean package hashes from `3642805`:
  - sdist SHA-256:
    `6E0AFF3F54ED4B7D4BFE2658E0A1D50BE3A01618C9628EAE12CE631F950D3408`
  - wheel SHA-256:
    `EA904754993DADF6F46ADF4042F51505220669BA55C128AF61DA32D3E13368E5`

**Security verdict:** pass for the changed declared runtime surface; **VETO**
for final repository publication until the environment-wide dependency
findings are dispositioned under release policy.

**QA verdict:** pass for Slice 122 behavior, bounds, authentication, cursor
pagination, retention-gap handling, static checks, regression coverage, and
clean package evidence. Durable replay, event batching, fleet aggregation,
remote trace search, principal scopes, and exactly-once delivery remain outside
the contract.
