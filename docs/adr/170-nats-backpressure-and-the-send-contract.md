# ADR-170: NATS backpressure, and the shape of `send()`

**Date:** 2026-09-06
**Status:** accepted
**Deciders:** Chief Architect + Interop Engineer

## Context

[ADR-168](168-presence-over-nats.md) closed routability and undeliverable
reporting over NATS. One capability remained: **backpressure**, which
[ADR-161](161-broker-contract-and-the-path-to-multi-host.md)'s conformance
suite requires as `send()` raising `BrokerOverflowError` once a bound is
reached.

Two obstacles were recorded there, and both turned out to be smaller than they
looked once a third problem surfaced.

### `send()` has the wrong shape, and it is already a bug

`NATSBrokerSync.send()` returns `Result`. `Agent.send()` does:

```python
message_id = self.broker.send(message)
return Result.ok(message_id)
```

Over NATS that produces **`Result.ok(Result.ok("id"))`**. A caller doing
`sent.unwrap()` gets a `Result`, not a message id.

Worse, when the transport fails, `broker.send()` returns `Result.err(...)` and
`Agent.send()` wraps it as **`Result.ok(...)`** — a failed send reported as a
success. That is the fail-open class this series exists to close, sitting
undetected in the one transport nobody could execute.

So aligning `send()` to return `str` and raise is not a concession to the
conformance suite. It is a fix, and the suite happens to want the same shape
`Agent` already expects.

### Backpressure needs a queue, and the queue solves something else too

Core NATS publish hands the message to the client and returns; there is nothing
to be full. MAPLE therefore holds a **bounded outbound queue** and drains it to
NATS.

That bounds *MAPLE's* memory rather than anything about NATS, and the ADR says
so plainly. But it also answers a question the suite asks and this transport
could not: `test_a_full_queue_refuses` and `test_send_returns_an_identifier`
both call `send()` **before `connect()`**. With a queue, a send made while
disconnected is accepted and drains on connect, exactly as the in-memory broker
behaves.

JetStream was the alternative. It makes "outstanding" a real quantity through
acknowledgement, and it is the right answer eventually — but it requires the
server to have JetStream enabled and streams provisioned, which changes what a
deployment must supply. That is not a decision a library should impose while a
bounded local queue does the job.

## Decision

### `send()` returns an identifier and raises

- Returns `str` — the message id.
- Raises `BrokerOverflowError` with `MESSAGE_TOO_LARGE` above
  `max_message_bytes`, and with `QUEUE_FULL` when the outbound queue is at
  `max_queue_size`.
- Raises `SecurityError` where a separation policy denies, as the in-memory
  broker does.

**This is a breaking change** to `NATSBrokerSync.send()` and
`NATSBroker.send()`. It is taken because the previous shape produced nested
`Result`s and reported failures as successes through `Agent`.

### A bounded outbound queue, drained by the client

`send()` appends; a drain hands messages to NATS as fast as it can. The bound
is `max_queue_size`, and reaching it refuses rather than growing — the same
choice ADR-159 made for the in-memory broker, for the same reason: a queue that
cannot refuse is a memory leak with extra steps.

Admission order matters and is fixed: **size, then policy, then presence, then
capacity.** A message too large is refused whatever the queue depth, and a
message nobody can receive is dead-lettered rather than occupying a slot.

### Conformance runs against a real server, not in the default suite

NATS cannot join `BROKER_FACTORIES` in the ordinary suite: every factory there
must be constructible with no external infrastructure, and NATS needs a server.

So the conformance suite gains a NATS factory that is **selected only under the
`nats` marker**, which the live CI job runs against a real server. The same
tests, the same assertions, against the real transport — rather than a second,
weaker suite written to be passable.

## Alternatives considered

| Option | Decision | Reason |
| --- | --- | --- |
| JetStream | Deferred | The right long-term answer, but it requires server features and provisioned streams. A library should not impose that while a local bound suffices. |
| Keep `send()` returning `Result`, adapt at the edge | Rejected | The nested-`Result` and success-on-failure bugs live in that mismatch. An adapter would preserve them for direct callers. |
| Unbounded outbound queue | Rejected | ADR-159 already settled this: a queue that cannot refuse is a memory leak. |
| Drop the message when the queue is full | Rejected | Silent loss, which is the defect class this series closes. |
| Write NATS-specific conformance tests | Rejected | A suite written to be passable proves nothing. The existing tests run against the real server or NATS is not conformant. |

## Consequences

Positive: NATS satisfies the behavioural contract; `Agent.send()` over NATS
returns a real message id and reports failures as failures; sends made before
`connect()` are accepted and drained rather than lost.

Negative:

- **Breaking:** `send()` no longer returns `Result`. Direct callers must catch
  `BrokerOverflowError` instead of inspecting a returned error.
- **The bound is MAPLE's, not the transport's.** A full queue means MAPLE is
  producing faster than it can hand off to NATS. It says nothing about the
  server's capacity, and the ADR resists implying otherwise.
- **Queued messages do not survive a crash.** The outbound queue is memory.
  Nothing here is durability, and the capability flag stays `durable=False`.
- **The conformance run needs infrastructure.** It gates on CI having a NATS
  container; a developer without one sees skips, which the live job treats as
  failure so the skip cannot hide.

## Invalidation triggers

A move to JetStream, which replaces the local queue with acknowledgement and
makes `undeliverable` answerable without presence; or a NATS client that
exposes its own outbound bound, which would make MAPLE's redundant.
