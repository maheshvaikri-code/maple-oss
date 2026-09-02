# Copyright (C) 2025 Mahesh Vaijainthymala Krishnamoorthy
# (Mahesh Vaikri)
#
# This file is part of MAPLE - Multi Agent Protocol Language Engine.
#
# MAPLE - Multi Agent Protocol Language Engine is free software: you can
# redistribute it and/or modify it under the terms of the GNU Affero General
# Public License as published by the Free Software Foundation, either version 3
# of the License, or (at your option) any later version.
# MAPLE - Multi Agent Protocol Language Engine is distributed in the hope that
# it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty
# of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero
# General Public License for more details. You should have received a copy of
# the GNU Affero General Public License along with MAPLE - Multi Agent Protocol
# Language Engine. If not, see <https://www.gnu.org/licenses/>.
"""Export MAPLE's statistics without taking a dependency (ADR-162).

Thirteen modules implement ``get_statistics()`` and none of it left the
process. This turns those dictionaries into metrics an operator can scrape or
forward, using only the standard library.

MAPLE renders; the host serves. There is no HTTP server here and no port is
bound - that is deployment, which the operational boundary assigns to the host.

    from maple.monitoring import MetricsRegistry, render_prometheus

    registry = MetricsRegistry()
    registry.register("broker", agent.broker.get_statistics)

    text = render_prometheus(registry)   # serve this at /metrics
    samples = registry.collect()         # or forward them anywhere

``refused`` is the number worth alerting on: sustained non-zero means producers
are outrunning consumers.
"""

from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple

__all__ = [
    "MetricType",
    "Sample",
    "MetricsRegistry",
    "render_prometheus",
    "normalize_name",
]


class MetricType:
    """Prometheus metric types this module emits."""

    COUNTER = "counter"
    GAUGE = "gauge"


#: Keys whose semantics are known. Everything else defaults to GAUGE, because a
#: gauge on a counter is merely less useful while a counter on a gauge is
#: actively misleading - it makes rate() produce nonsense.
#:
#: Keyed by the *normalized* key name, so a source may use camelCase or
#: snake_case without changing anything here.
_DECLARED_COUNTERS = frozenset(
    {
        # broker delivery accounting (ADR-159)
        "delivered",
        "undeliverable",
        "refused",
        # queue lifecycle
        "messages_queued",
        "messages_dequeued",
        "messages_dropped",
        "messages_expired",
        "messages_retried",
        "total_queued",
        "total_dequeued",
        # communication
        "messages_sent",
        "messages_received",
        "messages_failed",
        "requests_sent",
        "responses_received",
        "requests_timeout",
        "published_messages",
        "delivered_messages",
        # security
        "expired_tokens",
        "revoked_tokens",
        "events_logged",
        "events_dropped",
        # state
        "reads",
        "writes",
        "conflicts",
        "syncs",
    }
)

#: One-line descriptions for keys worth explaining. Absent keys emit no HELP,
#: which is valid exposition rather than a placeholder nobody wrote.
_HELP: Dict[str, str] = {
    "delivered": "Messages delivered to at least one handler.",
    "undeliverable": "Messages that reached zero handlers.",
    "undeliverable_receivers": "Distinct receivers that had no handler.",
    "refused": "Messages the broker declined as backpressure.",
    "pending_fallback": "Messages held in the fallback queue.",
    "max_queue_size": "Configured admission limit, in messages.",
    "max_message_bytes": "Configured per-message payload limit, in bytes.",
    "subscribed_agents": "Agents with a live subscription.",
}

logger = logging.getLogger(__name__)

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_ILLEGAL = re.compile(r"[^a-zA-Z0-9_]+")


def normalize_name(key: str) -> str:
    """Turn a statistics key into a Prometheus-legal metric name fragment.

    ``maxQueueSize`` -> ``max_queue_size``. Sources keep their own convention;
    it does not leak into the metrics namespace.
    """
    spaced = _CAMEL_BOUNDARY.sub("_", str(key))
    cleaned = _ILLEGAL.sub("_", spaced).strip("_").lower()
    cleaned = re.sub(r"_+", "_", cleaned)
    return cleaned


@dataclass(frozen=True)
class Sample:
    """One exported measurement.

    Plain data with no MAPLE types in it, so forwarding to OpenTelemetry,
    statsd or JSON is a short function rather than an integration.
    """

    name: str
    value: float
    metric_type: str = MetricType.GAUGE
    labels: Mapping[str, str] = field(default_factory=dict)
    help_text: Optional[str] = None


