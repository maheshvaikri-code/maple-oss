"""Tests for resource-model improvement #6 (revalidate with owner; uncommitted spike).

Three cohesive additions to the resources subsystem:
  - ResourceLifecycle taxonomy + lifecycle-driven release() (renewable refunds, consumable
    stays spent) -- fixes release() hard-coding a compute/memory/bandwidth/tokens list.
  - `ResourceRequest.custom` -- arbitrary named numeric dimensions (gpu, disk, money, ...).
  - LeaseManager/Lease -- exclusive, TTL-bounded leases with fencing tokens (the "one
    holder at a time" semantic the renewable pool cannot express).

All additions are backward-compatible; the built-in fields behave exactly as before.
"""

import threading

import pytest

from maple.resources.manager import (
    ResourceManager,
    ResourceLifecycle,
    DEFAULT_LIFECYCLES,
)
from maple.resources.specification import ResourceRequest, ResourceRange
from maple.resources.lease import Lease, LeaseManager


# --------------------------------------------------------------------------- #
# Lifecycle taxonomy
# --------------------------------------------------------------------------- #
class TestResourceLifecycle:
    def test_known_defaults(self):
        assert DEFAULT_LIFECYCLES["compute"] == ResourceLifecycle.RENEWABLE
        assert DEFAULT_LIFECYCLES["gpu"] == ResourceLifecycle.RENEWABLE
        assert DEFAULT_LIFECYCLES["money"] == ResourceLifecycle.CONSUMABLE
        assert DEFAULT_LIFECYCLES["api_calls"] == ResourceLifecycle.CONSUMABLE

    def test_register_uses_default_lifecycle(self):
        rm = ResourceManager()
        rm.register_resource("money", 100)
        assert rm.lifecycle_of("money") == ResourceLifecycle.CONSUMABLE

    def test_register_explicit_override(self):
        rm = ResourceManager()
        # Force a normally-renewable type to be consumable for this manager.
        rm.register_resource("compute", 10, lifecycle=ResourceLifecycle.CONSUMABLE)
        assert rm.lifecycle_of("compute") == ResourceLifecycle.CONSUMABLE

    def test_unknown_type_defaults_renewable(self):
        rm = ResourceManager()
        rm.register_resource("widgets", 5)
        assert rm.lifecycle_of("widgets") == ResourceLifecycle.RENEWABLE

    def test_lifecycle_of_unregistered_falls_back(self):
        rm = ResourceManager()
        assert rm.lifecycle_of("money") == ResourceLifecycle.CONSUMABLE  # via DEFAULT_LIFECYCLES
        assert rm.lifecycle_of("mystery") == ResourceLifecycle.RENEWABLE


class TestLifecycleRelease:
    def test_renewable_is_refunded(self):
        rm = ResourceManager()
        rm.register_resource("gpu", 8)  # renewable by default
        alloc = rm.allocate(ResourceRequest(custom={"gpu": ResourceRange(min=2)})).unwrap()
        assert rm.get_available_resources()["gpu"] == 6
        rm.release(alloc)
        assert rm.get_available_resources()["gpu"] == 8  # returned to the pool

    def test_consumable_is_not_refunded(self):
        rm = ResourceManager()
        rm.register_resource("money", 100)  # consumable by default
        alloc = rm.allocate(ResourceRequest(custom={"money": ResourceRange(min=30)})).unwrap()
        assert rm.get_available_resources()["money"] == 70
        rm.release(alloc)
        assert rm.get_available_resources()["money"] == 70  # spent stays spent

    def test_mixed_release_refunds_only_renewable(self):
        rm = ResourceManager()
        rm.register_resource("gpu", 4)
        rm.register_resource("money", 100)
        alloc = rm.allocate(ResourceRequest(custom={
            "gpu": ResourceRange(min=1),
            "money": ResourceRange(min=10),
        })).unwrap()
        rm.release(alloc)
        avail = rm.get_available_resources()
        assert avail["gpu"] == 4    # refunded
        assert avail["money"] == 90  # not refunded

    def test_builtin_compute_still_refunds(self):
        # Backward-compat: the historical renewable pools behave exactly as before.
        rm = ResourceManager()
        rm.register_resource("compute", 32)
        alloc = rm.allocate(ResourceRequest(compute=ResourceRange(min=4, preferred=8))).unwrap()
        assert rm.get_available_resources()["compute"] == 24
        rm.release(alloc)
        assert rm.get_available_resources()["compute"] == 32

    def test_override_makes_compute_consumable(self):
        rm = ResourceManager()
        rm.register_resource("compute", 32, lifecycle=ResourceLifecycle.CONSUMABLE)
        alloc = rm.allocate(ResourceRequest(compute=ResourceRange(min=4, preferred=8))).unwrap()
        rm.release(alloc)
        assert rm.get_available_resources()["compute"] == 24  # not refunded now


