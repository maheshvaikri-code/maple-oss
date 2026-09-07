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
"""receive() and the handler loop read the same queue (ADR-169).

Before this, whichever polled first won, so a caller using ``receive()`` on a
started agent got messages *sometimes*. That was found while writing the
ADR-165 tests: the handler loop ate the message and the test failed, and it
was worked around by not starting the agent rather than fixed.

Refusing to serve ``receive()`` on a started agent was tried first and is
worse — it makes pulling impossible there, and makes ADR-165's
wake-on-shutdown unreachable. So the pull takes precedence while it waits and
the loop defers, which makes the outcome deterministic rather than a race.
"""

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


class TestAWaitingReceiverWins:
    def test_a_started_agent_delivers_to_receive_not_the_loop(self):
        """The race, run enough times that winning by luck is not plausible."""
        handled = []
        agent = Agent(Config(agent_id="r", broker_url="memory://prec-1"))

        @agent.handler("WORK")
        def _work(message):
            handled.append(message.payload["i"])

        agent.start()
        try:
            for i in range(15):
                received = []
                thread = threading.Thread(
                    target=lambda: received.append(agent.receive(timeout="5s")),
                    daemon=True,
                )
                thread.start()
                time.sleep(0.03)  # let the receiver claim precedence
                agent.message_queue.put(
                    Message(message_type="WORK", receiver="r", payload={"i": i})
                )
                thread.join(timeout=6)

                assert received, f"iteration {i}: receive() never returned"
                assert received[0].is_ok(), (
                    f"iteration {i}: the handler loop took the message "
                    f"({received[0].unwrap_err()})"
                )
                assert received[0].unwrap().payload["i"] == i
        finally:
            agent.stop(drain_timeout=0)

        assert (
            handled == []
        ), f"the handler loop consumed {handled} while a receiver was waiting"

    def test_the_loop_resumes_once_nobody_is_receiving(self):
        """Precedence must be temporary, or registering a handler would stop
        working the moment anyone called receive() once."""
        handled = []
        agent = Agent(Config(agent_id="r", broker_url="memory://prec-2"))

        @agent.handler("WORK")
        def _work(message):
            handled.append(message.payload["i"])

        agent.start()
        try:
            assert agent.receive(timeout="100ms").is_err()  # times out, releases

            agent.message_queue.put(
                Message(message_type="WORK", receiver="r", payload={"i": 1})
            )
            deadline = time.perf_counter() + 5
            while not handled and time.perf_counter() < deadline:
                time.sleep(0.01)

            assert handled == [1], "the handler loop never resumed"
        finally:
            agent.stop(drain_timeout=0)

    def test_precedence_is_released_even_if_the_wait_raises(self):
        agent = Agent(Config(agent_id="r", broker_url="memory://prec-3"))
        agent.start()
        try:
            agent.receive(timeout="50ms")
            assert agent._a_receiver_is_waiting() is False
        finally:
            agent.stop(drain_timeout=0)

    def test_nested_receivers_are_counted_not_flagged(self):
        """Two threads receiving at once must both be tracked, so the loop
        does not resume when only one of them finishes."""
        agent = Agent(Config(agent_id="r", broker_url="memory://prec-4"))
        agent.start()
        try:
            with agent._receiving():
                with agent._receiving():
                    assert agent._a_receiver_is_waiting() is True
                assert agent._a_receiver_is_waiting() is True
            assert agent._a_receiver_is_waiting() is False
        finally:
            agent.stop(drain_timeout=0)

    def test_an_unstarted_agent_is_unaffected(self):
        agent = Agent(Config(agent_id="r", broker_url="memory://prec-5"))
        agent.message_queue.put(
            Message(message_type="WORK", receiver="r", payload={"i": 7})
        )
        result = agent.receive(timeout="2s")
        assert result.is_ok()
        assert result.unwrap().payload["i"] == 7
