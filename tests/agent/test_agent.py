"""Tests for maple.agent.agent - Agent class."""

import pytest
from maple.agent.agent import Agent
from maple.agent.config import Config
from maple.core.message import Message
from maple.broker.broker import MessageBroker


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
    return Config(agent_id="test_agent", broker_url="memory://local")


@pytest.fixture
def agent(config):
    a = Agent(config)
    a.start()
    yield a
    a.stop()


class TestAgentLifecycle:
    """Test agent start/stop."""

    def test_agent_creation(self, config):
        a = Agent(config)
        assert a.agent_id == "test_agent"
        assert a.running is False

    def test_agent_start(self, config):
        a = Agent(config)
        a.start()
        assert a.running is True
        a.stop()

    def test_agent_stop(self, config):
        a = Agent(config)
        a.start()
        a.stop()
        assert a.running is False

    def test_agent_has_broker(self, config):
        a = Agent(config)
        assert a.broker is not None


class TestSendMessage:
    """Test message sending."""

    def test_send_returns_ok(self, agent):
        msg = Message(
            message_type="TEST",
            receiver="other_agent",
            payload={"data": "hello"}
        )
        result = agent.send(msg)
        assert result.is_ok()
        assert isinstance(result.unwrap(), str)

    def test_send_sets_sender(self, agent):
        msg = Message(
            message_type="TEST",
            receiver="other_agent",
            payload={}
        )
        agent.send(msg)
        assert msg.sender == "test_agent"

    def test_send_preserves_existing_sender(self, agent):
        msg = Message(
            message_type="TEST",
            receiver="other_agent",
            sender="custom_sender",
            payload={}
        )
        agent.send(msg)
        assert msg.sender == "custom_sender"


class TestBroadcast:
    """Test broadcast messaging."""

    def test_broadcast_to_multiple(self, agent):
        msg = Message(
            message_type="ALERT",
            payload={"alert": "test"}
        )
        results = agent.broadcast(["a1", "a2", "a3"], msg)
        assert len(results) == 3
        for recipient, result in results.items():
            assert result.is_ok()


class TestPublish:
    """Test pub/sub."""

    def test_publish(self, agent):
        msg = Message(
            message_type="EVENT",
            payload={"event": "test"}
        )
        result = agent.publish("test_topic", msg)
        assert result.is_ok()


class TestHandlerRegistration:
    """Test handler registration."""

    def test_register_handler(self, agent):
        def my_handler(msg):
            pass
        agent.register_handler("MY_TYPE", my_handler)
        assert "MY_TYPE" in agent.message_handlers

    def test_register_topic_handler(self, agent):
        def my_handler(msg):
            pass
        agent.register_topic_handler("my_topic", my_handler)
        assert "my_topic" in agent.topic_handlers

    def test_register_stream_handler(self, agent):
        def my_handler(msg):
            pass
        agent.register_stream_handler("my_stream", my_handler)
        assert "my_stream" in agent.stream_handlers


class TestHandlerDecorators:
    """Test decorator-based handler registration."""

    def test_handler_decorator(self, agent):
        @agent.handler("DECORATED_TYPE")
        def handle(msg):
            return None

        assert "DECORATED_TYPE" in agent.message_handlers

    def test_topic_handler_decorator(self, agent):
        @agent.topic_handler("decorated_topic")
        def handle(msg):
            return None

        assert "decorated_topic" in agent.topic_handlers

    def test_stream_handler_decorator(self, agent):
        @agent.stream_handler("decorated_stream")
        def handle(msg):
            pass

        assert "decorated_stream" in agent.stream_handlers

    def test_decorator_returns_original_function(self, agent):
        @agent.handler("TEST_TYPE")
        def handle(msg):
            return "result"

        assert handle(None) == "result"


class TestReceive:
    """Test message reception."""

    def test_receive_timeout(self, agent):
        result = agent.receive(timeout="0.1s")
        assert result.is_err()
        assert result.unwrap_err()['errorType'] == 'TIMEOUT'

    def test_receive_message(self, agent):
        msg = Message(
            message_type="TEST",
            sender="other",
            receiver="test_agent",
            payload={"data": "hello"}
        )
        agent.message_queue.put(msg)
        result = agent.receive(timeout="1s")
        assert result.is_ok()
        assert result.unwrap().message_type == "TEST"


