# Skill: Performance

**Scope.** Latency, throughput, memory, and binary/artifact size — measured,
budgeted, and defended.

## Principles
- Measure first. Intuition about hot spots is wrong often enough that
  unprofiled optimization is gambling with readability as the stake.
- Budgets, not vibes: a target ("p95 < 50ms", "peak RSS < 200MB",
  "startup < 100ms") turns performance into a testable requirement.
- Big-O before micro-opt: the algorithm and the I/O pattern dominate;
  instruction-level cleverness comes last and must pay rent in numbers.
- Optimize the workload you actually have — realistic data shapes and
  volumes, not toy inputs.

## Defaults
- Rust: `criterion` benches for hot paths, committed with baselines;
  `--release` for any measurement; profile with flamegraphs before surgery.
- Python: `pytest-benchmark` / `timeit` for micro, `cProfile`+snakeviz or
  py-spy for macro; know when the answer is "do it in Rust" (PyO3) and
  prove the boundary cost is worth it first.
- Track allocations on hot paths: reuse buffers, preallocate with real
  capacity hints, prefer borrowing to cloning (Rust) and generators to
  materialized lists (Python) where profiles justify it.

## Do
- Capture a before-number, change one thing, capture after — in the same
  environment; report both with the method.
- Add a regression guard (bench threshold or budget test) when a hot path
  earns an optimization, so it stays earned.
- Cache with a story: invalidation rule, size bound, and a metric proving
  the hit rate — otherwise it's a memory leak with good PR.
- Load-test boundaries at 10× expected before calling scale done.

## Don't
- Don't optimize unmeasured code, and don't keep an optimization that
  didn't move its number.
- Don't trade correctness or clarity for speed without the budget demanding
  it — and write the comment explaining the crime scene when you must.
- Don't benchmark debug builds, cold caches (unless cold is the case), or
  your laptop against production claims.
- Don't let O(n²) hide behind small test fixtures.

## Review checklist
- [ ] Claimed improvements carry before/after numbers + method
- [ ] Budgets stated for perf-sensitive work; guarded in CI where feasible
- [ ] Algorithmic complexity sane for realistic n
- [ ] Caches bounded + invalidation defined
- [ ] Readability sacrifices justified by measurements, in comments

## Common failure modes
Optimizing the 2% while the 98% sleeps in an N+1; the cache that "can't
grow" and did; benchmark-driven development on toy data; perf claims from
memory instead of measurement.
