# QA + Security Report - bounded local tool spans @ 4b60676

**QA Engineer** - **Security Reviewer** - **Date:** 2026-08-26  
**Build under test:** `4b60676 feat(observability): add local tool spans`

## Acceptance criteria verification

| # | Criterion | How executed | Evidence (real output) | Pass |
|---|---|---|---|---|
| 1 | Record normal synchronous tool calls as bounded `agent.tool` child spans | `tests/autonomy/test_runs.py` | `38 passed in 0.44s`; sync test verifies model/tool/model order, parent span ID, trace ID, status, and bounded metadata | Yes |
| 2 | Record normal asynchronous tool calls with the same parent contract | `tests/autonomy/test_runs.py` | `38 passed in 0.44s`; async test verifies the same child relationship and status | Yes |
| 3 | Exclude tool arguments and results from retained span data | Sync/async span tests and targeted source scan | Tests assert `secret-input` is absent from `tool_span.to_dict()`; scan exit `0` found no new raw-payload retention path | Yes |
| 4 | Preserve approval/HITL, tool-error, and run-result behavior | Exact tracked regression manifest | `1263 passed, 1 skipped in 263.89s` across 108 tracked test files | Yes |
| 5 | Keep the slice bounded, typed, and dependency-free | Static gates and security audit | Black/Ruff/mypy/compile/diff/doctor pass; no dependency changed; `SpanRecorder` bounds and typed failures remain in force | Yes |
| 6 | Document the public boundary and produce a clean package | API/README/parity/ADR review plus package audit | Package candidate `ccdf03d`: `build_exit=0`, `twine_exit=0`, `sdist_entries=504`, required public files `5/5`, workspace-only audit `0` | Yes |

## Adversarial & edge matrix

| Input/scenario | Expected | Observed | Pass |
|---|---|---|---|
| Successful sync tool | `agent.tool` finishes `ok` under active model span | Child span retained with `is_error=False` and result length only | Yes |
| Successful async tool | Same hierarchy without blocking the async loop | Async child span retained with matching parent/trace IDs | Yes |
| Tool arguments containing a secret-like value | Never retain arguments | `secret-input` absent from the span record | Yes |
| Tool result containing structured content | Retain only bounded length/status | Span attributes contain no result payload | Yes |
| Unknown or rejected tool | Typed tool error and error span | Existing exact suite remains green; span helper maps error `ToolResult` to `error` | Yes |
| Approval/HITL pause | Preserve pause and resume semantics; finish model span before return | Existing sync/async approval and human-input tests pass | Yes |
| Multiple normal tools in one step | Each tool gets its own child span | Loop starts/finishes one span per tool call under the same model span | Yes |
| Recorder retention pressure | Existing bounded eviction semantics | Recorder remains capped by `max_spans`; parent-not-retained is typed | Yes |
| Telemetry failure | Agent outcome remains independent | Span start/finish errors are logged diagnostically and do not alter `ToolResult` | Yes |

## Regression

Focused tool/run/trace suite:

```text
python -m pytest tests/autonomy/test_runs.py tests/autonomy/test_observability.py -q --no-cov -p no:dash -p no:benchmark --tb=short --no-header
collected 38 items
tests\\autonomy\\test_runs.py ...................                          [ 50%]
tests\\autonomy\\test_observability.py ...................                 [100%]
============================== 38 passed in 0.44s ==============================
```

Exact tracked regression manifest:

```text
collected 1264 items
================= 1263 passed, 1 skipped in 263.89s (0:04:23) =================
```

Flakes: none observed in the final exact run.

Package audit on committed candidate `ccdf03d`:

```text
head=ccdf03d
build_exit=0
twine_exit=0
artifact_count=2
sdist_entries=504
required_hits=5/5
workspace_only_hits=0
maple_oss-1.1.3-py3-none-any.whl: PASSED
maple_oss-1.1.3.tar.gz: PASSED
```

## Bugs found

| # | Repro steps (minimal) | Severity | Fixed @ | Re-verified | Regression test |
|---|---|---|---|---|---|
| 1 | Execute a normal tool while the model span is still open | Major | `4b60676` | Yes | `test_sync_tool_span_is_a_child_of_the_model_span` |
| 2 | Execute the same normal tool through the async ReAct path | Major | `4b60676` | Yes | `test_async_tool_span_is_a_child_of_the_model_span` |

## Security sweep

Secrets scan: `gitleaks` unavailable; targeted Slice 106 scan exit `0`, with
no embedded credential values and no new raw tool-payload retention.  
Injection review: tool names are recorded only as bounded scalar attributes;
arguments/results remain in the existing validated execution path and are not
copied into spans. No new shell, SQL, path, template, pickle, eval, or exec
surface was added.  
Dependency audit: `pip-audit` rerun against the host environment reported
`Found 383 known vulnerabilities in 77 packages`; Slice 106 adds no
dependency. This remains an open release-governance item and publication veto.
  
Dangerous constructs: no new subprocess, TLS, unsafe, deserialization, or
world-writable-file behavior.  
Bounds/fail-closed: tool span attributes are redacted flat scalars under the
existing count/string/byte limits; parent linkage requires a retained open
model span; tool and telemetry failures are typed or isolated.

**Security verdict:** **VETO** for a final repository publication claim until
the dependency-audit findings are dispositioned; no new Slice 106 security
defect found. Human override: n/a.  
**QA verdict:** pass for Slice 106 behavior and committed-package boundaries.
No publication was performed.
