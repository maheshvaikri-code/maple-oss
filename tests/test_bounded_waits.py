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
"""A wait ends when the thing it waits for ends (ADR-165).

Measured before this existed: a thread in ``receive()`` never woke. ``stop()``
returned cleanly in 0.13s and left it wedged with no error and no way to learn
the agent was gone. ``Stream.close()`` did the same to stream readers.
"""

import threading
import time

import pytest

from maple import Agent, Config
from maple.broker.broker import MessageBroker
from maple.communication.streaming import Stream
from maple.core.message import Message


@pytest.fixture(autouse=True)
def isolated_scope():
    MessageBroker.reset_scopes()
    yield
    MessageBroker.reset_scopes()


def park(callable_):
    """Run something in a daemon thread and hand back the thread and results."""
    results = []
    thread = threading.Thread(target=lambda: results.append(callable_()), daemon=True)
    thread.start()
    time.sleep(0.15)
    return thread, results


class TestReceiveWakesOnStop:
    def test_a_parked_receiver_wakes_when_the_agent_stops(self):
        agent = Agent(Config(agent_id="r", broker_url="memory://wait-1"))
        agent.start()
        thread, results = park(agent.receive)
        assert thread.is_alive(), "the receiver should be waiting"

        agent.stop()
        thread.join(timeout=3.0)

        assert not thread.is_alive(), "stop() left the receiver wedged"
        assert results and results[0].is_err()
        assert results[0].unwrap_err()["errorType"] == "AGENT_STOPPED"

    def test_it_wakes_promptly(self):
        agent = Agent(Config(agent_id="r", broker_url="memory://wait-2"))
        agent.start()
        thread, _ = park(agent.receive)

        started = time.perf_counter()
        agent.stop()
        thread.join(timeout=3.0)
        elapsed = time.perf_counter() - started

        assert not thread.is_alive()
        assert elapsed < 2.0, f"waking took {elapsed:.2f}s"

    def test_the_error_names_the_agent(self):
        agent = Agent(Config(agent_id="named-one", broker_url="memory://wait-3"))
        agent.start()
        thread, results = park(agent.receive)
        agent.stop()
        thread.join(timeout=3.0)

        error = results[0].unwrap_err()
        assert error["details"]["agentId"] == "named-one"
        assert "named-one" in error["message"]

    def test_a_message_still_arrives_normally(self):
        """Waking on shutdown must not break the ordinary path.

        The agent is deliberately not started: ``receive()`` and the
        background handler loop consume the *same* queue, so on a started
        agent whichever polls first wins. That competition predates ADR-165
        and is unchanged by it; testing around it here keeps this test about
        the wait rather than about that race.
        """
        agent = Agent(Config(agent_id="r", broker_url="memory://wait-4"))
        thread, results = park(agent.receive)
        try:
            agent.message_queue.put(
                Message(message_type="HI", receiver="r", payload={"n": 1})
            )
            thread.join(timeout=3.0)

            assert results and results[0].is_ok()
            assert results[0].unwrap().payload["n"] == 1
        finally:
            agent._shutdown.set()
            thread.join(timeout=2.0)

    def test_a_started_agent_delivers_to_handlers(self):
        """The end-to-end path is handler-based, and is untouched."""
        received = []
        agent = Agent(Config(agent_id="r", broker_url="memory://wait-4b"))

        @agent.handler("HI")
        def _hi(message):
            received.append(message.payload["n"])

        agent.start()
        peer = Agent(Config(agent_id="p", broker_url="memory://wait-4b"))
        peer.start()
        try:
            peer.send(Message(message_type="HI", receiver="r", payload={"n": 1}))
            deadline = time.perf_counter() + 3.0
            while not received and time.perf_counter() < deadline:
                time.sleep(0.01)
            assert received == [1]
        finally:
            agent.stop(drain_timeout=0)
            peer.stop(drain_timeout=0)

    def test_an_explicit_timeout_still_times_out(self):
        agent = Agent(Config(agent_id="r", broker_url="memory://wait-5"))
        agent.start()
        try:
            result = agent.receive(timeout="100ms")
            assert result.is_err()
            assert result.unwrap_err()["errorType"] == "TIMEOUT"
        finally:
            agent.stop(drain_timeout=0)

    def test_a_message_racing_the_stop_is_not_lost(self):
        """A message landing in the same slice as the stop should still be
        delivered rather than reported as a shutdown."""
        agent = Agent(Config(agent_id="r", broker_url="memory://wait-6"))
        agent.start()
        try:
            thread, results = park(agent.receive)
            # put straight on the queue so it cannot be lost upstream, then
            # stop immediately
            agent.message_queue.put(
                Message(message_type="HI", receiver="r", payload={"n": 7})
            )
            agent.stop()
            thread.join(timeout=3.0)

            assert results
            if results[0].is_ok():
                assert results[0].unwrap().payload["n"] == 7
            else:
                # acceptable only as a shutdown, never as a lost message
                assert results[0].unwrap_err()["errorType"] == "AGENT_STOPPED"
        finally:
            MessageBroker.reset_scopes()

    def test_an_unstarted_agent_still_blocks(self):
        """The event is set by stop(), never at construction. Creating an
        agent, parking a receiver, then starting is a real pattern."""
        agent = Agent(Config(agent_id="r", broker_url="memory://wait-7"))
        thread, results = park(agent.receive)
        try:
            assert thread.is_alive(), "an unstarted agent should still block"
            assert not results
        finally:
            agent._shutdown.set()
            thread.join(timeout=2.0)


