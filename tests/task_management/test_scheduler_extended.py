"""Extended tests for TaskScheduler — agent selection strategies, rebalancing, task completion."""

import pytest
from unittest.mock import MagicMock
from dataclasses import dataclass, field
from maple.task_management.task_queue import TaskQueue, TaskPriority, TaskStatus
from maple.task_management.scheduler import TaskScheduler, SchedulingPolicy, SchedulingMetrics
from maple.core.result import Result


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

@dataclass
class FakeAgent:
    agent_id: str = "a1"
    capabilities: list = field(default_factory=lambda: ["compute"])
    max_concurrent_tasks: int = 5


@dataclass
class FakeMatch:
    agent_id: str = "a1"
    availability_score: float = 0.9


@pytest.fixture
def task_queue():
    tq = TaskQueue(max_queue_size=100)
    tq.start()
    yield tq
    tq.stop()


def _make_scheduler(task_queue, agents=None, policy=None, match_result=None):
    """Helper to build a scheduler with configurable mocks."""
    if agents is None:
        agents = [FakeAgent("w1", ["compute"]), FakeAgent("w2", ["compute", "gpu"])]

    registry = MagicMock()
    registry.list_agents.return_value = agents

    matcher = MagicMock()
    if match_result is None:
        matcher.match_capabilities.return_value = Result.ok(
            [FakeMatch(a.agent_id, 0.8 + i * 0.05) for i, a in enumerate(agents)]
        )
    else:
        matcher.match_capabilities.return_value = match_result

    return TaskScheduler(task_queue, registry, matcher, policy=policy)


def _submit(task_queue, reqs=None):
    r = task_queue.submit_task("compute", {"n": 1}, priority=TaskPriority.NORMAL, requirements=reqs or [])
    return r.unwrap()


# ---------------------------------------------------------------------------
#  SchedulingPolicy / SchedulingMetrics
# ---------------------------------------------------------------------------

class TestPolicyAndMetrics:
    def test_policy_defaults(self):
        p = SchedulingPolicy()
        assert p.load_balancing == "least_loaded"
        assert p.capability_matching == "best_match"
        assert p.preemption_enabled is False

    def test_metrics_defaults(self):
        m = SchedulingMetrics()
        assert m.total_scheduled == 0


# ---------------------------------------------------------------------------
#  Capability matching strategies
# ---------------------------------------------------------------------------

class TestCapabilityMatching:
    def test_first_match(self, task_queue):
        sched = _make_scheduler(task_queue, policy=SchedulingPolicy(capability_matching="first_match"))
        tid = _submit(task_queue, reqs=["compute"])
        result = sched.schedule_task(tid)
        assert result.is_ok()

    def test_best_match(self, task_queue):
        agents = [FakeAgent("w1"), FakeAgent("w2")]
        sched = _make_scheduler(
            task_queue,
            agents=agents,
            policy=SchedulingPolicy(capability_matching="best_match"),
            match_result=Result.ok([FakeMatch("w1", 0.5), FakeMatch("w2", 0.9)]),
        )
        tid = _submit(task_queue, reqs=["compute"])
        result = sched.schedule_task(tid)
        assert result.is_ok()
        assert result.unwrap() == "w2"  # highest availability_score

    def test_weighted_score(self, task_queue):
        agents = [FakeAgent("w1"), FakeAgent("w2")]
        sched = _make_scheduler(
            task_queue,
            agents=agents,
            policy=SchedulingPolicy(capability_matching="weighted_score"),
            match_result=Result.ok([FakeMatch("w1", 0.9), FakeMatch("w2", 0.8)]),
        )
        tid = _submit(task_queue, reqs=["compute"])
        result = sched.schedule_task(tid)
        assert result.is_ok()

    def test_unknown_matching_strategy(self, task_queue):
        sched = _make_scheduler(task_queue, policy=SchedulingPolicy(capability_matching="magic"))
        tid = _submit(task_queue, reqs=["compute"])
        result = sched.schedule_task(tid)
        assert result.is_err()

    def test_no_requirements_uses_load_balancing(self, task_queue):
        sched = _make_scheduler(task_queue, policy=SchedulingPolicy(capability_matching="first_match"))
        tid = _submit(task_queue, reqs=[])
        result = sched.schedule_task(tid)
        assert result.is_ok()

    def test_no_matching_agents(self, task_queue):
        sched = _make_scheduler(
            task_queue,
            match_result=Result.ok([]),  # empty matches
        )
        tid = _submit(task_queue, reqs=["rare_skill"])
        result = sched.schedule_task(tid)
        assert result.is_err()


