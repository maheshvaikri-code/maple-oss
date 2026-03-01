"""Tests for maple.resources.specification - ResourceRange, TimeConstraint, ResourceRequest."""

import pytest
from maple.resources.specification import ResourceRange, TimeConstraint, ResourceRequest


class TestResourceRange:
    """Test ResourceRange dataclass."""

    def test_create_with_min_only(self):
        r = ResourceRange(min=4)
        assert r.min == 4
        assert r.preferred == 4  # defaults to min
        assert r.max == 4  # defaults to preferred

    def test_create_with_all(self):
        r = ResourceRange(min=4, preferred=8, max=16)
        assert r.min == 4
        assert r.preferred == 8
        assert r.max == 16

    def test_preferred_defaults_to_min(self):
        r = ResourceRange(min=4, max=16)
        assert r.preferred == 4

    def test_max_defaults_to_preferred(self):
        r = ResourceRange(min=4, preferred=8)
        assert r.max == 8

    def test_to_dict(self):
        r = ResourceRange(min=4, preferred=8, max=16)
        d = r.to_dict()
        assert d == {'min': 4, 'preferred': 8, 'max': 16}

    def test_from_dict(self):
        d = {'min': 4, 'preferred': 8, 'max': 16}
        r = ResourceRange.from_dict(d)
        assert r.min == 4
        assert r.preferred == 8
        assert r.max == 16

    def test_roundtrip(self):
        original = ResourceRange(min=2, preferred=4, max=8)
        restored = ResourceRange.from_dict(original.to_dict())
        assert restored.min == original.min
        assert restored.preferred == original.preferred
        assert restored.max == original.max

    def test_string_values(self):
        r = ResourceRange(min="8GB", preferred="16GB", max="32GB")
        assert r.min == "8GB"
        assert r.preferred == "16GB"
        assert r.max == "32GB"


class TestTimeConstraint:
    """Test TimeConstraint dataclass."""

    def test_create_with_timeout(self):
        tc = TimeConstraint(timeout="30s")
        assert tc.timeout == "30s"
        assert tc.deadline is None

    def test_create_with_deadline(self):
        tc = TimeConstraint(deadline="2025-01-01T00:00:00")
        assert tc.deadline == "2025-01-01T00:00:00"

    def test_create_with_both(self):
        tc = TimeConstraint(deadline="2025-01-01", timeout="60s")
        assert tc.deadline == "2025-01-01"
        assert tc.timeout == "60s"

    def test_to_dict_timeout_only(self):
        tc = TimeConstraint(timeout="30s")
        d = tc.to_dict()
        assert d == {'timeout': '30s'}
        assert 'deadline' not in d

    def test_to_dict_empty(self):
        tc = TimeConstraint()
        d = tc.to_dict()
        assert d == {}

    def test_from_dict(self):
        d = {'timeout': '30s', 'deadline': '2025-01-01'}
        tc = TimeConstraint.from_dict(d)
        assert tc.timeout == "30s"
        assert tc.deadline == "2025-01-01"

    def test_roundtrip(self):
        original = TimeConstraint(timeout="120s", deadline="2025-06-01")
        restored = TimeConstraint.from_dict(original.to_dict())
        assert restored.timeout == original.timeout
        assert restored.deadline == original.deadline


class TestResourceRequest:
    """Test ResourceRequest dataclass."""

    def test_create_empty(self):
        rr = ResourceRequest()
        assert rr.compute is None
        assert rr.memory is None
        assert rr.bandwidth is None
        assert rr.time is None
        assert rr.priority == "MEDIUM"

    def test_create_with_all(self):
        rr = ResourceRequest(
            compute=ResourceRange(min=4, preferred=8),
            memory=ResourceRange(min="8GB"),
            bandwidth=ResourceRange(min=100),
            time=TimeConstraint(timeout="60s"),
            priority="HIGH"
        )
        assert rr.compute.min == 4
        assert rr.memory.min == "8GB"
        assert rr.bandwidth.min == 100
        assert rr.time.timeout == "60s"
        assert rr.priority == "HIGH"

    def test_to_dict(self):
        rr = ResourceRequest(
            compute=ResourceRange(min=4),
            priority="HIGH"
        )
        d = rr.to_dict()
        assert d['priority'] == "HIGH"
        assert 'compute' in d
        assert d['compute']['min'] == 4
        assert 'memory' not in d

    def test_to_dict_all_fields(self):
        rr = ResourceRequest(
            compute=ResourceRange(min=4),
            memory=ResourceRange(min="8GB"),
            bandwidth=ResourceRange(min=100),
            time=TimeConstraint(timeout="30s"),
            priority="LOW"
        )
        d = rr.to_dict()
        assert 'compute' in d
        assert 'memory' in d
        assert 'bandwidth' in d
        assert 'time' in d
        assert d['priority'] == "LOW"

    def test_from_dict(self):
        d = {
            'compute': {'min': 4, 'preferred': 8, 'max': 16},
            'memory': {'min': '8GB', 'preferred': '16GB', 'max': '32GB'},
            'time': {'timeout': '60s'},
            'priority': 'HIGH'
        }
        rr = ResourceRequest.from_dict(d)
        assert rr.compute.min == 4
        assert rr.memory.min == "8GB"
        assert rr.time.timeout == "60s"
        assert rr.priority == "HIGH"
        assert rr.bandwidth is None

    def test_from_dict_minimal(self):
        d = {}
        rr = ResourceRequest.from_dict(d)
        assert rr.compute is None
        assert rr.priority == "MEDIUM"

    def test_roundtrip(self):
        original = ResourceRequest(
            compute=ResourceRange(min=4, preferred=8, max=16),
            memory=ResourceRange(min="8GB"),
            time=TimeConstraint(timeout="120s"),
            priority="HIGH"
        )
        restored = ResourceRequest.from_dict(original.to_dict())
        assert restored.compute.min == original.compute.min
        assert restored.compute.preferred == original.compute.preferred
        assert restored.memory.min == original.memory.min
        assert restored.time.timeout == original.time.timeout
        assert restored.priority == original.priority

    def test_range_factory(self):
        r = ResourceRequest.Range(min=4, preferred=8)
        assert isinstance(r, ResourceRange)
        assert r.min == 4
        assert r.preferred == 8

    def test_time_constraint_factory(self):
        tc = ResourceRequest.TimeConstraint(timeout="30s")
        assert isinstance(tc, TimeConstraint)
        assert tc.timeout == "30s"
