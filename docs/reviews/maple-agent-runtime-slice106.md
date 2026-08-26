# Code Review - bounded local tool spans @ 4b60676

**Reviewer role:** Code Reviewer - **Date:** 2026-08-26  
**Reviewed against:** `docs/plans/maple-agent-runtime-release.md` Slice 106,
ADR-052, and the Slice 106 implementation/tests  
**Executed:** complete Slice 106 diff from `4b60676^..4b60676`; focused
tool/run/observability tests; full tracked suite and static gates

## Findings

| # | Sev | Location | Finding | Suggested fix | Resolution |
|---|---|---|---|---|---|
| 1 | [NIT] | `maple/autonomy/agent.py` sync/async execution wrappers | The sync and async wrappers intentionally duplicate span-finalization plumbing so each existing tool path keeps its return type and error behavior | Consider a shared internal result-finalization helper if the two execution contracts change together later | open follow-up; does not block Slice 106 |

## Scope check

The diff matches Slice 106: normal sync/async tool executions get bounded
`agent.tool` spans under their open model span; only safe identity, step,
error status, and result length are retained; existing tool, approval, human
input, checkpoint, and run-result behavior remains intact. ADR-052, API,
README, parity, plan, changelog, tests, and public-boundary documentation are
included. No exporter, remote routing, sampling, backpressure, or dependency
change was added.

Correctness pass checked model-span lifetime through normal tool execution,
multiple calls, approval/HITL pause paths, sync/async dispatch, unknown-tool
and tool-error results, parent/trace linkage, and telemetry degradation.
Design pass checked that tool arguments/results do not cross into span
attributes and that the existing `SpanRecorder` bounds and retention remain
the single local storage contract. Standards pass checked typed result
handling, public docs, no TODO/placeholder implementation, and no new
dependency.

## Executed evidence

```text
python -m pytest tests/autonomy/test_runs.py tests/autonomy/test_observability.py -q --no-cov -p no:dash -p no:benchmark --tb=short --no-header
collected 38 items
============================== 38 passed in 0.34s ==============================

python -m black --check maple
97 files would be left unchanged.
python -m ruff check maple
All checks passed!
python -m mypy maple/autonomy/agent.py maple/autonomy/observability.py --follow-imports=skip
Success: no issues found in 2 source files
python -m compileall -q maple
git diff --check
python -m maple.cli doctor --json
{"checks": {"core": true, "evaluation": true, "events": true, "execution": true, "interop": true, "retrieval": true, "server": true, "sessions": true}, "network": false, "ready": true, "status": "SUCCESS", "version": "1.1.3"}
```

## Verdict

- [x] Pass (0 BLOCKER, MAJORs resolved)
- [ ] Return to build - findings above

The only observation is a non-blocking duplication follow-up; it preserves
separate sync/async error and scheduling semantics and does not indicate a
correctness defect. No open blocker, major, or security finding remains. The
dependency-governance veto is recorded in the QA/security report and is not a
code-review finding. No publication was performed.
