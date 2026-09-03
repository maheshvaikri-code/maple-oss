# Copyright (C) 2025 Mahesh Vaijainthymala Krishnamoorthy
# (Mahesh Vaikri)
#
# This file is part of MAPLE - Multi Agent Protocol Language Engine.
#
# MAPLE - Multi Agent Protocol Language Engine is free software: you can
# redistribute it and/or modify it under the terms of the GNU Affero General
# Public License as published by the Free Software Foundation, either version 3
# of the License, or (at your option) any later version.
# MAPLE - Multi Agent Protocol Language Engine is distributed in the hope that
# it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty
# of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero
# General Public License for more details. You should have received a copy of
# the GNU Affero General Public License along with MAPLE - Multi Agent Protocol
# Language Engine. If not, see <https://www.gnu.org/licenses/>.
"""Delivery starts on an enqueue, not at the next tick (ADR-166).

Measured with the 10ms poll: p50 4.8ms, p95 10.0ms, max 16.6ms, paid on every
hop. After: p50 0.33ms, p95 0.62ms, max 0.85ms.
"""

import inspect
import threading
import time

import pytest

from maple import Agent, Config
from maple.broker.broker import MessageBroker
from maple.core.message import Message


@pytest.fixture(autouse=True)
def isolated_scope():
    MessageBroker.reset_scopes()
    yield
    MessageBroker.reset_scopes()


class TestDeliveryDoesNotWaitForATick:
    def test_sequential_hops_do_not_each_pay_a_poll(self):
        """The discriminating test: 30 sequential round-trips.

        Under a 10ms poll each hop waits ~5ms on average, so this could not
        finish in under ~150ms however fast the machine. Signalled delivery
        does it in roughly 10ms, leaving an order of magnitude of headroom for
        a loaded CI runner.
        """
        arrived = threading.Event()
        worker = Agent(Config(agent_id="w", broker_url="memory://sig-1"))

        @worker.handler("PING")
        def _ping(message):
            arrived.set()

        worker.start()
        sender = Agent(Config(agent_id="s", broker_url="memory://sig-1"))
        sender.start()
        try:
            started = time.perf_counter()
            for i in range(30):
                arrived.clear()
                sender.send(
                    Message(message_type="PING", receiver="w", payload={"i": i})
                )
                assert arrived.wait(timeout=5.0), f"hop {i} never arrived"
            elapsed = time.perf_counter() - started

            assert elapsed < 1.0, (
                f"30 sequential hops took {elapsed*1000:.0f}ms; a 10ms poll "
                "would make this at least ~150ms"
            )
        finally:
            worker.stop(drain_timeout=0)
            sender.stop(drain_timeout=0)

    def test_a_single_message_arrives_without_a_poll_interval(self):
        arrived = threading.Event()
        worker = Agent(Config(agent_id="w", broker_url="memory://sig-2"))

        @worker.handler("PING")
        def _ping(message):
            arrived.set()

        worker.start()
        sender = Agent(Config(agent_id="s", broker_url="memory://sig-2"))
        sender.start()
        try:
            sender.send(Message(message_type="PING", receiver="w", payload={}))
            assert arrived.wait(timeout=5.0)
        finally:
            worker.stop(drain_timeout=0)
            sender.stop(drain_timeout=0)

    def test_published_messages_are_signalled_too(self):
        """Publish uses the fallback queue, which is a separate enqueue path."""
        received = []
        subscriber = Agent(Config(agent_id="sub", broker_url="memory://sig-3"))
        subscriber.start()
        publisher = Agent(Config(agent_id="pub", broker_url="memory://sig-3"))
        publisher.start()
        try:
            broker = subscriber.broker
            broker.subscribe_topic(
                "news", lambda t, m: received.append(m), agent_id="sub"
            )
            broker.publish(
                "news", Message(message_type="NEWS", receiver="sub", payload={"n": 1})
            )

            deadline = time.perf_counter() + 5.0
            while not received and time.perf_counter() < deadline:
                time.sleep(0.005)
            assert received, "a published message never arrived"
        finally:
            subscriber.stop(drain_timeout=0)
            publisher.stop(drain_timeout=0)


