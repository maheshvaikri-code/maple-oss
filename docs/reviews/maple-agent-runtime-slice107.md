# Code Review - bounded local observability retention metrics @ ec190bc

**Reviewer role:** Code Reviewer - **Date:** 2026-08-26  
**Reviewed against:** `docs/plans/maple-agent-runtime-release.md` Slice 107,
ADR-053, and the Slice 107 implementation/tests  
**Executed:** complete Slice 107 diff from `00cccac^..ec190bc`; focused
event/observability tests; full tracked suite and static gates

## Findings

| # | Sev | Location | Finding | Suggested fix | Resolution |
|---|---|---|---|---|---|
| 1 | [MINOR] | `maple/autonomy/events.py:575` in the initial metrics candidate | The existing lazy EventStream configuration contract could expose a non-integer configured capacity through a new `metrics()` snapshot | Report the actual deque capacity so the public metrics contract stays integer-typed even for invalid lazy configuration | fixed@`ec190bc`; `test_ring_buffer_tracks_evictions_and_snapshot_order` |

## Scope check

The diff matches Slice 107: local event/span buffers expose bounded,
thread-safe integer snapshots for retention, capacity, evictions, subscribers,
and open spans. Existing buffer behavior is unchanged. ADR-053, API/README/
parity documentation, plan, changelog, and regression assertions are present.
No sampling policy, histogram backend, exporter transport, dependency, or
remote behavior was added.

Correctness pass checked empty and full rings, eviction accounting, active
subscriber count, open-span derivation, concurrent recorder state, and
invalid lazy event configuration. Design pass checked lock coverage,
read-only snapshots, bounded integer values, and separation from payloads.
Standards pass checked public docs, typed return values, no TODO/placeholder
behavior, and no unrelated refactor.

## Executed evidence

```text
python -m pytest tests/autonomy/test_events.py tests/autonomy/test_observability.py -q --no-cov -p no:dash -p no:benchmark --tb=short --no-header
collected 30 items
============================== 30 passed in 0.25s ==============================

python -m black --check maple
97 files would be left unchanged.
python -m ruff check maple
All checks passed!
python -m mypy maple/autonomy/events.py maple/autonomy/observability.py --follow-imports=skip
Success: no issues found in 2 source files
python -m compileall -q maple
git diff --check
python -m maple.cli doctor --json
{"checks": {"core": true, "evaluation": true, "events": true, "execution": true, "interop": true, "retrieval": true, "server": true, "sessions": true}, "network": false, "ready": true, "status": "SUCCESS", "version": "1.1.3"}
```

## Verdict

- [x] Pass (0 BLOCKER, MAJORs resolved)
- [ ] Return to build - findings above

The one minor contract finding was fixed and re-tested. No open correctness,
security, scope, or documentation finding remains in Slice 107. The separate
dependency-governance veto is recorded in the QA/security report and is not a
code-review finding. No publication was performed.
