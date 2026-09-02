"""Scope isolation (ADR-160).

`broker_url` carries a namespace that used to be discarded: every URL returned
the same process-wide broker, so `memory://tenant-a` and `memory://tenant-b`
shared one bus, one set of handlers, and one discovery registry. Agents on
deliberately separate buses enumerated each other.
"""

import time

import pytest

from maple.agent.agent import Agent
from maple.agent.config import Config, SecurityConfig
from maple.broker.broker import MessageBroker
from maple.core.message import Message


@pytest.fixture(autouse=True)
def reset_scopes():
    MessageBroker.reset_scopes()
    Agent._shared_registry = None
    yield
    MessageBroker.reset_scopes()
    Agent._shared_registry = None


def _agent(agent_id, url):
    return Agent(Config(agent_id=agent_id, broker_url=url))


class TestScopeKey:
    def test_absent_url_resolves_to_the_default_scope(self):
        assert MessageBroker.scope_key(None) == "default"
        assert MessageBroker.scope_key("") == "default"
        assert MessageBroker.scope_key("   ") == "default"

    def test_a_url_is_its_own_scope(self):
        assert MessageBroker.scope_key("memory://a") == "memory://a"

    def test_surrounding_whitespace_does_not_create_a_second_scope(self):
        assert MessageBroker.scope_key("  memory://a  ") == MessageBroker.scope_key(
            "memory://a"
        )


class TestBrokerIsolation:
    def test_different_urls_get_different_brokers(self):
        a = _agent("a", "memory://tenant-a")
        b = _agent("b", "memory://tenant-b")
        assert a.broker is not b.broker

    def test_same_url_still_shares_one_broker(self):
        a = _agent("a", "memory://shared")
        b = _agent("b", "memory://shared")
        assert a.broker is b.broker

    def test_each_broker_reports_its_own_url(self):
        """Previously every agent reported the first config's URL."""
        a = _agent("a", "memory://tenant-a")
        b = _agent("b", "memory://tenant-b")
        assert a.broker.config.broker_url == "memory://tenant-a"
        assert b.broker.config.broker_url == "memory://tenant-b"

    def test_handlers_do_not_leak_between_scopes(self):
        received = []
        alice = _agent("alice", "memory://tenant-a")
        intruder = _agent("alice", "memory://tenant-b")  # same id, other scope

        @intruder.handler("PING")
        def _handle(message):  # pragma: no cover - must never run
            received.append(message)

        alice.start()
        intruder.start()
        try:
            alice.send(Message(message_type="PING", receiver="alice", payload={}))
            time.sleep(0.5)
            assert received == []
        finally:
            alice.stop()
            intruder.stop()

    def test_a_message_is_undeliverable_across_a_scope_boundary(self):
        alice = _agent("alice", "memory://tenant-a")
        _agent("bob", "memory://tenant-b").start()
        alice.start()
        try:
            alice.send(Message(message_type="PING", receiver="bob", payload={}))
            time.sleep(0.5)
            assert alice.broker.get_statistics()["undeliverable"] == 1
        finally:
            alice.stop()


class TestRegistryIsolation:
    """The cross-tenant discovery leak this ADR exists to close."""

    def test_discovery_does_not_cross_scopes(self):
        a = _agent("a-worker", "memory://tenant-a")
        b = _agent("b-worker", "memory://tenant-b")
        a.start()
        b.start()
        try:
            assert a.registry is not b.registry

            seen_by_a = {
                getattr(x, "agent_id", x) for x in (a.registry.list_agents() or [])
            }
            seen_by_b = {
                getattr(x, "agent_id", x) for x in (b.registry.list_agents() or [])
            }
            assert seen_by_a == {"a-worker"}
            assert seen_by_b == {"b-worker"}
        finally:
            a.stop()
            b.stop()

    def test_agents_in_one_scope_share_a_registry(self):
        a = _agent("one", "memory://team")
        b = _agent("two", "memory://team")
        a.start()
        b.start()
        try:
            assert a.registry is b.registry
        finally:
            a.stop()
            b.stop()


class TestSecurityIsolation:
    def test_a_security_config_does_not_arm_another_scope(self):
        """ADR-157 adoption is per-scope, not process-wide."""
        secure = _agent("secure", "memory://locked")
        sec = SecurityConfig("jwt", {"token": "t"}, require_links=True)
        armed = Agent(
            Config(agent_id="armed", broker_url="memory://locked", security=sec)
        )
        plain = _agent("plain", "memory://open")

        assert armed.broker.security_config is sec
        assert secure.broker.security_config is sec  # same scope
        assert plain.broker.security_config is None  # different scope


class TestResetScopes:
    def test_reset_scopes_drops_every_scope(self):
        first = _agent("a", "memory://x").broker
        MessageBroker.reset_scopes()
        second = _agent("a", "memory://x").broker
        assert first is not second

    def test_reset_replaces_the_manual_surgery_tests_used_to_do(self):
        """State is on the instance now, so clearing class dicts would no-op."""
        agent = _agent("a", "memory://y")
        agent.start()
        try:
            agent.send(Message(message_type="X", receiver="ghost", payload={}))
            time.sleep(0.3)
            assert agent.broker.get_statistics()["undeliverable"] >= 1
        finally:
            agent.stop()

        MessageBroker.reset_scopes()
        fresh = _agent("a", "memory://y")
        assert fresh.broker.get_statistics()["undeliverable"] == 0
