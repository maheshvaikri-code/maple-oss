# Review - MAPLE agent-runtime slice 58

## Scope

Review the OpenAI and Anthropic provider SDK typing boundaries.

## Findings

- Optional SDK constructor arguments now use a deliberately broad payload
  mapping so optional timeout, key, and base URL values retain their runtime
  types.
- Provider-compatible request dictionaries remain flexible at the SDK call
  boundary; static casts are limited to third-party SDK constructors and call
  surfaces whose runtime contract already supports the payloads.
- Response parser inputs are explicitly opaque SDK response values, while the
  existing native text, tool-call, finish-reason, and error behavior is
  unchanged.

## Verification

- Native provider streaming regression: `3 passed`.
- Changed-file mypy with skipped imports: clean.
- Black, isort, and compile checks: pass.
- Aggregate audit: `62 errors in 5 files`; remaining diagnostics are outside
  this slice.

## Disposition

Approved for the release-readiness branch as a behavior-preserving optional-SDK
typing slice. Remaining type debt and release gates remain tracked in the
release plan.
