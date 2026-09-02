# ADR-161: The broker contract, and the path to multi-host

**Date:** 2026-09-01
**Status:** accepted — contract and conformance suite implemented 2026-09-01; transports beyond the in-memory broker remain future work
**Deciders:** Chief Architect + SRE

## Context

MAPLE ships two brokers. They share no interface — no ABC, no `Protocol`, no
`abstractmethod` anywhere in `maple/broker/` — and their surfaces have drifted:

```text
MessageBroker (14)  connect disconnect get_statistics is_routable publish send
                    set_separation_policy set_undeliverable_handler subscribe
                    subscribe_temporary subscribe_topic unsubscribe
                    unsubscribe_temporary unsubscribe_topic

NATSBroker     (8)  connect disconnect get_cluster_info publish request send
                    subscribe subscribe_topic
```

Six methods exist only on the in-memory broker, and two of them are security
and observability controls:

- **`set_separation_policy`** — the separation-of-duties guarantee (broker-
  enforced sender allowlist and artifact-ref-only payloads). It does not exist
  on the NATS broker at all.
- **`set_undeliverable_handler`** and **`get_statistics`** — the delivery
  accounting added in ADR-159.
- **`is_routable`** — `Agent.send` guards its use with
  `hasattr(self.broker, "is_routable")`, so `require_routable=True` **silently
  does nothing** on a broker that lacks it.

The consequence is the same fail-open shape ADR-157 fixed, one level up:
**moving to the "production" broker silently reduces the security and
observability guarantees**, and nothing in the type system, the tests, or the
runtime says so. A user following the README's advice to use `nats://` in
production would lose controls they had configured, with no error.

Compounding it, the NATS implementation is not in a shippable state: 458 lines
of source against 35 lines of test, excluded from coverage measurement via
`pyproject.toml`, and `nats-py` is not declared in any extra — there is no
`pip install maple-oss[nats]`.

## Decision

**MAPLE will not build a distributed message broker.** It will define a narrow
transport contract and delegate transport to proven infrastructure. The value
MAPLE adds is the agent protocol — typed messages, resource negotiation,
links, `Result[T, E]` — not message routing, which is a solved problem with
mature implementations.

The work is therefore in this order, and the order matters:

### 1. Define the contract (prerequisite for everything else)

A `Broker` `Protocol` in `maple/broker/contract.py` naming the operations every
transport must provide, with the delivery semantics of each stated in the
docstring rather than implied:

```text
connect / disconnect          lifecycle
send(message) -> id           point-to-point; raises BrokerOverflowError
publish(topic, message)       fan-out
subscribe(agent_id, handler)  registration
unsubscribe(agent_id)         teardown  <- missing on NATS today
is_routable(agent_id) -> bool reachability at check time
get_statistics() -> dict      delivered / undeliverable / refused
set_separation_policy(p)      security control  <- missing on NATS today
set_undeliverable_handler(h)  dead-letter hook  <- missing on NATS today
```

An implementation that cannot honor a control must **refuse to be constructed**,
not silently omit it. That is the ADR-157 rule applied to transports: a
guarantee that cannot be provided is an error, never a quiet absence.

### 2. A conformance suite the contract is defined by

This is the part that makes MAPLE production-grade, more than any individual
transport. One parameterised test suite runs against **every** broker
implementation and asserts identical observable behavior:

- backpressure: a full queue refuses with `QUEUE_FULL`, never buffers unbounded
- undeliverable messages are counted and reach the dead-letter hook
- `require_routable=True` genuinely refuses an unroutable send
- a configured separation policy is enforced
- ordering guarantees, stated and tested
- delivery semantics, stated and tested

Today there is no such suite, so "swap in NATS for production" is not a
verifiable operation. With it, adding a transport becomes a bounded task with a
pass/fail gate, and the in-memory broker gets tested against the same contract
it defines.

### 3. One reference transport, done properly

NATS, because it is already started and it fits agent messaging well —
subjects map to agent addresses, queue groups give competing consumers, and
JetStream provides durability and acknowledgements when they are wanted.

"Done properly" means: declared as an extra, removed from the coverage
exclusion, unit-tested to the same standard as the rest of the tree, and
integration-tested against a live server in CI. Not a wrapper that imports.

### 4. The properties multi-host actually requires

Transport is the visible part and the smallest. These are the rest, and each is
a decision rather than an implementation detail:

