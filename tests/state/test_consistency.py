"""Tests for maple.state.consistency - ConsistencyManager."""

import pytest
from unittest.mock import MagicMock
from maple.state.consistency import (
    ConsistencyManager, ConsistencyModel, ConsistencyConstraint
)
from maple.state.store import StateStore, StorageBackend, ConsistencyLevel


@pytest.fixture
def mock_agent():
    agent = MagicMock()
    agent.agent_id = "test_agent"
    return agent


@pytest.fixture
def store():
    return StateStore(backend=StorageBackend.MEMORY, consistency=ConsistencyLevel.EVENTUAL)


@pytest.fixture
def cm(mock_agent, store):
    return ConsistencyManager(mock_agent, store)


class TestConsistencyConstraints:
    """Test constraint management."""

    def test_set_constraint(self, cm):
        constraint = ConsistencyConstraint(
            model=ConsistencyModel.STRONG,
            tolerance_ms=100
        )
        cm.set_constraint("critical_key", constraint)
        result = cm.get_constraint("critical_key")
        assert result.model == ConsistencyModel.STRONG

    def test_get_default_constraint(self, cm):
        constraint = cm.get_constraint("unset_key")
        assert constraint.model == ConsistencyModel.EVENTUAL

    def test_override_constraint(self, cm):
        cm.set_constraint("key", ConsistencyConstraint(
            model=ConsistencyModel.STRONG, tolerance_ms=50
        ))
        cm.set_constraint("key", ConsistencyConstraint(
            model=ConsistencyModel.CAUSAL, tolerance_ms=200
        ))
        assert cm.get_constraint("key").model == ConsistencyModel.CAUSAL


class TestConsistentReadWrite:
    """Test consistent read and write operations."""

    def test_eventual_write_and_read(self, cm, store):
        cm.set_constraint("key", ConsistencyConstraint(
            model=ConsistencyModel.EVENTUAL, tolerance_ms=1000
        ))
        w_result = cm.consistent_write("key", {"val": 1})
        assert w_result.is_ok()

        r_result = cm.consistent_read("key")
        assert r_result.is_ok()
        assert r_result.unwrap() == {"val": 1}

    def test_strong_write_and_read(self, cm, store):
        cm.set_constraint("key", ConsistencyConstraint(
            model=ConsistencyModel.STRONG, tolerance_ms=100
        ))
        w_result = cm.consistent_write("key", "strong_value")
        assert w_result.is_ok()

        r_result = cm.consistent_read("key")
        assert r_result.is_ok()
        assert r_result.unwrap() == "strong_value"

    def test_causal_write_and_read(self, cm, store):
        cm.set_constraint("key", ConsistencyConstraint(
            model=ConsistencyModel.CAUSAL, tolerance_ms=500
        ))
        w_result = cm.consistent_write("key", [1, 2, 3])
        assert w_result.is_ok()

        r_result = cm.consistent_read("key")
        assert r_result.is_ok()

    def test_read_your_writes(self, cm, store):
        cm.set_constraint("key", ConsistencyConstraint(
            model=ConsistencyModel.READ_YOUR_WRITES, tolerance_ms=100
        ))
        cm.consistent_write("key", "written")
        result = cm.consistent_read("key")
        assert result.is_ok()
        assert result.unwrap() == "written"

    def test_monotonic_read(self, cm, store):
        cm.set_constraint("key", ConsistencyConstraint(
            model=ConsistencyModel.MONOTONIC_READ, tolerance_ms=100
        ))
        cm.consistent_write("key", "v1")
        r1 = cm.consistent_read("key")
        assert r1.is_ok()

    def test_write_with_metadata(self, cm, store):
        result = cm.consistent_write("key", "value", metadata={"source": "test"})
        assert result.is_ok()


class TestViolationDetection:
    """Test consistency violation detection and repair."""

    def test_detect_no_violations(self, cm):
        violations = cm.detect_violations()
        assert isinstance(violations, list)

    def test_repair_empty_violations(self, cm):
        repaired = cm.repair_violations([])
        assert repaired == 0


class TestStatistics:
    """Test statistics tracking."""

    def test_initial_stats(self, cm):
        stats = cm.get_statistics()
        assert isinstance(stats, dict)
        # Stats may be nested under 'statistics' key
        inner = stats.get('statistics', stats)
        assert 'violations_detected' in inner

    def test_stats_after_operations(self, cm):
        cm.consistent_write("key", "value")
        cm.consistent_read("key")
        stats = cm.get_statistics()
        inner = stats.get('statistics', stats)
        total = inner.get('eventual_operations', 0) + inner.get('strong_operations', 0) + inner.get('causal_operations', 0)
        assert total > 0
