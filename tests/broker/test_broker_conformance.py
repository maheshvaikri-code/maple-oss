"""The conformance suite every MAPLE transport must pass (ADR-161).

This is the part that makes the contract worth stating. Before it existed, the
two shipped brokers shared no interface and had drifted six methods apart —
two of them security and observability controls — so "swap in NATS for
production" was not a verifiable operation.

Adding a transport is now bounded work with a pass/fail gate. Register it in
``BROKER_FACTORIES`` and it is held to the same observable behaviour as the
in-memory broker, which is itself tested here against the contract it defines.

A transport requiring external infrastructure should be added with a skip
guard, never by weakening an assertion.
"""

import shutil
import tempfile
import time
from pathlib import Path

import pytest

from maple.agent.config import Config, PerformanceConfig, SecurityConfig
from maple.broker.broker import MessageBroker
from maple.broker.contract import Broker, BrokerCapabilities, describe_conformance
from maple.broker.file_broker import FileBroker
from maple.core.message import Message
from maple.error.types import BrokerOverflowError, SecurityError


def _in_memory(**perf):
    config = Config(
        agent_id="conformance",
        broker_url="memory://conformance",
        performance=PerformanceConfig(**perf) if perf else None,
    )
    return MessageBroker(config)


def _file_backed(**perf):
    """A file-backed broker on a fresh spool (ADR-167).

    Needs no external infrastructure, so it belongs in this suite: proving the
    contract is implementable twice is what makes it a contract.
    """
    root = Path(tempfile.mkdtemp(prefix="maple-spool-"))
    _SPOOLS.append(root)
    url = root.as_uri()
    config = Config(
        agent_id="conformance",
        broker_url=url,
        performance=PerformanceConfig(**perf) if perf else None,
    )
    return FileBroker(config)


#: Spools created during the run, removed afterwards.
_SPOOLS = []


#: Every transport that can be constructed without external infrastructure.
#: A new transport is added here and must pass everything below unchanged.
BROKER_FACTORIES = {
    "in-memory": _in_memory,
    "file": _file_backed,
}


@pytest.fixture(autouse=True)
def reset_scopes():
    MessageBroker.reset_scopes()
    yield
    MessageBroker.reset_scopes()
    while _SPOOLS:
        shutil.rmtree(_SPOOLS.pop(), ignore_errors=True)


@pytest.fixture(params=sorted(BROKER_FACTORIES))
def factory(request):
    return BROKER_FACTORIES[request.param]


class TestStructuralConformance:
    def test_declares_capabilities(self, factory):
        broker = factory()
        assert isinstance(broker.CAPABILITIES, BrokerCapabilities)

    def test_provides_every_contract_member(self, factory):
        report = describe_conformance(factory())
        assert report["missingMembers"] == []
        assert report["conforms"] is True

    def test_satisfies_the_runtime_protocol(self, factory):
        assert isinstance(factory(), Broker)


class TestLifecycle:
    def test_connect_is_idempotent(self, factory):
        broker = factory()
        broker.connect()
        broker.connect()
        try:
            assert broker.running is True
        finally:
            broker.disconnect()

    def test_disconnect_without_connect_is_safe(self, factory):
        factory().disconnect()  # must not raise

    def test_disconnect_is_idempotent(self, factory):
        broker = factory()
        broker.connect()
        broker.disconnect()
        broker.disconnect()  # must not raise


class TestDelivery:
    def test_a_subscribed_handler_receives_its_message(self, factory):
        broker = factory()
        got = []
        broker.subscribe("alice", lambda m: got.append(m.message_type))
        broker.connect()
        try:
            broker.send(
                Message(message_type="PING", sender="s", receiver="alice", payload={})
            )
            time.sleep(0.5)
            assert got == ["PING"]
        finally:
            broker.disconnect()

    def test_send_returns_an_identifier(self, factory):
        broker = factory()
        broker.subscribe("alice", lambda m: None)
        result = broker.send(
            Message(message_type="X", sender="s", receiver="alice", payload={})
        )
        assert isinstance(result, str) and result

    def test_unsubscribe_stops_delivery(self, factory):
        broker = factory()
        got = []
        broker.subscribe("alice", lambda m: got.append(m))
        broker.unsubscribe("alice")
        broker.connect()
        try:
            broker.send(
                Message(message_type="X", sender="s", receiver="alice", payload={})
            )
            time.sleep(0.4)
            assert got == []
        finally:
            broker.disconnect()

    def test_unsubscribe_is_idempotent(self, factory):
        broker = factory()
        broker.unsubscribe("never-subscribed")  # must not raise


