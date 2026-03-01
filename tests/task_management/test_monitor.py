"""Tests for maple.task_management.monitor - TaskMonitor."""

import pytest
import time
from maple.task_management.task_queue import TaskQueue, TaskPriority
from maple.task_management.monitor import TaskMonitor


@pytest.fixture
def task_queue():
    tq = TaskQueue(max_queue_size=100)
    tq.start()
    yield tq
    tq.stop()


@pytest.fixture
def monitor(task_queue):
    return TaskMonitor(task_queue)


class TestMonitorLifecycle:
    """Test monitor start/stop."""

    def test_start_stop(self, monitor):
        monitor.start_monitoring()
        monitor.stop_monitoring()


class TestTaskMonitoring:
    """Test task monitoring operations."""

    def test_start_task_monitoring(self, monitor, task_queue):
        r = task_queue.submit_task("compute", {}, priority=TaskPriority.NORMAL)
        task_id = r.unwrap()

        result = monitor.start_task_monitoring(task_id, "worker_1", estimated_duration=60.0)
        assert result.is_ok()

    def test_update_progress(self, monitor, task_queue):
        r = task_queue.submit_task("compute", {}, priority=TaskPriority.NORMAL)
        task_id = r.unwrap()
        monitor.start_task_monitoring(task_id, "worker_1")

        result = monitor.update_task_progress(task_id, 50.0, current_step="processing")
        assert result.is_ok()

    def test_update_resources(self, monitor, task_queue):
        r = task_queue.submit_task("compute", {}, priority=TaskPriority.NORMAL)
        task_id = r.unwrap()
        monitor.start_task_monitoring(task_id, "worker_1")

        result = monitor.update_task_resources(
            task_id, memory_usage_mb=256.0, cpu_usage_percentage=75.0
        )
        assert result.is_ok()

    def test_stop_task_monitoring(self, monitor, task_queue):
        r = task_queue.submit_task("compute", {}, priority=TaskPriority.NORMAL)
        task_id = r.unwrap()
        monitor.start_task_monitoring(task_id, "worker_1")

        result = monitor.stop_task_monitoring(task_id)
        assert result.is_ok()

    def test_get_task_metrics(self, monitor, task_queue):
        r = task_queue.submit_task("compute", {}, priority=TaskPriority.NORMAL)
        task_id = r.unwrap()
        monitor.start_task_monitoring(task_id, "worker_1")
        monitor.update_task_progress(task_id, 30.0)

        result = monitor.get_task_metrics(task_id)
        assert result.is_ok()
        metrics = result.unwrap()
        assert metrics.progress_percentage == 30.0


class TestListAndFilter:
    """Test listing and filtering monitored tasks."""

    def test_list_monitored_tasks(self, monitor, task_queue):
        r = task_queue.submit_task("compute", {}, priority=TaskPriority.NORMAL)
        monitor.start_task_monitoring(r.unwrap(), "worker_1")

        tasks = monitor.list_monitored_tasks()
        assert len(tasks) >= 1

    def test_get_stalled_tasks(self, monitor):
        stalled = monitor.get_stalled_tasks()
        assert isinstance(stalled, list)

    def test_get_timeout_warnings(self, monitor):
        warnings = monitor.get_timeout_warnings()
        assert isinstance(warnings, list)


class TestAlerts:
    """Test alert system."""

    def test_get_alerts(self, monitor):
        alerts = monitor.get_alerts()
        assert isinstance(alerts, list)

    def test_alert_callback(self, monitor):
        alerts_received = []
        monitor.add_alert_callback(lambda alert: alerts_received.append(alert))


class TestProgressCallback:
    """Test progress callbacks."""

    def test_progress_callback(self, monitor, task_queue):
        progress_updates = []
        monitor.add_progress_callback(lambda tid, pct: progress_updates.append((tid, pct)))

        r = task_queue.submit_task("compute", {}, priority=TaskPriority.NORMAL)
        task_id = r.unwrap()
        monitor.start_task_monitoring(task_id, "worker_1")
        monitor.update_task_progress(task_id, 75.0)

        assert len(progress_updates) >= 1


class TestMonitoringStats:
    """Test monitoring statistics."""

    def test_stats(self, monitor):
        stats = monitor.get_monitoring_stats()
        assert stats is not None
