# ADR-168: Presence over NATS

**Date:** 2026-09-05
**Status:** accepted
**Deciders:** Chief Architect + Interop Engineer

## Context

[ADR-167](167-file-broker-multi-process-on-one-host.md) proved the broker
contract is implementable twice. NATS is the third, and the one that would make
MAPLE multi-*host*. It now provides every contract member and, since the live
CI suite exposed three defects, actually works — it connects, honours
`broker_url`, and delivers.

Three capabilities remain `False`:

| Capability | Why NATS does not give it |
| --- | --- |
| `supports_routability_check` | A client sees its own subscriptions, never the cluster's |
| `reports_undeliverable` | Publish is fire-and-forget; nothing reports that no subscriber existed |
| `applies_backpressure` | There is no queue to be full — the message is gone |

This ADR closes the first two. The third is **not** closed here, for reasons
worth stating rather than leaving as an unexplained gap.

### Why backpressure is not in this ADR

Two separate obstacles, and both are decisions rather than work:

1. **There is no queue.** Core NATS publish hands the message to the client and
   returns. To refuse a fourth message after three, MAPLE would have to hold an
   outbound queue of its own — bounding *MAPLE's* memory rather than anything
   about NATS — or move to JetStream, where acknowledgement makes "outstanding"
   a real quantity.
2. **The contract wants a raise, and this transport returns a `Result`.**
   `test_a_full_queue_refuses` expects `send()` to raise `BrokerOverflowError`;
   `NATSBrokerSync.send()` returns `Result`. Behavioural conformance therefore
   needs a **breaking change to this transport's public API**, not just a new
   check.

Neither belongs in a change about presence, and pretending otherwise would
produce a `send()` that refuses on a bound with no relationship to the
transport.

## Decision

### Presence is a subject, not a registry

Subscribers announce themselves on `maple.presence.<agent_id>`; every connected
broker subscribes to `maple.presence.>` and keeps a local cache of who was last
heard from. Routability and undeliverable both fall out of that one mechanism —
the same shape `FileBroker` uses, where presence files made "undeliverable"
decidable across processes.

No extra infrastructure: presence rides the transport it describes. If NATS is
reachable, presence is reachable.

### A beacon on subscribe, then a heartbeat

`subscribe()` publishes immediately, so a subscriber is visible as soon as it
exists rather than at the next tick. A heartbeat then refreshes it, and an entry
older than the TTL is treated as gone — a crashed process stops being routable
without anyone having to notice.

The TTL is several heartbeats wide. A single lost beacon must not evict a live
agent, because the cost of a false eviction is a message counted undeliverable
and **not sent**.

### An unroutable message is not published

If presence says nobody serves the receiver, the message is **not** published:
it is counted undeliverable and passed to the dead-letter hook. That matches the
in-memory broker, where undeliverable means zero handlers, and it keeps the
counter meaningful — publishing anyway *and* counting it undeliverable would
make the number describe neither what was sent nor what arrived.

The cost is stated plainly: **during the liveness window, a real subscriber can
look absent.** A message sent in that gap is refused rather than published. The
window is bounded by the beacon-on-subscribe, and it is the price of an honest
`undeliverable` count on a transport that will not report one.

### Locally-served agents skip the check

An agent this broker serves itself is known without consulting presence. That
removes the window entirely for the single-process case and keeps the common
path free of a cache lookup that cannot fail.

## Alternatives considered

| Option | Decision | Reason |
| --- | --- | --- |
| Publish anyway and count undeliverable | Rejected | The counter would describe neither what was sent nor what arrived. A number that means two things means nothing. |
| Use `nc.request()` and NATS "no responders" | Rejected | Turns every send into request/reply, changing delivery semantics and cost for every message to answer a question about one. |
| A dedicated presence service | Rejected | New infrastructure to describe infrastructure. Presence should fail with the transport it describes, not separately. |
| Ask the NATS server for subscriptions | Rejected | Monitoring endpoints are an operational surface, not a client API, and may be disabled. |
| Close backpressure here too | Deferred | Needs either a MAPLE-side outbound queue or JetStream, **and** a breaking change to `send()`'s signature. Two decisions, neither about presence. |

## Consequences

Positive: `is_routable` answers for the cluster rather than for one client;
undeliverable messages are counted and dead-lettered on a transport that reports
neither; both use one mechanism instead of two; and `Agent.send(require_routable=True)`
becomes meaningful over NATS, since the capability flag now says the answer can
be trusted.

Negative:

- **A liveness window.** A subscriber that has just appeared, or whose beacons
  were lost, reads as absent and its messages are refused. Bounded by the
  beacon-on-subscribe and a TTL several heartbeats wide.
- **Presence traffic scales with agents.** One small message per agent per
  heartbeat, on a wildcard subscription every broker holds.
- **A partitioned broker sees stale presence** and will refuse messages for
  agents that are alive on the other side. That is the correct failure for a
  partition — refusing beats claiming delivery — but it is a behaviour change
  from "publish and hope".
- **`applies_backpressure` stays `False`,** so NATS remains outside
  `BROKER_FACTORIES`. This ADR narrows the gap; it does not close it.

## Invalidation triggers

A move to JetStream, which makes both undeliverable *and* backpressure
answerable from acknowledgement rather than presence; a NATS client API that
exposes cluster subscriptions directly; or agent counts where per-agent
heartbeats become the dominant traffic.
