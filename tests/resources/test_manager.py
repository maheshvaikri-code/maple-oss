"""Tests for maple.resources.manager - ResourceManager."""

import pytest
from maple.resources.manager import ResourceManager, ResourceAllocation
from maple.resources.specification import ResourceRequest, ResourceRange, TimeConstraint


@pytest.fixture
def manager():
    rm = ResourceManager()
    rm.register_resource("compute", 32)
    rm.register_resource("memory", 65536)  # 64GB in MB
    rm.register_resource("bandwidth", 1000)
    return rm


class TestResourceAllocation:
    """Test ResourceAllocation class."""

    def test_create(self):
        alloc = ResourceAllocation("alloc_1", {"compute": 4, "memory": 8192})
        assert alloc.allocation_id == "alloc_1"
        assert alloc.resources['compute'] == 4

    def test_to_dict(self):
        alloc = ResourceAllocation("alloc_1", {"compute": 4})
        d = alloc.to_dict()
        assert d['allocation_id'] == "alloc_1"
        assert d['resources']['compute'] == 4


class TestRegisterResource:
    """Test resource registration."""

    def test_register(self):
        rm = ResourceManager()
        rm.register_resource("compute", 16)
        available = rm.get_available_resources()
        assert available['compute'] == 16

    def test_register_overwrites(self):
        rm = ResourceManager()
        rm.register_resource("compute", 16)
        rm.register_resource("compute", 32)
        available = rm.get_available_resources()
        assert available['compute'] == 32

    def test_get_available_is_copy(self):
        rm = ResourceManager()
        rm.register_resource("compute", 16)
        available = rm.get_available_resources()
        available['compute'] = 999
        assert rm.get_available_resources()['compute'] == 16


class TestAllocate:
    """Test resource allocation."""

    def test_allocate_compute(self, manager):
        request = ResourceRequest(compute=ResourceRange(min=4, preferred=8))
        result = manager.allocate(request)
        assert result.is_ok()
        alloc = result.unwrap()
        assert alloc.resources['compute'] == 8

    def test_allocate_reduces_available(self, manager):
        request = ResourceRequest(compute=ResourceRange(min=4, preferred=8))
        manager.allocate(request)
        available = manager.get_available_resources()
        assert available['compute'] == 24

    def test_allocate_insufficient_resources(self):
        rm = ResourceManager()
        rm.register_resource("compute", 2)
        request = ResourceRequest(compute=ResourceRange(min=4))
        result = rm.allocate(request)
        assert result.is_err()
        assert result.unwrap_err()['errorType'] == 'RESOURCE_UNAVAILABLE'

    def test_allocate_from_dict(self, manager):
        request_dict = {
            'compute': {'min': 4, 'preferred': 8, 'max': 16},
            'priority': 'HIGH'
        }
        result = manager.allocate(request_dict)
        assert result.is_ok()

    def test_allocate_preferred_capped_at_available(self):
        rm = ResourceManager()
        rm.register_resource("compute", 6)
        request = ResourceRequest(compute=ResourceRange(min=4, preferred=8))
        result = rm.allocate(request)
        assert result.is_ok()
        alloc = result.unwrap()
        assert alloc.resources['compute'] == 6

    def test_allocate_bandwidth(self, manager):
        request = ResourceRequest(bandwidth=ResourceRange(min=100, preferred=200))
        result = manager.allocate(request)
        assert result.is_ok()
        alloc = result.unwrap()
        assert alloc.resources['bandwidth'] == 200

    def test_multiple_allocations(self, manager):
        r1 = ResourceRequest(compute=ResourceRange(min=4, preferred=8))
        r2 = ResourceRequest(compute=ResourceRange(min=4, preferred=8))
        res1 = manager.allocate(r1)
        res2 = manager.allocate(r2)
        assert res1.is_ok()
        assert res2.is_ok()
        assert res1.unwrap().allocation_id != res2.unwrap().allocation_id

    def test_no_matching_resource_type(self):
        rm = ResourceManager()
        request = ResourceRequest(compute=ResourceRange(min=4))
        result = rm.allocate(request)
        assert result.is_ok()  # No compute registered means no shortfall check


class TestRelease:
    """Test resource release."""

    def test_release_restores_resources(self, manager):
        request = ResourceRequest(compute=ResourceRange(min=4, preferred=8))
        alloc = manager.allocate(request).unwrap()
        before = manager.get_available_resources()['compute']
        manager.release(alloc)
        after = manager.get_available_resources()['compute']
        assert after == before + 8

    def test_release_removes_allocation(self, manager):
        request = ResourceRequest(compute=ResourceRange(min=4, preferred=8))
        alloc = manager.allocate(request).unwrap()
        manager.release(alloc)
        assert alloc.allocation_id not in manager.allocations

    def test_release_nonexistent(self, manager):
        fake_alloc = ResourceAllocation("fake_id", {"compute": 4})
        manager.release(fake_alloc)  # Should not raise
