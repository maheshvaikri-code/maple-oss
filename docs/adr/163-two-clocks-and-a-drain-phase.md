# ADR-163: Two clocks, and a drain phase on shutdown

**Date:** 2026-09-02
**Status:** accepted
**Deciders:** Chief Architect + SRE

## Context

Two items sat next to each other in the roadmap's Tier 2 — wall-clock expiry and
no drain on shutdown. They are separate defects that share a surface: the agent
lifecycle. Both were measured before anything was designed.

### The clock defect, measured

`time.monotonic` appears **zero** times in `broker/`, `security/`, `error/` and
`agent/`, against **45** calls to `time.time()`. `time.time()` is the wall
clock: NTP corrects it, operators set it, and it can step backwards.

A circuit breaker with a 30-second reset window, with the clock stepped:

```text
state after 2 failures     : CircuitState.OPEN
call while open            : BLOCKED
after clock steps +1h      : ALLOWED   <-- the 30s window skipped entirely
after a real 1.2s wait     : allowed   (window genuinely elapsed)
same wait, clock steps -1h : BLOCKED   <-- held open
   time remaining reported : 3599.8 seconds
```

Both directions are wrong and neither is theoretical. Forward: a failing
dependency gets retried immediately, when the whole point of the window was to
stop hammering it. Backward: a recovered dependency stays cut off for an hour
against a configured one second — and the breaker cheerfully reports the
absurd figure itself.

### The shutdown defect, measured

40 messages sent to an agent with a 250 ms handler, `stop()` called while they
were queued:

```text
messages sent             : 40
handlers started          : 2
handlers completed        : 2
never started at all      : 38   <-- dropped from the queue
stop() returned in        : 0.11s
```

**38 of 40 messages discarded with no error, no counter, and no log.** `stop()`
returned in 0.11 s reporting success. A process restarting on deploy loses
whatever was in flight, and nothing anywhere says so.

The roadmap described this as "discards in-flight messages and abandons
submitted executor work". The measurement corrects it: work already *executing*
completed. What is lost is everything **accepted but not yet started** — which
is the larger number, and worse, because those messages were accepted with an
`Ok` result that promised nothing.

## Decision

### 1. Two clocks, chosen by purpose — not a blanket replacement

The obvious move is to replace `time.time()` with `time.monotonic()`. It is
wrong. Those 45 calls are three different things:

| Purpose | Clock | Why |
| --- | --- | --- |
| **How long has it been** — reset windows, TTLs, timeouts, staleness | `time.perf_counter` | Immune to NTP; the only correct choice for a duration. `monotonic` was the first choice and lost on resolution — see *Discovered during implementation* |
| **What time is it** — audit records, `created_at` | `time.time` | A record of when something happened in the world |
| **Interop-defined instants** — JWT `iat`/`exp` | `time.time` | RFC 7519 NumericDate is seconds since epoch, verified by other parties |

Making JWT expiry monotonic would produce tokens no standard verifier accepts.
Making an audit timestamp monotonic would record "seconds since boot" as the
time an event occurred.

**Where a field is both a record and an input to arithmetic, the wall-clock
field stays and a monotonic companion is added.** An observable field never
changes meaning. This applies to:

- `CircuitBreaker.last_failure_time` — exposed as a property by both
  `FailureDetector` and `fault_tolerance`, and surfaced in a `get_statistics()`
  dict, which now reaches the metrics exporter (ADR-162). An operator reading
  `last_failure_time` expects an epoch. It stays wall clock; the reset window
  is computed from a private monotonic deadline.
- `Link.established_at`, queue `timestamp`, routing `last_routed` — records.

The arithmetic moves to a monotonic clock in: the circuit-breaker reset window,
message TTL expiry, the queue dequeue timeout, link expiry, routing staleness,
and the agent's receive deadline — 19 sites in five modules.

### 2. Draining is the default, and it is bounded

`stop()` drains queued work before shutting down, up to a deadline.

Draining **by default** rather than on request, because silently discarding
accepted work is precisely the class of defect 2.1.0 existed to close: a
mechanism that looks like it succeeded and did not. An opt-in flag would leave
the bad behaviour as what everyone gets.

Bounded, because an unbounded drain turns a shutdown into a hang. The deadline
is a parameter, and the drain reports what it achieved rather than claiming
success:

```python
agent.stop()                    # drain with the default deadline
agent.stop(drain_timeout=30.0)  # a deployment with more patience
agent.stop(drain_timeout=0)     # the old behaviour, explicitly chosen
```

An empty queue returns immediately, so the common case — including 111
`.stop()` calls across the test suite — costs nothing.

**What remains after the deadline is reported, not swallowed.** A drain that
could not finish says how much it left behind, at WARNING. Losing messages on
shutdown may be an acceptable trade for a given deployment; losing them
*silently* never is.

### 3. The unused thread pool is removed

Every `Agent` constructs `ThreadPoolExecutor(max_workers=10)` and shuts it
down. It is referenced **nowhere else**. Measured thread counts:

