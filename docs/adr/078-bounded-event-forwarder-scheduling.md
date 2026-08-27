# ADR-078: Bounded event-forwarder scheduling

**Status:** Accepted

**Date:** 2026-08-27

## Context

`EventForwarder` already provides an explicit, synchronous, at-least-once
delivery boundary for a host-owned `EventStream`. A caller that wants periodic
delivery previously had to own the timer, concurrency guard, stop signal, and
metrics. That makes it easy to accidentally create overlapping calls or an
unbounded drain loop.

The missing capability is a small local scheduling seam, not a hosted queue or
distributed scheduler. It must preserve the existing forwarder's cursor and
failure semantics and must remain safe when the remote destination blocks.

## Decision

Add an opt-in `EventForwarderScheduler` and an immutable
`EventForwarderSchedulerStats` snapshot.

The scheduler contract is:

- `start()` explicitly creates one non-daemon worker; construction does not
  start background work.
- Each tick performs at most `max_batches_per_tick` synchronous
  `forwarder.forward()` calls. The default is one call and the hard bound is
  100 calls per tick.
- A tick stops early when a forward report attempted no events. This provides
  bounded local drain/backpressure without an unbounded catch-up loop.
- Only one tick may be active. The scheduler never holds its state lock while
  calling the host forwarder or remote sender.
- `stop()` sets a cooperative event and joins for a bounded timeout. It does
  not interrupt a blocking sender. A timeout returns a typed failure and the
  still-running worker remains owned by the scheduler.
- `run_once()` is available for deterministic host-controlled polling while
  stopped. It shares the same active-tick guard and metrics.
- Interval, batch-count, and stop-timeout values are finite and bounded.
- Metrics contain only integer counters, a boolean running state, and a
  sanitized error type/cause. Raw transport messages and credentials are not
  retained.

The scheduler does not add retry policy, remote deduplication, queue
persistence, exactly-once effects, fleet coordination, or hosted telemetry.
The existing `EventForwarder` remains the authority for cursor advancement and
at-least-once behavior.

## Alternatives considered

1. **Host-owned timer:** preserves minimal runtime surface, but repeats the
   concurrency and shutdown obligations at every integration site.
2. **Unbounded background drain:** improves catch-up latency but can monopolize
   a caller's sender and makes backpressure implicit.
3. **Persistent/distributed scheduler:** would require leases, ownership,
   retry, deduplication, and deployment contracts outside this local slice.

## Consequences

Hosts can choose explicit polling or a bounded local worker with observable
progress. A blocked remote sender still requires the host to choose a timeout
on its sender and to investigate a stop timeout. Callers that need durable
queueing, multiple workers, cross-process ownership, remote deduplication, or
hosted aggregation must provide those contracts separately.

## Verification

The regression suite covers bounded drain, explicit lifecycle, cooperative stop
timeout ownership, and sanitized forward errors. The scheduler is exported
from both `maple.autonomy` and the package root.
