# Review - MAPLE agent-runtime slice 59

## Scope

Review the OpenAI SDK adapter's resource-function boundary.

## Findings

- The previously undefined `maple_resource_request` dispatch now has an
  explicit implementation instead of surfacing an attribute error.
- Resource requests require a non-empty type and finite positive numeric amount;
  built-in and custom resource dimensions are translated into the existing
  `ResourceManager.allocate` request shape.
- Missing resource services fail closed with structured data. Allocation errors
  are propagated, and successful allocations return the existing allocation
  serialization without changing OpenAI transport behavior.
- SDK calls are isolated behind narrow opaque boundaries for the installed SDK's
  typed overloads; no broad module-level type suppression was added.

## Verification

- Offline adapter regression: `2 passed`.
- Changed-file mypy and Ruff: clean.
- Black, isort, and compile checks: pass.
- Aggregate audit: `51 errors in 4 files`; remaining diagnostics are outside
  this slice.

## Disposition

Approved for the release-readiness branch. The resource route is now
fail-closed and test-covered; remaining type debt and release gates stay
tracked in the release plan.
