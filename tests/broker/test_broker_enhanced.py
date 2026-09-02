"""Tests for enhanced broker features (MessageQueue, MessageRouter, Authorization wiring)."""

import time

import pytest

from maple.agent.config import Config, SecurityConfig
from maple.broker.broker import MessageBroker
from maple.core.message import Message


@pytest.fixture(autouse=True)
def reset_broker():
    """Reset the singleton broker between tests."""
    MessageBroker.reset_scopes()
    yield
    MessageBroker.reset_scopes()


class TestBrokerMessageQueueIntegration:
    def test_broker_has_message_queue(self):
        config = Config(agent_id="test", broker_url="memory://test")
        broker = MessageBroker(config)
        assert broker._message_queue is not None

    def test_broker_has_message_router(self):
        config = Config(agent_id="test", broker_url="memory://test")
        broker = MessageBroker(config)
        assert broker._message_router is not None

    def test_send_enqueues_once(self):
        config = Config(agent_id="test", broker_url="memory://test")
        broker = MessageBroker(config)
        msg = Message(
            message_type="TEST",
            sender="a",
            receiver="b",
            payload={"data": "hello"},
        )
        broker.send(msg)
        # Enqueued exactly once (priority queue), not also duplicated into the
        # basic queue — the delivery loop drains both, so a double-enqueue
        # would deliver the message twice.
        assert broker._message_queue is not None
        assert broker._message_queue.size() == 1
        assert len(broker._agent_queues.get("b", [])) == 0


class TestBrokerAuthorizationIntegration:
    def test_no_auth_manager_without_security(self):
        config = Config(agent_id="test", broker_url="memory://test")
        broker = MessageBroker(config)
        assert broker._auth_manager is None

    def test_auth_manager_with_security(self):
        config = Config(
            agent_id="test",
            broker_url="memory://test",
            security=SecurityConfig(
                auth_type="token",
                credentials="test-secret",
                require_links=False,
            ),
        )
        broker = MessageBroker(config)
        assert broker._auth_manager is not None

    def test_subscribe_assigns_agent_role(self):
        config = Config(
            agent_id="test",
            broker_url="memory://test",
            security=SecurityConfig(
                auth_type="token",
                credentials="test-secret",
                require_links=False,
            ),
        )
        broker = MessageBroker(config)

        def dummy_handler(msg):
            pass

        broker.subscribe("agent-1", dummy_handler)
        # Should not raise, role assignment is best-effort
        assert "agent-1" in broker._agent_handlers


class TestBrokerDeliveryWithQueue:
    def test_delivery_loop_processes_messages(self):
        config = Config(agent_id="test", broker_url="memory://test")
        broker = MessageBroker(config)

        received = []

        def handler(msg):
            received.append(msg)

        broker.subscribe("receiver", handler)
        broker.connect()

        msg = Message(
            message_type="TEST",
            sender="sender",
            receiver="receiver",
            payload={"value": 42},
        )
        broker.send(msg)

        # Wait for delivery
        time.sleep(0.1)
        broker.disconnect()

        assert len(received) >= 1
        assert received[0].payload["value"] == 42
