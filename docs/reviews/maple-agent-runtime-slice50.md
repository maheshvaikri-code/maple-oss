# Review — MAPLE agent-runtime slice 50

## Scope

Review the next-node initialization in `maple/autonomy/workflow.py`.

## Findings

- The local next-node value is initialized as `Optional[str]`, matching the
  terminal route returned by the workflow graph.
- Sequential routing and parallel join routing still assign the same values as
  before; checkpoint status still derives from whether next-node is `None`.
- The change removes a cross-branch static assignment conflict without
  changing execution order or persistence behavior.

## Verification

- Workflow/replay regression suite: `19 passed`.
- Changed-file mypy: clean.
- Black, isort, and compile checks: pass.
- Aggregate audit: `142 errors in 16 files`; remaining diagnostics are outside
  this slice.

## Disposition

Approved for the release-readiness branch as a behavior-preserving typing
slice. Remaining type debt and release gates remain tracked in the release
plan.
