# QA + Security Report - bounded local trace spans @ 5200ece

**QA Engineer** - **Security Reviewer** - **Date:** 2026-08-26  
**Build under test:** `5200ece fix(observability): enforce direct span attribute bounds`

## Acceptance criteria verification

| # | Criterion | How executed | Evidence (real output) | Pass |
|---|---|---|---|---|
| 1 | Provide bounded `TraceSpan` and `SpanRecorder` contracts | `tests/autonomy/test_observability.py` | `36 passed in 0.43s`; creation, validation, retention, export, direct-constructor byte bounds, and concurrent recording covered | Yes |
| 2 | Redact and bound span attributes without persisting raw payloads | Focused observability tests and source scan | `test_recorder_redacts_and_finishes_once` and `test_recorder_rejects_nested_attributes_and_exports_json` passed; only flat scalar attributes are accepted and sensitive keys are redacted | Yes |
| 3 | Enforce parent/trace integrity and terminal transitions | Focused observability tests | `test_recorder_enforces_parent_trace_and_retention` passed; mismatched traces, evicted parents, and finish-once behavior are typed failures | Yes |
| 4 | Link optional sync and async model steps to spans | `tests/autonomy/test_runs.py` | `36 passed in 0.43s`; sync and async model events, response metadata, and decision traces carry the same trace/span IDs | Yes |
| 5 | Preserve existing behavior and fail safely when telemetry is unavailable | Exact tracked regression manifest and full gates | `1261 passed, 1 skipped in 260.28s` across 108 tracked test files; telemetry failures are isolated from agent outcomes | Yes |
| 6 | Keep the public/package boundary documented and committed | API/README/parity/ADR review plus package audit | Package candidate `fc39e9a`: `build_exit=0`, `twine_exit=0`, `sdist_entries=501`, required public files `5/5`, workspace-only audit `0` | Yes |

## Adversarial & edge matrix

| Input/scenario | Expected | Observed | Pass |
|---|---|---|---|
| Empty/default span values | Valid open span with bounded identifiers | `TraceSpan` creation test passed with default open status | Yes |
| Nested attribute value | Typed rejection; no raw structured payload retained | `SPAN_ATTRIBUTES_INVALID` | Yes |
| Sensitive attribute key | Redact value before retention/export | Value becomes `[REDACTED]` | Yes |
| Parent from another trace | Typed rejection | `SPAN_TRACE_MISMATCH` | Yes |
| Parent evicted by bounded retention | Typed rejection rather than dangling linkage | Parent lookup fails after eviction | Yes |
| Finish an already terminal span | Typed rejection; first terminal state remains | `SPAN_ALREADY_FINISHED` | Yes |
| Concurrent span starts | Unique IDs and bounded recorder state | 16 concurrent starts retained with unique IDs | Yes |
| Export filtered by trace ID | Return only the selected trace | JSON export contains the selected span ID | Yes |
| Sync and async model paths | Same lifecycle linkage contract | `model.chunk`, `model.response`, and decision traces share IDs | Yes |
| Telemetry recorder failure | Agent result remains unaffected | Agent catches recorder failures and logs at debug level | Yes |

## Regression

Focused suite:

```text
python -m pytest tests/autonomy/test_observability.py tests/autonomy/test_runs.py -q --no-cov -p no:dash -p no:benchmark --tb=short --no-header
============================= test session starts =============================
collected 36 items
tests\\autonomy\\test_observability.py ...................                 [ 52%]
tests\\autonomy\\test_runs.py .................                            [100%]
============================== 36 passed in 0.43s ==============================
```

Exact tracked regression manifest:

```text
tracked_test_files=108
collected 1261 items
1261 passed, 1 skipped in 260.28s (0:04:20)
pytest_exit=0
```

Flakes: none observed in the final exact run.

Package audit on committed candidate `fc39e9a`:

```text
build_exit=0
twine_exit=0
sdist_entries=501
required_hits=5/5
workspace_only_hits=0
```

## Bugs found

| # | Repro steps (minimal) | Severity | Fixed @ | Re-verified | Regression test |
|---|---|---|---|---|---|
| 1 | Start a child span with a parent from a different trace | Medium | `95b337c` | Yes | `test_recorder_enforces_parent_trace_and_retention` |
| 2 | Finish the same span twice | Medium | `95b337c` | Yes | `test_recorder_redacts_and_finishes_once` |
| 3 | Construct a direct span whose serialized attributes exceed the byte limit | Minor | `5200ece` | Yes | `test_trace_span_rejects_oversized_serialized_attributes` |

## Security sweep

Secrets scan: `gitleaks` is unavailable; the targeted Slice 105 source scan
found no embedded credential values and only expected token/metadata names.
Injection review: no new shell, SQL, path, template, pickle, eval, or exec
surface; event and span payloads exclude raw model content and tool arguments.
Dependency audit: `pip-audit` ran against the host environment and reported
`Found 383 known vulnerabilities in 77 packages`. The report includes
unrelated host/development/ML packages; Slice 105 adds no dependency. This is
still an open release-governance item and must be dispositioned before any
publication claim.  
Dangerous constructs: no new subprocess, TLS, unsafe, deserialization, or
world-writable-file behavior.  
Bounds/fail-closed: IDs, names, attribute count/size, numeric finiteness,
retention, parent linkage, and terminal transitions are bounded or rejected;
recorder failures do not alter agent outcomes.

**Security verdict:** **VETO** for a final repository publication claim until
the dependency-audit findings are dispositioned; no new Slice 105 security
defect found. Human override: n/a.  
**QA verdict:** pass for Slice 105 behavior and committed-package boundaries.
No publication was performed.
