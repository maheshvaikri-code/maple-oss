# ADR-054: Local observability sampling and latency metrics

**Date:** 2026-08-26  
**Status:** accepted  
**Deciders:** Chief Architect

## Context

MAPLE's local span recorder and event stream expose bounded retention metrics,
but hosts cannot reduce span volume or distinguish callback/exporter pressure
from ordinary retention eviction. Framework integrations need a local,
dependency-free way to sample trace spans and inspect coarse latency without
silently changing agent behavior.

## Decision

We will add an optional `SpanRecorder(sample_rate=...)` control. The rate is a
finite number from `0.0` through `1.0`; `1.0` preserves current behavior. A
stable SHA-256 bucket over bounded trace/span identity inputs makes the
decision without global random state. A sampled-out span returns the typed
`SPAN_SAMPLED_OUT` result and does not enter retention; callers such as the
agent already treat observability drops as non-fatal. Parent linkage is only
available for spans retained by the recorder.

The local metrics snapshots also report completed-span counts, integer
millisecond total/maximum/average latency, terminal error/cancellation counts,
and sampled-out spans. `EventStream.metrics()` reports accepted event count,
subscriber/exporter failures, and integer millisecond publish latency totals,
maximum, and average. These are process-local inspection counters; they do not
export, persist, or schedule work.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Stable local sampling and scalar latency counters (chosen) | Deterministic tests, no global RNG, no dependency or transport | Coarse integer latency and no percentile view | Fits the current local observability boundary |
| Random sampling | Familiar tracing model | Global RNG coupling and nondeterministic tests | Unnecessary for a local bounded contract |
| Add OpenTelemetry or metrics backend | Rich exporters, histograms, and dashboards | Dependency, configuration, credentials, and remote failure surface | Deferred until exporter and dependency governance are approved |

## Consequences

- Positive: hosts can cap local span volume, identify sampled-out work, and
  observe callback/exporter pressure without reading payloads or private state.
- Negative / debt accepted: sampling is span-local, latency is integer and
  process-local, and there are no percentiles, queue-depth guarantees, or
  remote delivery semantics.
- Invalidation triggers: a requirement for trace-consistent tail sampling,
  percentile histograms, durable counters, or fleet-wide export would reopen
  this contract.
