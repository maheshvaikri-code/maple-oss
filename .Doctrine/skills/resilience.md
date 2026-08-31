# Skill: Resilience

**Scope.** Staying up when dependencies don't — timeouts, retries, breakers,
bulkheads, shedding, degradation, and shipping risky change progressively.

## Principles
- A timeout is part of every call's contract. No unbounded waits, anywhere;
  a call without a deadline is a lock without an owner.
- Retry storms are self-inflicted DDoS. Retries amplify load exactly when
  the system can least afford it — budget them like money.
- Graceful degradation is designed, not discovered. Every feature names its
  fallback in advance: cached answer, reduced feature, or honest error.
- Backpressure beats buffering. An unbounded queue converts overload into
  a later, larger outage with an out-of-memory bonus.
- An untested fallback is a rumor. The breaker path, the cache path, the
  shed response — exercise them deliberately or assume they don't work.

## Defaults
- Timeouts on every network call, tuned per dependency; deadlines propagate
  across hops so a doomed request dies early everywhere, not just locally.
- Retries only on idempotent operations: exponential backoff + jitter,
  bounded attempts, and a retry budget per dependency. The retry/no-retry
  decision is explicit per call (see `standards/error-handling.md`).
- Circuit breakers on any dependency that can brown-out: open fast, probe
  gently, emit a metric on every state change.
- Bulkheads — separate pools (connections, threads, semaphores) per
  dependency, so one slow downstream can't drain everything.
- Rate limiting and load shedding at the boundary: shed early and cheaply
  with a clear signal — 429 + Retry-After, never a silent hang.

## Do
- Define automatic rollback criteria BEFORE the deploy: metrics,
  thresholds, observation window. Canary or percentage rollout for
  anything risky; the criteria decide, not vibes.
- Put risky changes behind feature flags — ship/kill switches with a named
  owner and an expiry date, evaluated at one place in the code.
- Inject failure on purpose: kill the dependency in staging, force the
  breaker open, and verify the fallback actually serves.
- Distinguish shed load from errors in metrics; shedding that looks like
  failure poisons your rollback signals.

## Don't
- Don't retry non-idempotent operations — a double charge is worse than a
  failed one.
- Don't let a flag outlive its expiry date: a stale flag is dead code with
  root access.
- Don't buffer what you cannot bound; reject at the edge instead.
- Don't promote a canary because it "looked fine" — only the pre-declared
  criteria promote.
- Don't meet your degraded mode for the first time in production.

## Review checklist
- [ ] Every external call: timeout set, deadline propagated across hops
- [ ] Retries idempotent-only, with backoff + jitter + budget
- [ ] Breakers/bulkheads on brown-out-capable dependencies, with metrics
- [ ] Boundary sheds load early with 429 + Retry-After, cheaply
- [ ] Fallback named per feature and exercised by a test or drill
- [ ] Rollout plan: flag/canary + automatic rollback criteria pre-declared

## Common failure modes
The missing timeout that turned one slow dependency into thread-pool
exhaustion everywhere; synchronized retries hammering a recovering service
back down; the flag from last quarter nobody dares delete; a canary judged
by eyeball; fallback code that had never run once until the night it
mattered — and didn't.
