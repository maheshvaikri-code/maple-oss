"""Tests for maple.broker.broker - MessageBroker."""

import pytest
import time
from maple.broker.broker import MessageBroker
from maple.agent.config import Config
from maple.core.message import Message


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
        # Enqueued exactly once (in the priority queue), not duplicated into
        # the basic queue — otherwise the delivery loop delivers it twice.
        assert broker._message_queue is not None
        assert broker._message_queue.size() == 1
        assert len(MessageBroker._agent_queues.get("agent_b", [])) == 0

    def test_direct_message_delivered_exactly_once(self):
        """Regression: a direct send fires the receiver's handler once, not twice."""
        _reset_broker_singleton()
        config = Config(agent_id="delivery_test", broker_url="memory://local")
        broker = MessageBroker(config)
        calls = []
        broker.subscribe("agent_b", lambda m: calls.append(m.message_id))
        broker.connect()
        try:
            broker.send(Message(message_type="TEST", sender="agent_a", receiver="agent_b"))
            deadline = time.time() + 2.0
            while not calls and time.time() < deadline:
                time.sleep(0.02)
            time.sleep(0.1)  # allow any (erroneous) second delivery to land
            assert len(calls) == 1
        finally:
            broker.disconnect()
            _reset_broker_singleton()


class TestSubscribe:
    """Test agent subscription."""

    def test_subscribe_creates_queue(self, broker):
        def handler(msg):
            pass

        broker.subscribe("agent_x", handler)
        assert "agent_x" in MessageBroker._agent_queues
        assert "agent_x" in MessageBroker._agent_handlers

    def test_unsubscribe(self, broker):
        def handler(msg):
            pass

        broker.subscribe("agent_x", handler)
        broker.unsubscribe("agent_x")
        assert "agent_x" not in MessageBroker._agent_handlers
        assert "agent_x" not in MessageBroker._agent_queues

    def test_subscribe_multiple_handlers(self, broker):
        def h1(msg):
            pass

        def h2(msg):
            pass

        broker.subscribe("agent_x", h1)
        broker.subscribe("agent_x", h2)
        assert len(MessageBroker._agent_handlers["agent_x"]) == 2


class TestTemporaryHandlers:
    """Test temporary handler subscription."""

    def test_subscribe_temporary(self, broker):
        def handler(msg):
            pass

        broker.subscribe_temporary("agent_x", handler)
        assert "agent_x" in MessageBroker._temp_handlers
        assert handler in MessageBroker._temp_handlers["agent_x"]

    def test_unsubscribe_temporary(self, broker):
        def handler(msg):
            pass

        broker.subscribe_temporary("agent_x", handler)
        broker.unsubscribe_temporary("agent_x", handler)
        assert handler not in MessageBroker._temp_handlers.get("agent_x", [])

    def test_unsubscribe_nonexistent_temporary(self, broker):
        def handler(msg):
            pass

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
        def handler(topic, message):
            pass

        broker.subscribe_topic("alerts", handler, agent_id="agent_x")

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
        def handler(topic, message):
            pass

        broker.subscribe_topic("news", handler, agent_id="agent_1")
        assert "agent_1" in MessageBroker._topic_subscribers.get("news", [])

    def test_subscribe_topic_idempotent(self, broker):
        def handler(topic, message):
            pass

        broker.subscribe_topic("news", handler, agent_id="agent_1")
        broker.subscribe_topic("news", handler, agent_id="agent_1")
        assert MessageBroker._topic_subscribers["news"].count("agent_1") == 1

    def test_unsubscribe_topic(self, broker):
        def handler(topic, message):
            pass

        broker.subscribe_topic("news", handler, agent_id="agent_1")
        broker.unsubscribe_topic("news", "agent_1")
        assert "agent_1" not in MessageBroker._topic_subscribers.get("news", [])

    def test_unsubscribe_nonexistent_topic(self, broker):
        broker.unsubscribe_topic("nonexistent", "agent_1")  # Should not raise


class TestMessageDelivery:
    """Test the message delivery loop."""

    def test_delivery_to_handler(self, broker):
        received = []

        def handler(msg):
            received.append(msg)

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

        def handler(msg):
            received.append(msg)

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

        def handler(topic, message):
            received.append((topic, message))

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


class TestIsRoutable:
    """Routability check — distinguishes 'enqueued' from 'deliverable' (#2)."""

    def test_unsubscribed_not_routable(self, broker):
        assert broker.is_routable("nobody") is False

    def test_subscribed_is_routable(self, broker):
        broker.subscribe("worker", lambda m: None)
        assert broker.is_routable("worker") is True

    def test_empty_or_none_not_routable(self, broker):
        assert broker.is_routable("") is False
        assert broker.is_routable(None) is False

    def test_after_unsubscribe_not_routable(self, broker):
        broker.subscribe("worker", lambda m: None)
        broker.unsubscribe("worker")
        assert broker.is_routable("worker") is False