def _coerce(value: Any) -> Optional[float]:
    """Return a numeric value, or None when this is not a metric.

    Strings like ``queue_type='priority'`` and lists like
    ``supported_methods=[...]`` are skipped rather than coerced - a label or a
    cardinality explosion dressed up as a measurement helps nobody. Booleans
    are exported, because on/off is a real signal.
    """
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        # NaN and infinities are legal in the exposition format but almost
        # always indicate a bug upstream; pass them through rather than hide.
        return float(value)
    return None


class MetricsRegistry:
    """Collects statistics from registered sources on demand.

    A source is a **callable** returning a dict, not a snapshot, so the
    registry stays correct as state changes and never holds stale data.

    Thread-safe: registration and collection take a lock, and sources are
    invoked outside it so a slow source cannot block registration.
    """

    #: Prefix applied to every exported metric.
    namespace = "maple"

    def __init__(self, namespace: str = "maple") -> None:
        self.namespace = namespace
        self._lock = threading.Lock()
        self._sources: List[
            Tuple[str, Callable[[], Mapping[str, Any]], Dict[str, str]]
        ] = []
        self._errors: Dict[Tuple[str, Tuple[Tuple[str, str], ...]], int] = {}
        self._duplicates = 0
        self._warned_duplicates: set = set()

    def register(
        self,
        subsystem: str,
        source: Callable[[], Mapping[str, Any]],
        labels: Optional[Mapping[str, str]] = None,
    ) -> None:
        """Register a ``get_statistics``-style callable under a subsystem name.

        ``subsystem`` becomes part of the metric name:
        ``maple_<subsystem>_<key>``. ``labels`` are attached to every sample
        from this source - useful for a scope or agent id.
        """
        if not callable(source):
            raise TypeError("source must be callable, not a snapshot")
        with self._lock:
            self._sources.append(
                (normalize_name(subsystem), source, dict(labels or {}))
            )

    def unregister(self, subsystem: str) -> None:
        """Remove every source registered under a subsystem. Idempotent."""
        target = normalize_name(subsystem)
        with self._lock:
            self._sources = [s for s in self._sources if s[0] != target]

    def clear(self) -> None:
        with self._lock:
            self._sources = []
            self._errors = {}
            self._duplicates = 0
            self._warned_duplicates = set()

    @property
    def subsystems(self) -> List[str]:
        with self._lock:
            return [name for name, _, _ in self._sources]

    def collect(self) -> List[Sample]:
        """Snapshot every source.

        A source that raises is skipped rather than allowed to break the whole
        collection - metrics must never be the reason a process fails.

        Skipping it silently would be its own defect, though: the subsystem's
        metrics would simply stop appearing, which reads identically to a
        subsystem that was never registered. Every failure is counted and
        exported as ``<namespace>_metrics_source_errors``, so a broken source
        is visible in the same place an operator is already looking.
        """
        with self._lock:
            sources = list(self._sources)

        samples: List[Sample] = []
        for subsystem, source, labels in sources:
            try:
                stats = source()
            except Exception:  # noqa: BLE001 - collection must not raise
                self._record_error(subsystem, labels)
                logger.debug(
                    "Metrics source %r raised; its metrics are omitted from "
                    "this collection.",
                    subsystem,
                    exc_info=True,
                )
                continue
            if not isinstance(stats, Mapping):
                self._record_error(subsystem, labels)
                logger.debug(
                    "Metrics source %r returned %s, not a mapping.",
                    subsystem,
                    type(stats).__name__,
                )
                continue
            for key, raw in stats.items():
                value = _coerce(raw)
                if value is None:
                    continue
                short = normalize_name(key)
                samples.append(
                    Sample(
                        name=f"{self.namespace}_{subsystem}_{short}",
                        value=value,
                        metric_type=(
                            MetricType.COUNTER
                            if short in _DECLARED_COUNTERS
                            else MetricType.GAUGE
                        ),
                        labels=labels,
                        help_text=_HELP.get(short),
                    )
                )

        samples = self._drop_duplicate_series(samples)
        samples.extend(self._error_samples(sources))
        if sources:
            # A registry with nothing registered renders nothing; the health
            # counters describe registered sources, and there are none.
            samples.append(
                Sample(
                    name=f"{self.namespace}_metrics_duplicate_series",
                    value=float(self._duplicates),
                    metric_type=MetricType.COUNTER,
                    help_text=(
                        "Samples dropped because an identical series was "
                        "already present in the same collection."
                    ),
                )
            )
        return samples

    def _drop_duplicate_series(self, samples: List[Sample]) -> List[Sample]:
        """Keep the first of any repeated (name, labels) pair.

        Prometheus rejects an entire scrape that contains the same series
        twice, so emitting both would take down *all* metrics rather than
        just the ambiguous one. Two registrations of one subsystem with no
        distinguishing labels produce exactly that, and so does a source whose
        dict holds two keys that normalize alike.

        Dropping silently would repeat the mistake this module exists to fix,
        so each collision is warned about once and counted in
        ``<namespace>_metrics_duplicate_series``.
        """
        seen: set = set()
        kept: List[Sample] = []
        for sample in samples:
            series = (sample.name, tuple(sorted(sample.labels.items())))
            if series in seen:
                with self._lock:
                    self._duplicates += 1
                    first_time = series not in self._warned_duplicates
                    self._warned_duplicates.add(series)
                if first_time:
                    logger.warning(
                        "Duplicate metric series %s%s - keeping the first and "
                        "dropping the rest. Give each source distinct labels, "
                        "or register it once.",
                        sample.name,
                        dict(sample.labels) or "",
                    )
                continue
            seen.add(series)
            kept.append(sample)
        return kept

    def _record_error(self, subsystem: str, labels: Mapping[str, str]) -> None:
        key = (subsystem, tuple(sorted(labels.items())))
        with self._lock:
            self._errors[key] = self._errors.get(key, 0) + 1

    def _error_samples(
        self,
        sources: List[Tuple[str, Callable[[], Mapping[str, Any]], Dict[str, str]]],
    ) -> List[Sample]:
        """One error counter per registered source, zero included.

        A counter that appears only once it is non-zero cannot be alerted on
        before the first failure, and an absent series is indistinguishable
        from a healthy one. Zeros are exported for that reason.

        The subsystem is a *label* here rather than part of the name, unlike
        every other metric, so that failures across subsystems aggregate in
        one query.
        """
        with self._lock:
            errors = dict(self._errors)

        seen: set = set()
        out: List[Sample] = []
        for subsystem, _, labels in sources:
            key = (subsystem, tuple(sorted(labels.items())))
            if key in seen:
                continue
            seen.add(key)
            out.append(
                Sample(
                    name=f"{self.namespace}_metrics_source_errors",
                    value=float(errors.get(key, 0)),
                    metric_type=MetricType.COUNTER,
                    labels=dict(labels, subsystem=subsystem),
                    help_text=(
                        "Times a registered statistics source raised or "
                        "returned a non-mapping during collection."
                    ),
                )
            )
        return out


