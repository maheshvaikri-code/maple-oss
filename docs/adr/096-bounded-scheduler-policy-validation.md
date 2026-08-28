# ADR-096: Bounded Scheduler Policy Validation

## Status

Accepted for preview release readiness.

## Context

`SchedulingPolicy` was a plain dataclass. Unknown strategy names, zero or
negative concurrency, non-finite intervals, and non-boolean flags were
accepted and failed only when a scheduler later attempted to use them. A
zero interval could also produce an overly aggressive worker loop, while an
invalid retry strategy had no meaningful runtime implementation.

## Decision

Validate policy values in `SchedulingPolicy.__post_init__`:

- `load_balancing` must be `least_loaded`, `round_robin`, or
  `capability_weighted`;
- `capability_matching` must be `best_match`, `first_match`, or
  `weighted_score`;
- `retry_strategy` must be `exponential_backoff`, `linear`, or `immediate`;
- `max_concurrent_per_agent` must be a non-boolean integer from `1` through
  `10,000`;
- `scheduling_interval` must be a finite non-boolean number from `0.01`
  through `3,600.0` seconds;
- `preemption_enabled` must be a boolean.

Invalid values raise `ValueError` during policy construction. The values are
bounded for local runtime safety and clear failure semantics; this decision
does not add automatic policy correction, dynamic strategy plugins, durable
configuration, or hosted policy distribution.

## Data flow and failure behavior

1. A caller constructs `SchedulingPolicy` with defaults or explicit values.
2. `__post_init__` checks the strategy allowlists, numeric bounds, finiteness,
   and boolean type before the object is returned.
3. A valid policy is attached to `TaskScheduler` and can be consumed by its
   worker loop.
4. An invalid policy fails at the caller boundary and creates no scheduler
   worker state.

The allowlists match the strategy branches implemented by `TaskScheduler`.
The scheduler remains local and in-process; policy validation does not claim
distributed rate limits, durable scheduling, cross-process ownership, or
exactly-once effects.

## Alternatives considered

| Alternative | Reason not selected |
|---|---|
| Accept arbitrary values and fail during scheduling | Delays configuration errors until worker execution and can leave a partially running scheduler. |
| Silently replace invalid values with defaults | Hides deployment mistakes and changes caller intent without evidence. |
| Add plugin loading for arbitrary strategy names | Introduces dynamic code, dependency, trust, and lifecycle scope beyond local policy hardening. |
| Validate at construction against explicit finite allowlists and bounds | Selected: failures are deterministic, local, and visible before worker start. |

## Consequences and invalidation triggers

Positive consequences:

- invalid scheduler configuration fails at the public construction boundary;
- strategy names correspond to implemented branches;
- worker concurrency and polling intervals have finite local bounds;
- no dependency, network, persistence, or hosted-runtime surface is added.

Boundaries:

- policy bounds are per local scheduler instance;
- `retry_strategy` remains configuration metadata for the existing scheduler
  surface and does not add new retry execution behavior in this slice;
- preemption remains an existing flag and is not implemented by validation;
- durable configuration, remote policy distribution, and hosted administration
  remain separate.

Revisit this ADR if policy values must be negotiated across processes, loaded
from untrusted configuration, extended by plugins, or persisted for recovery.

## Evidence

Focused scheduler regressions cover invalid strategy/type/bound values and
documented boundary acceptance. Final suite, package, static, and security
evidence is recorded in the slice 151 QA and review records.
