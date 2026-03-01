"""Extended tests for PerformanceOptimizer — recommendations, apply, status, trends, cache."""

import time
import pytest
from unittest.mock import MagicMock, PropertyMock
from dataclasses import dataclass, field
from maple.task_management.task_queue import TaskQueue, TaskPriority, TaskStatus
from maple.task_management.scheduler import TaskScheduler, SchedulingPolicy
from maple.task_management.monitor import TaskMonitor
from maple.task_management.performance_optimizer import (
    PerformanceOptimizer,
    OptimizationMetrics,
    OptimizationRecommendation,
    OptimizationStrategy,
    BatchingConfig,
    CachingConfig,
)


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

@dataclass
class FakeQueueStats:
    throughput_per_minute: float = 10.0
    total_tasks: int = 100
    completed_tasks: int = 80
    failed_tasks: int = 5
    average_wait_time: float = 2.0
    average_execution_time: float = 5.0


@dataclass
class FakeTask:
    task_id: str = "t1"
    task_type: str = "compute"
    payload: dict = field(default_factory=lambda: {"key": "val"})
    priority: TaskPriority = TaskPriority.NORMAL
    created_at: float = field(default_factory=lambda: time.time() - 10)
    completed_at: float = field(default_factory=time.time)
    started_at: float = field(default_factory=lambda: time.time() - 5)
    status: TaskStatus = TaskStatus.COMPLETED
    requirements: list = field(default_factory=list)


@dataclass
class FakeAgent:
    agent_id: str = "agent-1"
    capabilities: list = field(default_factory=lambda: ["compute"])
    max_concurrent_tasks: int = 5


@pytest.fixture
def optimizer():
    """Build a PerformanceOptimizer wired to mocks."""
    tq = MagicMock(spec=TaskQueue)
    tq.get_queue_stats.return_value = FakeQueueStats()
    tq.list_tasks.return_value = [FakeTask(task_id=f"t{i}") for i in range(10)]

    sched = MagicMock(spec=TaskScheduler)
    sched.get_scheduling_metrics.return_value = MagicMock()
    sched.get_agent_load.return_value = 2
    sched.rebalance_loads.return_value = MagicMock(is_ok=lambda: True, unwrap=lambda: 3)

    mon = MagicMock(spec=TaskMonitor)
    mon.get_monitoring_stats.return_value = MagicMock(stalled_tasks=0)

    registry = MagicMock()
    registry.list_agents.return_value = [FakeAgent()]

    opt = PerformanceOptimizer(tq, sched, mon, registry)
    return opt


# ---------------------------------------------------------------------------
#  Data-class construction
# ---------------------------------------------------------------------------

class TestDataClasses:
    def test_optimization_metrics_defaults(self):
        m = OptimizationMetrics()
        assert m.tasks_per_minute == 0.0
        assert m.active_agents == 0

    def test_optimization_recommendation(self):
        r = OptimizationRecommendation(
            strategy=OptimizationStrategy.CACHING,
            priority="low",
            description="test",
            expected_impact="small",
            implementation_cost="low",
        )
        assert r.confidence == 1.0

    def test_batching_config_defaults(self):
        bc = BatchingConfig()
        assert bc.enabled is True
        assert bc.batch_size == 10

    def test_caching_config_defaults(self):
        cc = CachingConfig()
        assert cc.ttl_seconds == 3600


# ---------------------------------------------------------------------------
#  analyze_performance
# ---------------------------------------------------------------------------

class TestAnalyzePerformance:
    def test_basic_analysis(self, optimizer):
        metrics = optimizer.analyze_performance()
        assert isinstance(metrics, OptimizationMetrics)
        assert metrics.tasks_per_minute == 10.0
        assert metrics.completion_rate == 0.8
        assert metrics.failure_rate == 0.05
        assert metrics.active_agents == 1

    def test_analysis_stores_history(self, optimizer):
        optimizer.analyze_performance()
        assert len(optimizer.metrics_history) == 1
        optimizer.analyze_performance()
        assert len(optimizer.metrics_history) == 2

    def test_analysis_zero_total_tasks(self, optimizer):
        optimizer.task_queue.get_queue_stats.return_value = FakeQueueStats(total_tasks=0)
        metrics = optimizer.analyze_performance()
        assert metrics.completion_rate == 0.0


# ---------------------------------------------------------------------------
#  generate_recommendations
# ---------------------------------------------------------------------------

