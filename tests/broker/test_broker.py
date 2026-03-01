"""Tests for maple.broker.broker - MessageBroker."""

import pytest
import time
import threading
from maple.broker.broker import MessageBroker, SecurityError
from maple.agent.config import Config
from maple.core.message import Message
from maple.core.types import Priority


def _reset_broker_singleton():
    """Reset the MessageBroker singleton for test isolation."""
    MessageBroker._instance = None
    MessageBroker._agent_queues = {}
    MessageBroker._agent_handlers = {}
    MessageBroker._temp_handlers = {}
    MessageBroker._topic_subscribers = {}
    MessageBroker._topic_handlers = {}


@pytest.fixture(autouse=True)
def reset_broker():
    """Reset broker singleton before each test."""
    _reset_broker_singleton()
    yield
    _reset_broker_singleton()


@pytest.fixture
def config():
    return Config(agent_id="broker_test", broker_url="memory://local")


@pytest.fixture
def broker(config):
    b = MessageBroker(config)
    yield b
    if b.running:
        b.disconnect()


class TestBrokerLifecycle:
    """Test broker connect/disconnect."""

    def test_broker_creation(self, broker):
        assert broker.running is False

    def test_connect(self, broker):
        broker.connect()
        assert broker.running is True

    def test_disconnect(self, broker):
        broker.connect()
        broker.disconnect()
        assert broker.running is False

    def test_singleton(self, config):
        b1 = MessageBroker(config)
        b2 = MessageBroker(config)
        assert b1 is b2


class TestSend:
    """Test message sending."""

    def test_send_returns_message_id(self, broker):
        msg = Message(
            message_type="TEST",
            sender="agent_a",
            receiver="agent_b",
            payload={"data": "hello"}
        )
        msg_id = broker.send(msg)
        assert isinstance(msg_id, str)
        assert len(msg_id) > 0

    def test_send_generates_message_id(self, broker):
        msg = Message(
            message_type="TEST",
            sender="agent_a",
            receiver="agent_b",
            payload={}
        )
        msg.message_id = None
        msg_id = broker.send(msg)
        assert msg_id is not None

    def test_send_queues_message(self, broker):
        msg = Message(
            message_type="TEST",
            sender="agent_a",
            receiver="agent_b",
            payload={}
        )
        broker.send(msg)
        assert "agent_b" in MessageBroker._agent_queues
        assert len(MessageBroker._agent_queues["agent_b"]) == 1


class TestSubscribe:
    """Test agent subscription."""

    def test_subscribe_creates_queue(self, broker):
        handler = lambda msg: None
        broker.subscribe("agent_x", handler)
        assert "agent_x" in MessageBroker._agent_queues
        assert "agent_x" in MessageBroker._agent_handlers

    def test_unsubscribe(self, broker):
        handler = lambda msg: None
        broker.subscribe("agent_x", handler)
        broker.unsubscribe("agent_x")
        assert "agent_x" not in MessageBroker._agent_handlers
        assert "agent_x" not in MessageBroker._agent_queues

    def test_subscribe_multiple_handlers(self, broker):
        h1 = lambda msg: None
        h2 = lambda msg: None
        broker.subscribe("agent_x", h1)
        broker.subscribe("agent_x", h2)
        assert len(MessageBroker._agent_handlers["agent_x"]) == 2


class TestTemporaryHandlers:
    """Test temporary handler subscription."""

    def test_subscribe_temporary(self, broker):
        handler = lambda msg: None
        broker.subscribe_temporary("agent_x", handler)
        assert "agent_x" in MessageBroker._temp_handlers
        assert handler in MessageBroker._temp_handlers["agent_x"]

    def test_unsubscribe_temporary(self, broker):
        handler = lambda msg: None
        broker.subscribe_temporary("agent_x", handler)
        broker.unsubscribe_temporary("agent_x", handler)
        assert handler not in MessageBroker._temp_handlers.get("agent_x", [])

    def test_unsubscribe_nonexistent_temporary(self, broker):
        handler = lambda msg: None
        broker.unsubscribe_temporary("nobody", handler)  # Should not raise


