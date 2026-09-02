# ADR-159: Backpressure, observable delivery, and a race-free delivery path

**Date:** 2026-09-01
**Status:** accepted
**Deciders:** SRE + Chief Architect

## Context

A production-readiness assessment of the 2.1.0 tree found that the in-memory
broker — the only transport that works out of the box — accepts everything and
reports nothing. Three defects, measured rather than inferred:

**No backpressure.** `MessageQueue` is constructed with `max_size=10000`, but
when it rejects a message `send()` falls through to
`self._agent_queues[receiver].append(message)` — a plain unbounded list. With a
stalled consumer:

```text
messages sent            : 25000
send() accepted          : 25000      <- every one returned Ok
held in bounded queue    : 10000      (max_size=10000)
held in fallback list    : 15000      <- unbounded
```

The bound is decorative. A producer outrunning a consumer grows memory until
the process dies, and no `send()` ever signals that anything is wrong.

**Silent message loss.** A message addressed to an agent that never subscribed
is accepted, drained by the delivery loop, delivered to zero handlers, and
discarded. No error, no dead-letter, no counter, no log. `is_routable()` and
`send(require_routable=True)` exist, but they are opt-in and check at send time
only — the default path loses messages silently.

**A data race on the handler tables.** `subscribe()` mutates
`_agent_handlers` / `_temp_handlers` under `self._lock`; `_deliver_message()`
reads and iterates them on the delivery thread with no lock at all. A subscribe
concurrent with a delivery can mutate a list mid-iteration. Identified by
inspection; not reproduced deterministically, which is normal for a race and no
reason to leave it.

A fourth, adjacent: `send()` enforces no bound on message size, so one large
payload defeats a bounded queue count regardless of how many messages it holds.

## Decision

### Backpressure: refuse, don't buffer

The unbounded spill is removed. When the queue is full, `send()` raises
`BrokerOverflowError`, which `Agent.send()` surfaces as
`Result.err({"errorType": "QUEUE_FULL", ...})`. The fallback list — reached
only when `MessageQueue` could not be constructed at all — carries the same
bound, so there is no path that buffers without a limit.

This follows `skills/resilience.md` directly: *"Backpressure beats buffering"*
and *"shed early and cheaply with a clear signal."* A caller that gets
`QUEUE_FULL` can slow down, shed, or fail; a caller that gets `Ok` for a
message the process will never deliver cannot do anything at all.

### Delivery: observable, not silent

`_deliver_message()` now counts a message delivered to zero handlers as
**undeliverable** rather than complete. It increments a counter surfaced by
`get_statistics()`, logs at WARNING the first time a given receiver is seen
undeliverable (rate-limited per receiver, so a hot loop cannot flood the log),
and offers an optional dead-letter hook via
`set_undeliverable_handler(callable)`.

The default remains fire-and-forget — changing `require_routable` to default
`True` would break the ordinary pattern of sending to an agent that starts
moments later. The fix is not to forbid the pattern; it is to stop the loss
being invisible.

### Delivery path: copy under the lock, call outside it

`_deliver_message()` snapshots the handler lists while holding `self._lock`,
then invokes handlers after releasing it. This closes the race without holding
a lock across user code — `skills/concurrency.md`: *"Don't hold a lock across
an await point or any blocking call."* A handler that blocks forever must not
be able to freeze `subscribe()` for every other agent.

### Message size: bounded at the edge

`send()` rejects a message whose serialized payload exceeds
`max_message_bytes`, raising `BrokerOverflowError` with a distinct
`MESSAGE_TOO_LARGE` error type. The default is 1 MiB, matching the limits
already enforced in `core/serialization.py`, so the transport and the
serializer agree rather than contradicting each other.

Limits read from `PerformanceConfig` where supplied, and are **process-wide**:
the broker is a process-wide singleton, and these are process resource limits,
so that scope is correct rather than merely convenient.

## Boundary

```text
agent.send(msg)
    |
    +-- payload > max_message_bytes ---------> Err MESSAGE_TOO_LARGE
    |
    +-- security / link / authorization ------> Err (ADR-157, fail-closed)
    |
    +-- queue at max_queue_size --------------> Err QUEUE_FULL   (backpressure)
    |
    v
  enqueued -> delivery loop -> snapshot handlers under lock
    |
    +-- zero handlers ---> counter++ , WARNING once , dead-letter hook
    |
    v
  handler invoked outside the lock
```

## Alternatives considered

| Option | Decision | Reason |
|---|---|---|
| Keep the spill, cap it at a larger number | Rejected | A bigger unbounded-ish buffer is the same defect with a later failure. The caller still learns nothing. |
| Block `send()` until space frees | Rejected | Converts an overload into a distributed hang, and `send()` has no deadline parameter to bound the wait. Refusing is honest and immediate. |
| Drop the oldest message to admit the newest | Rejected | Silent loss again, just relocated — and it makes loss depend on arrival order, which is worse to debug. |
| Default `require_routable=True` | Rejected | Breaks sending to an agent that starts shortly after. The defect is invisibility, not the pattern. |
| Hold the lock across handler invocation | Rejected | One slow handler would then block every subscribe and every other delivery — trading a race for a stall. |
| Leave message size to the serializer | Rejected | The serializer bounds what it encodes; the broker bounds what it holds. A 500 MB payload never reaching the serializer still exhausts memory. |

## Consequences

Positive: overload produces a typed refusal instead of an OOM; lost messages
are counted, logged, and hookable; the delivery path is race-free; one large
message can no longer defeat the queue bound.

Negative — **behavior changes callers may notice**:

- `send()` can now fail where it previously always succeeded. Callers that
  ignored the `Result` will silently drop messages under load — the failure is
  now *reported*, but a caller that discards the report is no better off.
  This is called out in the changelog as the migration note.
- A process that was quietly accumulating a backlog will now start returning
  `QUEUE_FULL` at 10,000 pending messages. That is the defect surfacing, not a
  new limitation, but it will look like a new error to anyone who was living on
  the unbounded path.
- Undeliverable messages now emit a WARNING on first occurrence per receiver.
  Log volume rises for applications that routinely address absent agents.

## Scope

This ADR hardens the **in-memory broker**, which its own docstring describes as
"a simple in-memory implementation for development/testing." That framing is
now inaccurate in one direction and still accurate in another: the delivery
contract is production-grade, and the transport remains **single-process**.

Explicitly **not** addressed here, and tracked in the hardening analysis:
metrics export, drain-on-shutdown, the 10ms busy-poll, wall-clock expiry in
`link.py` and `circuit_breaker.py`, per-agent thread scaling, and the fact that
the NATS transport is 458 lines with 35 lines of tests and no declared extra.

## Invalidation triggers

Any new path that enqueues without consulting the bound; any handler invocation
moved back inside the lock; a second broker implementation that does not
implement the same refusal contract; or a decision to make the in-memory broker
multi-process, which changes the meaning of "process-wide limits".
