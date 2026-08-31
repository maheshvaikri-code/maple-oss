# Skill: Data Engineering

**Scope.** Batch and streaming pipelines, warehousing, and the datasets
they produce — ingestion through serving, orchestration included.

## Principles
- Pipelines are idempotent and replayable: reprocessing a day is safe and
  produces the same result. Deterministic transforms; no wall-clock logic
  inside a transform — the run date is an input, not `now()`.
- Schema contracts at every boundary: producers version, consumers pin,
  breaking changes are migrations with a deprecation window — not
  surprises discovered downstream.
- Silent bad data is worse than no data. Quality checks are the pipeline's
  tests (the data form of "behavior changes ship with tests") and they
  fail loudly.
- Delivery semantics are explicit per stage. At-least-once delivery into
  an idempotent sink beats an "exactly-once" claim you can't audit.
- Late and out-of-order data is handled by design — watermarks and a
  stated lateness policy — not by hope.

## Defaults
- Partition by time; the partition is the unit of reprocessing.
- Quality gates in the DAG: freshness, volume anomaly, null/dupe rates,
  referential integrity — a failing check blocks downstream consumers.
- Orchestration as explicit DAGs with retries, timeouts, and alerts wired
  per `skills/observability.md`; dependencies declared, no cron-and-pray.
- Lineage: every derived dataset names its sources and its owner, in
  metadata a human can query.
- PII minimized/pseudonymized at ingestion per
  `skills/privacy-compliance.md` — never "scrubbed later" downstream,
  because downstream copies multiply.

## Do
- Treat backfills as first-class operations: declared, bounded, monitored,
  and rate-limited so they never blindly eat production capacity.
- Write transforms as pure functions of (input partitions, run date); test
  them on fixture partitions including empty and duplicate-heavy ones.
- Make sinks idempotent: upsert by key or overwrite the partition —
  append-only sinks turn every retry into duplicate rows.
- Cost the pipeline in review: storage, scan, and compute. A change that
  doubles the warehouse bill is a finding, same as a perf regression.

## Don't
- Don't put `now()` or wall-clock branches in a transform; replays will
  diverge from the original run.
- Don't auto-widen schemas on read to paper over a producer's break.
- Don't mark a run green when quality checks failed — a dashboard fed by
  bad data is a lie with uptime.
- Don't report a backfill "done" without row-count/checksum evidence —
  derived confidence isn't verified (doctrine honesty rules).
- Don't ship an unowned dataset; no owner means no one notices decay.

## Review checklist
- [ ] Replay-safe: deterministic, run-date-as-input, idempotent sink
- [ ] Schema contract versioned; breaking changes staged as migrations
- [ ] Quality checks (freshness/volume/null/dupe/RI) in-DAG and blocking
- [ ] Lateness policy and delivery semantics stated per stage
- [ ] Backfill plan bounded and monitored; capacity impact stated
- [ ] Lineage + owner recorded; storage/compute cost delta noted

## Common failure modes
A transform keyed on `now()` that backfills garbage; an upstream schema
"tweak" nulling a column for a week before anyone looks; retries doubling
rows into an append-only sink; a backfill saturating the warehouse during
business hours; ten dashboards green over data that stopped arriving on
Tuesday.