class TestRoutability:
    def test_is_routable_is_false_before_subscribe(self, factory):
        assert factory().is_routable("nobody") is False

    def test_is_routable_is_true_after_subscribe(self, factory):
        broker = factory()
        broker.subscribe("alice", lambda m: None)
        assert broker.is_routable("alice") is True

    def test_is_routable_rejects_an_empty_agent_id(self, factory):
        assert factory().is_routable("") is False


class TestBackpressure:
    """Refusal, not unbounded buffering. A bound that spills is not a bound."""

    def test_a_full_queue_refuses(self, factory):
        broker = factory(max_queue_size=3)
        for _ in range(3):
            broker.send(
                Message(message_type="X", sender="s", receiver="stalled", payload={})
            )

        with pytest.raises(BrokerOverflowError) as excinfo:
            broker.send(
                Message(message_type="X", sender="s", receiver="stalled", payload={})
            )
        assert excinfo.value.error["errorType"] == "QUEUE_FULL"

    def test_an_oversized_payload_refuses(self, factory):
        broker = factory(max_message_bytes=512)
        with pytest.raises(BrokerOverflowError) as excinfo:
            broker.send(
                Message(
                    message_type="BIG",
                    sender="s",
                    receiver="x",
                    payload={"blob": "z" * 4000},
                )
            )
        assert excinfo.value.error["errorType"] == "MESSAGE_TOO_LARGE"

    def test_refusals_are_counted(self, factory):
        broker = factory(max_queue_size=1)
        broker.send(Message(message_type="X", sender="s", receiver="r", payload={}))
        for _ in range(4):
            with pytest.raises(BrokerOverflowError):
                broker.send(
                    Message(message_type="X", sender="s", receiver="r", payload={})
                )
        assert broker.get_statistics()["refused"] == 4


class TestUndeliverableReporting:
    def test_a_message_with_no_handler_is_counted(self, factory):
        broker = factory()
        broker.connect()
        try:
            broker.send(
                Message(message_type="X", sender="s", receiver="ghost", payload={})
            )
            time.sleep(0.4)
            assert broker.get_statistics()["undeliverable"] == 1
        finally:
            broker.disconnect()

    def test_the_dead_letter_hook_receives_it(self, factory):
        broker = factory()
        dead = []
        broker.set_undeliverable_handler(lambda r, m: dead.append(r))
        broker.connect()
        try:
            broker.send(
                Message(message_type="X", sender="s", receiver="ghost", payload={})
            )
            time.sleep(0.4)
            assert dead == ["ghost"]
        finally:
            broker.disconnect()

    def test_the_hook_can_be_cleared(self, factory):
        broker = factory()
        dead = []
        broker.set_undeliverable_handler(lambda r, m: dead.append(r))
        broker.set_undeliverable_handler(None)
        broker.connect()
        try:
            broker.send(
                Message(message_type="X", sender="s", receiver="ghost", payload={})
            )
            time.sleep(0.4)
            assert dead == []
        finally:
            broker.disconnect()


class TestStatisticsSurface:
    def test_required_keys_are_present(self, factory):
        stats = factory().get_statistics()
        assert {"delivered", "undeliverable", "refused"} <= set(stats)


class TestSecurityEnforcement:
    """Only asserted where the transport claims to enforce."""

    def test_a_declared_enforcer_applies_the_link_policy(self, factory):
        broker = factory()
        if not broker.CAPABILITIES.enforces_security_policy:
            pytest.skip("transport does not claim to enforce security policy")

        MessageBroker.reset_scopes()
        secured = MessageBroker(
            Config(
                agent_id="c",
                broker_url="memory://conformance-secure",
                security=SecurityConfig(
                    "jwt", {"token": "t"}, require_links=True, strict_link_policy=True
                ),
            )
        )
        with pytest.raises(SecurityError):
            secured.send(
                Message(message_type="S", sender="a", receiver="b", payload={})
            )


