"""Regression tests for the broker's production hardening (ADR-159).

Three measured defects in the in-memory broker, which is the only transport
that works out of the box:

- No backpressure: a full bounded queue spilled into an unbounded list, so
  25,000 sends were all accepted and 15,000 messages sat in memory unbounded.
- Silent loss: a message reaching zero handlers was discarded with no error,
  counter, or log.
- A data race: ``subscribe`` wrote the handler tables under the lock while
  ``_deliver_message`` read them on the delivery thread without it.
"""

import threading
import time

import pytest

from maple.agent.agent import Agent
from maple.agent.config import Config, PerformanceConfig
from maple.broker.broker import BrokerOverflowError, MessageBroker
from maple.core.message import Message


def _reset_broker_singleton():
    MessageBroker.reset_scopes()


@pytest.fixture(autouse=True)
def reset_broker():
    _reset_broker_singleton()
    yield
    _reset_broker_singleton()


def _agent(agent_id, **perf):
    """An agent whose broker is deliberately not started, so nothing drains."""
    return Agent(
        Config(
            agent_id=agent_id,
            broker_url="memory://backpressure",
            performance=PerformanceConfig(**perf) if perf else None,
        )
    )


class TestBackpressure:
    """The bound must be a bound, and the caller must be told."""

    def test_queue_full_is_refused_not_buffered(self):
        agent = _agent("producer", max_queue_size=5)

        accepted, refused = 0, 0
        for i in range(50):
            result = agent.send(
                Message(message_type="X", receiver="stalled", payload={"i": i})
            )
            if result.is_ok():
                accepted += 1
            else:
                refused += 1

        assert accepted == 5, "the bound must actually bound"
        assert refused == 45

    def test_refusal_carries_a_machine_readable_error_type(self):
        agent = _agent("producer", max_queue_size=1)
        agent.send(Message(message_type="X", receiver="s", payload={}))

        result = agent.send(Message(message_type="X", receiver="s", payload={}))

        assert result.is_err()
        error = result.unwrap_err()
        assert error["errorType"] == "QUEUE_FULL"
        assert error["details"]["maxQueueSize"] == 1

    def test_nothing_accumulates_in_the_unbounded_fallback(self):
        """The spill path that made the bound decorative is gone."""
        agent = _agent("producer", max_queue_size=5)
        for i in range(200):
            agent.send(Message(message_type="X", receiver="stalled", payload={"i": i}))

        pending = sum(len(q) for q in agent.broker._agent_queues.values())
        assert pending == 0

    def test_broker_send_raises_the_typed_exception(self):
        """Below Agent.send, the broker refuses by raising."""
        agent = _agent("producer", max_queue_size=1)
        agent.broker.send(
            Message(message_type="X", sender="p", receiver="s", payload={})
        )

        with pytest.raises(BrokerOverflowError) as excinfo:
            agent.broker.send(
                Message(message_type="X", sender="p", receiver="s", payload={})
            )
        assert excinfo.value.error["errorType"] == "QUEUE_FULL"

    def test_refusals_are_counted_for_operators(self):
        agent = _agent("producer", max_queue_size=2)
        for i in range(10):
            agent.send(Message(message_type="X", receiver="s", payload={"i": i}))

        assert agent.broker.get_statistics()["refused"] == 8


class TestMessageSizeLimit:
    """A bounded message count is no protection against one huge message."""

    def test_oversized_payload_is_refused(self):
        agent = _agent("producer", max_message_bytes=2048)

        result = agent.send(
            Message(message_type="BIG", receiver="x", payload={"blob": "z" * 5000})
        )

        assert result.is_err()
        error = result.unwrap_err()
        assert error["errorType"] == "MESSAGE_TOO_LARGE"
        assert error["details"]["maxMessageBytes"] == 2048
        assert error["details"]["payloadBytes"] > 2048

    def test_payload_under_the_limit_passes(self):
        agent = _agent("producer", max_message_bytes=8192)
        result = agent.send(
            Message(message_type="OK", receiver="x", payload={"blob": "z" * 100})
        )
        assert result.is_ok()

    def test_non_json_values_are_measured_by_their_string_form(self):
        """Admission control is an estimate, not serializer validation.

        Values the JSON encoder cannot represent natively are sized via
        ``default=str`` rather than waved through, so a payload full of exotic
        objects still cannot evade the memory bound.
        """
        agent = _agent("producer", max_message_bytes=64)
        result = agent.send(
            Message(message_type="ODD", receiver="x", payload={"fn": lambda: None})
        )
        assert result.is_err()
        assert result.unwrap_err()["errorType"] == "MESSAGE_TOO_LARGE"

    def test_a_small_exotic_payload_still_passes(self):
        agent = _agent("producer", max_message_bytes=8192)
        result = agent.send(
            Message(message_type="ODD", receiver="x", payload={"fn": lambda: None})
        )
        assert result.is_ok()