| Property | Today | Multi-host requires |
|---|---|---|
| **Discovery** | in-process dict (ADR-160 scopes it) | shared registry — NATS KV or JetStream — with TTL and heartbeats |
| **Identity** | plain string, process-local | globally unique, namespaced `scope/agent-id`, collision handling |
| **Delivery semantics** | "enqueued", fire-and-forget | explicit at-most-once / at-least-once per message, with acks and redelivery |
| **Idempotency** | none at the transport | idempotency keys, since at-least-once means duplicates |
| **Ordering** | priority queue, in-process | per-sender ordering or an explicit partition key; state that it is not global |
| **State** | file-backed, host-local | network-backed store behind the existing interfaces |
| **Leases / fencing** | file fencing, host-local | distributed lease with fencing tokens — where correctness bugs concentrate |
| **Failure detection** | in-process health monitor | heartbeats over the transport, and a stated split-brain position |
| **Security** | in-process ECDH links | mTLS between nodes, node authentication; the link layer starts carrying real weight |
| **Backpressure** | local refusal (ADR-159) | the refusal must reach a *remote* producer, not just a local one |
| **Observability** | local spans, no export | correlation IDs propagated across hops, and an export path |

**Backpressure is the one most likely to be underestimated.** ADR-159 made a
local producer learn that a local consumer is full. Across hosts, that signal
has to survive a network hop, or the queue simply moves to the other side and
the OOM happens somewhere less obvious.

## Alternatives considered

| Option | Decision | Reason |
|---|---|---|
| Implement a distributed broker in MAPLE | **Rejected** | Consensus, partition handling, and durable replication are years of work and a category of bug MAPLE has no need to own. NATS, Redis and Kafka exist. |
| Ship the NATS broker as-is and call it production | **Rejected** | 35 lines of tests, no coverage measurement, undeclared dependency, and it silently drops two security controls. Shipping it would repeat the fallback defect of ADR-157 at a larger scale. |
| Contract first, then transports | **Chosen** | Makes substitutability verifiable, retroactively tests the in-memory broker, and turns each new transport into a bounded task with a pass/fail gate. |
| Skip the contract, just test NATS harder | Rejected | Leaves the surfaces divergent. The defect is not that NATS is untested; it is that nothing defines what a broker *is*. |
| File-based multi-process broker as the next step | **Recommended, separately** | `FileTaskQueue` already proves the pattern here — file-backed fencing leases, at-least-once with hydration on restart. A `FileBroker` gives multi-process on one host at a fraction of the cost, and would be the first real test of the contract. |

## Consequences

Positive: swapping transports becomes safe and verifiable; the in-memory broker
acquires a specification; a security control that cannot be honored becomes a
construction error instead of a silent gap; adding a transport is bounded work.

Negative:

- The contract exposed that the NATS broker does not satisfy it, naming five
  missing members: `get_statistics`, `is_routable`, `set_separation_policy`,
  `set_undeliverable_handler`, `unsubscribe`. That is the finding, not a
  regression — but it means `nats://` should be
  documented as **experimental** until it conforms, and possibly refuse to
  construct when a separation policy is configured.
- A conformance suite is real work before any user-visible feature ships.
- Naming `Protocol` methods fixes them; changing them later is a breaking
  change. The contract should start minimal and grow, not start speculative.

### Outcome of step 2

The suite was expected to "find gaps in the implementation that defines it".
It did not: `MessageBroker` passed all 23 conformance tests unmodified. The
prediction was wrong, and the reason is worth recording — the ADR-159
hardening had already brought the in-memory broker up to the standard the
contract describes. The contract codified behavior that existed rather than
demanding new behavior.

The NATS transport, by contrast, is pinned as non-conformant by a test that
asserts exactly which five members it lacks, so the gap cannot be forgotten
and closing it is a deliberate edit.

## Recommended sequence

1. **ADR-160 scopes** — in-process isolation; prerequisite for a scoped registry.
2. **Broker `Protocol` + conformance suite** — run it against `MessageBroker`
   first; expect it to find gaps in the implementation that defines it.
3. **`FileBroker`** — multi-process on one host, on the proven `FileTaskQueue`
   pattern. The first genuine test that the contract is implementable twice.
4. **NATS to conformance** — extra declared, coverage restored, integration
   tested. This is the 3.0.0 anchor: it is what turns "runs on my laptop" into
   "runs in your cluster," and it is a better use of a major version than any
   new feature.
5. **Distributed registry, leases, and correlation** — the properties table
   above, each with its own decision.

Until step 4 completes, the honest statement in the README is that MAPLE
supports a **single process**, with multi-process available once step 3 lands.

## Invalidation triggers

Any broker added without passing the conformance suite; any method added to one
broker and not the contract; a decision to own transport rather than delegate
it; or evidence that NATS is the wrong substrate, which would change step 4 but
not steps 1–3.
