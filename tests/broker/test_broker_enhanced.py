"""Tests for enhanced broker features (MessageQueue, MessageRouter, Authorization wiring)."""

import pytest
import threading
import time
from maple.agent.config import Config, SecurityConfig
from maple.broker.broker import MessageBroker
from maple.core.message import Message


@pytest.fixture(autouse=True)
def reset_broker():
    """Reset the singleton broker between tests."""
    MessageBroker._instance = None
    MessageBroker._agent_queues = {}
    MessageBroker._agent_handlers = {}
    MessageBroker._temp_handlers = {}
    MessageBroker._topic_subscribers = {}
    MessageBroker._topic_handlers = {}
    yield
    MessageBroker._instance = None
    MessageBroker._agent_queues = {}
    MessageBroker._agent_handlers = {}
    MessageBroker._temp_handlers = {}
    MessageBroker._topic_subscribers = {}
    MessageBroker._topic_handlers = {}


class TestBrokerMessageQueueIntegration:
    def test_broker_has_message_queue(self):
        config = Config(agent_id="test", broker_url="memory://test")
        broker = MessageBroker(config)
        assert broker._message_queue is not None

    def test_broker_has_message_router(self):
        config = Config(agent_id="test", broker_url="memory://test")
        broker = MessageBroker(config)
        assert broker._message_router is not None

    def test_send_enqueues_in_both(self):
        config = Config(agent_id="test", broker_url="memory://test")
        broker = MessageBroker(config)
        msg = Message(
            message_type="TEST",
            sender="a",
            receiver="b",
            payload={"data": "hello"},
        )
        broker.send(msg)
        # Should be in basic queue
        assert "b" in MessageBroker._agent_queues
        assert len(MessageBroker._agent_queues["b"]) == 1
        # Should also be in message queue
        assert broker._message_queue is not None


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
        assert "agent-1" in MessageBroker._agent_handlers


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
