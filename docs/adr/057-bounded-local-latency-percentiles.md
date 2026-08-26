# ADR-057: Bounded Local Latency Percentiles

- Status: Accepted
- Date: 2026-08-26
- Decision owners: Chief Architect, Observability, Security, QA

## Context

MAPLE exposes local integer latency totals, maxima, and averages for event
publishing and trace spans. Averages hide tail pressure, which makes local
callback/exporter and model/tool span diagnosis less useful. A full metrics
histogram or remote metrics backend would introduce a larger dependency,
retention, and transport boundary.

## Decision

Retain a bounded ring of integer-millisecond latency samples in `EventStream`
and `SpanRecorder`. The ring is capped at 4,096 entries and is further bounded
by the configured event/span capacity. Each metrics snapshot computes nearest-
rank p50, p95, and p99 values from the retained sample ring.

- Event samples measure the complete local publish path, including synchronous
  subscribers and the optional host exporter.
- Span samples are added only when a span reaches a terminal state; sampled-out
  spans do not create latency samples.
- Empty samples return zero, and all metrics remain integer-only, thread-safe,
  process-local, and JSON-compatible.
- Existing totals, maxima, averages, retention, and failure counters remain
  unchanged.

## Rejected alternatives

- Unbounded exact histories would allow an observability feature to exhaust
  process memory.
- Random reservoirs would make local tests and operator comparisons less
  deterministic.
- OpenTelemetry or a hosted metrics service belongs behind a separately
  approved exporter/dependency contract.

## Consequences

Hosts can inspect common tail latency locally without a new dependency or
remote service. Percentiles describe only the bounded retained sample window,
not a durable fleet-wide distribution. Remote aggregation, histogram export,
alerts, and percentile dashboards remain follow-on capabilities.
