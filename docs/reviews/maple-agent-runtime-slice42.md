# Review — MAPLE agent-runtime slice 42

## Scope

Close the failure detector's lifecycle, circuit-breaker wrapper, recovery,
callback, and background-loop type boundaries.

## Review findings

- Circuit-breaker wrapper properties now expose concrete runtime contracts and
  retain the shared generic breaker behind a typed boundary.
- Detector startup/shutdown, failure recording, recovery callbacks, circuit
  updates, and the background loop now declare their return contracts.
- Recovery behavior, callback ordering, and circuit transitions are unchanged.

## Decision

Slice accepted. The casts are confined to the legacy generic circuit-breaker
wrapper where the imported dependency surface is dynamic; no failure policy
was changed.
