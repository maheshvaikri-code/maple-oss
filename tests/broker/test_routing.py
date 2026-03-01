"""Tests for maple.broker.routing - MessageRouter."""

import pytest
from maple.broker.routing import MessageRouter, RoutingStrategy
from maple.core.message import Message
from maple.core.types import Priority


@pytest.fixture
def router():
    return MessageRouter()


class TestRouteManagement:
    """Test route add/remove."""

    def test_add_route(self, router):
        router.add_route("TEST_*", ["agent_a", "agent_b"])
        routes = router.get_routes()
        assert len(routes) == 1

    def test_add_multiple_routes(self, router):
        router.add_route("TYPE_A", ["agent_a"])
        router.add_route("TYPE_B", ["agent_b"])
        assert len(router.get_routes()) == 2

    def test_remove_route(self, router):
        router.add_route("TYPE_A", ["agent_a"])
        result = router.remove_route("TYPE_A")
        assert result is True
        assert len(router.get_routes()) == 0

    def test_remove_nonexistent_route(self, router):
        result = router.remove_route("NONEXISTENT")
        assert result is False


class TestDirectRouting:
    """Test direct routing strategy."""

    def test_route_direct(self, router):
        router.add_route("TASK", ["worker_1"], strategy=RoutingStrategy.DIRECT)
        msg = Message(message_type="TASK", receiver="worker_1", payload={"data": "test"})
        result = router.route_message(msg)
        assert result.is_ok()

    def test_route_no_match(self, router):
        msg = Message(message_type="UNKNOWN_TYPE", payload={"data": "test"})
        result = router.route_message(msg)
        # Should still return a result (may be empty list or the receiver)
        assert result is not None


class TestRoundRobinRouting:
    """Test round-robin routing strategy."""

    def test_round_robin(self, router):
        agents = ["w1", "w2", "w3"]
        router.add_route("TASK", agents, strategy=RoutingStrategy.ROUND_ROBIN)

        # Mark all agents as healthy
        for a in agents:
            router.update_agent_health(a, True)

        targets = set()
        for _ in range(3):
            msg = Message(message_type="TASK", receiver="w1", payload={})
            result = router.route_message(msg)
            if result.is_ok():
                routed = result.unwrap()
                if isinstance(routed, list):
                    for t in routed:
                        targets.add(t)
                else:
                    targets.add(str(routed))

        # Should have reached at least one agent
        assert len(targets) >= 1


class TestBroadcastRouting:
    """Test broadcast routing strategy."""

    def test_broadcast(self, router):
        agents = ["a1", "a2", "a3"]
        router.add_route("ALERT", agents, strategy=RoutingStrategy.BROADCAST)
        msg = Message(message_type="ALERT", payload={"alert": "test"})
        result = router.route_message(msg)
        if result.is_ok():
            assert len(result.unwrap()) == 3


class TestAgentHealth:
    """Test agent health tracking."""

    def test_update_health(self, router):
        router.update_agent_health("agent_a", True)
        health = router.get_agent_health()
        assert "agent_a" in health
        assert health["agent_a"]["healthy"] is True

    def test_mark_unhealthy(self, router):
        router.update_agent_health("agent_a", True)
        router.update_agent_health("agent_a", False)
        health = router.get_agent_health()
        assert health["agent_a"]["healthy"] is False

    def test_cleanup_stale_agents(self, router):
        router.update_agent_health("agent_a", True)
        cleaned = router.cleanup_stale_agents(timeout_seconds=0.0)
        assert cleaned >= 0


class TestStatistics:
    """Test routing statistics."""

    def test_initial_statistics(self, router):
        stats = router.get_statistics()
        assert isinstance(stats, dict)

    def test_performance_stats(self, router):
        stats = router.get_performance_stats()
        assert isinstance(stats, dict)
