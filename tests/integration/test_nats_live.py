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
"""Ground truth for the NATS transport, against a real server.

Every other transport in MAPLE is verified by running it. NATS was not: it
needs ``nats-py`` and a live server, neither of which exists on a developer
machine by default, so its behaviour was described rather than measured.

This module measures it. It runs in CI against a NATS service container and
**skips** anywhere a server is not reachable, so it never becomes a test that
quietly passes by not running.

Two kinds of test live here, and the second kind matters more:

1. What the transport **does** - delivery, statistics, unsubscribe.
2. What it **does not** - no backpressure, no undeliverable reporting, no
   remote routability. Those are asserted as *currently false* so that the day
   any of them changes, this file fails and the change is deliberate. They are
   the reason NATS is not in ``BROKER_FACTORIES`` (ADR-161), and they are the
   measurements the eventual implementation has to be designed against.
"""

import os
import time
import uuid

import pytest

from maple.agent.config import Config, PerformanceConfig
from maple.core.message import Message

pytestmark = pytest.mark.nats

DEFAULT_URL = "nats://127.0.0.1:4222"


def _server_url():
    return os.environ.get("MAPLE_NATS_URL", DEFAULT_URL)


@pytest.fixture(scope="module")
def nats_available():
    """Skip unless a real NATS server answers.

    Deliberately strict: an unreachable server is a skip, never a silent pass.
    """
    pytest.importorskip("nats", reason="nats-py is not installed")

    import asyncio

    from nats.aio.client import Client as NATS

    async def _probe():
        client = NATS()
        await client.connect(servers=[_server_url()], connect_timeout=5)
        await client.close()

    try:
        asyncio.run(asyncio.wait_for(_probe(), timeout=15))
    except Exception as exc:  # noqa: BLE001 - any failure means "no server"
        pytest.skip(f"no NATS server at {_server_url()}: {type(exc).__name__}")
    return _server_url()


def make_broker(nats_available, agent_id, **perf):
    from maple.broker.nats_broker import NATSBrokerSync

    config = Config(
        agent_id=agent_id,
        broker_url=nats_available,
        performance=PerformanceConfig(**perf) if perf else None,
    )
    return NATSBrokerSync(config)


@pytest.fixture
def subject():
    """A unique agent id, so tests cannot see each other's traffic."""
    return f"probe-{uuid.uuid4().hex[:10]}"


class TestWhatTheTransportDoes:
    def test_a_message_crosses_the_broker(self, nats_available, subject):
        received = []
        consumer = make_broker(nats_available, "consumer")
        assert consumer.connect().is_ok()
        producer = make_broker(nats_available, "producer")
        assert producer.connect().is_ok()
        try:
            assert consumer.subscribe(subject, received.append).is_ok()
            time.sleep(0.5)  # let the subscription register server-side

            result = producer.send(
                Message(message_type="PING", receiver=subject, payload={"n": 1})
            )
            assert result.is_ok(), result.unwrap_err()

            deadline = time.time() + 15
            while not received and time.time() < deadline:
                time.sleep(0.05)

            assert received, "a message published to NATS never arrived"
            assert received[0].payload["n"] == 1
        finally:
            consumer.disconnect()
            producer.disconnect()

    def test_statistics_count_what_was_published(self, nats_available, subject):
        producer = make_broker(nats_available, "producer")
        assert producer.connect().is_ok()
        try:
            before = producer.get_statistics()["delivered"]
            for i in range(5):
                producer.send(
                    Message(message_type="X", receiver=subject, payload={"i": i})
                )
            after = producer.get_statistics()["delivered"]

            assert after - before == 5, (
                "delivered counts what this client handed to NATS; it moved by "
                f"{after - before} for 5 sends"
            )
        finally:
            producer.disconnect()

    def test_unsubscribe_stops_delivery(self, nats_available, subject):
        received = []
        consumer = make_broker(nats_available, "consumer")
        assert consumer.connect().is_ok()
        producer = make_broker(nats_available, "producer")
        assert producer.connect().is_ok()
        try:
            consumer.subscribe(subject, received.append)
            time.sleep(0.5)
            consumer.unsubscribe(subject)
            time.sleep(0.5)

            producer.send(Message(message_type="X", receiver=subject, payload={"n": 2}))
            time.sleep(2.0)

            assert received == [], "delivery continued after unsubscribe"
        finally:
            consumer.disconnect()
            producer.disconnect()

    def test_connect_reports_failure_for_an_unreachable_server(self):
        """A refused connection must be a typed error, not an exception."""
        pytest.importorskip("nats")
        from maple.broker.nats_broker import NATSBrokerSync

        broker = NATSBrokerSync(
            Config(agent_id="nowhere", broker_url="nats://127.0.0.1:4"),
        )
        result = broker.connect()
        assert result.is_err(), "connecting to a dead port reported success"