def _nats_broker_without_a_server():
    """A NATSBroker with its state set up but no nats-py and no server.

    ``NATSBroker.__init__`` raises ImportError without ``nats-py``, so the
    members that are pure local bookkeeping are exercised on an instance built
    around it. Anything touching the network is *not* covered here and is
    honestly out of reach until CI runs a real server.
    """
    from maple.broker.nats_broker import NATSBroker

    broker = object.__new__(NATSBroker)
    broker.nc = None
    broker.subscriptions = {}
    broker._undeliverable_handler = None
    broker._separation_policy = None
    broker._published = 0
    broker._refused = 0
    return broker


class TestKnownNonConformance:
    """The NATS transport satisfies the contract *structurally* but not
    *behaviourally*. Pinned, not ignored.

    ADR-161 recorded five missing members; those now exist. What remains is
    harder and is not a matter of adding methods: NATS publish is
    fire-and-forget, so backpressure, undeliverable reporting and routability
    are capabilities the transport does not natively provide. Until it does,
    it stays out of ``BROKER_FACTORIES`` - because everything in that dict has
    to pass the behavioural tests above, and passing is the only thing that
    counts as conforming.
    """

    def test_nats_now_provides_every_contract_member(self):
        from maple.broker.nats_broker import NATSBrokerSync

        report = describe_conformance(NATSBrokerSync)
        assert report["missingMembers"] == []
        assert report["conforms"] is True

    def test_nats_is_not_in_the_conformance_factories(self):
        """Structural conformance is not conformance. Adding it here must be
        a deliberate edit made when it can actually pass."""
        assert "nats" not in BROKER_FACTORIES

    def test_the_remaining_gap_is_capability_shaped(self):
        """The honest description of what is left."""
        from maple.broker.nats_broker import NATSBrokerSync

        caps = NATSBrokerSync.CAPABILITIES
        assert caps.applies_backpressure is False
        assert caps.reports_undeliverable is False
        assert caps.supports_routability_check is False

    def test_a_policy_it_cannot_enforce_is_refused_not_accepted(self):
        """ADR-157: a control that cannot run must refuse. Accepting a
        separation policy this transport ignores would leave a caller
        believing a boundary exists."""
        from maple.error.types import SecurityError

        broker = _nats_broker_without_a_server()
        with pytest.raises(SecurityError):
            broker.set_separation_policy(object())

        broker.set_separation_policy(None)  # clearing is always allowed

    def test_routability_is_local_only(self):
        """The NATS client sees its own subscriptions and nothing else, which
        is why the capability flag says not to trust the answer."""
        broker = _nats_broker_without_a_server()
        broker.subscriptions = {"here": object()}

        assert broker.is_routable("here") is True
        assert broker.is_routable("elsewhere") is False
        assert broker.is_routable("") is False

    def test_an_undeliverable_hook_is_stored_but_warned_about(self, caplog):
        """A hook that silently never fires is the defect ADR-159 and ADR-162
        exist to close, so accepting one says so out loud."""
        import logging

        broker = _nats_broker_without_a_server()
        with caplog.at_level(logging.WARNING, logger="maple.broker.nats_broker"):
            broker.set_undeliverable_handler(lambda receiver, message: None)

        assert any(
            "will not be called" in record.getMessage() for record in caplog.records
        )

    def test_statistics_expose_the_required_keys(self):
        broker = _nats_broker_without_a_server()
        stats = broker.get_statistics()
        assert {"delivered", "undeliverable", "refused"} <= set(stats)

    def test_unsubscribe_is_idempotent_bookkeeping(self):
        broker = _nats_broker_without_a_server()
        broker.subscriptions = {"a": object()}
        broker.unsubscribe_local("a")
        broker.unsubscribe_local("a")
        assert broker.subscriptions == {}

    def test_nats_declares_its_capabilities_honestly(self):
        from maple.broker.nats_broker import NATSBrokerSync

        caps = NATSBrokerSync.CAPABILITIES
        assert caps.enforces_security_policy is False
        assert caps.applies_backpressure is False
        assert caps.reports_undeliverable is False
        assert caps.cross_process is True