class TestUndeliverableIsObservable:
    """Messages nobody handles must be counted, not silently dropped."""

    def test_undeliverable_messages_are_counted(self):
        agent = _agent("sender")
        agent.start()
        try:
            for _ in range(4):
                agent.send(Message(message_type="X", receiver="ghost", payload={}))
            time.sleep(0.4)

            stats = agent.broker.get_statistics()
            assert stats["undeliverable"] == 4
            assert stats["undeliverableReceivers"] == 1
        finally:
            agent.stop()

    def test_dead_letter_handler_receives_them(self):
        agent = _agent("sender")
        dead = []
        agent.broker.set_undeliverable_handler(
            lambda receiver, message: dead.append((receiver, message.message_type))
        )
        agent.start()
        try:
            agent.send(Message(message_type="IMPORTANT", receiver="ghost", payload={}))
            time.sleep(0.4)
            assert dead == [("ghost", "IMPORTANT")]
        finally:
            agent.stop()

    def test_delivered_messages_are_not_counted_as_undeliverable(self):
        alice = _agent("alice")
        bob = _agent("bob")
        seen = []

        @bob.handler("PING")
        def _handle(message):
            seen.append(message.payload["n"])

        alice.start()
        bob.start()
        try:
            for n in range(10):
                alice.send(
                    Message(message_type="PING", receiver="bob", payload={"n": n})
                )
            time.sleep(0.8)

            stats = alice.broker.get_statistics()
            assert len(seen) == 10
            assert stats["undeliverable"] == 0
            assert stats["delivered"] >= 10
        finally:
            alice.stop()
            bob.stop()

    def test_a_raising_handler_counts_as_delivered(self):
        """It ran and failed. That is a handler bug, not an undelivered message."""
        alice = _agent("alice")
        bob = _agent("bob")

        @bob.handler("BOOM")
        def _handle(message):
            raise RuntimeError("handler blew up")

        alice.start()
        bob.start()
        try:
            alice.send(Message(message_type="BOOM", receiver="bob", payload={}))
            time.sleep(0.5)
            assert alice.broker.get_statistics()["undeliverable"] == 0
        finally:
            alice.stop()
            bob.stop()


class TestDeliveryPathIsRaceFree:
    """subscribe() and _deliver_message() must not fight over the tables."""

    def test_concurrent_subscribe_during_delivery_does_not_raise(self):
        """Churn subscriptions while messages flow.

        Before ADR-159 the delivery thread iterated the handler lists with no
        lock while subscribe mutated them under one. This does not prove the
        race is gone - no finite test can - but it exercises the interleaving
        that used to be able to raise mid-iteration.
        """
        agent = _agent("churn")
        agent.start()
        errors = []

        def churn():
            try:
                for i in range(300):
                    agent.broker.subscribe(f"tmp-{i % 12}", lambda m: None)
            except Exception as exc:  # pragma: no cover - the defect path
                errors.append(exc)

        def publish():
            try:
                for i in range(300):
                    agent.send(
                        Message(message_type="X", receiver=f"tmp-{i % 12}", payload={})
                    )
            except Exception as exc:  # pragma: no cover
                errors.append(exc)

        threads = [threading.Thread(target=churn), threading.Thread(target=publish)]
        try:
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=30)
            time.sleep(0.3)
            assert errors == []
        finally:
            agent.stop()

    def test_a_blocking_handler_does_not_freeze_subscribe(self):
        """Handlers run outside the lock, so a slow one cannot wedge the broker."""
        agent = _agent("slow-host")
        release = threading.Event()

        def blocking_handler(message):
            release.wait(timeout=10)

        agent.broker.subscribe("blocker", blocking_handler)
        agent.start()
        try:
            agent.send(Message(message_type="X", receiver="blocker", payload={}))
            time.sleep(0.3)

            # The delivery thread is now inside the blocking handler. If the
            # lock were held across invocation, this would block for 10s.
            started = time.time()
            agent.broker.subscribe("other", lambda m: None)
            elapsed = time.time() - started

            assert elapsed < 2.0, "subscribe blocked behind a handler"
        finally:
            release.set()
            agent.stop()


class TestStatisticsSurface:
    def test_statistics_expose_the_limits_in_force(self):
        agent = _agent("s", max_queue_size=77, max_message_bytes=4096)
        stats = agent.broker.get_statistics()

        assert stats["maxQueueSize"] == 77
        assert stats["maxMessageBytes"] == 4096
        assert set(stats) >= {
            "delivered",
            "undeliverable",
            "refused",
            "subscribedAgents",
        }

    def test_defaults_apply_without_a_performance_config(self):
        agent = _agent("s")
        stats = agent.broker.get_statistics()
        assert stats["maxQueueSize"] == 10000
        assert stats["maxMessageBytes"] == 1_048_576