class TestWhatTheTransportDoesNotDo:
    """Asserted as currently false, so the day it changes is deliberate.

    These are the measurements the conformance work has to be designed
    against - not opinions about NATS, but what this client actually does.
    """

    def test_there_is_no_backpressure(self, nats_available, subject):
        """`max_queue_size` is not enforced: publish is fire-and-forget.

        The conformance suite requires a full queue to raise
        BrokerOverflowError. Nothing here can, because MAPLE holds no queue.
        """
        from maple.error.types import BrokerOverflowError

        producer = make_broker(nats_available, "producer", max_queue_size=3)
        assert producer.connect().is_ok()
        try:
            refused = 0
            for i in range(50):
                try:
                    producer.send(
                        Message(message_type="X", receiver=subject, payload={"i": i})
                    )
                except BrokerOverflowError:
                    refused += 1

            assert refused == 0, (
                "backpressure appeared - if the transport now refuses, update "
                "CAPABILITIES.applies_backpressure and reconsider "
                "BROKER_FACTORIES"
            )
            assert producer.get_statistics()["refused"] == 0
        finally:
            producer.disconnect()

    def test_an_oversized_payload_is_not_refused_by_maple(
        self, nats_available, subject
    ):
        """The conformance suite requires MESSAGE_TOO_LARGE. NATS enforces its
        own server-side limit instead, which is a different guarantee."""
        from maple.error.types import BrokerOverflowError

        producer = make_broker(nats_available, "producer", max_message_bytes=512)
        assert producer.connect().is_ok()
        try:
            raised = False
            try:
                producer.send(
                    Message(
                        message_type="BIG",
                        receiver=subject,
                        payload={"blob": "z" * 4000},
                    )
                )
            except BrokerOverflowError:
                raised = True

            assert raised is False, (
                "MAPLE-side size admission appeared on the NATS transport - "
                "update the capability declaration"
            )
        finally:
            producer.disconnect()

    def test_nothing_is_reported_undeliverable(self, nats_available, subject):
        """Publishing to a subject nobody subscribes to succeeds silently."""
        dead = []
        producer = make_broker(nats_available, "producer")
        producer.set_undeliverable_handler(
            lambda receiver, message: dead.append(receiver)
        )
        assert producer.connect().is_ok()
        try:
            producer.send(Message(message_type="X", receiver=subject, payload={}))
            time.sleep(2.0)

            assert producer.get_statistics()["undeliverable"] == 0
            assert dead == [], (
                "the dead-letter hook fired - if undeliverable reporting now "
                "works, update CAPABILITIES.reports_undeliverable"
            )
        finally:
            producer.disconnect()

    def test_routability_cannot_see_a_remote_subscriber(self, nats_available, subject):
        """The measurement behind `supports_routability_check=False`.

        One broker subscribes; a *different* broker cannot tell.
        """
        consumer = make_broker(nats_available, "consumer")
        assert consumer.connect().is_ok()
        producer = make_broker(nats_available, "producer")
        assert producer.connect().is_ok()
        try:
            consumer.subscribe(subject, lambda m: None)
            time.sleep(0.5)

            assert (
                consumer.is_routable(subject) is True
            ), "a broker cannot see its own subscription"
            assert producer.is_routable(subject) is False, (
                "remote routability appeared - if the client can now see "
                "cluster subscriptions, update "
                "CAPABILITIES.supports_routability_check and the gate in "
                "Agent.send"
            )
        finally:
            consumer.disconnect()
            producer.disconnect()

    def test_a_separation_policy_is_refused(self, nats_available):
        """ADR-157: a control that cannot run must refuse."""
        from maple.error.types import SecurityError

        broker = make_broker(nats_available, "producer")
        with pytest.raises(SecurityError):
            broker.set_separation_policy(object())


class TestTheCapabilityDeclarationMatchesReality:
    """The flags are a promise. This checks the promise against the server."""

    def test_flags_still_say_what_the_tests_above_measured(self):
        pytest.importorskip("nats")
        from maple.broker.nats_broker import NATSBrokerSync

        caps = NATSBrokerSync.CAPABILITIES
        assert caps.applies_backpressure is False
        assert caps.reports_undeliverable is False
        assert caps.supports_routability_check is False
        assert caps.enforces_security_policy is False
        assert caps.cross_process is True