class TestGenerateRecommendations:
    def test_no_history_returns_empty(self, optimizer):
        assert optimizer.generate_recommendations() == []

    def test_overloaded_agents_trigger_load_balance(self, optimizer):
        m = OptimizationMetrics(
            overloaded_agents=2,
            average_wait_time=1.0,
            resource_efficiency=0.9,
            tasks_per_minute=10,
        )
        optimizer.metrics_history.append(m)
        recs = optimizer.generate_recommendations()
        strategies = [r.strategy for r in recs]
        assert OptimizationStrategy.LOAD_BALANCING in strategies

    def test_high_wait_time_triggers_priority_adj(self, optimizer):
        m = OptimizationMetrics(
            overloaded_agents=0,
            average_wait_time=100.0,  # way above target_response_time=30
            resource_efficiency=0.9,
            tasks_per_minute=10,
        )
        optimizer.metrics_history.append(m)
        recs = optimizer.generate_recommendations()
        strategies = [r.strategy for r in recs]
        assert OptimizationStrategy.PRIORITY_ADJUSTMENT in strategies

    def test_low_efficiency_triggers_resource_opt(self, optimizer):
        m = OptimizationMetrics(
            overloaded_agents=0,
            average_wait_time=1.0,
            resource_efficiency=0.3,
            tasks_per_minute=10,
        )
        optimizer.metrics_history.append(m)
        recs = optimizer.generate_recommendations()
        strategies = [r.strategy for r in recs]
        assert OptimizationStrategy.RESOURCE_OPTIMIZATION in strategies

    def test_predict_load_increase(self, optimizer):
        for i in range(6):
            optimizer.metrics_history.append(
                OptimizationMetrics(
                    tasks_per_minute=10 + i * 5,
                    overloaded_agents=0,
                    average_wait_time=1.0,
                    resource_efficiency=0.9,
                )
            )
        recs = optimizer.generate_recommendations()
        strategies = [r.strategy for r in recs]
        assert OptimizationStrategy.PREDICTIVE_SCALING in strategies


# ---------------------------------------------------------------------------
#  apply_optimization (all strategies)
# ---------------------------------------------------------------------------

class TestApplyOptimization:
    def test_apply_load_balancing(self, optimizer):
        rec = OptimizationRecommendation(
            strategy=OptimizationStrategy.LOAD_BALANCING,
            priority="high",
            description="",
            expected_impact="",
            implementation_cost="low",
            parameters={"rebalance_threshold": 0.9},
        )
        result = optimizer.apply_optimization(rec)
        assert result.is_ok()
        assert "load_balancing" in optimizer.active_optimizations

    def test_apply_priority_adjustment(self, optimizer):
        rec = OptimizationRecommendation(
            strategy=OptimizationStrategy.PRIORITY_ADJUSTMENT,
            priority="medium",
            description="",
            expected_impact="",
            implementation_cost="low",
            parameters={"boost_critical_tasks": True},
        )
        result = optimizer.apply_optimization(rec)
        assert result.is_ok()

    def test_apply_priority_adjustment_no_boost(self, optimizer):
        rec = OptimizationRecommendation(
            strategy=OptimizationStrategy.PRIORITY_ADJUSTMENT,
            priority="medium",
            description="",
            expected_impact="",
            implementation_cost="low",
            parameters={},
        )
        result = optimizer.apply_optimization(rec)
        assert result.is_ok()

    def test_apply_resource_optimization(self, optimizer):
        rec = OptimizationRecommendation(
            strategy=OptimizationStrategy.RESOURCE_OPTIMIZATION,
            priority="high",
            description="",
            expected_impact="",
            implementation_cost="medium",
            parameters={"target_utilization": 0.8},
        )
        result = optimizer.apply_optimization(rec)
        assert result.is_ok()
        assert "resource_optimization" in optimizer.active_optimizations

    def test_apply_batching(self, optimizer):
        rec = OptimizationRecommendation(
            strategy=OptimizationStrategy.BATCHING,
            priority="medium",
            description="",
            expected_impact="",
            implementation_cost="low",
            parameters={"batch_size": 20, "batch_timeout": 15},
        )
        result = optimizer.apply_optimization(rec)
        assert result.is_ok()
        assert optimizer.batching_config.batch_size == 20

    def test_apply_caching(self, optimizer):
        rec = OptimizationRecommendation(
            strategy=OptimizationStrategy.CACHING,
            priority="medium",
            description="",
            expected_impact="",
            implementation_cost="medium",
            parameters={"cache_size": 500, "ttl_seconds": 1800},
        )
        result = optimizer.apply_optimization(rec)
        assert result.is_ok()
        assert optimizer.caching_config.cache_size == 500

    def test_apply_predictive_scaling(self, optimizer):
        rec = OptimizationRecommendation(
            strategy=OptimizationStrategy.PREDICTIVE_SCALING,
            priority="medium",
            description="",
            expected_impact="",
            implementation_cost="high",
            parameters={"scale_factor": 2.0},
        )
        result = optimizer.apply_optimization(rec)
        assert result.is_ok()
        assert "predictive_scaling" in optimizer.active_optimizations


# ---------------------------------------------------------------------------
#  get_optimization_status / trends / cache
# ---------------------------------------------------------------------------

