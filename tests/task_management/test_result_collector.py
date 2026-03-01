"""Tests for maple.task_management.result_collector - ResultCollector."""

import pytest
from maple.task_management.task_queue import TaskQueue, TaskPriority
from maple.task_management.result_collector import (
    ResultCollector, AggregationType
)


@pytest.fixture
def task_queue():
    tq = TaskQueue(max_queue_size=100)
    tq.start()
    yield tq
    tq.stop()


@pytest.fixture
def collector(task_queue):
    return ResultCollector(task_queue)


class TestResultCollection:
    """Test result collection."""

    def test_collect_result(self, collector, task_queue):
        result = task_queue.submit_task("compute", {"data": 1}, priority=TaskPriority.NORMAL)
        task_id = result.unwrap()

        collect_result = collector.collect_task_result(
            task_id, "worker_1", {"output": 42}, confidence_score=0.95
        )
        assert collect_result.is_ok()

    def test_get_task_result(self, collector, task_queue):
        result = task_queue.submit_task("compute", {"data": 1}, priority=TaskPriority.NORMAL)
        task_id = result.unwrap()
        collector.collect_task_result(task_id, "worker_1", {"output": 42})

        get_result = collector.get_task_result(task_id)
        assert get_result.is_ok()
        assert get_result.unwrap().result_data == {"output": 42}

    def test_get_nonexistent_result(self, collector):
        result = collector.get_task_result("nonexistent")
        assert result.is_err()


class TestAggregation:
    """Test result aggregation groups."""

    def test_create_aggregation_group(self, collector, task_queue):
        task_ids = []
        for i in range(3):
            r = task_queue.submit_task("compute", {"n": i}, priority=TaskPriority.NORMAL)
            task_ids.append(r.unwrap())

        group_result = collector.create_aggregation_group(
            "group_1", task_ids, AggregationType.COLLECT_ALL
        )
        assert group_result.is_ok()

    def test_get_aggregation_group(self, collector, task_queue):
        task_ids = []
        for i in range(2):
            r = task_queue.submit_task("compute", {"n": i}, priority=TaskPriority.NORMAL)
            task_ids.append(r.unwrap())

        collector.create_aggregation_group("grp", task_ids, AggregationType.FIRST_COMPLETE)
        result = collector.get_aggregation_group("grp")
        assert result.is_ok()


class TestListResults:
    """Test listing and filtering results."""

    def test_list_results(self, collector, task_queue):
        r = task_queue.submit_task("compute", {}, priority=TaskPriority.NORMAL)
        collector.collect_task_result(r.unwrap(), "w1", "result_data")

        results = collector.list_results()
        assert len(results) >= 1

    def test_list_results_by_agent(self, collector, task_queue):
        r = task_queue.submit_task("compute", {}, priority=TaskPriority.NORMAL)
        collector.collect_task_result(r.unwrap(), "specific_worker", "data")

        results = collector.list_results(agent_id="specific_worker")
        assert len(results) >= 1


class TestCallbacks:
    """Test collection callbacks."""

    def test_collection_callback(self, collector, task_queue):
        collected = []
        collector.add_collection_callback(lambda tr: collected.append(tr))

        r = task_queue.submit_task("compute", {}, priority=TaskPriority.NORMAL)
        collector.collect_task_result(r.unwrap(), "w1", "data")

        assert len(collected) >= 1


class TestStatistics:
    """Test collection statistics."""

    def test_stats(self, collector):
        stats = collector.get_collection_stats()
        assert isinstance(stats, dict)
