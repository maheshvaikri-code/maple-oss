"""Regression tests for the broker configuration-fidelity blockers (ADR-157).

Three defects shared one root cause: ``MessageBroker`` is a process-wide
singleton that froze its configuration at first construction, and ``import
maple`` used to perform that first construction itself.

- B1: importing the package seeded the singleton with a throwaway config.
- B2: every later ``SecurityConfig`` was discarded, and ``require_links``
      enforcement was nested such that a missing link manager failed *open*.
- B3: ``nats://`` / ``s2://`` silently degraded to the in-memory broker.
"""

import subprocess
import sys

import pytest

from maple.agent.agent import Agent
from maple.agent.config import Config, SecurityConfig
from maple.broker.broker import MessageBroker, SecurityError
from maple.core.message import Message
from maple.error.types import BrokerUnavailableError


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
    _reset_broker_singleton()
    yield
    _reset_broker_singleton()


class TestImportHasNoBrokerSideEffect:
    """B1 - importing the package must not construct anything global."""

    def test_import_maple_does_not_construct_broker_singleton(self):
        # A fresh interpreter is the only honest check: this process has
        # already imported maple, so an in-process assertion would be
        # meaningless.
        code = (
            "import maple\n"
            "from maple.broker.broker import MessageBroker\n"
            "print(MessageBroker._instance)\n"
        )
        out = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, timeout=120
        )
        assert out.returncode == 0, out.stderr
        assert out.stdout.strip() == "None", (
            "importing maple constructed a broker; the singleton is now pinned "
            "to the import-time config"
        )

    def test_validate_installation_has_no_broker_side_effect(self):
        import maple

        assert MessageBroker._instance is None
        result = maple.validate_installation()

        assert result["status"] == "SUCCESS"
        assert MessageBroker._instance is None

    def test_user_broker_url_is_not_overridden_by_package_import(self):
        agent = Agent(Config(agent_id="first", broker_url="memory://mine"))
        assert agent.broker.config.broker_url == "memory://mine"


class TestSecurityConfigAdoption:
    """B2a - a later config's security block must reach the singleton."""

    def test_security_config_adopted_by_initialized_singleton(self):
        # First agent has no security at all - it used to pin the broker.
        Agent(Config(agent_id="plain", broker_url="memory://local"))
        assert MessageBroker._instance.security_config is None

        sec = SecurityConfig("jwt", {"token": "t"})
        second = Agent(
            Config(agent_id="secure", broker_url="memory://local", security=sec)
        )

        assert second.broker.security_config is sec

    def test_link_manager_built_when_security_adopted(self):
        Agent(Config(agent_id="plain", broker_url="memory://local"))
        assert MessageBroker._instance.link_manager is None

        sec = SecurityConfig("jwt", {"token": "t"})
        second = Agent(
            Config(agent_id="secure", broker_url="memory://local", security=sec)
        )

        assert second.broker.link_manager is not None
        assert second.broker._auth_manager is not None

    def test_security_config_not_cleared_by_later_plain_config(self):
        """The never-clear invariant: a security-less config must not disarm."""
        sec = SecurityConfig("jwt", {"token": "t"})
        first = Agent(
            Config(agent_id="secure", broker_url="memory://local", security=sec)
        )
        link_manager = first.broker.link_manager

        Agent(Config(agent_id="plain", broker_url="memory://local"))

        assert first.broker.security_config is sec
        assert first.broker.link_manager is link_manager

    def test_adopting_security_preserves_live_link_manager(self):
        """Adoption is idempotent - it must not rebuild and drop live state."""
        sec_a = SecurityConfig("jwt", {"token": "a"})
        agent = Agent(Config(agent_id="a", broker_url="memory://local", security=sec_a))
        original = agent.broker.link_manager

        sec_b = SecurityConfig("jwt", {"token": "b"})
        Agent(Config(agent_id="b", broker_url="memory://local", security=sec_b))

        assert agent.broker.security_config is sec_b
        assert agent.broker.link_manager is original


