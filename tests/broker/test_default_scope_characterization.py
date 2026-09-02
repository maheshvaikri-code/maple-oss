"""Pins the behaviour the default scope must keep across the ADR-160 migration.

ADR-160 names the single largest risk of introducing AgentScope: "The default
scope must behave exactly as today, or every existing deployment changes
semantics silently."

These tests are written to pass BEFORE the migration and must still pass
after it, unchanged. They characterise what callers actually rely on, so a
regression shows up here rather than in somebody's deployment.

They are deliberately behavioural — no assertions about `_instance`, class
attributes, or any other private mechanism the migration is free to change.
"""

import time

import pytest

from maple.agent.agent import Agent
from maple.agent.config import Config, SecurityConfig
from maple.broker.broker import MessageBroker
from maple.core.message import Message


def _reset_broker_singleton():
    MessageBroker.reset_scopes()
    Agent._shared_registry = None


@pytest.fixture(autouse=True)
def reset_runtime():
    _reset_broker_singleton()
    yield
    _reset_broker_singleton()


SCOPE = "memory://characterization"


class TestSameScopeSharing:
    """Agents addressing the same broker share one bus. The core contract."""

    def test_two_agents_on_one_url_share_a_broker(self):
        a = Agent(Config(agent_id="a", broker_url=SCOPE))
        b = Agent(Config(agent_id="b", broker_url=SCOPE))
        assert a.broker is b.broker

    def test_messages_flow_between_agents_on_one_url(self):
        received = []
        alice = Agent(Config(agent_id="alice", broker_url=SCOPE))
        bob = Agent(Config(agent_id="bob", broker_url=SCOPE))

        @bob.handler("PING")
        def _handle(message):
            received.append(message.payload["n"])

        alice.start()
        bob.start()
        try:
            for n in range(5):
                assert alice.send(
                    Message(message_type="PING", receiver="bob", payload={"n": n})
                ).is_ok()
            time.sleep(0.8)
            assert sorted(received) == [0, 1, 2, 3, 4]
        finally:
            alice.stop()
            bob.stop()

    def test_topic_publish_reaches_subscribers_on_the_same_url(self):
        got = []
        pub = Agent(Config(agent_id="pub", broker_url=SCOPE))
        sub = Agent(Config(agent_id="sub", broker_url=SCOPE))
        sub.start()
        pub.start()
        try:
            sub.broker.subscribe_topic(
                "news", lambda topic, m: got.append(topic), agent_id="sub"
            )
            pub.broker.publish("news", Message(message_type="NEWS", payload={}))
            time.sleep(0.5)
            assert got == ["news"]
        finally:
            pub.stop()
            sub.stop()

    def test_is_routable_reflects_a_started_agent(self):
        alice = Agent(Config(agent_id="alice", broker_url=SCOPE))
        bob = Agent(Config(agent_id="bob", broker_url=SCOPE))
        alice.start()
        try:
            assert alice.broker.is_routable("alice") is True
            assert alice.broker.is_routable("bob") is False
            bob.start()
            try:
                assert alice.broker.is_routable("bob") is True
            finally:
                bob.stop()
        finally:
            alice.stop()


class TestSecurityContractSurvives:
    """ADR-157 and ADR-159 guarantees must not regress in the default scope."""

    def test_security_config_reaches_the_broker(self):
        Agent(Config(agent_id="plain", broker_url=SCOPE))
        sec = SecurityConfig("jwt", {"token": "t"})
        second = Agent(Config(agent_id="secure", broker_url=SCOPE, security=sec))

        assert second.broker.security_config is sec
        assert second.broker.link_manager is not None

    def test_a_later_plain_config_does_not_disarm_security(self):
        sec = SecurityConfig("jwt", {"token": "t"})
        first = Agent(Config(agent_id="secure", broker_url=SCOPE, security=sec))
        Agent(Config(agent_id="plain", broker_url=SCOPE))
        assert first.broker.security_config is sec

    def test_strict_link_policy_still_refuses_an_unlinked_send(self):
        from maple.broker.broker import SecurityError

        sec = SecurityConfig(
            "jwt", {"token": "t"}, require_links=True, strict_link_policy=True
        )
        agent = Agent(Config(agent_id="alice", broker_url=SCOPE, security=sec))

        with pytest.raises(SecurityError):
            agent.broker.send(
                Message(
                    message_type="SECRET",
                    sender="alice",
                    receiver="mallory",
                    payload={},
                )
            )


class TestDeliveryContractSurvives:
    """ADR-159 accounting must not regress."""

    def test_backpressure_still_refuses_when_full(self):
        from maple.agent.config import PerformanceConfig

        agent = Agent(
            Config(
                agent_id="p",
                broker_url=SCOPE,
                performance=PerformanceConfig(max_queue_size=3),
            )
        )
        results = [
            agent.send(Message(message_type="X", receiver="stalled", payload={"i": i}))
            for i in range(20)
        ]
        assert sum(r.is_ok() for r in results) == 3
        assert results[-1].unwrap_err()["errorType"] == "QUEUE_FULL"

    def test_undeliverable_messages_are_still_counted(self):
        agent = Agent(Config(agent_id="s", broker_url=SCOPE))
        agent.start()
        try:
            agent.send(Message(message_type="X", receiver="ghost", payload={}))
            time.sleep(0.4)
            assert agent.broker.get_statistics()["undeliverable"] == 1
        finally:
            agent.stop()


class TestRegistryContractSurvives:
    """Discovery must keep working for agents that share a scope."""

    def test_agents_on_one_url_are_discoverable_together(self):
        a = Agent(Config(agent_id="worker-a", broker_url=SCOPE))
        b = Agent(Config(agent_id="worker-b", broker_url=SCOPE))
        a.start()
        b.start()
        try:
            assert a.registry is not None
            assert a.registry is b.registry
        finally:
            a.stop()
            b.stop()
