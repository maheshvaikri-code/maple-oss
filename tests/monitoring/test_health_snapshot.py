"""Tests for HealthMonitor.snapshot() -- an immediate, on-demand health summary.

MAPLE improvement #3 (proposed; revalidate with owner). A just-started monitor can be read
the instant it exists (from its accumulated counters), instead of 'no_data' until the
background loop's first collection_interval.
"""

from maple.monitoring.health_monitor import HealthMonitor


class TestSnapshot:
    def test_snapshot_is_immediate_and_never_no_data(self):
        m = HealthMonitor("c")  # NOT started -> no sampled record in history
        snap = m.snapshot()
        assert snap["status"] != "no_data"
        assert {"status", "uptime", "message_rate", "error_rate", "avg_response_time"} <= set(snap)

    def test_snapshot_reflects_recorded_counters_immediately(self):
        m = HealthMonitor("c")
        for _ in range(4):
            m.record_message(0.01)
        m.record_error()
        snap = m.snapshot()
        assert snap["message_rate"] >= 0 and snap["error_rate"] >= 0  # live rates
        assert snap["avg_response_time"] == 0.01  # the recorded processing time

    def test_get_health_summary_falls_back_to_on_demand_no_data_gone(self):
        # the sampled path still works, but a fresh monitor no longer returns no_data
        assert HealthMonitor("c").get_health_summary()["status"] != "no_data"

    def test_snapshot_status_is_a_valid_live_status(self):
        snap = HealthMonitor("c").snapshot()
        assert snap["status"] in ("healthy", "degraded", "warning", "unhealthy")