class TestLinkEnforcementFailsClosed:
    """B2b - an unenforceable link policy must refuse, not pass."""

    def _secure_broker(self, **security_kwargs):
        sec = SecurityConfig("jwt", {"token": "t"}, **security_kwargs)
        agent = Agent(
            Config(agent_id="alice", broker_url="memory://secure", security=sec)
        )
        return agent.broker

    def test_require_links_without_link_manager_raises(self):
        broker = self._secure_broker(require_links=True)
        # Simulate LinkManager being unimportable at construction time.
        broker.link_manager = None

        message = Message(
            message_type="SECRET", sender="alice", receiver="mallory", payload={}
        )
        with pytest.raises(SecurityError, match="no link manager is available"):
            broker.send(message)

    def test_strict_link_policy_rejects_unlinked_send(self):
        broker = self._secure_broker(require_links=True, strict_link_policy=True)

        message = Message(
            message_type="SECRET", sender="alice", receiver="mallory", payload={}
        )
        with pytest.raises(SecurityError, match="No valid link exists"):
            broker.send(message)

    def test_rejected_send_is_not_enqueued(self):
        """A refused send must leave no trace - assert absence of side effects."""
        broker = self._secure_broker(require_links=True, strict_link_policy=True)

        message = Message(
            message_type="SECRET", sender="alice", receiver="mallory", payload={}
        )
        with pytest.raises(SecurityError):
            broker.send(message)

        assert MessageBroker._agent_queues.get("mallory", []) == []

    def test_existing_link_is_reused_for_an_unlinked_message(self):
        """Cover the link-reuse path that the fail-closed change re-indented.

        The enforcement block was un-nested from under ``if self.link_manager:``
        (ADR-157). These two tests pin the behavior that moved, so a purely
        structural change cannot silently break link reuse or validation.
        """
        broker = self._secure_broker(require_links=True, strict_link_policy=True)
        broker.subscribe("alice", lambda _message: None)
        broker.subscribe("bob", lambda _message: None)

        link = broker.link_manager.initiate_link("alice", "bob")
        assert broker.link_manager.establish_link(link.link_id).is_ok()

        # No link id on the message: the broker must find and attach the
        # established one rather than reject under the strict policy.
        message = Message(
            message_type="SECRET", sender="alice", receiver="bob", payload={}
        )
        assert broker.send(message)

    def test_invalid_link_id_is_rejected(self):
        """Cover the validate_link failure path."""
        broker = self._secure_broker(require_links=True)
        broker.subscribe("alice", lambda _message: None)
        broker.subscribe("bob", lambda _message: None)

        message = Message(
            message_type="SECRET", sender="alice", receiver="bob", payload={}
        ).with_link("link-that-does-not-exist")

        with pytest.raises(SecurityError, match="Link validation failed"):
            broker.send(message)

    def test_send_without_require_links_is_unaffected(self):
        """The guard must not fire when the caller never asked for links."""
        broker = self._secure_broker(require_links=False)
        broker.link_manager = None
        # subscribe() is what start() uses to assign each party's role. The
        # authorization manager is live now that the security config is
        # adopted, and it checks sender *and* receiver.
        broker.subscribe("alice", lambda _message: None)
        broker.subscribe("bob", lambda _message: None)

        message = Message(
            message_type="PING", sender="alice", receiver="bob", payload={}
        )
        assert broker.send(message)  # returns a message id, does not raise

    def test_started_secure_agent_can_still_send(self):
        """Adopting security must not brick the ordinary secure send path.

        Regression guard for the adoption fix itself: ``_auth_manager`` is now
        built whenever a security config is adopted, so a started agent must
        still pass its own authorization check.
        """
        sec = SecurityConfig("jwt", {"token": "t"})
        alice = Agent(
            Config(agent_id="alice", broker_url="memory://secure", security=sec)
        )
        bob = Agent(Config(agent_id="bob", broker_url="memory://secure", security=sec))
        alice.start()
        bob.start()
        try:
            result = alice.send(
                Message(message_type="PING", receiver="bob", payload={"n": 1})
            )
            assert result.is_ok(), result.unwrap_err()
        finally:
            alice.stop()
            bob.stop()

    def test_secure_send_to_unsubscribed_receiver_is_denied(self):
        """Documents a consequence of adopting security config (ADR-157).

        ``_auth_manager`` used to be pinned to None by the import-time agent,
        so ``authorize_message`` never ran. It runs now, and it checks the
        receiver's role as well as the sender's - so a security-configured
        agent cannot send to a peer that has never subscribed. This test
        exists to make that behavior explicit rather than incidental.
        """
        broker = self._secure_broker(require_links=False)
        broker.subscribe("alice", lambda _message: None)

        message = Message(
            message_type="PING", sender="alice", receiver="never_started", payload={}
        )
        with pytest.raises(SecurityError, match="authorization denied"):
            broker.send(message)


