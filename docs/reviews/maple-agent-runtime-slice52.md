# Review — MAPLE agent-runtime slice 52

## Scope

Review the constructor and decode typing changes in the A2A, ACP, and FIPA ACL
adapters.

## Findings

- Adapter constructors now explicitly accept the host agent boundary and return
  no value.
- FIPA JSON decoding is statically narrowed to the adapter’s declared mapping
  contract; the decoded runtime object is unchanged.
- No protocol field mapping, transport behavior, or error handling changed.
- The repository has no dedicated tests for these three legacy adapters; this
  limitation is recorded rather than masked.

## Verification

- Import smoke: passed.
- Changed-file mypy: clean for all three adapters.
- Black, isort, and compile checks: pass.
- Aggregate audit: `132 errors in 12 files`; remaining diagnostics are outside
  this slice.

## Disposition

Approved for the release-readiness branch as a behavior-preserving typing
slice, with missing dedicated adapter coverage retained as a release-quality
follow-up.
