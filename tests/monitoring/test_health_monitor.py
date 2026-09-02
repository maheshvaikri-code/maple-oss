"""Tests for maple.monitoring.health_monitor - ComponentHealthMonitor."""

import time

import pytest

from maple.monitoring.health_monitor import (
    ComponentHealthMetrics,
    ComponentHealthMonitor,
)


@pytest.fixture
def monitor():
    return ComponentHealthMonitor("test_component", collection_interval=0.1)


class TestHealthMetrics:
    """Test ComponentHealthMetrics dataclass."""

    def test_create(self):
        m = ComponentHealthMetrics(
            agent_id="a1",
            timestamp=1000.0,
            cpu_usage=25.0,
            memory_usage=512.0,
            message_rate=100.0,
            error_rate=0.01,
            response_time_avg=0.05,
            uptime=3600.0,
            connection_status="connected",
        )
        assert m.agent_id == "a1"
        assert m.cpu_usage == 25.0
        assert m.connection_status == "connected"


class TestHealthMonitorInit:
    """Test monitor initialization."""

    def test_defaults(self, monitor):
        assert monitor.component_id == "test_component"
        assert monitor.running is False
        assert monitor.message_count == 0
        assert monitor.error_count == 0

    def test_custom_interval(self):
        m = ComponentHealthMonitor("comp", collection_interval=60.0)
        assert m.collection_interval == 60.0


class TestRecording:
    """Test metric recording."""

    def test_record_message(self, monitor):
        monitor.record_message()
        assert monitor.message_count == 1

    def test_record_message_with_time(self, monitor):
        monitor.record_message(processing_time=0.05)
        assert monitor.message_count == 1
        assert len(monitor.response_times) == 1

    def test_record_error(self, monitor):
        monitor.record_error()
        assert monitor.error_count == 1

    def test_multiple_recordings(self, monitor):
        for _ in range(10):
            monitor.record_message(processing_time=0.1)
        monitor.record_error()
        monitor.record_error()
        assert monitor.message_count == 10
        assert monitor.error_count == 2


class TestGetCurrentMetrics:
    """Test current metrics retrieval."""

    def test_get_metrics(self, monitor):
        monitor.record_message(processing_time=0.1)
        monitor.record_message(processing_time=0.2)
        time.sleep(0.01)  # Ensure measurable uptime on Windows
        metrics = monitor.get_current_metrics()
        assert isinstance(metrics, ComponentHealthMetrics)
        assert metrics.agent_id == "test_component"
        assert metrics.uptime >= 0
        assert metrics.message_rate >= 0
        assert metrics.response_time_avg == pytest.approx(0.15, abs=0.01)
        assert metrics.connection_status == "connected"

    def test_metrics_with_no_messages(self, monitor):
        metrics = monitor.get_current_metrics()
        assert metrics.message_rate == 0
        assert metrics.response_time_avg == 0.0

    def test_error_rate(self, monitor):
        monitor.record_error()
        # Ensure some uptime has elapsed so error_rate = error_count/uptime > 0
        monitor.start_time = time.time() - 1.0  # simulate 1s of uptime
        metrics = monitor.get_current_metrics()
        assert metrics.error_rate > 0


class TestCallbacks:
    """Test health metric callbacks."""

    def test_add_callback(self, monitor):
        def cb(metrics):
            pass

        monitor.add_callback(cb)
        assert len(monitor.callbacks) == 1


class TestLifecycle:
    """Test start/stop."""

    def test_start_stop(self, monitor):
        monitor.start()
        assert monitor.running is True
        time.sleep(0.15)
        monitor.stop()
        assert monitor.running is False

    def test_metrics_collected_during_run(self, monitor):
        monitor.start()
        time.sleep(0.25)
        monitor.stop()
        assert len(monitor.metrics_history) >= 1


class TestHealthSummary:
    """Test health summary."""

    def test_fresh_monitor_reports_live_not_no_data(self):
        # BEHAVIOR CHANGE (MAPLE improvement #3, revalidate with owner): a monitor with no
        # SAMPLED record no longer returns 'no_data' -- get_health_summary falls back to an
        # on-demand read, so a just-started monitor reports live metrics (zero rates ->
        # 'healthy'), never the misleading 'no_data'.
        from maple.monitoring.health_monitor import ComponentHealthMonitor

        summary = ComponentHealthMonitor("fresh").get_health_summary()
        assert summary["status"] != "no_data"
        assert summary["status"] == "healthy"
        assert summary["message_rate"] == 0 and summary["error_rate"] == 0

    def test_healthy(self, monitor):
        # Record some normal activity
        for _ in range(5):
            monitor.record_message(processing_time=0.01)
        metrics = monitor.get_current_metrics()
        monitor.metrics_history.append(metrics)

        summary = monitor.get_health_summary()
        assert summary["status"] == "healthy"
        assert "uptime" in summary
        assert "message_rate" in summary

    def test_unhealthy_high_error_rate(self):
        m = ComponentHealthMonitor("test_err", collection_interval=0.1)
        # Record many errors
        for _ in range(1000):
            m.record_error()
        # Ensure uptime is 1s so error_rate = 1000/1 = 1000 >> 0.1
        m.start_time = time.time() - 1.0
        metrics = m.get_current_metrics()
        assert metrics.error_rate > 0.1
        m.metrics_history.append(metrics)

        summary = m.get_health_summary()
        assert summary["status"] == "unhealthy"


class TestPublicSurface:
    """The module was unreachable from the public API until ADR-158."""

    def test_exported_from_package_root(self):
        import maple
        from maple.monitoring.health_monitor import (
            ComponentHealthMetrics,
            ComponentHealthMonitor,
        )

        assert maple.ComponentHealthMonitor is ComponentHealthMonitor
        assert maple.ComponentHealthMetrics is ComponentHealthMetrics

    def test_legacy_deep_import_names_still_resolve(self):
        """The old names were reachable by deep import; keep them working."""
        from maple.monitoring.health_monitor import (
            ComponentHealthMetrics,
            ComponentHealthMonitor,
            HealthMetrics,
            HealthMonitor,
        )

        assert HealthMonitor is ComponentHealthMonitor
        assert HealthMetrics is ComponentHealthMetrics

    def test_does_not_collide_with_the_discovery_health_monitor(self):
        """Same name, different job - the collision ADR-158 resolved."""
        from maple.discovery.health_monitor import HealthMonitor as DiscoveryMonitor
        from maple.monitoring.health_monitor import ComponentHealthMonitor

        assert ComponentHealthMonitor is not DiscoveryMonitor
