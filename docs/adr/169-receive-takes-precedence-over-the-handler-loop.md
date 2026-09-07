# ADR-169: `receive()` takes precedence over the handler loop

**Date:** 2026-09-06
**Status:** accepted
**Deciders:** Chief Architect

## Context

`Agent.receive()` and `Agent._message_handler_loop` read the **same**
`message_queue`. On a started agent, whichever polls first wins, so a caller
using `receive()` gets messages *sometimes*.

It was found while writing the [ADR-165](165-waits-end-when-the-thing-they-wait-for-does.md)
tests. A test sent a message and waited for `receive()` to return it; the
handler loop ate it and the test failed with `No handler found for message type
HI`. The workaround at the time was to not start the agent — the race was
documented in the test and left in the code.

Two consumers on one queue with no arbitration is not a subtle bug. It is the
same shape as the rest of this series: something reports success it did not
achieve, or fails to, depending on timing.

## Decision

### The pull wins while it is waiting

While any `receive()` is blocked, the handler loop **defers**. A counter of
waiting receivers is incremented for the duration of the wait, and the loop
skips its own `get()` while that count is non-zero.

Precedence rather than exclusion, because a `receive()` that is not waiting
must not affect anything: the loop resumes the moment the last receiver
returns, so registering a handler keeps working for callers who never pull.

### Refusing was tried first, and is worse

The first implementation refused: `receive()` on a started agent returned
`RECEIVE_CONFLICTS_WITH_HANDLERS` rather than racing. It fails loudly, which
usually wins in this codebase.

It broke six existing tests, and the reason matters — ADR-165 exists to make a
*parked receiver on a started agent* wake when the agent stops. If `receive()`
cannot be used there at all, that capability is unreachable and the ADR-165
work becomes untestable. Refusing removes a legitimate pattern to avoid
arbitrating between two, so precedence it is.

### Deferring before the `get()` is not sufficient

Checking the counter at the top of the loop leaves a window: the loop may
already be blocked *inside* `get(timeout=...)` when a receiver arrives, and it
then consumes the very message the receiver is waiting for. Measured — the
receiver timed out at 5 s while the loop took the message.

So after a successful `get()`, the loop checks again and **hands the message
back** to the queue if a receiver is now waiting. The poll interval is also
shortened, which narrows the window rather than closing it; the hand-back is
what closes it.

## Alternatives considered

| Option | Decision | Reason |
| --- | --- | --- |
| Refuse `receive()` on a started agent | **Rejected** | Removes a legitimate pattern and makes ADR-165's wake-on-shutdown unreachable. Broke six tests for that reason. |
| Document the race and leave it | Rejected | It was already documented in a test, which is how it survived. A documented race is still a race. |
| One consumer, with `receive()` registering a pull request the loop satisfies | Deferred | The cleanest model, and a larger refactor of the delivery path than this defect justifies. Worth revisiting if pull becomes a common pattern. |
| Separate queues for push and pull | Rejected | Doubles the delivery state to arbitrate a case that a counter settles. |

## Consequences

Positive: delivery to a waiting `receive()` is deterministic rather than a coin
flip; the handler loop is unaffected when nobody is pulling; and ADR-165's
parked-receiver behaviour stays reachable.

Negative:

- **A parked receiver holds the loop off.** A caller who blocks in `receive()`
  indefinitely stops handlers from running. That is what asking to pull means,
  and the wait still ends when the agent stops (ADR-165) — but it is a way to
  starve handlers that did not exist before.
- **The hand-back can reorder.** A message returned to the queue goes to the
  back. With traffic in flight during the narrow window, ordering between that
  message and its neighbours can change. The queue never claimed ordering
  across senders, but this makes the exception explicit.
- **One more counter on the hot path.** A lock acquisition per loop iteration,
  which is cheap next to the delivery it guards.

## Invalidation triggers

A move to one consumer with an explicit pull request, which removes the
arbitration entirely; or a delivery path where handlers and receivers no longer
share a queue.
