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
"""Metrics export (ADR-162).

The tests that matter most here are the ones about *fidelity*: a metric that
reports a different number than its source is worse than no metric, and a
counter mislabelled as a gauge breaks rate() silently.
"""

import contextlib
import logging as _logging
import threading
import time

import pytest

from maple.monitoring.metrics import (
    _DECLARED_COUNTERS,
    _HELP,
    MetricsRegistry,
    MetricType,
    Sample,
    _coerce,
    _format_value,
    normalize_name,
    render_prometheus,
)


@contextlib.contextmanager
def caplog_at(level):
    """Capture records from the metrics logger regardless of pytest config."""
    records = []

    class _Collect(_logging.Handler):
        def emit(self, record):
            records.append(record)

    logger = _logging.getLogger("maple.monitoring.metrics")
    handler = _Collect(level=level)
    previous_level, previous_propagate = logger.level, logger.propagate
    logger.addHandler(handler)
    logger.setLevel(level)
    try:
        yield records
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)
        logger.propagate = previous_propagate


ERRORS = "maple_metrics_source_errors"
DUPES = "maple_metrics_duplicate_series"


def stats_only(samples):
    """The samples that came from sources, without the registry's own health
    counter. Tests about statistics assert on these."""
    return [
        s
        for s in samples
        if not s.name.endswith("_metrics_source_errors")
        and not s.name.endswith("_metrics_duplicate_series")
    ]


def names(samples):
    return [s.name for s in stats_only(samples)]


# --------------------------------------------------------------------------
# Name normalization
# --------------------------------------------------------------------------