class TestStatusAndTrends:
    def test_get_status_empty(self, optimizer):
        status = optimizer.get_optimization_status()
        assert status["active_optimizations"] == []
        assert status["batching_enabled"] is True
        assert status["optimization_history"] == 0

    def test_get_status_with_metrics(self, optimizer):
        optimizer.analyze_performance()
        status = optimizer.get_optimization_status()
        assert status["latest_metrics"] is not None
        assert status["optimization_history"] == 1

    def test_get_performance_trends_empty(self, optimizer):
        trends = optimizer.get_performance_trends(hours=1)
        assert trends["throughput"] == []
        assert trends["timestamps"] == []

    def test_get_performance_trends_with_data(self, optimizer):
        optimizer.metrics_history.append(
            OptimizationMetrics(tasks_per_minute=42, completion_rate=0.9)
        )
        trends = optimizer.get_performance_trends(hours=1)
        assert trends["throughput"] == [42]

    def test_calculate_cache_hit_rate_empty(self, optimizer):
        assert optimizer._calculate_cache_hit_rate() == 0.0

    def test_calculate_cache_hit_rate_with_data(self, optimizer):
        optimizer.cache_access_counts = {"a": 3, "b": 1, "c": 2}
        rate = optimizer._calculate_cache_hit_rate()
        assert rate > 0


# ---------------------------------------------------------------------------
#  _cleanup_cache
# ---------------------------------------------------------------------------

class TestCleanupCache:
    def test_cleanup_disabled(self, optimizer):
        optimizer.caching_config.enabled = False
        optimizer.result_cache["k"] = "v"
        optimizer._cleanup_cache()
        assert "k" in optimizer.result_cache  # not cleaned because disabled

    def test_cleanup_expired(self, optimizer):
        optimizer.caching_config.enabled = True
        optimizer.caching_config.ttl_seconds = 1
        optimizer.result_cache["old"] = "data"
        optimizer.cache_timestamps["old"] = time.time() - 10
        optimizer.cache_access_counts["old"] = 1
        optimizer._cleanup_cache()
        assert "old" not in optimizer.result_cache

    def test_cleanup_size_limit(self, optimizer):
        optimizer.caching_config.enabled = True
        optimizer.caching_config.cache_size = 2
        for i in range(5):
            key = f"k{i}"
            optimizer.result_cache[key] = f"v{i}"
            optimizer.cache_timestamps[key] = time.time() + i
            optimizer.cache_access_counts[key] = 1
        optimizer._cleanup_cache()
        assert len(optimizer.result_cache) <= 2


# ---------------------------------------------------------------------------
#  _predict_load_increase and _estimate_cache_hit_potential
# ---------------------------------------------------------------------------

class TestInternalHelpers:
    def test_predict_load_no_history(self, optimizer):
        assert optimizer._predict_load_increase() is False

    def test_predict_load_flat(self, optimizer):
        for _ in range(5):
            optimizer.metrics_history.append(OptimizationMetrics(tasks_per_minute=50))
        assert optimizer._predict_load_increase() is False

    def test_predict_load_rising(self, optimizer):
        for i in range(5):
            optimizer.metrics_history.append(OptimizationMetrics(tasks_per_minute=10 + i * 10))
        assert optimizer._predict_load_increase() is True

    def test_estimate_cache_few_tasks(self, optimizer):
        optimizer.task_queue.list_tasks.return_value = [FakeTask()]
        assert optimizer._estimate_cache_hit_potential() == 0.0

    def test_estimate_cache_duplicates(self, optimizer):
        tasks = [FakeTask(task_id=f"t{i}", task_type="compute", payload={"x": 1}) for i in range(20)]
        optimizer.task_queue.list_tasks.return_value = tasks
        potential = optimizer._estimate_cache_hit_potential()
        assert potential > 0


# ---------------------------------------------------------------------------
#  callbacks
# ---------------------------------------------------------------------------

class TestOptimizationCallbacks:
    def test_add_and_fire_callback(self, optimizer):
        fired = []
        optimizer.add_optimization_callback(lambda rec: fired.append(rec))
        # Manually fire via force_optimization_analysis
        optimizer.force_optimization_analysis()
        # Callbacks are only called when there are recommendations
        # We just verify no error occurs

    def test_force_analysis_returns_recommendations(self, optimizer):
        recs = optimizer.force_optimization_analysis()
        assert isinstance(recs, list)


# ---------------------------------------------------------------------------
#  start / stop
# ---------------------------------------------------------------------------

class TestStartStop:
    def test_start_stop_optimizer(self, optimizer):
        optimizer.analysis_interval = 0.05
        optimizer.start_optimizer()
        assert optimizer._running is True
        optimizer.stop_optimizer()
        assert optimizer._running is False

    def test_double_start(self, optimizer):
        optimizer.analysis_interval = 0.05
        optimizer.start_optimizer()
        optimizer.start_optimizer()  # should be a no-op
        optimizer.stop_optimizer()
