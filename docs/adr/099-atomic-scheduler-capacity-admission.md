# ADR-099: Atomic Scheduler Capacity Admission

## Status

Accepted for preview release readiness.

## Context

`TaskScheduler` selected an available agent by reading its current load and
then incremented the load only after `TaskQueue.assign_task()` succeeded. Two
concurrent schedulers could both observe a free slot and both claim tasks,
exceeding `max_concurrent_per_agent`.

## Decision

Reserve one scheduler capacity slot before attempting the queue claim:

- under the scheduler lock, reject an agent already at the configured limit;
- increment the local load and append the task to the assignment list;
- release the scheduler lock before invoking the queue claim and its callbacks;
- if the queue rejects or raises, remove the matching reservation and restore
  the load under the scheduler lock;
- retain the reservation after a successful queue claim.

The queue remains authoritative for task ownership and status. The reservation
only serializes this scheduler instance's capacity admission.

## Data flow and failure behavior

1. Agent selection reads an available candidate.
2. `_assign_task_to_agent()` reserves capacity under the scheduler lock.
3. `TaskQueue.assign_task()` validates and records ownership under the queue
   lock.
4. A failed claim rolls back the scheduler reservation; a successful claim
   leaves the reservation as the active assignment.

The reservation is local and in-process. It does not coordinate quotas across
processes, detect dead workers, or guarantee that a claimed worker performs an
external side effect.

## Alternatives considered

| Alternative | Reason not selected |
|---|---|
| Check capacity only during agent selection | The check and increment are separated and race under concurrent scheduling. |
| Hold the scheduler lock through queue callbacks | Serializes user callbacks and risks lock re-entry or callback-induced stalls. |
| Increment after the queue claim | Prevents early reservation and still allows concurrent over-admission. |
| Reserve under the scheduler lock, claim outside it, and roll back failures | Selected: closes the local race while keeping queue callbacks outside the scheduler lock. |

## Consequences and invalidation triggers

Positive consequences:

- concurrent local assignments cannot exceed the configured scheduler limit;
- rejected queue claims do not leak scheduler capacity;
- queue ownership remains the authoritative state boundary;
- no dependency, network, persistence, or hosted runtime surface is added.

Boundaries:

- a short reservation window can temporarily make capacity unavailable while a
  queue claim is in progress;
- process crashes still require host-level reconciliation;
- distributed quotas, worker heartbeats, and hosted scheduling remain separate.

Revisit this ADR if capacity reservations must span scheduler processes, be
durable across restart, or depend on worker liveness leases.

## Evidence

Focused regressions synchronize concurrent assignments against a one-slot
policy and verify exactly one accepted claim, one capacity rejection, and one
active scheduler load. Final suite, package, static, and security evidence is
recorded in the slice 154 QA and review records.