class TestNormalizeName:
    """Sources keep their own convention; it must not leak into the namespace."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("maxQueueSize", "max_queue_size"),
            ("undeliverableReceivers", "undeliverable_receivers"),
            ("pendingFallback", "pending_fallback"),
            ("messages_queued", "messages_queued"),
            ("delivered", "delivered"),
            ("HTTPRequests", "httprequests"),
            ("queue.size", "queue_size"),
            ("queue-size", "queue_size"),
            ("  spaced  out ", "spaced_out"),
            ("__leading", "leading"),
            ("trailing__", "trailing"),
            ("a__b___c", "a_b_c"),
            ("size2Bytes", "size2_bytes"),
        ],
    )
    def test_normalizes(self, raw, expected):
        assert normalize_name(raw) == expected

    def test_result_is_prometheus_legal(self):
        for raw in ("maxQueueSize", "queue.type!", "a b c", "%weird%"):
            name = normalize_name(raw)
            assert name.replace("_", "").isalnum() or name == ""
            assert not name.startswith("_")

    def test_non_string_keys_do_not_explode(self):
        assert normalize_name(42) == "42"


# --------------------------------------------------------------------------
# Value coercion - what is a metric and what is not
# --------------------------------------------------------------------------


class TestCoerce:
    def test_numbers_pass_through(self):
        assert _coerce(3) == 3.0
        assert _coerce(2.5) == 2.5
        assert _coerce(-1) == -1.0

    def test_booleans_export_as_one_and_zero(self):
        # on/off is a real signal, unlike a free-text status
        assert _coerce(True) == 1.0
        assert _coerce(False) == 0.0

    @pytest.mark.parametrize(
        "value",
        [
            "priority",  # queue_type
            ["jwt", "api_key"],  # supported_methods
            {"a": 1},
            None,
            object(),
        ],
    )
    def test_non_numeric_is_skipped_not_coerced(self, value):
        assert _coerce(value) is None


# --------------------------------------------------------------------------
# Value formatting - the fidelity guarantee
# --------------------------------------------------------------------------


class TestFormatValue:
    def test_large_integers_are_exact(self):
        """%g would render this 1.04858e+06, which reads back as 1048580."""
        assert _format_value(1048576.0) == "1048576"
        assert float(_format_value(1048576.0)) == 1048576.0

    @pytest.mark.parametrize("value", [0, 1, -1, 10000, 1048576, 999999999, 2**40])
    def test_integral_values_round_trip_exactly(self, value):
        assert float(_format_value(float(value))) == float(value)
        assert "e" not in _format_value(float(value)).lower()

    @pytest.mark.parametrize("value", [0.5, 1.25, -0.001, 1.5e-9, 3.14159265358979])
    def test_fractional_values_round_trip_exactly(self, value):
        assert float(_format_value(value)) == value

    def test_special_values_use_prometheus_spellings(self):
        assert _format_value(float("nan")) == "NaN"
        assert _format_value(float("inf")) == "+Inf"
        assert _format_value(float("-inf")) == "-Inf"

    def test_integral_rendering_stops_where_float_precision_does(self):
        # beyond 2**53 an integer is not exactly representable, so rendering it
        # as an integer would invent digits
        assert "." in _format_value(float(2**53))


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------


class TestMetricsRegistry:
    def test_register_and_collect(self):
        registry = MetricsRegistry()
        registry.register("broker", lambda: {"delivered": 7})
        samples = stats_only(registry.collect())
        assert len(samples) == 1
        assert samples[0].name == "maple_broker_delivered"
        assert samples[0].value == 7.0

    def test_source_is_called_each_collect_not_snapshotted(self):
        state = {"delivered": 1}
        registry = MetricsRegistry()
        registry.register("broker", lambda: state)
        assert stats_only(registry.collect())[0].value == 1.0
        state["delivered"] = 99
        assert stats_only(registry.collect())[0].value == 99.0

    def test_snapshot_is_rejected_at_registration(self):
        registry = MetricsRegistry()
        with pytest.raises(TypeError, match="callable"):
            registry.register("broker", {"delivered": 1})

    def test_raising_source_is_skipped_and_others_still_collect(self):
        """Metrics must never be the reason a process fails."""

        def boom():
            raise RuntimeError("statistics exploded")

        registry = MetricsRegistry()
        registry.register("broken", boom)
        registry.register("healthy", lambda: {"delivered": 3})

        assert names(registry.collect()) == ["maple_healthy_delivered"]

    def test_non_mapping_return_is_skipped(self):
        registry = MetricsRegistry()
        registry.register("odd", lambda: ["not", "a", "mapping"])
        registry.register("good", lambda: {"x": 1})
        assert names(registry.collect()) == ["maple_good_x"]

    def test_labels_are_attached_to_every_sample_from_a_source(self):
        registry = MetricsRegistry()
        registry.register(
            "broker", lambda: {"delivered": 1, "refused": 2}, labels={"scope": "a"}
        )
        for sample in stats_only(registry.collect()):
            assert sample.labels == {"scope": "a"}

    def test_two_sources_same_subsystem_different_labels(self):
        registry = MetricsRegistry()
        registry.register("broker", lambda: {"delivered": 1}, labels={"scope": "a"})
        registry.register("broker", lambda: {"delivered": 5}, labels={"scope": "b"})
        samples = stats_only(registry.collect())
        assert len(samples) == 2
        assert {s.labels["scope"]: s.value for s in samples} == {"a": 1.0, "b": 5.0}

    def test_unregister_removes_every_source_for_a_subsystem(self):
        registry = MetricsRegistry()
        registry.register("broker", lambda: {"a": 1}, labels={"scope": "x"})
        registry.register("broker", lambda: {"a": 2}, labels={"scope": "y"})
        registry.register("queue", lambda: {"b": 3})
        registry.unregister("broker")
        assert names(registry.collect()) == ["maple_queue_b"]

    def test_unregister_is_idempotent(self):
        registry = MetricsRegistry()
        registry.unregister("never-registered")
        registry.unregister("never-registered")
        assert registry.collect() == []

    def test_subsystem_name_is_normalized_on_both_paths(self):
        registry = MetricsRegistry()
        registry.register("Broker Pool", lambda: {"a": 1})
        assert registry.subsystems == ["broker_pool"]
        registry.unregister("Broker Pool")
        assert registry.subsystems == []

    def test_clear(self):
        registry = MetricsRegistry()
        registry.register("broker", lambda: {"a": 1})
        registry.clear()
        assert registry.collect() == []
        assert registry.subsystems == []

    def test_custom_namespace(self):
        registry = MetricsRegistry(namespace="acme")
        registry.register("broker", lambda: {"delivered": 1})
        assert stats_only(registry.collect())[0].name == "acme_broker_delivered"

    def test_non_numeric_values_never_become_samples(self):
        registry = MetricsRegistry()
        registry.register(
            "queue",
            lambda: {
                "messages_queued": 4,
                "queue_type": "priority",
                "supported_methods": ["jwt"],
            },
        )
        assert names(registry.collect()) == ["maple_queue_messages_queued"]

    def test_concurrent_registration_and_collection_is_safe(self):
        registry = MetricsRegistry()
        errors = []

        def register_many():
            try:
                for i in range(50):
                    registry.register("s{}".format(i), lambda: {"v": 1})
            except Exception as exc:  # pragma: no cover - failure path
                errors.append(exc)

        def collect_many():
            try:
                for _ in range(50):
                    registry.collect()
            except Exception as exc:  # pragma: no cover - failure path
                errors.append(exc)

        threads = [threading.Thread(target=register_many) for _ in range(3)]
        threads += [threading.Thread(target=collect_many) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert errors == []

    def test_a_slow_source_does_not_hold_the_registration_lock(self):
        """Sources are invoked outside the lock."""
        release = threading.Event()
        registry = MetricsRegistry()

        def slow():
            release.wait(timeout=5)
            return {"v": 1}

        registry.register("slow", slow)
        collector = threading.Thread(target=registry.collect)
        collector.start()
        time.sleep(0.1)

        started = time.monotonic()
        registry.register("fast", lambda: {"v": 2})  # must not block
        elapsed = time.monotonic() - started

        release.set()
        collector.join(timeout=5)
        assert elapsed < 1.0


# --------------------------------------------------------------------------
# A source that breaks must not break quietly
# --------------------------------------------------------------------------


class TestCollectionFailuresAreVisible:
    """Skipping a raising source keeps the process alive; skipping it
    *silently* makes a broken subsystem look like an unregistered one."""

    def test_a_raising_source_increments_its_error_counter(self):
        def boom():
            raise RuntimeError("statistics exploded")

        registry = MetricsRegistry()
        registry.register("broken", boom)

        errors = [s for s in registry.collect() if s.name == ERRORS]
        assert len(errors) == 1
        assert errors[0].value == 1.0
        assert errors[0].metric_type == MetricType.COUNTER
        assert errors[0].labels["subsystem"] == "broken"

    def test_the_counter_accumulates_across_collections(self):
        def boom():
            raise RuntimeError("still broken")

        registry = MetricsRegistry()
        registry.register("broken", boom)
        for _ in range(3):
            registry.collect()
        errors = [s for s in registry.collect() if s.name == ERRORS]
        assert errors[0].value == 4.0

    def test_a_non_mapping_return_counts_as_a_failure_too(self):
        registry = MetricsRegistry()
        registry.register("odd", lambda: ["not", "a", "mapping"])
        errors = [s for s in registry.collect() if s.name == ERRORS]
        assert errors[0].value == 1.0

    def test_healthy_sources_export_a_zero_not_nothing(self):
        """An absent series is indistinguishable from a healthy one, so the
        counter is initialised rather than created on first failure."""
        registry = MetricsRegistry()
        registry.register("healthy", lambda: {"delivered": 1})
        errors = [s for s in registry.collect() if s.name == ERRORS]
        assert len(errors) == 1
        assert errors[0].value == 0.0

    def test_the_failing_source_is_identifiable_among_healthy_ones(self):
        def boom():
            raise RuntimeError("only this one")

        registry = MetricsRegistry()
        registry.register("broken", boom)
        registry.register("healthy", lambda: {"delivered": 1})

        by_subsystem = {
            s.labels["subsystem"]: s.value
            for s in registry.collect()
            if s.name == ERRORS
        }
        assert by_subsystem == {"broken": 1.0, "healthy": 0.0}

    def test_source_labels_are_preserved_so_the_right_instance_is_named(self):
        def boom():
            raise RuntimeError("scope b is broken")

        registry = MetricsRegistry()
        registry.register("broker", lambda: {"delivered": 1}, labels={"scope": "a"})
        registry.register("broker", boom, labels={"scope": "b"})

        by_scope = {
            s.labels["scope"]: s.value for s in registry.collect() if s.name == ERRORS
        }
        assert by_scope == {"a": 0.0, "b": 1.0}

    def test_the_subsystem_is_a_label_so_failures_aggregate_in_one_query(self):
        registry = MetricsRegistry()
        registry.register("one", lambda: {"a": 1})
        registry.register("two", lambda: {"b": 2})
        errors = [s for s in registry.collect() if s.name == ERRORS]
        assert len({s.name for s in errors}) == 1, "one metric name, many series"
        assert len(errors) == 2

    def test_a_raising_source_is_logged_for_diagnosis(self, caplog):
        import logging

        def boom():
            raise RuntimeError("the cause an operator needs")

        registry = MetricsRegistry()
        registry.register("broken", boom)
        with caplog.at_level(logging.DEBUG, logger="maple.monitoring.metrics"):
            registry.collect()

        assert any("broken" in record.message for record in caplog.records)
        assert any(record.exc_info for record in caplog.records)

    def test_clear_resets_the_error_ledger(self):
        def boom():
            raise RuntimeError("x")

        registry = MetricsRegistry()
        registry.register("broken", boom)
        registry.collect()
        registry.clear()
        registry.register("broken", lambda: {"a": 1})
        errors = [s for s in registry.collect() if s.name == ERRORS]
        assert errors[0].value == 0.0

    def test_error_counter_renders_with_help_and_type(self):
        registry = MetricsRegistry()
        registry.register("healthy", lambda: {"delivered": 1})
        text = render_prometheus(registry)
        assert f"# TYPE {ERRORS} counter" in text
        assert f"# HELP {ERRORS} " in text
        assert f'{ERRORS}{{subsystem="healthy"}} 0' in text

    def test_the_namespace_applies_to_the_error_counter(self):
        registry = MetricsRegistry(namespace="acme")
        registry.register("healthy", lambda: {"a": 1})
        names_seen = {s.name for s in registry.collect()}
        assert "acme_metrics_source_errors" in names_seen


# --------------------------------------------------------------------------
# A duplicate series would poison the whole scrape
# --------------------------------------------------------------------------


class TestDuplicateSeries:
    """Prometheus rejects an entire scrape containing the same series twice.
    Emitting both would take down every metric, not just the ambiguous one."""

    def test_the_same_subsystem_registered_twice_yields_one_series(self):
        registry = MetricsRegistry()
        registry.register("broker", lambda: {"delivered": 1})
        registry.register("broker", lambda: {"delivered": 5})

        delivered = [
            s for s in registry.collect() if s.name == "maple_broker_delivered"
        ]
        assert len(delivered) == 1
        assert delivered[0].value == 1.0, "the first registration wins"

    def test_keys_that_normalize_alike_collapse_to_one_series(self):
        registry = MetricsRegistry()
        registry.register("b", lambda: {"maxQueueSize": 10, "max_queue_size": 20})
        rendered = [
            line
            for line in render_prometheus(registry).splitlines()
            if line.startswith("maple_b_max_queue_size")
        ]
        assert len(rendered) == 1

    def test_dropped_duplicates_are_counted(self):
        registry = MetricsRegistry()
        registry.register("broker", lambda: {"delivered": 1})
        registry.register("broker", lambda: {"delivered": 5})
        dupes = [s for s in registry.collect() if s.name == DUPES]
        assert len(dupes) == 1
        assert dupes[0].value == 1.0
        assert dupes[0].metric_type == MetricType.COUNTER

    def test_the_counter_is_zero_rather_than_absent_when_all_is_well(self):
        registry = MetricsRegistry()
        registry.register("broker", lambda: {"delivered": 1})
        dupes = [s for s in registry.collect() if s.name == DUPES]
        assert len(dupes) == 1 and dupes[0].value == 0.0

    def test_distinct_labels_are_not_duplicates(self):
        registry = MetricsRegistry()
        registry.register("broker", lambda: {"delivered": 1}, labels={"scope": "a"})
        registry.register("broker", lambda: {"delivered": 5}, labels={"scope": "b"})
        delivered = [
            s for s in registry.collect() if s.name == "maple_broker_delivered"
        ]
        assert len(delivered) == 2
        assert [s for s in registry.collect() if s.name == DUPES][0].value == 0.0

    def test_a_collision_is_warned_about_once_not_every_scrape(self):
        import logging

        registry = MetricsRegistry()
        registry.register("broker", lambda: {"delivered": 1})
        registry.register("broker", lambda: {"delivered": 5})

        with caplog_at(logging.WARNING) as records:
            for _ in range(5):
                registry.collect()

        warnings = [r for r in records if "Duplicate metric series" in r.getMessage()]
        assert len(warnings) == 1, "a per-scrape warning would flood the log"

    def test_rendered_output_has_no_repeated_series(self):
        registry = MetricsRegistry()
        registry.register("broker", lambda: {"delivered": 1, "refused": 2})
        registry.register("broker", lambda: {"delivered": 9, "refused": 8})

        series = [
            line.split(" ")[0]
            for line in render_prometheus(registry).splitlines()
            if line and not line.startswith("#")
        ]
        assert len(series) == len(set(series)), "a repeat would fail the scrape"

    def test_clear_resets_the_duplicate_ledger(self):
        registry = MetricsRegistry()
        registry.register("broker", lambda: {"delivered": 1})
        registry.register("broker", lambda: {"delivered": 5})
        registry.collect()
        registry.clear()
        registry.register("broker", lambda: {"delivered": 1})
        assert [s for s in registry.collect() if s.name == DUPES][0].value == 0.0


# --------------------------------------------------------------------------
# Type classification
# --------------------------------------------------------------------------


class TestMetricTypes:
    def test_declared_counters_are_counters(self):
        registry = MetricsRegistry()
        registry.register("broker", lambda: {"delivered": 1, "refused": 2})
        for sample in stats_only(registry.collect()):
            assert sample.metric_type == MetricType.COUNTER

    def test_unknown_keys_default_to_gauge(self):
        """A counter on a gauge is actively misleading; a gauge on a counter
        is merely less useful. Default in the safe direction."""
        registry = MetricsRegistry()
        registry.register("broker", lambda: {"something_nobody_declared": 1})
        assert stats_only(registry.collect())[0].metric_type == MetricType.GAUGE

    def test_classification_uses_the_normalized_name(self):
        """A camelCase source key still matches a snake_case declaration."""
        registry = MetricsRegistry()
        registry.register("comm", lambda: {"messagesSent": 5})
        sample = stats_only(registry.collect())[0]
        assert sample.name == "maple_comm_messages_sent"
        assert sample.metric_type == MetricType.COUNTER

    def test_configured_limits_are_gauges_not_counters(self):
        registry = MetricsRegistry()
        registry.register("broker", lambda: {"maxQueueSize": 10000})
        assert stats_only(registry.collect())[0].metric_type == MetricType.GAUGE


# --------------------------------------------------------------------------
# Prometheus exposition format
# --------------------------------------------------------------------------


class TestRenderPrometheus:
    def test_shape_of_a_described_metric(self):
        text = render_prometheus(
            [
                Sample(
                    name="maple_broker_refused",
                    value=3,
                    metric_type=MetricType.COUNTER,
                    help_text="Messages the broker declined as backpressure.",
                )
            ]
        )
        assert text == (
            "# HELP maple_broker_refused Messages the broker declined as"
            " backpressure.\n"
            "# TYPE maple_broker_refused counter\n"
            "maple_broker_refused 3\n"
        )

    def test_accepts_a_registry_or_an_iterable_of_samples(self):
        registry = MetricsRegistry()
        registry.register("broker", lambda: {"delivered": 2})
        from_registry = render_prometheus(registry)
        from_samples = render_prometheus(registry.collect())
        assert from_registry == from_samples

    def test_help_and_type_are_emitted_once_per_metric_name(self):
        samples = [
            Sample(
                "maple_broker_delivered", 1, MetricType.COUNTER, {"scope": "a"}, "H"
            ),
            Sample(
                "maple_broker_delivered", 2, MetricType.COUNTER, {"scope": "b"}, "H"
            ),
        ]
        text = render_prometheus(samples)
        assert text.count("# TYPE maple_broker_delivered") == 1
        assert text.count("# HELP maple_broker_delivered") == 1
        assert text.count("maple_broker_delivered{") == 2

    def test_metric_without_help_emits_type_only(self):
        text = render_prometheus([Sample("maple_x_y", 1)])
        assert "# HELP" not in text
        assert "# TYPE maple_x_y gauge" in text

    def test_labels_are_sorted_for_stable_output(self):
        text = render_prometheus(
            [Sample("m", 1, labels={"zebra": "1", "alpha": "2", "middle": "3"})]
        )
        assert 'm{alpha="2",middle="3",zebra="1"} 1' in text

    def test_label_names_are_normalized(self):
        text = render_prometheus([Sample("m", 1, labels={"agentId": "a1"})])
        assert 'agent_id="a1"' in text

    @pytest.mark.parametrize(
        "raw,escaped",
        [
            ('quote"inside', 'quote\\"inside'),
            ("back\\slash", "back\\\\slash"),
            ("new\nline", "new\\nline"),
        ],
    )
    def test_label_values_are_escaped(self, raw, escaped):
        text = render_prometheus([Sample("m", 1, labels={"k": raw})])
        assert 'k="{}"'.format(escaped) in text

    def test_output_always_ends_with_a_newline(self):
        assert render_prometheus([Sample("m", 1)]).endswith("\n")
        assert render_prometheus([]) == "\n"

    def test_empty_registry_renders_valid_empty_exposition(self):
        assert render_prometheus(MetricsRegistry()) == "\n"

    def test_values_survive_a_round_trip_through_the_text_format(self):
        """Parse the rendered text back and compare against the source."""
        stats = {
            "delivered": 3,
            "maxMessageBytes": 1048576,
            "maxQueueSize": 10000,
            "ratio": 0.125,
        }
        registry = MetricsRegistry()
        registry.register("broker", lambda: stats)
        text = render_prometheus(registry)

        parsed = {}
        for line in text.splitlines():
            if not line or line.startswith("#"):
                continue
            name, _, value = line.rpartition(" ")
            if name.startswith(ERRORS) or name.startswith(DUPES):
                continue
            parsed[name] = float(value)

        assert parsed == {
            "maple_broker_delivered": 3.0,
            "maple_broker_max_message_bytes": 1048576.0,
            "maple_broker_max_queue_size": 10000.0,
            "maple_broker_ratio": 0.125,
        }

    def test_booleans_render_as_one_and_zero(self):
        registry = MetricsRegistry()
        registry.register("broker", lambda: {"running": True, "stopped": False})
        text = render_prometheus(registry)
        assert "maple_broker_running 1" in text
        assert "maple_broker_stopped 0" in text


class TestSample:
    def test_sample_is_immutable(self):
        sample = Sample("m", 1)
        with pytest.raises(Exception):
            sample.value = 2  # type: ignore[misc]

    def test_defaults_to_gauge_with_no_labels(self):
        sample = Sample("m", 1)
        assert sample.metric_type == MetricType.GAUGE
        assert sample.labels == {}
        assert sample.help_text is None


# --------------------------------------------------------------------------
# The guard ADR-162 promised: declarations must not fall behind the sources
# --------------------------------------------------------------------------


class TestDeclarationsKeepUpWithSources:
    """ADR-162: "A test asserts every key the broker currently emits is
    declared, so the omission surfaces in CI rather than in a dashboard."

    A new key in get_statistics() is exported as an undocumented gauge until
    someone declares it. That is a quiet failure, so it is made loud here.
    """

    def _broker_statistics(self):
        from maple import Agent, Config
        from maple.broker.broker import MessageBroker

        MessageBroker.reset_scopes()
        agent = Agent(Config(agent_id="declares", broker_url="memory://declares"))
        agent.start()
        try:
            return dict(agent.broker.get_statistics())
        finally:
            agent.stop()
            MessageBroker.reset_scopes()

    def test_every_broker_key_is_declared(self):
        undeclared = sorted(
            normalize_name(key)
            for key, value in self._broker_statistics().items()
            if _coerce(value) is not None
            and normalize_name(key) not in _HELP
            and normalize_name(key) not in _DECLARED_COUNTERS
        )
        assert undeclared == [], (
            "These broker statistics have no declaration in maple/monitoring/"
            "metrics.py and would export as undocumented gauges: {}. "
            "Add them to _HELP (and to _DECLARED_COUNTERS if they only "
            "rise).".format(undeclared)
        )

    def test_the_adr_159_counters_are_typed_as_counters(self):
        stats = self._broker_statistics()
        for key in ("delivered", "undeliverable", "refused"):
            assert key in stats, "broker no longer reports {}".format(key)
            assert normalize_name(key) in _DECLARED_COUNTERS

    def test_declared_help_text_is_present_and_single_line(self):
        for key, text in _HELP.items():
            assert text.strip(), "{} has empty help".format(key)
            assert "\n" not in text, "{} help breaks the exposition format".format(key)


# --------------------------------------------------------------------------
# Against the real runtime
# --------------------------------------------------------------------------


class TestAgainstARealBroker:
    def test_refused_is_reachable_as_a_counter_after_backpressure(self):
        """The number 2.1.0 added and an operator needs to alert on."""
        import logging

        from maple import Agent, Config
        from maple.agent.config import PerformanceConfig
        from maple.broker.broker import MessageBroker
        from maple.core.message import Message

        logging.disable(logging.CRITICAL)
        MessageBroker.reset_scopes()
        agent = Agent(
            Config(
                agent_id="pressed",
                broker_url="memory://pressed",
                performance=PerformanceConfig(max_queue_size=3),
            )
        )
        agent.start()
        try:
            for i in range(40):
                agent.send(
                    Message(message_type="X", receiver="nobody", payload={"i": i})
                )

            registry = MetricsRegistry()
            registry.register(
                "broker",
                agent.broker.get_statistics,
                labels={"scope": "memory://pressed"},
            )
            samples = {s.name: s for s in registry.collect()}

            refused = samples["maple_broker_refused"]
            assert refused.value > 0, "backpressure did not register"
            assert refused.metric_type == MetricType.COUNTER
            assert refused.labels == {"scope": "memory://pressed"}

            text = render_prometheus(registry)
            assert "# TYPE maple_broker_refused counter" in text
            assert 'maple_broker_refused{scope="memory://pressed"} ' in text
            # the configured limit exports exactly, not in scientific notation
            assert 'maple_broker_max_queue_size{scope="memory://pressed"} 3' in text
        finally:
            agent.stop()
            MessageBroker.reset_scopes()
            logging.disable(logging.NOTSET)

    def test_every_get_statistics_implementer_renders_without_error(self):
        """Thirteen modules implement it; none may break the renderer."""
        from maple.broker.queue import MessageQueue
        from maple.security.audit import AuditLogger
        from maple.security.authentication import AuthenticationManager
        from maple.state.store import StateStore

        registry = MetricsRegistry()
        registry.register("queue", MessageQueue(max_size=10).get_statistics)
        registry.register("audit", AuditLogger().get_statistics)
        registry.register("auth", AuthenticationManager().get_statistics)
        registry.register("state", StateStore().get_statistics)

        text = render_prometheus(registry)
        assert text.endswith("\n")
        for line in text.splitlines():
            if line.startswith("#") or not line:
                continue
            name, _, value = line.rpartition(" ")
            assert name, "unnamed metric in {!r}".format(line)
            float(value)  # every emitted value must parse as a number

    def test_string_and_list_statistics_are_dropped_not_rendered(self):
        from maple.broker.queue import MessageQueue

        stats = MessageQueue(max_size=10).get_statistics()
        assert isinstance(stats.get("queue_type"), str), "fixture assumption changed"

        registry = MetricsRegistry()
        registry.register("queue", MessageQueue(max_size=10).get_statistics)
        text = render_prometheus(registry)
        assert "queue_type" not in text
        assert "priority" not in text
