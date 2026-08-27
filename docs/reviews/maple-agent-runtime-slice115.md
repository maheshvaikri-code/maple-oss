# Code Review - MAPLE Agent Runtime Slice 115 @ 8c08018

**Reviewer role:** Code Reviewer · **Date:** 2026-08-26  
**Reviewed against:** [project brief](../briefs/maple-agent-runtime-release.md),
[ADR-061](../adr/061-composable-bounded-subworkflows.md), and the Slice 115
entry in the [implementation plan](../plans/maple-agent-runtime-release.md)

**Executed:**

```text
29 passed in 2.54s
30 passed in 2.90s
3 files would be left unchanged.
All checks passed!
Success: no issues found in 1 source file
git diff --check: no output (exit 0)
```

The first focused run covered the feature; the second included the malformed
child-checkpoint regression added during review hardening.

## Findings

| # | Sev | Location | Finding | Suggested fix | Resolution |
|---|-----|----------|---------|---------------|------------|
| 1 | [MAJOR] | `maple/autonomy/workflow.py` child checkpoint boundary | A custom child store returning a non-`WorkflowCheckpoint` object could otherwise cause an incidental attribute error. | Validate the loaded value before reading checkpoint fields and prove the failure is typed. | fixed in `8c08018`; `test_subworkflow_malformed_child_checkpoint_fails_closed` |

## Scope check

The committed diff matches Slice 115: one workflow API method, bounded state
mapping, deterministic child identity, child pause/resume/recovery handling,
focused workflow/replay regressions, ADR, public API documentation, parity
ledger, changelog, and plan evidence. No dependency, cloud, website,
publication, license, or preserved user-owned file was changed.

Correctness review covered normal completion, explicit input/output isolation,
missing mapped inputs, duplicate map destinations, self-reference, malformed
child checkpoints, child interruption/resume, and parent journal recovery.
The child store remains the state owner; external effects remain explicitly
at-least-once.

## Verdict

- [x] Pass (0 open BLOCKERs or MAJORs)
- [ ] Return to build - findings above

The final committed diff has no open findings. The only review finding was
closed before the feature commit and is covered by a regression test.
