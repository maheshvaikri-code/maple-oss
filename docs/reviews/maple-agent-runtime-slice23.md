# Code Review - MAPLE agent runtime slice 23 @ `1af7f3a`

**Reviewer role:** Code Reviewer
**Date:** 2026-08-24
**Reviewed against:** [agent-runtime brief](../briefs/maple-agent-runtime-release.md), [release plan](../plans/maple-agent-runtime-release.md), and [ADR-021](../adr/021-bounded-workflow-execution-journal.md)

## Executed

```text
python -m pytest tests/llm tests/autonomy tests/test_cli.py -q -o addopts=
235 passed in 3.33s

python -m pytest -q tests/autonomy/test_replay.py tests/autonomy/test_workflow_replay.py tests/autonomy/test_workflow.py -o addopts=
26 passed in 0.31s

python -m ruff check maple/autonomy/replay.py maple/autonomy/workflow.py tests/autonomy/test_replay.py tests/autonomy/test_workflow_replay.py
All checks passed!

python -m flake8 maple/autonomy/replay.py maple/autonomy/workflow.py tests/autonomy/test_replay.py tests/autonomy/test_workflow_replay.py --ignore=E501,E704,W503
RUFF_EXIT=0 FLAKE8_EXIT=0
```

## Findings

| # | Sev | Location | Finding | Suggested fix | Resolution |
|---|-----|----------|---------|---------------|------------|
| 1 | MINOR | `maple/autonomy/replay.py` file-journal inspection | Persistent inspection needed to reject record/key filename mismatches and bound directory scans, not only validate the requested key. | Verify the hashed filename for every inspected record and stop at `max_records`. | fixed in `1af7f3a`; regression coverage is in `test_file_journal_fails_closed_when_record_key_does_not_match_filename` |

No BLOCKER or MAJOR findings remain. The journal is explicitly opt-in,
bounded, atomic for local file replacement, and does not claim exactly-once
external side effects. Workflow recovery is public through `Workflow.recover`.

## Scope check

The diff matches Slice 23: execution records, in-memory/file journals,
deterministic execution keys and input digests, running-checkpoint recovery,
tests, API documentation, README, changelog, ADR, and plan evidence. No new
runtime dependency, website change, cloud call, or publication action was
introduced. User-owned untracked files remain outside the commit.

An independent fresh-context verifier session was unavailable in this tool
environment; this report is the local role review and does not represent that
missing independent gate as complete.

## Verdict

- [x] Local review pass: 0 open BLOCKER/MAJOR findings.
- [ ] Independent fresh-context G4 verification complete.
