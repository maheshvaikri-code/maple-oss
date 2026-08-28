# MAPLE agent-runtime slice 159 review

**Commit reviewed:** `da72c54` (`feat(transport): expose agent run history inspection`)

**Review roles:** Code Reviewer and Security Reviewer

## Scope

The review covered the authenticated `RunServer` route and `RunClient` method
for bounded agent-run history, the new ADR, the server regressions, and the
release documentation changes. The review was performed as an independent
pass over the committed diff and the surrounding authorization, transport,
and run-store contracts.

## Findings

No correctness, compatibility, or security blocker was found.

- Authentication and principal scope checks occur before route handling or
  store access; the route uses the existing `agent:read` scope.
- The server bounds the transport limit to `1..100`, rejects unknown or
  duplicate query parameters, checks the current run's agent ownership, and
  validates every returned snapshot's run and agent identity.
- The response is metadata-only. Descriptions, results, errors, messages, and
  reasoning steps are not serialized, so the route does not become a trace or
  result export surface.
- Stores that implement only the original `load()` contract remain valid for
  existing latest-summary/resume/cancel routes; history inspection returns the
  explicit typed 501 capability error.
- The route is read-only and does not restore checkpoints, replay handlers,
  consume interactions, retry requests, or claim exactly-once side effects.
- No new dependency, external service, credential, or executable-code path was
  added. Targeted secret and dangerous-construct scans returned no matches.

## Residual scope

Remote restore/replay, distributed history, hosted retention, separate tenant
or history scopes, hard cancellation, and exactly-once external effects remain
explicitly outside this slice and are recorded in ADR-104 and the parity
ledger.

## Disposition

**Pass for the reviewed change.** Release publication remains subject to the
repository QA/package gates and the pre-existing dependency-governance veto.
