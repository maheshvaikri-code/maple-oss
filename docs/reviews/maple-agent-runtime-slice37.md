# Review — MAPLE agent-runtime slice 37

## Scope

Close the fault-tolerance executor's public type-boundary debt and make its
background half-open circuit transition valid through the existing wrapper.

## Review findings

- Circuit-breaker wrapper properties and constructor are typed.
- Executor lifecycle, failure recording, retry scheduling, recovery handlers,
  callbacks, and background loop have explicit contracts.
- The executor loop previously assigned to a read-only `state` property; a
  validated setter now maps supported names to `CircuitState` and rejects
  unknown values with a chained `ValueError`.
- The regression suite covers valid and invalid state transitions.

## Decision

Slice accepted. The state setter is a narrowly scoped reliability fix required
to make the existing half-open transition executable; no retry policy or
circuit threshold semantics were changed.