# --------------------------------------------------------------------------- #
# ResourceRequest.custom (spec)
# --------------------------------------------------------------------------- #
class TestCustomSpec:
    def test_default_is_none(self):
        assert ResourceRequest().custom is None

    def test_omitted_when_unset(self):
        assert "custom" not in ResourceRequest(compute=ResourceRange(min=4)).to_dict()

    def test_custom_in_to_dict(self):
        rr = ResourceRequest(custom={"gpu": ResourceRange(min=1, preferred=2, max=4)})
        d = rr.to_dict()
        assert d["custom"]["gpu"] == {"min": 1, "preferred": 2, "max": 4}

    def test_custom_from_dict(self):
        rr = ResourceRequest.from_dict({"custom": {"disk": {"min": 10, "preferred": 20}}})
        assert isinstance(rr.custom["disk"], ResourceRange)
        assert rr.custom["disk"].min == 10
        assert rr.custom["disk"].preferred == 20

    def test_custom_roundtrip(self):
        original = ResourceRequest(
            compute=ResourceRange(min=2),
            custom={
                "gpu": ResourceRange(min=1, preferred=2),
                "money": ResourceRange(min=5, preferred=10, max=20),
            },
            priority="HIGH",
        )
        restored = ResourceRequest.from_dict(original.to_dict())
        assert restored.custom["gpu"].preferred == 2
        assert restored.custom["money"].max == 20
        assert restored.compute.min == 2
        assert restored.priority == "HIGH"


# --------------------------------------------------------------------------- #
# ResourceManager custom-dimension allocation
# --------------------------------------------------------------------------- #
class TestCustomAllocation:
    def test_allocate_custom(self):
        rm = ResourceManager()
        rm.register_resource("gpu", 8)
        alloc = rm.allocate(
            ResourceRequest(custom={"gpu": ResourceRange(min=1, preferred=3)})
        ).unwrap()
        assert alloc.resources["gpu"] == 3
        assert rm.get_available_resources()["gpu"] == 5

    def test_custom_shortfall(self):
        rm = ResourceManager()
        rm.register_resource("gpu", 2)
        result = rm.allocate(ResourceRequest(custom={"gpu": ResourceRange(min=4)}))
        assert result.is_err()
        err = result.unwrap_err()
        assert err["errorType"] == "RESOURCE_UNAVAILABLE"
        assert "gpu" in err["details"]["shortfall"]

    def test_unregistered_custom_is_ignored(self):
        # Mirrors the built-in fields: an unregistered dimension is a no-op, not a shortfall.
        rm = ResourceManager()
        result = rm.allocate(ResourceRequest(custom={"gpu": ResourceRange(min=4)}))
        assert result.is_ok()
        assert "gpu" not in result.unwrap().resources

    def test_custom_preferred_capped_at_available(self):
        rm = ResourceManager()
        rm.register_resource("gpu", 2)
        alloc = rm.allocate(
            ResourceRequest(custom={"gpu": ResourceRange(min=1, preferred=8)})
        ).unwrap()
        assert alloc.resources["gpu"] == 2  # capped at what's available

    def test_custom_and_builtin_together(self):
        rm = ResourceManager()
        rm.register_resource("compute", 16)
        rm.register_resource("gpu", 4)
        rm.register_resource("money", 100)
        alloc = rm.allocate(ResourceRequest(
            compute=ResourceRange(min=2, preferred=4),
            custom={
                "gpu": ResourceRange(min=1, preferred=2),
                "money": ResourceRange(min=10, preferred=25),
            },
        )).unwrap()
        assert alloc.resources["compute"] == 4
        assert alloc.resources["gpu"] == 2
        assert alloc.resources["money"] == 25

    def test_custom_size_string_dimension(self):
        # A custom dimension may carry a size string (e.g. disk '10GB' -> bytes).
        rm = ResourceManager()
        rm.register_resource("disk", "10GB")
        alloc = rm.allocate(
            ResourceRequest(custom={"disk": ResourceRange(min="1GB", preferred="4GB")})
        ).unwrap()
        assert alloc.resources["disk"] == pytest.approx(4 * 1024 ** 3)


# --------------------------------------------------------------------------- #
# LeaseManager / Lease (exclusive leases)
# --------------------------------------------------------------------------- #
class FakeClock:
    """A manually advanced monotonic clock for deterministic expiry tests."""

    def __init__(self, start: float = 0.0):
        self.t = start

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


