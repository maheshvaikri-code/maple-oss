# ADR-162: Metrics export without a dependency

**Date:** 2026-09-02
**Status:** accepted
**Deciders:** Chief Architect + SRE

## Context

Thirteen modules implement `get_statistics()` — broker, queue, routing, pub/sub,
request/response, audit, authentication, authorization, three state modules, and
the S2 adapter. None of it leaves the process. There is no Prometheus endpoint,
no OpenTelemetry, no statsd.

2.1.0 sharpened the problem. The broker now reports `refused` — messages
declined as backpressure — which is the earliest honest signal that producers
are outrunning consumers, and precisely the number an operator needs to alert
on. It is unreachable without writing glue.

The roadmap ranks this first: smallest change, largest operator benefit.

### What makes it awkward

The statistics dictionaries were written for humans reading a REPL, not for a
metrics system:

```text
broker : {'delivered': 0, 'refused': 0, 'maxQueueSize': 10000, ...}     camelCase
queue  : {'messages_queued': 0, 'queue_type': 'priority', ...}          snake_case + a string
auth   : {'active_tokens': 0, 'supported_methods': ['jwt', ...]}        a list
```

Three problems: inconsistent naming, non-numeric values that are not metrics at
all, and no declaration of which numbers are counters and which are gauges.

## Decision

### No new dependency

`standards/dependency-policy.md` sets zero-runtime-dependency as the preferred
state for a library MAPLE ships, and asks what a dependency does that ~50 lines
of owned code would not. The Prometheus text exposition format is a documented,
stable, line-oriented format. Emitting it is well under that bar, and
`prometheus_client` would pull a dependency into every install for the benefit
of the minority who scrape.

The OpenTelemetry SDK is a larger commitment still, with its own release cadence
and transitive tree. Neither is taken.

### MAPLE renders; the host serves

MAPLE does not start an HTTP server, bind a port, or own a scrape endpoint.
That is deployment, which the operational boundary already assigns to the host —
the same line that keeps TLS, credentials and network exposure outside the
library.

`render_prometheus()` returns a string. The host serves it from whatever it
already runs: an existing web framework, `RunServer`, or a three-line
`http.server`. A host wanting OpenTelemetry or statsd reads `collect()` and
forwards; the sample objects are plain data with no MAPLE types in them.

### Types are declared, not guessed

A counter mislabelled as a gauge silently breaks `rate()`; a gauge mislabelled
as a counter produces nonsense. Guessing from the name would be wrong often
enough to matter, and wrong quietly.

Known keys are declared in one table in the metrics module. **Unknown numeric
keys default to gauge**, which is the safe direction: a gauge on a counter is
merely less useful, while a counter on a gauge is actively misleading.

Non-numeric values — `queue_type`, `supported_methods` — are **skipped**, not
coerced. Booleans are exported as `1`/`0` because that is a real signal.

### Names are normalised

Prometheus names are `snake_case` with a namespace prefix. `maxQueueSize`
becomes `maple_broker_max_queue_size`. The transformation is mechanical and
tested, so a source can keep its own convention without leaking it into the
metrics namespace.

## Shape

```python
from maple.monitoring import MetricsRegistry, render_prometheus

registry = MetricsRegistry()
registry.register("broker", agent.broker.get_statistics)

text = render_prometheus(registry)      # ready to serve at /metrics
samples = registry.collect()            # or forward wherever you like
```

```text
# HELP maple_broker_refused Messages the broker declined as backpressure.
# TYPE maple_broker_refused counter
maple_broker_refused 0
# TYPE maple_broker_subscribed_agents gauge
maple_broker_subscribed_agents 3
```

A source is a **callable**, not a snapshot, so the registry stays correct as
state changes and holds no reference to stale data.

## Alternatives considered

| Option | Decision | Reason |
|---|---|---|
| Depend on `prometheus_client` | Rejected | A runtime dependency for every install to benefit those who scrape. The exposition format is ~50 lines to emit. |
| Depend on the OpenTelemetry SDK | Rejected | Larger commitment, own cadence, transitive tree. Offered as a seam over `collect()` instead. |
| Ship a `/metrics` HTTP server | Rejected | Binding a port is deployment, which the operational boundary assigns to the host. A library that opens a socket by surprise is a bad neighbour. |
| Change all 13 `get_statistics()` to return typed metrics | Rejected | Invasive, breaks a public surface people already read, for a benefit one adapter layer delivers. |
| Infer counter/gauge from key names | Rejected | Wrong often enough to matter, and wrong silently. Declared table with a gauge default instead. |
| Auto-register every component | Deferred | Registration is explicit so the host decides what it exposes. Convenience helpers can follow once real usage shows what is wanted. |

## Consequences

Positive: `refused` and the rest become reachable with three lines and no new
dependency; the exported surface is plain data, so OTel, statsd and JSON
consumers are all a short function away; naming and typing become consistent
without touching the sources.

Negative:

- **The host must serve it.** There is no endpoint out of the box, which will
  surprise anyone expecting `prometheus_client`'s `start_http_server`. The
  README and the production guide state it.
- **The declaration table needs maintenance.** A new key in a `get_statistics()`
  is exported as a gauge until someone declares otherwise. A test asserts every
  key the broker currently emits is declared, so the omission surfaces in CI
  rather than in a dashboard.
- **No histograms.** The sources expose counters and gauges only;
  `average_wait_time` is a pre-computed mean, which cannot be re-aggregated
  correctly across instances. Exported as a gauge and documented as such rather
  than dressed up as a summary.

## Discovered during implementation

Two defects surfaced while building this that the decision above did not
anticipate. Both are recorded because both are the *same shape* as the bugs
2.1.0 existed to fix: a mechanism that looks correct and silently is not.

### `%g` is lossy, and quietly

The obvious way to render a float is `f"{value:g}"`. It defaults to six
significant digits, so the broker's `max_message_bytes` of **1048576 exported
as `1.04858e+06`** — which reads back as 1048580. A metric reporting a
different number than its source is worse than no metric, and nothing about the
output looks wrong.

Integral values now render as integers and the rest use `repr`, which
round-trips a float exactly. Caught by reading the first real output rather than
by a test, which is why a round-trip parse is now among the tests.

### A duplicate series poisons the entire scrape

Prometheus rejects a whole scrape containing the same series twice. Two
registrations of one subsystem with no distinguishing labels produce exactly
that:

```text
maple_broker_delivered 1
maple_broker_delivered 5
```

The consequence is disproportionate to the mistake: one careless
double-registration takes down **every** metric, not the ambiguous one. The
registry now keeps the first of any repeated `(name, labels)` pair.

Dropping it silently would repeat the pattern this module exists to close, so
each collision is warned about once — not per scrape, which would flood the log
— and counted.

### Health counters for the exporter itself

Both fixes share a conclusion the original decision missed: **the exporter needs
to report on its own failures.** A source that raises is skipped so metrics can
never crash a process, but a subsystem whose metrics silently disappear is
indistinguishable from one that was never registered.

`<namespace>_metrics_source_errors` (labelled by subsystem) and
`<namespace>_metrics_duplicate_series` are exported alongside the statistics,
**including zeros** — a counter that appears only after its first failure cannot
be alerted on before it, and an absent series looks identical to a healthy one.
A registry with no sources registered still renders nothing at all.

## Invalidation triggers

A source that needs histogram or exemplar semantics; a decision to accept a
metrics dependency; or any move to have MAPLE own a listening socket, which
would reopen the boundary question rather than this one.
