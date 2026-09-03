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
"""stop() drains queued work instead of discarding it (ADR-163).

Measured before the fix: of 40 messages sent to an agent with a 250ms handler,
stop() discarded 38 with no error, no counter and no log, returning in 0.11s.
Every one had been accepted with an Ok result.
"""

import logging
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


class Workload:
    """A worker agent whose handler takes real time, plus a sender."""

    def __init__(self, scope, handler_seconds=0.02):
        self.started = []
        self.finished = []
        self._lock = threading.Lock()
        self.worker = Agent(Config(agent_id="worker", broker_url=scope))

        @self.worker.handler("WORK")
        def _work(message):
            with self._lock:
                self.started.append(message.payload["i"])
            time.sleep(handler_seconds)
            with self._lock:
                self.finished.append(message.payload["i"])

        self.worker.start()
        self.sender = Agent(Config(agent_id="sender", broker_url=scope))
        self.sender.start()

    def send(self, count):
        for i in range(count):
            self.sender.send(
                Message(message_type="WORK", receiver="worker", payload={"i": i})
            )

    def close(self):
        try:
            self.sender.stop(drain_timeout=0)
        except Exception:
            pass


class TestDrainOnStop:
    def test_queued_work_completes_instead_of_being_discarded(self):
        w = Workload("memory://drain-1")
        try:
            w.send(30)
            time.sleep(0.05)
            undrained = w.worker.stop()
            assert undrained == 0
            assert len(w.finished) == 30, (
                "queued messages were discarded; "
                f"only {len(w.finished)} of 30 completed"
            )
        finally:
            w.close()

    def test_stop_reports_what_it_could_not_drain(self):
        w = Workload("memory://drain-2", handler_seconds=0.2)
        try:
            w.send(40)
            time.sleep(0.05)
            undrained = w.worker.stop(drain_timeout=0.3)
            # the deadline is short on purpose; the point is that whatever is
            # lost is counted rather than silently dropped
            assert undrained > 0
            assert w.worker.messages_undrained == undrained
        finally:
            w.close()

    def test_an_incomplete_drain_warns(self, caplog):
        w = Workload("memory://drain-3", handler_seconds=0.2)
        try:
            w.send(40)
            time.sleep(0.05)
            with caplog.at_level(logging.WARNING, logger="maple.agent.agent"):
                undrained = w.worker.stop(drain_timeout=0.2)
            if undrained:
                assert any(
                    "still queued" in record.getMessage() for record in caplog.records
                ), "messages were dropped without a warning"
        finally:
            w.close()

    def test_zero_timeout_restores_the_old_behaviour(self):
        w = Workload("memory://drain-4", handler_seconds=0.05)
        try:
            w.send(40)
            time.sleep(0.05)
            started = time.perf_counter()
            undrained = w.worker.stop(drain_timeout=0)
            elapsed = time.perf_counter() - started
            assert undrained > 0, "drain_timeout=0 should not drain"
            assert elapsed < 1.0, "opting out of the drain should be immediate"
        finally:
            w.close()

    def test_an_idle_agent_stops_immediately(self):
        """111 .stop() calls in this suite are on idle agents; the drain must
        cost them nothing."""
        agent = Agent(Config(agent_id="idle", broker_url="memory://drain-5"))
        agent.start()
        started = time.perf_counter()
        undrained = agent.stop()
        elapsed = time.perf_counter() - started

        assert undrained == 0
        assert elapsed < 1.0, f"stopping an idle agent took {elapsed:.2f}s"

    def test_the_drain_does_not_declare_victory_mid_message(self):
        """An empty queue with a handler still running is not drained."""
        w = Workload("memory://drain-6", handler_seconds=0.3)
        try:
            w.send(1)
            time.sleep(0.05)  # the single message is now being handled
            assert w.worker.message_queue.empty()
            w.worker.stop()
            assert len(w.finished) == 1, "stop() returned mid-handler"
        finally:
            w.close()

    def test_intake_closes_before_the_drain(self):
        """The drain must chase a queue that cannot grow."""
        w = Workload("memory://drain-7", handler_seconds=0.02)
        try:
            w.send(10)
            time.sleep(0.03)
            w.worker.stop()
            # sending after the stop must not reach the stopped worker
            before = len(w.finished)
            w.sender.send(
                Message(message_type="WORK", receiver="worker", payload={"i": 99})
            )
            time.sleep(0.2)
            assert len(w.finished) == before
        finally:
            w.close()

    def test_stop_is_idempotent(self):
        agent = Agent(Config(agent_id="twice", broker_url="memory://drain-8"))
        agent.start()
        assert agent.stop() == 0
        assert agent.stop() == 0

    def test_stop_returns_an_int_for_callers_that_look(self):
        agent = Agent(Config(agent_id="ret", broker_url="memory://drain-9"))
        agent.start()
        assert isinstance(agent.stop(), int)

    def test_default_drain_timeout_is_declared_not_magic(self):
        assert Agent.DEFAULT_DRAIN_TIMEOUT > 0


class TestStoppingOneAgentDoesNotTearDownItsPeers:
    """Brokers are scoped and shared (ADR-160), so a shared delivery thread
    must survive one agent stopping.

    An earlier draft of the drain closed intake with ``broker.disconnect()``,
    which stops that thread for the whole scope. It passed every targeted test
    and broke two autonomy server tests only under the full suite.
    """

    def test_a_peer_still_receives_after_another_agent_stops(self):
        received = []
        a = Agent(Config(agent_id="stopper", broker_url="memory://peers"))
        a.start()
        b = Agent(Config(agent_id="survivor", broker_url="memory://peers"))

        @b.handler("PING")
        def _ping(message):
            received.append(message.payload["i"])

        b.start()
        sender = Agent(Config(agent_id="sender", broker_url="memory://peers"))
        sender.start()
        try:
            a.stop()  # must not disconnect the shared broker

            sender.send(
                Message(message_type="PING", receiver="survivor", payload={"i": 1})
            )
            deadline = time.perf_counter() + 3.0
            while not received and time.perf_counter() < deadline:
                time.sleep(0.01)

            assert received == [
                1
            ], "stopping one agent stopped delivery for the whole scope"
        finally:
            b.stop(drain_timeout=0)
            sender.stop(drain_timeout=0)

    def test_stop_closes_intake_without_disconnecting(self):
        """Comments mention disconnect(); only executable lines are checked."""
        import inspect

        source = inspect.getsource(Agent.stop)
        before_drain = source.split("self._drain(")[0]
        code = "\n".join(
            line
            for line in before_drain.splitlines()
            if line.strip() and not line.strip().startswith("#")
        )
        # drop the docstring, which names disconnect() in prose
        if code.count('"""') >= 2:
            code = code.split('"""')[-1]

        assert "unsubscribe" in code, "intake is never closed before the drain"
        assert "disconnect" not in code, (
            "disconnect() before the drain stops the shared delivery thread "
            "for every agent in the scope"
        )

    def test_the_broker_survives_until_its_last_subscriber_leaves(self):
        """A single-agent process must still clean up after itself."""
        agent = Agent(Config(agent_id="only", broker_url="memory://solo"))
        agent.start()
        broker = agent.broker
        assert broker.running is True
        agent.stop()
        assert broker.running is False, "the last subscriber left it connected"


class TestDrainDeadlineUsesAStableClock:
    def test_the_deadline_is_not_measured_on_the_wall_clock(self):
        """A clock step during shutdown must not extend or truncate the drain."""
        import inspect

        source = inspect.getsource(Agent._drain)
        assert "perf_counter" in source
        assert "time.time()" not in source