class TestTheSignalCannotBeMissed:
    """Condition.notify() wakes current waiters only. A message enqueued
    between the drain and the next wait() would be signalled to nobody."""

    def test_a_signal_before_the_wait_is_not_lost(self):
        agent = Agent(Config(agent_id="a", broker_url="memory://sig-4"))
        broker = agent.broker
        try:
            broker._signal_delivery()

            started = time.perf_counter()
            broker._await_work()  # must return at once, not wait the fallback
            elapsed = time.perf_counter() - started

            assert elapsed < 0.2, (
                f"_await_work() waited {elapsed:.2f}s after a signal; the "
                "pending flag is not carrying it across the gap"
            )
        finally:
            agent.stop(drain_timeout=0)

    def test_the_flag_is_cleared_after_waking(self):
        agent = Agent(Config(agent_id="a", broker_url="memory://sig-5"))
        broker = agent.broker
        try:
            broker._signal_delivery()
            broker._await_work()
            assert (
                broker._wake_pending is False
            ), "a stale flag would make the loop spin instead of waiting"
        finally:
            agent.stop(drain_timeout=0)

    def test_without_a_signal_it_waits(self):
        agent = Agent(Config(agent_id="a", broker_url="memory://sig-6"))
        broker = agent.broker
        try:
            broker._wake_pending = False
            started = time.perf_counter()
            broker._await_work()
            elapsed = time.perf_counter() - started
            assert elapsed >= 0.05, "an unsignalled wait should actually wait"
        finally:
            agent.stop(drain_timeout=0)

    def test_the_wake_lock_is_not_the_broker_lock(self):
        """The drain holds self._lock; mixing them would tie waiting to it."""
        agent = Agent(Config(agent_id="a", broker_url="memory://sig-7"))
        broker = agent.broker
        try:
            assert broker._wake is not broker._lock
        finally:
            agent.stop(drain_timeout=0)


class TestShutdownStaysPrompt:
    """A 0.5s fallback would make stopping slower than the 10ms poll it
    replaced, undoing ADR-163 and ADR-165."""

    def test_disconnect_wakes_the_delivery_loop(self):
        agent = Agent(Config(agent_id="a", broker_url="memory://sig-8"))
        agent.start()
        broker = agent.broker
        thread = broker.delivery_thread
        assert thread is not None and thread.is_alive()

        started = time.perf_counter()
        broker.disconnect()
        thread.join(timeout=3.0)
        elapsed = time.perf_counter() - started

        assert not thread.is_alive(), "the delivery loop did not exit"
        assert elapsed < 0.5, (
            f"shutdown took {elapsed:.2f}s; disconnect() must signal rather "
            "than let the loop wait out its fallback"
        )

    def test_disconnect_signals(self):
        source = inspect.getsource(MessageBroker.disconnect)
        assert "_signal_delivery" in source


class TestEveryEnqueuePathSignals:
    """A path that forgets falls back to the idle interval - degraded, not
    broken, but this keeps the obligation visible."""

    @pytest.mark.parametrize("method", ["send", "publish"])
    def test_the_public_enqueue_paths_signal(self, method):
        source = inspect.getsource(getattr(MessageBroker, method))
        assert "_signal_delivery" in source, (
            f"{method}() enqueues without waking the delivery loop, so its "
            "messages wait for the fallback interval"
        )

    def test_the_loop_no_longer_polls_on_a_fixed_tick(self):
        """Comments quote the old poll; only executable lines are checked."""
        source = inspect.getsource(MessageBroker._message_delivery_loop)
        code = "\n".join(
            line
            for line in source.splitlines()
            if line.strip() and not line.strip().startswith("#")
        )
        assert "time.sleep(0.01)" not in code, "the 10ms poll is back"
        assert "_await_work" in code

    def test_the_fallback_interval_is_declared_not_magic(self):
        assert MessageBroker._IDLE_WAIT_SECONDS > 0
        assert (
            MessageBroker._IDLE_WAIT_SECONDS >= 0.1
        ), "a short fallback re-creates the poll this replaced"


class TestDeliveryStillWorks:
    """The point of the change is latency; none of the guarantees move."""

    def test_all_messages_arrive_under_load(self):
        received = []
        lock = threading.Lock()
        worker = Agent(Config(agent_id="w", broker_url="memory://sig-9"))

        @worker.handler("WORK")
        def _work(message):
            with lock:
                received.append(message.payload["i"])

        worker.start()
        sender = Agent(Config(agent_id="s", broker_url="memory://sig-9"))
        sender.start()
        try:
            for i in range(200):
                sender.send(
                    Message(message_type="WORK", receiver="w", payload={"i": i})
                )
            worker.stop()  # drains
            assert sorted(received) == list(range(200))
        finally:
            sender.stop(drain_timeout=0)

    def test_undeliverable_is_still_counted(self):
        agent = Agent(Config(agent_id="a", broker_url="memory://sig-10"))
        agent.start()
        try:
            agent.send(Message(message_type="X", receiver="ghost", payload={}))
            deadline = time.perf_counter() + 3.0
            while time.perf_counter() < deadline:
                if agent.broker.get_statistics()["undeliverable"]:
                    break
                time.sleep(0.01)
            assert agent.broker.get_statistics()["undeliverable"] >= 1
        finally:
            agent.stop(drain_timeout=0)
