"""Regression tests for bounded scheduler policy configuration."""

import pytest

from maple.task_management.scheduler import SchedulingPolicy


@pytest.mark.parametrize(
    "kwargs",
    [
        {"load_balancing": "random"},
        {"capability_matching": "random"},
        {"retry_strategy": "random"},
        {"max_concurrent_per_agent": 0},
        {"max_concurrent_per_agent": True},
        {"max_concurrent_per_agent": 10_001},
        {"scheduling_interval": 0},
        {"scheduling_interval": float("nan")},
        {"scheduling_interval": float("inf")},
        {"scheduling_interval": 3_600.1},
        {"preemption_enabled": 1},
    ],
)
def test_scheduler_policy_rejects_invalid_values(kwargs):
    with pytest.raises(ValueError):
        SchedulingPolicy(**kwargs)


def test_scheduler_policy_accepts_documented_bounds():
    policy = SchedulingPolicy(
        max_concurrent_per_agent=10_000,
        scheduling_interval=3_600.0,
    )

    assert policy.max_concurrent_per_agent == 10_000
    assert policy.scheduling_interval == 3_600.0
