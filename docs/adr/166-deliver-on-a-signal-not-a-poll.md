# ADR-166: Deliver on a signal, not a poll

**Date:** 2026-09-03
**Status:** accepted
**Deciders:** Chief Architect + SRE

## Context

The last Tier 3 roadmap item: *"The broker's delivery loop wakes 100 times a
second whether or not anything is moving. A condition variable signalled by
`send()` would idle at zero."*

The loop is `time.sleep(0.01)` followed by a drain of both queues. Measured
before designing anything:

```text
1 idle broker : 0.0 ms CPU over 3.0s wall  (0.00% of a core)
10 idle scopes: 31.2 ms CPU over 3.0s wall (1.04% of a core)
delivery latency: n=60 p50=4.8ms p95=10.0ms max=16.6ms
```

**The roadmap framed the wrong cost.** Idling is nearly free: a single broker's
CPU use is below the measurement floor, and ten scopes together cost about 1%
of one core. Nobody would fund a change for that.

What the poll actually costs is **latency on every message**. A 10 ms poll
means a message waits on average half a poll to be noticed — p50 4.8 ms — with
a p95 at the full interval and a tail past it. That is paid per hop, so a
five-step agent chain spends ~25 ms in sleep alone, on a machine doing nothing
else.

## Decision

### Wait on a condition, signalled by the enqueue

`send()` already knows a message arrived. The delivery loop waits on a
`threading.Condition` and `send()` notifies it, so delivery starts when there
is something to deliver rather than at the next tick.

### A separate lock, not the broker's

The condition gets its **own** lock rather than wrapping `self._lock`. The
drain path takes `self._lock` while copying the per-agent queues, and mixing
the two would make the waiting semantics depend on which lock the drain happens
to hold. A dedicated wake lock has one job and cannot deadlock against
delivery.

### A flag, because a notify with nobody waiting is lost

`Condition.notify()` wakes current waiters only. A message enqueued between the
loop's drain and its next `wait()` would be signalled to nobody and sit until
the fallback expires.

So a boolean is set under the wake lock and cleared by the loop after it wakes.
The loop skips waiting entirely when the flag is already set. This is the
standard fix and it is what makes the change safe rather than merely faster.

### The fallback timeout stays

The loop still wakes on its own every 500 ms even with no signal. This is not
the delivery path — it is insurance against a future enqueue path that forgets
to signal. Fifty times less often than the current poll, and it keeps a missed
signal a latency blip rather than a stuck queue.

### Shutdown signals too

`disconnect()` notifies the condition. Without that, a 500 ms wait would make
shutdown *slower* than the 10 ms poll it replaces — the opposite of ADR-163 and
ADR-165, which exist to make stopping prompt and observable.

## Alternatives considered

| Option | Decision | Reason |
| --- | --- | --- |
| Leave it; the CPU cost is negligible | Rejected | Correct about CPU, wrong about the cost that matters. p50 4.8 ms per hop compounds across a chain. |
| Shorten the poll to 1 ms | Rejected | Trades a real 10× CPU increase for a partial latency fix, and still pays a poll on every message. |
| Wrap `self._lock` in the `Condition` | Rejected | Couples waiting to the drain's locking. A dedicated lock has one job. |
| Notify without a pending flag | Rejected | Loses any signal that arrives between drain and wait, which is exactly the window a busy broker spends there. |
| Drop the fallback timeout entirely | Rejected | Makes every future enqueue path a potential permanent stall. 500 ms insurance is cheap. |

## Consequences

Positive: delivery latency drops from a poll interval to a signal; the idle
loop wakes twice a second instead of a hundred times; shutdown stays prompt
because it signals too.

Negative:

- **Every enqueue path must signal.** A new one that forgets gets fallback
  latency instead of immediate delivery — degraded, not broken, which is the
  right failure direction, but it is a new obligation. A test asserts the
  paths that exist today all signal.
- **One more synchronisation primitive** in a class that already has several.
  It is confined to waking the loop and touches no delivery state.
- **The latency win is invisible in the idle-CPU number** the roadmap cited, so
  that entry is corrected rather than marked done against a claim it never met.

## Invalidation triggers

A transport whose delivery is externally driven, where there is no local loop
to wake; or a move to async delivery, which replaces the thread and the
condition together.
