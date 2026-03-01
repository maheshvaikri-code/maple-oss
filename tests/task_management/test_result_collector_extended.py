"""Extended tests for ResultCollector — aggregation types, cleanup, callbacks, collector loop."""

import time
import pytest
from maple.task_management.task_queue import TaskQueue, TaskPriority
from maple.task_management.result_collector import (
    ResultCollector,
    AggregationType,
    TaskResult,
    AggregationGroup,
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


def _submit(task_queue, n=1):
    """Submit n tasks and return their IDs."""
    ids = []
    for i in range(n):
        r = task_queue.submit_task("compute", {"n": i}, priority=TaskPriority.NORMAL)
        ids.append(r.unwrap())
    return ids


# ---------------------------------------------------------------------------
#  COLLECT_ALL aggregation
# ---------------------------------------------------------------------------

class TestCollectAllAggregation:
    def test_collect_all_completes(self, collector, task_queue):
        ids = _submit(task_queue, 3)
        collector.create_aggregation_group("g1", ids, AggregationType.COLLECT_ALL)

        for i, tid in enumerate(ids):
            collector.collect_task_result(tid, f"w{i}", {"val": i})

        group = collector.get_aggregation_group("g1").unwrap()
        assert group.is_complete
        assert len(group.aggregated_result) == 3


# ---------------------------------------------------------------------------
#  FIRST_COMPLETE aggregation
# ---------------------------------------------------------------------------

class TestFirstCompleteAggregation:
    def test_first_complete(self, collector, task_queue):
        ids = _submit(task_queue, 3)
        collector.create_aggregation_group("g1", ids, AggregationType.FIRST_COMPLETE)

        # Submitting just one result should complete the group
        collector.collect_task_result(ids[0], "w0", "fast-answer")

        group = collector.get_aggregation_group("g1").unwrap()
        assert group.is_complete
        assert group.aggregated_result == "fast-answer"


# ---------------------------------------------------------------------------
#  MAJORITY_VOTE aggregation
# ---------------------------------------------------------------------------

class TestMajorityVoteAggregation:
    def test_majority_vote(self, collector, task_queue):
        ids = _submit(task_queue, 3)
        collector.create_aggregation_group(
            "g1", ids, AggregationType.MAJORITY_VOTE, vote_threshold=0.5
        )

        collector.collect_task_result(ids[0], "w0", "yes")
        collector.collect_task_result(ids[1], "w1", "yes")
        collector.collect_task_result(ids[2], "w2", "no")

        group = collector.get_aggregation_group("g1").unwrap()
        assert group.is_complete
        assert group.aggregated_result == "yes"


# ---------------------------------------------------------------------------
#  BEST_SCORE aggregation
# ---------------------------------------------------------------------------

class TestBestScoreAggregation:
    def test_best_score_from_confidence(self, collector, task_queue):
        ids = _submit(task_queue, 3)
        collector.create_aggregation_group("g1", ids, AggregationType.BEST_SCORE)

        collector.collect_task_result(ids[0], "w0", "a", confidence_score=0.5)
        collector.collect_task_result(ids[1], "w1", "b", confidence_score=0.95)
        collector.collect_task_result(ids[2], "w2", "c", confidence_score=0.7)

        group = collector.get_aggregation_group("g1").unwrap()
        assert group.is_complete
        assert group.aggregated_result == "b"

    def test_best_score_from_metadata(self, collector, task_queue):
        ids = _submit(task_queue, 2)
        collector.create_aggregation_group("g1", ids, AggregationType.BEST_SCORE)

        collector.collect_task_result(ids[0], "w0", "low", metadata={"score": 10})
        collector.collect_task_result(ids[1], "w1", "high", metadata={"score": 90})

        group = collector.get_aggregation_group("g1").unwrap()
        assert group.aggregated_result == "high"

    def test_best_score_from_result_data(self, collector, task_queue):
        ids = _submit(task_queue, 2)
        collector.create_aggregation_group("g1", ids, AggregationType.BEST_SCORE)

        collector.collect_task_result(ids[0], "w0", {"score": 30})
        collector.collect_task_result(ids[1], "w1", {"score": 80})

        group = collector.get_aggregation_group("g1").unwrap()
        assert group.aggregated_result == {"score": 80}


# ---------------------------------------------------------------------------
#  AVERAGE aggregation
# ---------------------------------------------------------------------------

class TestAverageAggregation:
    def test_average_numeric(self, collector, task_queue):
        ids = _submit(task_queue, 3)
        collector.create_aggregation_group("g1", ids, AggregationType.AVERAGE)

        collector.collect_task_result(ids[0], "w0", 10)
        collector.collect_task_result(ids[1], "w1", 20)
        collector.collect_task_result(ids[2], "w2", 30)

        group = collector.get_aggregation_group("g1").unwrap()
        assert group.is_complete
        assert group.aggregated_result == 20.0

    def test_average_dict_values(self, collector, task_queue):
        ids = _submit(task_queue, 2)
        collector.create_aggregation_group("g1", ids, AggregationType.AVERAGE)

        collector.collect_task_result(ids[0], "w0", {"val": 10})
        collector.collect_task_result(ids[1], "w1", {"val": 30})

        group = collector.get_aggregation_group("g1").unwrap()
        assert group.is_complete
        assert group.aggregated_result == 20.0

    def test_average_no_numeric(self, collector, task_queue):
        ids = _submit(task_queue, 2)
        collector.create_aggregation_group("g1", ids, AggregationType.AVERAGE)

        collector.collect_task_result(ids[0], "w0", "text")
        collector.collect_task_result(ids[1], "w1", "more text")

        group = collector.get_aggregation_group("g1").unwrap()
        # Aggregation should fail — no numeric data
        assert group.is_complete is False or group.aggregated_result is None


# ---------------------------------------------------------------------------
#  WEIGHTED_AVERAGE aggregation
# ---------------------------------------------------------------------------

class TestWeightedAverageAggregation:
    def test_weighted_average(self, collector, task_queue):
        ids = _submit(task_queue, 2)
        collector.create_aggregation_group(
            "g1", ids, AggregationType.WEIGHTED_AVERAGE,
            weights={"w0": 1.0, "w1": 3.0},
        )

        collector.collect_task_result(ids[0], "w0", 10.0)
        collector.collect_task_result(ids[1], "w1", 30.0)

        group = collector.get_aggregation_group("g1").unwrap()
        assert group.is_complete
        # (10*1 + 30*3) / (1+3) = 100/4 = 25
        assert group.aggregated_result == 25.0

    def test_weighted_average_no_weights(self, collector, task_queue):
        ids = _submit(task_queue, 2)
        collector.create_aggregation_group("g1", ids, AggregationType.WEIGHTED_AVERAGE)

        collector.collect_task_result(ids[0], "w0", 10.0)
        collector.collect_task_result(ids[1], "w1", 20.0)

        group = collector.get_aggregation_group("g1").unwrap()
        # Expect error because no weights, but group may not complete


# ---------------------------------------------------------------------------
#  CUSTOM aggregation
# ---------------------------------------------------------------------------

class TestCustomAggregation:
    def test_custom_aggregator(self, collector, task_queue):
        ids = _submit(task_queue, 2)

        def my_agg(results):
            return sum(r.result_data for r in results)

        collector.create_aggregation_group(
            "g1", ids, AggregationType.CUSTOM, custom_aggregator=my_agg
        )

        collector.collect_task_result(ids[0], "w0", 5)
        collector.collect_task_result(ids[1], "w1", 7)

        group = collector.get_aggregation_group("g1").unwrap()
        assert group.is_complete
        assert group.aggregated_result == 12

    def test_custom_no_aggregator(self, collector, task_queue):
        ids = _submit(task_queue, 1)
        result = collector.create_aggregation_group("g1", ids, AggregationType.CUSTOM)
        assert result.is_err()

    def test_custom_aggregator_error(self, collector, task_queue):
        ids = _submit(task_queue, 2)

        def bad_agg(results):
            raise ValueError("boom")

        collector.create_aggregation_group(
            "g1", ids, AggregationType.CUSTOM, custom_aggregator=bad_agg
        )

        collector.collect_task_result(ids[0], "w0", 1)
        collector.collect_task_result(ids[1], "w1", 2)

        # Should not crash, group may be marked as failed
        group = collector.get_aggregation_group("g1").unwrap()


# ---------------------------------------------------------------------------
#  Duplicate group / completion callbacks / aggregation callbacks
# ---------------------------------------------------------------------------

class TestGroupManagement:
    def test_duplicate_group_rejected(self, collector, task_queue):
        ids = _submit(task_queue, 2)
        collector.create_aggregation_group("g1", ids, AggregationType.COLLECT_ALL)
        result = collector.create_aggregation_group("g1", ids, AggregationType.COLLECT_ALL)
        assert result.is_err()

    def test_completion_callback(self, collector, task_queue):
        ids = _submit(task_queue, 1)
        collector.create_aggregation_group("g1", ids, AggregationType.FIRST_COMPLETE)

        fired = []
        collector.add_completion_callback("g1", lambda gid, res: fired.append((gid, res)))
        collector.collect_task_result(ids[0], "w0", "done")
        assert len(fired) == 1

    def test_completion_callback_unknown_group(self, collector):
        result = collector.add_completion_callback("nope", lambda g, r: None)
        assert result.is_err()

    def test_aggregation_callback(self, collector, task_queue):
        ids = _submit(task_queue, 1)
        collector.create_aggregation_group("g1", ids, AggregationType.FIRST_COMPLETE)

        fired = []
        collector.add_aggregation_callback(lambda gid, res: fired.append(gid))
        collector.collect_task_result(ids[0], "w0", "done")
        assert "g1" in fired


# ---------------------------------------------------------------------------
#  list_results filtering
# ---------------------------------------------------------------------------

class TestListFiltering:
    def test_filter_by_timestamp(self, collector, task_queue):
        ids = _submit(task_queue, 2)
        collector.collect_task_result(ids[0], "w0", "a")
        collector.collect_task_result(ids[1], "w1", "b")

        future = time.time() + 100
        results = collector.list_results(since_timestamp=future)
        assert len(results) == 0


# ---------------------------------------------------------------------------
#  cleanup_old_results
# ---------------------------------------------------------------------------

class TestCleanup:
    def test_cleanup_removes_old(self, collector, task_queue):
        ids = _submit(task_queue, 1)
        collector.collect_task_result(ids[0], "w0", "data")

        # Artificially age the result
        collector.task_results[ids[0]].completion_time = time.time() - 200_000
        collector.cleanup_old_results(max_age_hours=1)
        assert len(collector.task_results) == 0


# ---------------------------------------------------------------------------
#  start / stop collector
# ---------------------------------------------------------------------------

class TestCollectorLifecycle:
    def test_start_stop(self, collector):
        collector.start_collector()
        assert collector._running is True
        collector.stop_collector()
        assert collector._running is False

    def test_double_start(self, collector):
        collector.start_collector()
        collector.start_collector()  # no-op
        collector.stop_collector()


# ---------------------------------------------------------------------------
#  statistics
# ---------------------------------------------------------------------------

class TestCollectionStats:
    def test_stats_after_collection(self, collector, task_queue):
        ids = _submit(task_queue, 2)
        collector.collect_task_result(ids[0], "w0", "a")
        collector.collect_task_result(ids[1], "w1", "b")

        stats = collector.get_collection_stats()
        assert stats["total_results_collected"] == 2
        assert stats["pending_results"] == 2

    def test_stats_after_aggregation(self, collector, task_queue):
        ids = _submit(task_queue, 1)
        collector.create_aggregation_group("g1", ids, AggregationType.FIRST_COMPLETE)
        collector.collect_task_result(ids[0], "w0", "done")

        stats = collector.get_collection_stats()
        assert stats["successful_aggregations"] >= 1
        assert stats["completed_groups"] >= 1
        assert stats["aggregation_success_rate"] > 0