def _format_value(value: float) -> str:
    """Render a value without losing it.

    ``%g`` was the obvious choice and it is wrong: it defaults to six
    significant digits, so 1048576 exports as ``1.04858e+06`` - which reads
    back as 1048580. A metric that reports a different number than the source
    is worse than no metric.

    Integral values render as integers; everything else uses ``repr``, which
    round-trips a float exactly.
    """
    if value != value:  # NaN
        return "NaN"
    if value == float("inf"):
        return "+Inf"
    if value == float("-inf"):
        return "-Inf"
    if float(value).is_integer() and abs(value) < 2**53:
        return str(int(value))
    return repr(float(value))


def _escape_label(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def render_prometheus(source: Any) -> str:
    """Render samples in the Prometheus text exposition format.

    Accepts a ``MetricsRegistry`` or any iterable of ``Sample``. The result is
    a string; serving it is the host's business (ADR-162).
    """
    samples: Iterable[Sample]
    samples = source.collect() if isinstance(source, MetricsRegistry) else source

    lines: List[str] = []
    described: set = set()

    for sample in samples:
        if sample.name not in described:
            if sample.help_text:
                lines.append(f"# HELP {sample.name} {sample.help_text}")
            lines.append(f"# TYPE {sample.name} {sample.metric_type}")
            described.add(sample.name)

        if sample.labels:
            rendered = ",".join(
                f'{normalize_name(k)}="{_escape_label(v)}"'
                for k, v in sorted(sample.labels.items())
            )
            lines.append(f"{sample.name}{{{rendered}}} {_format_value(sample.value)}")
        else:
            lines.append(f"{sample.name} {_format_value(sample.value)}")

    # The exposition format requires a trailing newline.
    return "\n".join(lines) + "\n" if lines else "\n"