class TestPublish:
    """Test topic publishing."""

    def test_publish_returns_message_id(self, broker):
        msg = Message(
            message_type="EVENT",
            sender="publisher",
            payload={"event": "test"}
        )
        msg_id = broker.publish("test_topic", msg)
        assert isinstance(msg_id, str)

    def test_publish_to_subscribers(self, broker):
        # Subscribe an agent to a topic
        broker.subscribe_topic("alerts", lambda t, m: None, agent_id="agent_x")

        msg = Message(
            message_type="ALERT",
            sender="publisher",
            payload={"alert": "fire"}
        )
        broker.publish("alerts", msg)

        # Check that the message was queued for agent_x
        assert "agent_x" in MessageBroker._agent_queues
        assert len(MessageBroker._agent_queues["agent_x"]) == 1
        queued_msg = MessageBroker._agent_queues["agent_x"][0]
        assert queued_msg.receiver == "agent_x"
        assert queued_msg.metadata.get("topic") == "alerts"

    def test_publish_no_subscribers(self, broker):
        msg = Message(
            message_type="EVENT",
            sender="publisher",
            payload={}
        )
        msg_id = broker.publish("empty_topic", msg)
        assert msg_id is not None


class TestTopicSubscription:
    """Test topic subscription management."""

    def test_subscribe_topic(self, broker):
        handler = lambda t, m: None
        broker.subscribe_topic("news", handler, agent_id="agent_1")
        assert "agent_1" in MessageBroker._topic_subscribers.get("news", [])

    def test_subscribe_topic_idempotent(self, broker):
        handler = lambda t, m: None
        broker.subscribe_topic("news", handler, agent_id="agent_1")
        broker.subscribe_topic("news", handler, agent_id="agent_1")
        assert MessageBroker._topic_subscribers["news"].count("agent_1") == 1

    def test_unsubscribe_topic(self, broker):
        handler = lambda t, m: None
        broker.subscribe_topic("news", handler, agent_id="agent_1")
        broker.unsubscribe_topic("news", "agent_1")
        assert "agent_1" not in MessageBroker._topic_subscribers.get("news", [])

    def test_unsubscribe_nonexistent_topic(self, broker):
        broker.unsubscribe_topic("nonexistent", "agent_1")  # Should not raise


class TestMessageDelivery:
    """Test the message delivery loop."""

    def test_delivery_to_handler(self, broker):
        received = []
        handler = lambda msg: received.append(msg)
        broker.subscribe("agent_x", handler)
        broker.connect()

        msg = Message(
            message_type="TEST",
            sender="agent_a",
            receiver="agent_x",
            payload={"data": "hello"}
        )
        broker.send(msg)

        # Wait for delivery
        time.sleep(0.2)
        assert len(received) >= 1
        assert received[0].payload['data'] == "hello"

    def test_delivery_to_temp_handler(self, broker):
        received = []
        handler = lambda msg: received.append(msg)
        broker.subscribe_temporary("agent_x", handler)
        broker.connect()

        msg = Message(
            message_type="TEST",
            sender="agent_a",
            receiver="agent_x",
            payload={}
        )
        broker.send(msg)

        time.sleep(0.2)
        assert len(received) >= 1

    def test_delivery_to_topic_handler(self, broker):
        received = []
        handler = lambda t, m: received.append((t, m))
        broker.subscribe_topic("events", handler, agent_id="agent_x")
        broker.connect()

        msg = Message(
            message_type="EVENT",
            sender="publisher",
            payload={"event": "test"}
        )
        broker.publish("events", msg)

        time.sleep(0.2)
        assert len(received) >= 1
        assert received[0][0] == "events"
