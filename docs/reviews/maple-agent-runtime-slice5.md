# Code Review - MAPLE Agent Runtime Slice 5 @ 5be8115

**Reviewer role:** Code Reviewer  · **Date:** 2026-08-24
**Reviewed against:** [brief](../briefs/maple-agent-runtime-release.md),
[ADR-004](../adr/004-event-stream-redaction-contract.md), and
[implementation plan](../plans/maple-agent-runtime-release.md)

## Scope

This slice adds a thread-safe, bounded `EventStream` with monotonic sequence
numbers, snapshots, waiters, synchronous subscribers, recursive credential-key
redaction, and structured payload limits. It is an in-process observability
contract, not a durable broker or hosted telemetry exporter.

## Findings

| # | Sev | Location | Finding | Resolution |
|---|---|---|---|---|
| 1 | MINOR | Event retention | A live stream can evict old events. | Ring eviction is explicit through `dropped_count`; durable retention remains an adapter concern. |
| 2 | MINOR | Subscriber callbacks | Callbacks run synchronously and may be slow. | Callback exceptions are isolated; docs direct hosts to hand off blocking work to their own queue. |
| 3 | MINOR | Redaction | Key-based redaction cannot detect secrets embedded in arbitrary strings. | Docs call redaction defense in depth; callers must avoid placing secrets in payloads. |

## Verification evidence

```text
ruff check maple/autonomy/events.py tests/autonomy/test_events.py --output-format concise
All checks passed!

python -m pytest tests/autonomy/test_events.py tests/autonomy/test_retrieval.py -q -o addopts=
11 passed, 1 warning in 0.02s

python -m pytest tests/autonomy -q -o addopts=
125 passed, 1 warning in 0.18s

python -m compileall -q maple
exit code 0
```

The pytest warning is the existing `asyncio_mode` configuration warning when
plugin autoload is disabled. Existing aggregate Ruff debt in the two package
initializers remains a separate release-hardening item.

## Verdict

- [x] Slice review pass: no open BLOCKER or MAJOR finding.
- [ ] Final release review: pending slices 6-8 and independent fresh-context
  verifier availability.

The available environment has no separate fresh-agent session facility, so this
artifact records local review evidence and does not claim independent verifier
separation.
