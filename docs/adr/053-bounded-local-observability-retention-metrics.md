# ADR-053: Bounded local observability retention metrics

**Date:** 2026-08-26  
**Status:** accepted  
**Deciders:** Chief Architect

## Context

MAPLE's local `EventStream` and `SpanRecorder` already use bounded rings, but
hosts cannot inspect retention pressure consistently. The event stream exposes
only a single eviction count, while the span recorder exposes only its current
count. Operators need enough local signal to detect dropped history and open
span pressure without introducing a metrics backend, sampling policy, or
remote transport.

## Decision

We will expose a thread-safe `metrics()` snapshot on both local observability
buffers. The snapshot contains only bounded integer counts and configured
capacities: retained items, evictions, open spans where applicable, and event
subscriber count. It is an inspection surface only; it does not sample,
export, persist, or change retention behavior, and it adds no dependency.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Local integer snapshot (chosen) | Immediate host visibility, bounded, dependency-free | No aggregation or alert delivery | Fits the current local buffer boundary and can be tested deterministically |
| Add a metrics dependency/exporter | Ecosystem dashboards and aggregation | New dependency, transport, credentials, and failure surface | Deferred until hosted observability and dependency governance are approved |
| Keep only `dropped_count` | No code change | Omits span pressure and subscriber/capacity context | Too little signal to diagnose local backpressure |

## Consequences

- Positive: hosts can detect local retention pressure and open-span buildup
  without reading private state or parsing event/span payloads.
- Negative / debt accepted: sampling controls, histograms, latency metrics,
  remote aggregation, and exporter delivery remain separate contracts.
- Invalidation triggers: a requirement for fleet-wide aggregation, percentile
  latency, or host-configurable sampling would reopen this local snapshot.