```text
 1 agents running :  3 threads  (2.0 per agent)
 5 agents running : 11 threads  (2.0 per agent)
10 agents running : 21 threads  (2.0 per agent)
```

**Two threads per agent, not eleven.** `ThreadPoolExecutor` spawns workers
lazily, so a pool that is never submitted to never costs a thread. The roadmap's
Tier 3 claim — "~11 threads per agent … a hundred agents is roughly eleven
hundred threads" — is overstated by 5.5×; the real figure is about 200. That
entry is corrected rather than left to justify work that is not needed.

The executor is removed because dead code that looks like a concurrency
mechanism is worse than no code: it invites the reader to assume handlers are
dispatched in parallel, and they are not.

## Discovered during implementation

### Stopping one agent broke delivery for all of its peers

Closing intake looked like a one-liner — call `broker.disconnect()` before
draining. It is wrong twice over, and the second reason was already true before
this ADR.

Brokers are keyed by `broker_url` and **shared by every agent in that scope**
(ADR-160), while `disconnect()` stops that scope's single delivery thread. So
`agent.stop()` has always torn down delivery for every other agent on the same
bus. Measured on the unmodified tree — a peer receiving one message after an
unrelated agent stopped:

```text
main run: received []
main run: received [1]
main run: received []
```

**One run in three.** Flaky rather than absent, which is why it survived: a
test asserting delivery after an unrelated `stop()` would have failed
intermittently and been read as noise.

The first draft made it worse by moving `disconnect()` earlier. That draft
passed every targeted test and broke two autonomy server tests **only under the
full suite** — the same lesson as the 2.1.0 retrospective, that verifying the
thing changed is not the same as verifying what depends on it.

Two corrections:

- Intake closes with `broker.unsubscribe(agent_id)`, which affects only the
  stopping agent.
- `disconnect()` runs only when **no subscriber remains** on that broker, so a
  single-agent process still cleans up and a multi-agent one is left alone.

After the fix the same probe delivers 3 times in 3.

### The clock choice changed under measurement

`time.monotonic()` was the obvious call, and the roadmap named it. On Windows
its resolution is **15.625 ms**, and it advanced over a 10 ms sleep in only
**13 of 20 attempts** — a 35% flake rate for any interval shorter than a
scheduler tick. That surfaced immediately as a link-expiry test failure.

`time.perf_counter()` is also monotonic and unadjustable, at **100 ns**. It has
the property the defect actually requires — immunity to NTP steps — without the
resolution cliff, so it is used throughout.

```text
monotonic     resolution=0.015625000s  monotonic=True  adjustable=False
perf_counter  resolution=0.000000100s  monotonic=True  adjustable=False
```

### The caller re-derived the window

Fixing `CircuitBreaker` was not enough. `fault_tolerance`'s executor loop
computed its own reset window as `last_failure_time + reset_timeout` and
compared it against `time.time()`, reproducing the exact bug one layer up on a
field that must stay wall clock. `CircuitBreaker.reset_window_elapsed()` now
answers the question, and the loop asks instead of re-deriving.

## Alternatives considered

| Option | Decision | Reason |
| --- | --- | --- |
| Replace every `time.time()` with `time.monotonic()` | Rejected | Breaks JWT interop and turns audit timestamps into seconds-since-boot. The calls are three different things. |
| Repurpose `last_failure_time` as monotonic | Rejected | It is a public property on two classes and appears in exported statistics. Silently changing what a number means is the defect, not the fix. |
| Drain only when asked (`stop(drain=True)`) | Rejected | Leaves the silent data loss as the default everyone gets. |
| Drain without a deadline | Rejected | Converts a shutdown into a hang when a handler is slow or stuck. |
| Keep the executor and use it for handler dispatch | Deferred | A real change to the concurrency model with its own ordering and back-pressure questions. Out of scope here; removing dead code is not the moment to add parallelism. |

## Consequences

Positive: reset windows, TTLs and timeouts survive an NTP correction; a deploy
no longer discards accepted work without saying so; the observable timestamp
surface is unchanged, so ADR-162's exported metrics keep meaning what they say.

Negative:

- **`stop()` can now take longer.** Bounded by the deadline, and instant on an
  empty queue, but a caller that assumed `stop()` was immediate will notice.
  `drain_timeout=0` restores the old behaviour explicitly.
- **Two clocks is more to hold in your head.** The rule is stated once and
  applies everywhere: durations are monotonic, records are wall clock.
- **A monotonic deadline does not survive a process restart.** Nothing here
  needs it to — every one of these is in-process state — but a future durable
  or cross-host equivalent must re-derive its deadlines rather than carry them.

## Invalidation triggers

Any of these expiry values becoming durable or crossing a process boundary,
where a monotonic reading is meaningless; a decision to dispatch handlers
concurrently, which reopens the executor question; or a transport whose
shutdown semantics make a local drain insufficient.