class TestTransportFailsFast:
    """B3 - a named transport must be delivered or refused, never swapped."""

    @staticmethod
    def _require_unavailable(config, broker_type):
        """Skip unless the factory genuinely cannot build this transport.

        The precondition is taken from the factory itself rather than from an
        ``import`` probe. Driver availability is module-level state that other
        tests have mocked in the past, so an independent probe can disagree
        with the code path under test and produce a confusing failure. What is
        being tested here is narrow: that ``Agent`` *propagates* the factory's
        error instead of swallowing it.
        """
        from maple.broker.production_broker import ProductionBrokerManager

        probe = ProductionBrokerManager.create_broker(config, broker_type)
        if probe.is_ok():
            pytest.skip(
                f"{broker_type.value} driver is available here; "
                "the swallowed-error path is unreachable"
            )
        return probe.unwrap_err()

    @pytest.mark.parametrize(
        "url, broker_type_name",
        [("nats://prod-host:4222", "NATS"), ("s2://my-basin", "S2")],
    )
    def test_url_without_driver_raises_broker_unavailable(self, url, broker_type_name):
        from maple.broker.production_broker import BrokerType

        broker_type = getattr(BrokerType, broker_type_name)
        config = Config(agent_id="prod", broker_url=url)
        expected = self._require_unavailable(config, broker_type)

        with pytest.raises(BrokerUnavailableError) as excinfo:
            Agent(config)

        assert excinfo.value.broker_url == url
        assert excinfo.value.error["errorType"] == expected["errorType"]

    def test_broker_unavailable_error_carries_typed_cause(self):
        from maple.broker.production_broker import BrokerType

        config = Config(agent_id="prod", broker_url="nats://host:4222")
        expected = self._require_unavailable(config, BrokerType.NATS)

        with pytest.raises(BrokerUnavailableError) as excinfo:
            Agent(config)

        # The typed error survives; it is not flattened into a bare string.
        assert isinstance(excinfo.value.error, dict)
        assert excinfo.value.error["message"] == expected["message"]
        assert "nats://host:4222" in str(excinfo.value)

    def test_memory_url_still_uses_the_in_memory_broker(self):
        agent = Agent(Config(agent_id="local", broker_url="memory://local"))
        assert isinstance(agent.broker, MessageBroker)

    def test_explicit_broker_argument_bypasses_url_detection(self):
        """An injected broker wins - the scheme is not consulted."""
        injected = MessageBroker(Config(agent_id="x", broker_url="memory://local"))
        agent = Agent(
            Config(agent_id="prod", broker_url="nats://host:4222"), broker=injected
        )
        assert agent.broker is injected


class TestSecurityErrorIsOneType:
    """Supporting change - one catchable SecurityError, exported."""

    def test_broker_and_error_types_security_error_are_identical(self):
        from maple.error.types import SecurityError as TypesSecurityError

        assert SecurityError is TypesSecurityError

    def test_security_error_is_exported_from_package_root(self):
        import maple

        assert maple.SecurityError is SecurityError
        assert maple.BrokerUnavailableError is BrokerUnavailableError
