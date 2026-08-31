# Skill: Concurrency & Async

**Scope.** Threads, tasks, async runtimes, channels, locks — everywhere
two things can be true at once and both need to be correct.

## Principles
- Prefer not sharing: message passing and immutable data beat locks.
  The cheapest lock is the one the design made unnecessary.
- When you must share: one clear owner, one documented guard. Every
  public type states its thread-safety — safe / not-safe /
  externally-synchronized. Undocumented is unsafe.
- Structured concurrency: tasks have scopes, scopes have owners, and
  nothing outlives its scope unnoticed.
- Cancellation is cooperative and must propagate. A task that can't be
  cancelled is a leak with a thread attached.
- Deadlocks are design bugs, not bad luck. Where multiple locks exist,
  acquisition order is documented and enforced.
- A data race that "works" is still a BLOCKER. Racy code is broken code
  observed on a lucky schedule.

## Defaults
- Bounded queues and channels everywhere; backpressure over buffering.
  An unbounded channel is an OOM on layaway.
- Deadlines and timeouts travel with the request across every hop;
  spawned work inherits the caller's budget, not a fresh one.
- Sync I/O and CPU-heavy work move to a worker pool; the event loop /
  async runtime stays free to schedule.
- Async by necessity, not fashion: a function is colored async because
  it awaits, not because the ecosystem is trendy.
- Race detection in the test matrix — Go race detector, TSan, Rust loom,
  Python threading stress — per stack, wired into CI
  (see `skills/testing.md`).

## Do
- Name the owner of every piece of shared mutable state at its
  declaration; guard and owner live together.
- Make cancellation points explicit in long loops and between I/O calls.
- Test shutdown: everything spawned is awaited, drained, or cancelled —
  no orphan tasks after the scope closes.
- Prefer per-task state plus a merge step over shared accumulation.

## Don't
- Don't hold a lock across an await point or any blocking call.
- Don't fire-and-forget: detached tasks vanish with their errors.
- Don't add "just one more lock" to fix a race — find the owner.
- Don't sleep as synchronization; races don't heal, they hide.
- Don't share a non-thread-safe client across tasks because it "seems
  fine" — check its documented contract first.

## Review checklist
- [ ] Thread-safety stated on every public type touched
- [ ] All spawned work scoped: awaited, cancelled, or explicitly owned
- [ ] Cancellation propagates; deadlines travel with the request
- [ ] Queues and channels bounded; backpressure path exists
- [ ] No lock held across await/blocking calls; lock order documented
- [ ] Race detector run clean; any race treated as BLOCKER

## Common failure modes
The detached task that outlives its request and writes to a dead
connection; a lock held across an await, deadlocking only under load;
unbounded channels absorbing a slow consumer until the OOM killer
arbitrates; cancellation "supported" but never propagated past the first
hop; the race that passed a thousand test runs and then shipped.
