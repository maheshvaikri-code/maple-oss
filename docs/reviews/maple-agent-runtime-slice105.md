# Code Review - bounded local trace spans @ 5200ece

**Reviewer role:** Code Reviewer - **Date:** 2026-08-26  
**Reviewed against:** `docs/plans/maple-agent-runtime-release.md` Slice 105,
ADR-051, and the Slice 105 implementation/tests  
**Executed:** complete Slice 105 diff from `95b337c^..5200ece`; focused
observability/run tests; static gates already run on the candidate

## Findings

| # | Sev | Location | Finding | Suggested fix | Resolution |
|---|---|---|---|---|---|
| 1 | [MINOR] | `maple/autonomy/observability.py:139` in the initial candidate | Direct public `TraceSpan` construction enforced per-field limits but did not enforce the recorder's 16 KiB serialized-attribute ceiling | Apply the same JSON byte-bound validation in `TraceSpan.__post_init__` and add a direct-constructor regression test | fixed@`5200ece`; `test_trace_span_rejects_oversized_serialized_attributes` |

## Scope check

The diff matches Slice 105: immutable local spans, bounded/redacted scalar
attributes, parent/trace validation, terminal transitions, retention/export,
sync/async model-step linkage, public exports, documentation, and tests. No
hosted exporter, remote transport, tool-span claim, sampling implementation,
backpressure claim, or new dependency was added.

Correctness pass checked identifier/name/time validation, open/terminal state
invariants, parent retention and trace matching, eviction, finish-once
behavior, concurrent starts, JSON export, telemetry-failure isolation, and
sync/async event-to-decision linkage. Design pass checked the thread-safe
recorder boundary, immutable snapshots, bounded memory, redaction before
retention, and metadata-only model events. Standards pass checked public
exports, API/README/parity/ADR documentation, typed `Result` failures, and
absence of TODO/placeholder behavior.

## Executed evidence

```text
python -m pytest tests/autonomy/test_observability.py tests/autonomy/test_runs.py -q --no-cov -p no:dash -p no:benchmark --tb=short --no-header
collected 36 items
36 passed in 0.43s

python -m black --check maple
97 files would be left unchanged.
python -m ruff check maple
All checks passed!
python -m mypy maple/autonomy/observability.py maple/autonomy/agent.py --follow-imports=skip
Success: no issues found in 2 source files
python -m compileall -q maple
git diff --check
python -m maple.cli doctor --json
{"checks": {"core": true, "evaluation": true, "events": true, "execution": true, "interop": true, "retrieval": true, "server": true, "sessions": true}, "network": false, "ready": true, "status": "SUCCESS", "version": "1.1.3"}
```

## Verdict

- [x] Pass (0 BLOCKER, MAJORs resolved)
- [ ] Return to build - findings above

The one boundedness finding was fixed and re-tested. No open correctness,
security, scope, or documentation findings remain in the Slice 105 code. The
separate dependency-governance veto is recorded in the QA/security report and
is not a code-review finding. Package evidence remains pending the final
documentation commit; no publication was performed.
