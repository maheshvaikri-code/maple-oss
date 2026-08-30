# Skill: Backend

**Scope.** Services, handlers, business logic, background jobs, internal
libraries — the code between the boundary and the store.

## Principles
- Layers with one-way arrows: boundary (parse/validate) → logic (pure as
  possible) → effects (I/O at the edges). Logic that doesn't touch I/O is
  logic you can actually test.
- Parse, don't validate: convert raw input into typed structures once, at
  the boundary; everything inward trusts the types.
- Every external interaction is a failure waiting politely: timeout, error
  mapping, and an explicit retry/no-retry decision, per call.
- Idempotency is a design decision, made consciously for anything that can
  be delivered twice (webhooks, queues, retried requests).

## Defaults
- Configuration via environment with typed parsing at startup; fail fast on
  missing/invalid config with a message naming the variable.
- Structured errors (see `standards/error-handling.md`): typed in Rust
  (`thiserror` for libs, `anyhow` context in bins), exception hierarchy
  rooted per-package in Python.
- Pagination on every list endpoint from day one; hard caps on sizes,
  depths, and counts of everything user-influenced.
- Time: store and compute in UTC; convert at the display edge; never parse
  local times without a zone.

## Do
- Keep handlers thin: decode → call logic → encode. Logic lives in
  functions that don't know HTTP exists.
- Make invariants explicit — assert them, test them (property tests where
  the logic has algebra: roundtrips, ordering, idempotence).
- Treat append-only/hash-chained artifacts as transactions: compute
  content and hashes prospectively in memory, touch disk only after ALL
  validation passes — a rejected input leaves zero mutations.
- Reference files by content hash wherever integrity matters: existence
  is not evidence (empty files exist) and mtime is not an authority
  signal (clones reset it, attackers forge it) — order and trust come
  from the data, never the filesystem.
- Bound every queue, buffer, and cache. Unbounded = incident scheduled.
- Log at boundaries with correlation IDs; keep logic layers quiet.

## Don't
- Don't swallow errors, ever. Handle, wrap-with-context, or propagate.
- Don't share mutable state across requests without a documented, tested
  concurrency story.
- Don't call the network inside a database transaction.
- Don't build a plugin system, event bus, or "engine" for one use case.
- Don't reach for a framework when the stdlib server/library suffices.

## Review checklist
- [ ] Boundary validation total; interior code trusts types only
- [ ] Every external call: timeout + mapped errors + retry decision
- [ ] Idempotency stated for re-deliverable operations
- [ ] Invariants tested (property tests where applicable)
- [ ] Resource bounds on user-influenced allocations

## Common failure modes
Validation sprinkled everywhere and complete nowhere; retry storms without
backoff/jitter; catch-log-continue corruption; config read lazily deep in
the call stack, failing at 2 a.m. instead of at boot.