class TestLeaseBasics:
    def test_acquire_free_resource(self):
        lm = LeaseManager()
        result = lm.acquire("dev0", "agentA", ttl_seconds=60)
        assert result.is_ok()
        lease = result.unwrap()
        assert isinstance(lease, Lease)
        assert lease.holder == "agentA"
        assert lease.resource == "dev0"
        assert lm.holder_of("dev0") == "agentA"
        assert lm.is_held("dev0")

    def test_second_holder_rejected(self):
        lm = LeaseManager()
        lm.acquire("dev0", "agentA", 60)
        result = lm.acquire("dev0", "agentB", 60)
        assert result.is_err()
        err = result.unwrap_err()
        assert err["errorType"] == "RESOURCE_HELD"
        assert err["details"]["holder"] == "agentA"
        assert err["details"]["expires_in"] > 0

    def test_same_holder_reacquire_renews_with_new_token(self):
        lm = LeaseManager()
        first = lm.acquire("dev0", "agentA", 60).unwrap()
        second = lm.acquire("dev0", "agentA", 60).unwrap()
        assert second.token > first.token  # fencing token strictly increases

    def test_invalid_ttl_rejected(self):
        lm = LeaseManager()
        assert lm.acquire("dev0", "agentA", 0).is_err()
        assert lm.acquire("dev0", "agentA", -5).unwrap_err()["errorType"] == "INVALID_TTL"

    def test_free_resource_has_no_holder(self):
        lm = LeaseManager()
        assert lm.holder_of("nobody") is None
        assert not lm.is_held("nobody")


class TestLeaseExpiryAndFencing:
    def test_expiry_allows_preemption(self):
        clock = FakeClock()
        lm = LeaseManager(clock=clock)
        lm.acquire("dev0", "agentA", ttl_seconds=10)
        clock.advance(11)  # A's lease expired
        result = lm.acquire("dev0", "agentB", ttl_seconds=10)
        assert result.is_ok()
        assert lm.holder_of("dev0") == "agentB"

    def test_stale_holder_is_invalid_after_preemption(self):
        clock = FakeClock()
        lm = LeaseManager(clock=clock)
        stale = lm.acquire("dev0", "agentA", 10).unwrap()
        assert lm.is_valid(stale)
        clock.advance(11)
        lm.acquire("dev0", "agentB", 10)  # B preempts the expired lease
        # The classic fence: A resumes, but its token is no longer current.
        assert lm.is_valid(stale) is False

    def test_is_valid_false_when_simply_expired(self):
        clock = FakeClock()
        lm = LeaseManager(clock=clock)
        lease = lm.acquire("dev0", "agentA", 10).unwrap()
        clock.advance(11)
        assert lm.is_valid(lease) is False  # expired even with no preemptor

    def test_holder_of_none_after_expiry(self):
        clock = FakeClock()
        lm = LeaseManager(clock=clock)
        lm.acquire("dev0", "agentA", 10)
        clock.advance(11)
        assert lm.holder_of("dev0") is None
        assert lm.is_held("dev0") is False


class TestLeaseReleaseAndRenew:
    def test_release_by_current_holder(self):
        lm = LeaseManager()
        lease = lm.acquire("dev0", "agentA", 60).unwrap()
        assert lm.release(lease).unwrap() is True
        assert not lm.is_held("dev0")

    def test_release_by_stale_holder_is_noop(self):
        clock = FakeClock()
        lm = LeaseManager(clock=clock)
        stale = lm.acquire("dev0", "agentA", 10).unwrap()
        clock.advance(11)
        newlease = lm.acquire("dev0", "agentB", 10).unwrap()
        # Stale A tries to release -> must NOT drop B's live lease.
        assert lm.release(stale).unwrap() is False
        assert lm.is_valid(newlease) is True
        assert lm.holder_of("dev0") == "agentB"

    def test_renew_extends_and_bumps_token(self):
        clock = FakeClock()
        lm = LeaseManager(clock=clock)
        lease = lm.acquire("dev0", "agentA", 10).unwrap()
        clock.advance(5)
        renewed = lm.renew(lease, 10).unwrap()
        assert renewed.token > lease.token
        assert renewed.expires_at == clock.t + 10
        clock.advance(9)  # would have expired under the old deadline (15), still valid now
        assert lm.is_valid(renewed) is True

    def test_renew_after_lost_fails(self):
        clock = FakeClock()
        lm = LeaseManager(clock=clock)
        lease = lm.acquire("dev0", "agentA", 10).unwrap()
        clock.advance(11)
        lm.acquire("dev0", "agentB", 10)  # A lost it
        result = lm.renew(lease, 10)
        assert result.is_err()
        assert result.unwrap_err()["errorType"] == "LEASE_LOST"

    def test_renew_invalid_ttl(self):
        lm = LeaseManager()
        lease = lm.acquire("dev0", "agentA", 60).unwrap()
        assert lm.renew(lease, 0).unwrap_err()["errorType"] == "INVALID_TTL"


class TestLeaseConcurrency:
    def test_only_one_of_many_acquirers_wins(self):
        lm = LeaseManager()
        winners = []
        barrier = threading.Barrier(20)

        def contend(agent_id):
            barrier.wait()  # maximize the race
            result = lm.acquire("scarce", agent_id, ttl_seconds=60)
            if result.is_ok():
                winners.append(agent_id)

        threads = [threading.Thread(target=contend, args=(f"a{i}",)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(winners) == 1  # exactly one holder despite 20 concurrent acquirers
        assert lm.holder_of("scarce") == winners[0]