# ---------------------------------------------------------------------------
#  Load balancing strategies
# ---------------------------------------------------------------------------

class TestLoadBalancing:
    def test_least_loaded(self, task_queue):
        sched = _make_scheduler(task_queue, policy=SchedulingPolicy(load_balancing="least_loaded"))
        tid = _submit(task_queue)
        result = sched.schedule_task(tid)
        assert result.is_ok()

    def test_round_robin(self, task_queue):
        sched = _make_scheduler(task_queue, policy=SchedulingPolicy(load_balancing="round_robin"))
        results = []
        for _ in range(3):
            tid = _submit(task_queue)
            r = sched.schedule_task(tid)
            if r.is_ok():
                results.append(r.unwrap())
        assert len(results) >= 2

    def test_capability_weighted(self, task_queue):
        sched = _make_scheduler(task_queue, policy=SchedulingPolicy(load_balancing="capability_weighted"))
        tid = _submit(task_queue)
        result = sched.schedule_task(tid)
        assert result.is_ok()

    def test_unknown_lb_strategy(self, task_queue):
        sched = _make_scheduler(task_queue, policy=SchedulingPolicy(load_balancing="random"))
        tid = _submit(task_queue)
        result = sched.schedule_task(tid)
        assert result.is_err()

    def test_no_agents_available(self, task_queue):
        sched = _make_scheduler(task_queue, agents=[])
        tid = _submit(task_queue, reqs=["compute"])
        result = sched.schedule_task(tid)
        assert result.is_err()

    def test_all_agents_at_capacity(self, task_queue):
        sched = _make_scheduler(
            task_queue,
            policy=SchedulingPolicy(max_concurrent_per_agent=0),
        )
        tid = _submit(task_queue, reqs=["compute"])
        result = sched.schedule_task(tid)
        assert result.is_err()


# ---------------------------------------------------------------------------
#  task_completed
# ---------------------------------------------------------------------------

class TestTaskCompletion:
    def test_task_completed_decrements_load(self, task_queue):
        sched = _make_scheduler(task_queue)
        tid = _submit(task_queue, reqs=["compute"])
        sched.schedule_task(tid)
        agent = list(sched.agent_loads.keys())[0]
        assert sched.agent_loads[agent] >= 1
        sched.task_completed(tid, agent)
        assert sched.agent_loads[agent] == 0

    def test_task_completed_unknown_agent(self, task_queue):
        sched = _make_scheduler(task_queue)
        result = sched.task_completed("t1", "unknown")
        assert result.is_ok()


# ---------------------------------------------------------------------------
#  rebalance_loads
# ---------------------------------------------------------------------------

class TestRebalance:
    def test_rebalance_single_agent(self, task_queue):
        sched = _make_scheduler(task_queue, agents=[FakeAgent("w1")])
        result = sched.rebalance_loads()
        assert result.is_ok()
        assert result.unwrap() == 0

    def test_rebalance_no_imbalance(self, task_queue):
        sched = _make_scheduler(task_queue)
        result = sched.rebalance_loads()
        assert result.is_ok()
        assert result.unwrap() == 0


# ---------------------------------------------------------------------------
#  scheduling callbacks
# ---------------------------------------------------------------------------

class TestSchedulingCallbacks:
    def test_callback_fired_on_schedule(self, task_queue):
        sched = _make_scheduler(task_queue)
        fired = []
        sched.add_scheduling_callback(lambda tid, aid: fired.append((tid, aid)))
        tid = _submit(task_queue, reqs=["compute"])
        sched.schedule_task(tid)
        assert len(fired) == 1
        assert fired[0][0] == tid


# ---------------------------------------------------------------------------
#  metrics
# ---------------------------------------------------------------------------

class TestSchedulingMetrics:
    def test_metrics_update(self, task_queue):
        sched = _make_scheduler(task_queue)
        tid = _submit(task_queue, reqs=["compute"])
        sched.schedule_task(tid)
        metrics = sched.get_scheduling_metrics()
        assert metrics.total_scheduled >= 1
        assert metrics.successful_assignments >= 1
