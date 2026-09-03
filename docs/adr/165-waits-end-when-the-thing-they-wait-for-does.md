# ADR-165: Waits end when the thing they wait for does

**Date:** 2026-09-03
**Status:** accepted
**Deciders:** Chief Architect + SRE

## Context

The last Tier 2 roadmap item: *"Four sites wait without a timeout. Daemon
threads let the process exit, but a parked thread cannot observe a shutdown
flag — which is how a clean stop becomes a five-second timeout."*

Each site was probed rather than assumed, and the count was wrong in both
directions: one of the four is not a defect, and the real problem is not the
absence of a timeout.

### `Agent.receive()` — parked forever

```text
receiver parked      : True
stop() took          : 0.13s
receiver still parked: True   (after stop + 2s)
outcome              : never returned
```

A thread in `receive()` with no timeout never wakes. `stop()` returns cleanly
in 0.13 s and leaves it wedged — no error, no exception, no way to learn the
agent it is waiting on no longer exists.

### `Stream.receive()` — the same, on `close()`

```text
stream receiver parked : True
woke on close()        : False  after 2.01s
returned               : never
```

`close()` sets `self.closed`, messages subscribers and unregisters the handler.
It never touches `self.buffer`, which is what a local receiver is blocked on.

### `TaskQueue.get_next_task()` — **not a defect**

```text
taskqueue parked   : True
woke on stop       : True in 0.00s, returned=yes
```

`stop()` sets `_running = False` and calls `_condition.notify_all()`, so the
parked caller wakes immediately. This is the *correct* primitive — a condition
variable signalled by shutdown, strictly better than polling — and the roadmap
counted it as a defect because it matched a textual search for a wait with no
timeout argument. It is left alone, and the roadmap entry is corrected.

### `_complete_model_once()` — an unbounded join on a provider

`worker.join()` waits on a daemon thread collecting an LLM stream. A provider
that stalls blocks the calling thread forever. Unlike the others there is no
shutdown to observe: the thing being waited on is a network call that may
simply never end.

## Decision

### The rule: a wait ends when its subject ends

Adding arbitrary timeouts would be the wrong fix. A caller passing no timeout
is asking to wait until the message arrives, and turning that into "wait 30
seconds then fail" breaks a legitimate pattern to paper over a different bug.

The actual defect is that these waits cannot observe the **end of the thing
they are waiting for**. So:

| Wait | Ends when | On that ending |
| --- | --- | --- |
| `Agent.receive()` | the agent stops | `Result.err` with `AGENT_STOPPED` |
| `Stream.receive()` | the stream closes | `Result.err` with `STREAM_CLOSED` |
| `_complete_model_once` join | the configured provider timeout expires | `Result.err`, classified |

An indefinite wait stays indefinite while its subject is alive. That is the
part callers asked for, and it is kept.

### Waking, not polling-as-a-timeout

`receive()` waits in short slices and checks a shutdown `Event` between them.
The slice is an implementation detail, not a deadline: the call still blocks
indefinitely while the agent runs, and returns *promptly* once it does not.

The alternative — a sentinel value pushed into the queue on shutdown — was
rejected because it needs one sentinel per parked receiver to wake them all,
and a miscount leaves someone wedged. An `Event` wakes every waiter with no
bookkeeping.

**Only shutdown changes behaviour.** The event is set by `stop()` and by
`close()`, never at construction, so an agent that has not started yet still
blocks exactly as before. That matters: creating an agent, parking a receiver
thread, then starting is a real pattern, and it must not begin failing.

### The provider join is bounded by the timeout already declared

`LLMConfig.timeout` (default 120 s) is the caller's stated tolerance for that
provider. The join uses it plus a grace margin rather than inventing a number,
so in normal operation **the provider's own timeout fires first** and MAPLE's
join is a backstop for a provider that fails to honour its own deadline.

A new configuration knob was rejected: the question "how long will you wait for
this model" is already answered, and asking twice invites the two answers to
disagree.

## Alternatives considered

| Option | Decision | Reason |
| --- | --- | --- |
| Give every wait a default timeout | Rejected | Breaks the legitimate "block until it arrives" pattern, and reports a timeout for what is really a shutdown. |
| Push a sentinel into the queue on shutdown | Rejected | One per parked waiter; a miscount leaves a thread wedged. An `Event` needs no count. |
| Add a `stream_join_timeout` setting | Rejected | `LLMConfig.timeout` already states it. Two knobs for one question drift apart. |
| Also "fix" `TaskQueue` | Rejected | It is already correct. Replacing a signalled condition variable with polling would be a regression dressed as a fix. |
| Raise instead of returning `Result.err` | Rejected | These functions already return `Result`; a shutdown is an expected outcome, not an exceptional one. |

## Consequences

Positive: shutdown no longer strands threads; a parked receiver learns *why* it
woke rather than getting a bare timeout; the provider join can no longer hang a
run indefinitely.

Negative:

- **`receive()` can now return an error it never returned before.** Code that
  assumed it either returns a message or blocks forever will see
  `AGENT_STOPPED` after a stop. That is the point, but it is new.
- **Waking is not instant.** It is bounded by one slice, not by the queue's
  arrival, so a stop can take up to that slice to be observed per parked
  waiter. Measured in milliseconds against the previous "never".
- **The provider grace margin is a judgement call.** Too tight and a slow but
  healthy provider is cut off; too loose and a hung one is held longer than
  necessary. It is set relative to the configured timeout so it scales with the
  caller's own tolerance rather than being absolute.

## Invalidation triggers

A transport where receive is not queue-backed; a provider layer that grows its
own cancellation, which would make the join redundant; or any move to
non-daemon worker threads, where an unbounded join would block process exit
rather than one caller.
