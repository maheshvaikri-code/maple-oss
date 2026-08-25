# Review — MAPLE agent-runtime slice 30

## Scope

This slice covers broker core/queue/routing/factory type boundaries and the
MCP adapter's missing resource-management handler. Commits: `c98e871`,
`72496ad`, and `7a80472`.

## Review findings

- Broker singleton, delivery-thread, queue-statistics, routing-frame, and
  production-factory state now have explicit contracts.
- The MCP adapter previously advertised `maple_resource_management` but called
  a nonexistent method. It now returns a structured fail-closed error until a
  host configures a resource manager; this avoids an unhandled attribute error
  and keeps the unavailable capability explicit.
- The new MCP behavior has a regression test. No network transport or external
  resource manager is invoked by the test.
- Aggregate mypy remains non-zero at `287 errors in 44 files`; the explicit
  Python 3.10 audit and configured-target mismatch remain release blockers.
- This is an author-context review; fresh independent G4/G5 verification is
  unavailable in this environment.

## Decision

Approved as a bounded release-hardening slice. Not a release approval while
aggregate typing, full-suite completion, dependency/security audit disposition,
and independent verification remain open.