class TestReceiveFiltered:
    """Test filtered message reception."""

    def test_receive_filtered_timeout(self, agent):
        result = agent.receive_filtered(
            lambda m: m.message_type == "SPECIFIC",
            timeout="0.1s"
        )
        assert result.is_err()

    def test_receive_filtered_match(self, agent):
        msg = Message(
            message_type="WANTED",
            sender="other",
            receiver="test_agent",
            payload={}
        )
        agent.message_queue.put(msg)
        result = agent.receive_filtered(
            lambda m: m.message_type == "WANTED",
            timeout="1s"
        )
        assert result.is_ok()
        assert result.unwrap().message_type == "WANTED"


class TestNonceVerification:
    """Test nonce encryption/verification helpers."""

    def test_encrypt_nonce(self, agent):
        encrypted = agent._encrypt_nonce("test_nonce")
        assert isinstance(encrypted, str)
        assert len(encrypted) > 0

    def test_verify_nonce(self, agent):
        encrypted = agent._encrypt_nonce("test_nonce")
        assert agent._verify_nonce(encrypted, "test_nonce") is True

    def test_verify_wrong_nonce(self, agent):
        encrypted = agent._encrypt_nonce("test_nonce")
        assert agent._verify_nonce(encrypted, "wrong_nonce") is False

    def test_verify_invalid_data(self, agent):
        assert agent._verify_nonce("not_base64!!!", "test") is False


class TestEstablishLink:
    """Test link establishment."""

    def test_no_security_config(self, config):
        _reset_broker_singleton()
        a = Agent(config)
        a.start()
        result = a.establish_link("other_agent")
        assert result.is_err()
        assert result.unwrap_err()['errorType'] == 'NO_SECURITY_CONFIG'
        a.stop()


class TestHandlerKeyNormalization:
    """Regression tests for the handler-key case trap.

    ``Message`` upper-cases every ``message_type``; ``register_handler`` must
    key handlers the same way, or a lower-case registration silently never
    fires for the (upper-cased) incoming message.
    """

    def test_lowercase_registration_stored_uppercase(self, config):
        a = Agent(config)
        a.register_handler("work.package", lambda m: None)
        assert "WORK.PACKAGE" in a.message_handlers
        assert "work.package" not in a.message_handlers

    def test_lowercase_handler_fires_for_uppercase_message(self, config):
        a = Agent(config)
        seen = []
        a.register_handler("work.package", lambda m: seen.append(m.message_type) or None)
        # Message upper-cases the type; dispatch must still find the handler.
        a._process_message(
            Message(message_type="work.package", sender="x", receiver="test_agent")
        )
        assert seen == ["WORK.PACKAGE"]

    def test_mixed_case_registration_fires(self, config):
        a = Agent(config)
        seen = []
        a.register_handler("Gate.Result", lambda m: seen.append(m.message_type) or None)
        a._process_message(
            Message(message_type="GATE.RESULT", sender="x", receiver="test_agent")
        )
        assert seen == ["GATE.RESULT"]

    def test_decorator_path_normalizes(self, config):
        a = Agent(config)
        seen = []

        @a.handler("work.package")
        def _on_work(m):
            seen.append(m.message_type)
            return None

        a._process_message(
            Message(message_type="WORK.PACKAGE", sender="x", receiver="test_agent")
        )
        assert seen == ["WORK.PACKAGE"]

    def test_uppercase_registration_still_works(self, config):
        a = Agent(config)
        seen = []
        a.register_handler("PING", lambda m: seen.append(m.message_type) or None)
        a._process_message(
            Message(message_type="PING", sender="x", receiver="test_agent")
        )
        assert seen == ["PING"]


class TestRequireRoutable:
    """Opt-in routability on Agent.send (#2 — Ok should mean more than enqueued)."""

    def test_send_to_unsubscribed_is_unroutable(self, config):
        a = Agent(config)
        a.start()
        res = a.send(Message(message_type="PING", receiver="ghost"), require_routable=True)
        assert res.is_err()
        assert res.unwrap_err()["errorType"] == "UNROUTABLE"
        a.stop()

    def test_send_to_subscribed_is_ok(self, config):
        a = Agent(config)
        b = Agent(Config(agent_id="peer", broker_url="memory://local"))
        a.start()
        b.start()
        res = a.send(Message(message_type="PING", receiver="peer"), require_routable=True)
        assert res.is_ok()
        a.stop()
        b.stop()

    def test_default_send_still_enqueues_to_nonexistent(self, config):
        # Backward compatibility: without the flag, Ok-on-enqueue is preserved.
        a = Agent(config)
        a.start()
        res = a.send(Message(message_type="PING", receiver="ghost"))
        assert res.is_ok()
        a.stop()