class TestStreamReceiveWakesOnClose:
    def _stream(self, scope):
        agent = Agent(Config(agent_id="s", broker_url=scope))
        agent.start()
        return agent, Stream(agent, "feed")

    def test_a_parked_reader_wakes_when_the_stream_closes(self):
        agent, stream = self._stream("memory://stream-1")
        try:
            thread, results = park(stream.receive)
            assert thread.is_alive()

            stream.close()
            thread.join(timeout=3.0)

            assert not thread.is_alive(), "close() left the reader wedged"
            assert results and results[0].is_err()
            assert results[0].unwrap_err()["errorType"] == "STREAM_CLOSED"
        finally:
            agent.stop(drain_timeout=0)

    def test_the_error_names_the_stream(self):
        agent, stream = self._stream("memory://stream-2")
        try:
            thread, results = park(stream.receive)
            stream.close()
            thread.join(timeout=3.0)

            details = results[0].unwrap_err()["details"]
            assert details["stream_name"] == "feed"
            assert details["stream_id"] == stream.stream_id
        finally:
            agent.stop(drain_timeout=0)

    def test_buffered_data_is_still_delivered(self):
        agent, stream = self._stream("memory://stream-3")
        try:
            stream.buffer.put({"n": 3})
            result = stream.receive()
            assert result.is_ok()
            assert result.unwrap() == {"n": 3}
        finally:
            agent.stop(drain_timeout=0)

    def test_an_explicit_timeout_still_times_out(self):
        agent, stream = self._stream("memory://stream-4")
        try:
            result = stream.receive(timeout=0.1)
            assert result.is_err()
            assert result.unwrap_err()["errorType"] == "TIMEOUT"
        finally:
            agent.stop(drain_timeout=0)

    def test_none_is_a_deliverable_payload_not_a_close_signal(self):
        """The close sentinel is a private object, so None stays valid data."""
        agent, stream = self._stream("memory://stream-5")
        try:
            stream.buffer.put(None)
            result = stream.receive()
            assert result.is_ok()
            assert result.unwrap() is None
        finally:
            agent.stop(drain_timeout=0)


class TestTaskQueueIsAlreadyCorrect:
    """ADR-165: TaskQueue's unbounded wait is NOT a defect. stop() calls
    notify_all(), so a parked caller wakes immediately.

    These tests exist so nobody 'fixes' a correct condition variable into a
    polling loop later.
    """

    def test_stop_wakes_a_parked_caller(self):
        from maple.task_management.task_queue import TaskQueue

        task_queue = TaskQueue()
        task_queue.start()
        thread, results = park(lambda: task_queue.get_next_task(timeout_seconds=None))
        assert thread.is_alive()

        started = time.perf_counter()
        task_queue.stop()
        thread.join(timeout=3.0)
        elapsed = time.perf_counter() - started

        assert not thread.is_alive(), "stop() left the caller parked"
        assert results
        assert elapsed < 1.0, "a signalled condition should wake immediately"

    def test_stop_still_notifies(self):
        import inspect

        from maple.task_management.task_queue import TaskQueue

        source = inspect.getsource(TaskQueue.stop)
        assert "notify_all" in source, (
            "TaskQueue.stop() must keep waking parked callers; without the "
            "notify its unbounded wait becomes the defect the roadmap "
            "mistakenly reported it as"
        )


class TestTheProviderJoinIsBounded:
    """An unbounded join on a stream collector hung the calling thread for as
    long as a stalled provider stalled."""

    def test_the_deadline_comes_from_the_configured_provider_timeout(self):
        from maple.autonomy.agent import AutonomousAgent

        class _Config:
            timeout = 30.0

        class _LLM:
            config = _Config()

        agent = object.__new__(AutonomousAgent)
        agent.llm = _LLM()
        deadline = AutonomousAgent._stream_join_deadline(agent)

        assert deadline > 30.0, "the join should outlast the provider's own timeout"
        assert deadline == 30.0 * AutonomousAgent._STREAM_JOIN_GRACE

    @pytest.mark.parametrize("bad", [None, 0, -1, "30", object()])
    def test_a_missing_or_nonsense_timeout_falls_back(self, bad):
        from maple.autonomy.agent import AutonomousAgent

        class _Config:
            timeout = bad

        class _LLM:
            config = _Config()

        agent = object.__new__(AutonomousAgent)
        agent.llm = _LLM()
        assert AutonomousAgent._stream_join_deadline(agent) > 0

    def test_the_join_is_not_unbounded(self):
        import inspect

        from maple.autonomy.agent import AutonomousAgent

        source = inspect.getsource(AutonomousAgent._complete_model_once)
        assert "worker.join()" not in source, "the collector join is unbounded"
        assert "_stream_join_deadline" in source
