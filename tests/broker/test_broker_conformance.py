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


def _nats(**perf):
    """A NATS-backed broker, connected to a real server (ADR-170).

    Unlike the others this needs infrastructure, so it is selected only under
    the `nats` marker - which the live CI job runs against a service
    container. The tests are the same ones; a suite written to be passable
    would prove nothing.
    """
    pytest.importorskip("nats", reason="nats-py is not installed")
    import os

    from maple.broker.nats_broker import NATSBrokerSync

    url = os.environ.get("MAPLE_NATS_URL", "nats://127.0.0.1:4222")
    config = Config(
        agent_id="conformance",
        broker_url=url,
        performance=PerformanceConfig(**perf) if perf else None,
    )
    broker = NATSBrokerSync(config)
    _NATS_BROKERS.append(broker)
    return broker


#: Live NATS brokers created during a run, torn down afterwards.
_NATS_BROKERS = []


#: Every transport that can be constructed without external infrastructure.
#: A new transport is added here and must pass everything below unchanged.
BROKER_FACTORIES = {
    "in-memory": _in_memory,
    "file": _file_backed,
}

#: Selected only under `-m nats`, where a real server exists.
LIVE_BROKER_FACTORIES = {"nats": _nats}


@pytest.fixture(autouse=True)
def reset_scopes():
    MessageBroker.reset_scopes()
    yield
    MessageBroker.reset_scopes()
    while _SPOOLS:
        shutil.rmtree(_SPOOLS.pop(), ignore_errors=True)
    while _NATS_BROKERS:
        try:
            _NATS_BROKERS.pop().disconnect()
        except Exception:
            pass


def _factory_params():
    """In-process transports run always; NATS runs under `-m nats`."""
    params = [pytest.param(name, id=name) for name in sorted(BROKER_FACTORIES)]
    params += [
        pytest.param(name, id=name, marks=pytest.mark.nats)
        for name in sorted(LIVE_BROKER_FACTORIES)
    ]
    return params


@pytest.fixture(params=_factory_params())
def factory(request):
    both = {**BROKER_FACTORIES, **LIVE_BROKER_FACTORIES}
    return both[request.param]


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
    broker._undeliverable = 0
    broker._presence = {}
    broker._presence_sub = None
    broker._heartbeat_task = None
    return broker


class TestKnownNonConformance:
    """What the NATS transport still does not do. Pinned, not ignored.

    Once five members were missing (ADR-161), then three capabilities
    (ADR-168), then one (ADR-170). What remains is security enforcement,
    which is *refused* rather than faked.

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

    def test_the_delivery_capabilities_are_all_closed_now(self):
        """Presence closed routability and undeliverable (ADR-168); a bounded
        outbound queue closed backpressure (ADR-170)."""
        from maple.broker.nats_broker import NATSBrokerSync

        caps = NATSBrokerSync.CAPABILITIES
        assert caps.reports_undeliverable is True
        assert caps.supports_routability_check is True
        assert caps.applies_backpressure is True

    def test_security_enforcement_is_still_refused_not_faked(self):
        """The one capability deliberately still absent. ADR-157: a control
        that cannot run must refuse."""
        from maple.broker.nats_broker import NATSBrokerSync

        assert NATSBrokerSync.CAPABILITIES.enforces_security_policy is False
        assert NATSBrokerSync.ENFORCES_SECURITY_POLICY is False

    def test_nats_is_exercised_by_the_conformance_suite_itself(self):
        """Not a weaker parallel suite - the same tests, against a real
        server, selected under the `nats` marker (ADR-170)."""
        assert "nats" in LIVE_BROKER_FACTORIES
        assert (
            "nats" not in BROKER_FACTORIES
        ), "the default suite must stay constructible without infrastructure"

    def test_a_policy_it_cannot_enforce_is_refused_not_accepted(self):
        """ADR-157: a control that cannot run must refuse. Accepting a
        separation policy this transport ignores would leave a caller
        believing a boundary exists."""
        from maple.error.types import SecurityError

        broker = _nats_broker_without_a_server()
        with pytest.raises(SecurityError):
            broker.set_separation_policy(object())

        broker.set_separation_policy(None)  # clearing is always allowed

    def test_routability_answers_from_presence(self):
        """Was local-only; presence made it cluster-wide (ADR-168).

        An agent we serve ourselves needs no beacon; a remote one is known
        from its beacon, and an expired beacon is not routable.
        """
        import time as _time

        broker = _nats_broker_without_a_server()
        broker.subscriptions = {"here": object()}
        broker._presence = {
            "remote": _time.perf_counter(),
            "stale": _time.perf_counter() - (broker.PRESENCE_TTL_SECONDS + 5),
        }

        assert broker.is_routable("here") is True, "our own agent"
        assert broker.is_routable("remote") is True, "a fresh beacon"
        assert broker.is_routable("stale") is False, "an expired beacon"
        assert broker.is_routable("unknown") is False
        assert broker.is_routable("") is False

    def test_the_undeliverable_hook_is_live_now(self):
        """It used to be stored with a warning that it would never fire.
        Presence made it real (ADR-168), so the warning is gone and the hook
        is called when nobody serves a receiver."""
        dead = []
        broker = _nats_broker_without_a_server()
        broker.set_undeliverable_handler(
            lambda receiver, message: dead.append(receiver)
        )
        broker._report_undeliverable("ghost", object())

        assert dead == ["ghost"]
        assert broker.get_statistics()["undeliverable"] == 1

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
        assert caps.applies_backpressure is True  # outbound queue, ADR-170
        assert caps.reports_undeliverable is True  # presence, ADR-168
        assert caps.cross_process is True

    def test_the_wrapper_cannot_advertise_different_capabilities(self):
        """The sync wrapper duplicated this declaration and was updated in one
        place only - the exact "fixed one instance of a duplicated thing"
        mistake the 2.1.0 retrospective named. It now derives it."""
        from maple.broker.nats_broker import NATSBroker, NATSBrokerSync

        assert NATSBrokerSync.CAPABILITIES is NATSBroker.CAPABILITIES
