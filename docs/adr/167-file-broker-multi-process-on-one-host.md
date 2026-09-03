# ADR-167: FileBroker — multi-process on one host

**Date:** 2026-09-03
**Status:** accepted
**Deciders:** Chief Architect + SRE + Security Reviewer

## Context

[ADR-161](161-broker-contract-and-the-path-to-multi-host.md) defined a `Broker`
protocol and a conformance suite, and set the sequence to multi-host:

> `FileBroker` for multi-process on one host first — the `FileTaskQueue` fencing
> pattern already proves it here and it is the first real test that the contract
> is implementable twice — then NATS to conformance.

Until a second transport passes, MAPLE is a **single-process runtime**, and nine
Tier 4 capability rows inherit that ceiling. This is the 3.0.0 anchor.

The conformance suite is the specification. It is not negotiable and it is not
extended for this transport: a new broker is added to `BROKER_FACTORIES` and
must pass all 23 tests unchanged.

## The claim primitive: measured, and the obvious one rejected

A file-backed broker needs exactly one consumer to take each message. The
obvious primitive is claim-by-rename — `os.rename` is atomic, so the winner
takes it and the loser gets `FileNotFoundError`.

**Single-process, that is exactly what happens:**

```text
first  rename: OK
second rename: correctly failed: FileNotFoundError
```

**Across processes on this platform, it is not.** Two processes racing 200
files, each recording the outcome of its own `os.rename`:

```text
races: 200
exactly one winner : 8
BOTH won           : 192
proc0 outcomes: {'WON': 196, 'FileNotFoundError': 4}
proc1 outcomes: {'WON': 196, 'FileNotFoundError': 4}
```

Both processes were told they had won, 96% of the time. A four-process run
showed the same shape: 258 of 300 messages believed-claimed by more than one
worker, while the directory itself ended correct with exactly 300 single-owner
files.

This is not a filesystem-visibility problem — a control test confirmed each
process sees the other's files immediately. **The behaviour is unexplained**,
and that is precisely why it cannot be built on: a transport whose exclusion
depends on a primitive that reports success to two claimants would deliver most
messages twice.

### What is used instead

MAPLE already ships a cross-process lock and already depends on it for
`FileTaskQueue`: `_InterProcessFileLock`, using `msvcrt.locking` on Windows and
`fcntl.flock` on POSIX, with a timeout and an intra-process lock beneath it.

Measured, four processes incrementing a shared counter through it:

```text
processes x increments : 4 x 150 = 600
final counter          : 600
LOST UPDATES           : 0
```

Real mutual exclusion, on the same machine and filesystem where rename-claiming
misbehaved. It is also the pattern ADR-161 actually pointed at, and reusing a
proven primitive beats inventing a second one.

**Decision: every spool mutation happens under `_InterProcessFileLock`.**
Claim-by-rename is not used.

## Decision

### `file://` becomes a supported scheme

[ADR-164](164-configuration-is-validated-at-construction.md) refuses unknown
schemes, and a drift test pins `Config.KNOWN_SCHEMES` against what
`_create_broker` dispatches on. `file` is added to both together, or the URLs
this transport needs are rejected before reaching it.

`file:///var/run/maple/spool` names the spool directory. The host owns that
path, its permissions, and its lifetime — the same operational boundary that
keeps TLS and credentials outside the library.

### Layout

```text
<root>/
  spool.lock                     the one lock, held only for short mutations
  agents/<agent_id>.live         presence, refreshed while subscribed
  inbox/<agent_id>/<seq>.json    one file per message, fsynced before it counts
```

One file per message rather than one shared log: a partial write can never
corrupt another message, and the pending count is a directory listing rather
than a parse.

### Presence is what makes "undeliverable" decidable

`test_a_message_with_no_handler_is_counted` sends to an agent nobody serves and
requires `undeliverable == 1` within 400 ms. In one process that is trivial —
the handler table is right there. Across processes it is not, and "the inbox is
empty" cannot distinguish *nobody is listening* from *nobody has looked yet*.

So a subscriber writes a presence file and refreshes it while subscribed. A
receiver with no fresh presence entry is undeliverable: counted, dead-lettered,
and removed. A stale presence file — a process that died — expires by age, so a
crash degrades to undeliverable rather than to an inbox that fills forever.

This is the same reasoning as ADR-162's health counters and ADR-163's drain: the
failure has to be *observable*, not merely absent.

### Delivery is polled, and that is a real cost

[ADR-166](166-deliver-on-a-signal-not-a-poll.md) replaced the in-memory poll
with a condition variable and cut latency from p50 4.8 ms to 0.33 ms. A
condition variable does not cross processes, so this transport polls, and its
latency will be a poll interval rather than a signal.

That is stated plainly rather than hidden: `FileBroker` trades latency for
reach. An in-process deployment should keep using the in-memory broker, and the
capability declaration says which is which.

### Capabilities are declared honestly

`cross_process=True`, `durable=False` — messages survive a process restart
because they are files, but nothing here is a durability *guarantee*: there is
no replication, no ordering across agents, and no exactly-once claim.
`enforces_security_policy` follows what is actually implemented, because
ADR-157 refuses a transport that accepts controls it will ignore.

## Alternatives considered

| Option | Decision | Reason |
| --- | --- | --- |
| Claim by `os.rename` | **Rejected** | Measured: both racers told they won, 192/200. Unexplained, and unexplained is disqualifying for an exclusion primitive. |
| One shared append-only log with offsets | Rejected | Every consumer parses the whole log, and a torn write corrupts every message after it. Per-message files fail in isolation. |
| A SQLite spool | Rejected | Adds a dependency-shaped decision and a schema for what is a queue. Reconsider if ordering guarantees are ever required. |
| Skip `FileBroker`, go straight to NATS | Rejected | ADR-161's sequencing: proving the contract is implementable twice with **no external infrastructure** is what makes the conformance suite trustworthy. |
| Extend the conformance suite for file semantics | Rejected | The suite is the specification. A transport that needs the spec relaxed has not conformed. |

## Consequences

Positive: MAPLE stops being a single-process runtime; the broker contract is
proven implementable twice, which is what makes it a contract; and it needs no
external infrastructure, so the conformance suite can run it in CI.

Negative:

- **Latency is a poll interval**, not a signal. Worse than the in-memory broker
  on the same host, and stated as such.
- **One host only.** A shared filesystem is not a network transport; NFS
  locking semantics are explicitly out of scope.
- **The spool is a new operational surface** — permissions, disk, cleanup — that
  the host now owns.
- **Presence has a liveness window.** A crashed subscriber's messages are
  undeliverable only once its presence expires.

## Outcome

Built, and it passes the conformance suite **unchanged**:

```text
tests/broker/test_broker_conformance.py: 43 passed, 1 skipped
```

The skip is the security-enforcement test, which asserts only where a
transport claims to enforce. `FileBroker` declares `ENFORCES_SECURITY_POLICY =
False`, so ADR-157 refuses it a security-configured agent rather than accepting
controls it would ignore.

Across real process boundaries, 11 tests spawning real subprocesses. The one
that matters:

```text
3 consumer processes, 60 messages, each delivered exactly once, 0 duplicates
```

That is the property claim-by-rename could not give on this platform, and the
reason the spool lock is used instead.

**The contract is now implementable twice.** That is what turns ADR-161's
`Broker` protocol from a description of one class into a contract.

## Invalidation triggers

A cross-process signalling primitive that removes the poll; a requirement for
ordering or exactly-once, which the per-file layout does not provide; or NATS
reaching conformance, after which this transport's role narrows to
infrastructure-free deployments and testing.
