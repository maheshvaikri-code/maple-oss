"""A transport that cannot enforce a security control must refuse (ADR-161).

The NATS transport publishes straight to NATS and enforces none of
``SecurityConfig`` — no link policy, no separation of duties, no
authorization. Before this change, ``Agent(Config(broker_url="nats://...",
security=...))`` constructed successfully and silently dropped every one of
those guarantees: the same fail-open shape ADR-157 removed from the in-memory
broker, one level up.
"""

import pytest

from maple.agent.agent import Agent
from maple.agent.config import Config, SecurityConfig
from maple.broker.broker import MessageBroker
from maple.broker.contract import BrokerCapabilities
from maple.core.message import Message
from maple.error.types import BrokerUnavailableError


def _reset_broker_singleton():
    MessageBroker.reset_scopes()


@pytest.fixture(autouse=True)
def reset_broker():
    _reset_broker_singleton()
    yield
    _reset_broker_singleton()


class _NonEnforcingBroker:
    """Stands in for a transport that declares no enforcement."""

    ENFORCES_SECURITY_POLICY = False

    def __init__(self, config):
        self.config = config


class _EnforcingBroker:
    ENFORCES_SECURITY_POLICY = True

    def __init__(self, config):
        self.config = config


class TestCapabilityDeclaration:
    def test_in_memory_broker_declares_enforcement(self):
        assert MessageBroker.ENFORCES_SECURITY_POLICY is True

    def test_nats_brokers_declare_no_enforcement(self):
        from maple.broker.nats_broker import NATSBroker, NATSBrokerSync

        assert NATSBroker.ENFORCES_SECURITY_POLICY is False
        assert NATSBrokerSync.ENFORCES_SECURITY_POLICY is False


class TestRefusal:
    """The guard itself, exercised without needing a NATS server."""

    @pytest.mark.parametrize(
        "control",
        [
            {"separation_policy": object()},
            {"require_links": True},
            {"strict_link_policy": True},
        ],
    )
    def test_non_enforcing_transport_is_refused(self, control):
        security = SecurityConfig("jwt", {"token": "t"}, **control)
        config = Config(agent_id="a", broker_url="nats://host:4222", security=security)

        with pytest.raises(BrokerUnavailableError) as excinfo:
            Agent._require_security_enforcement(
                config, _NonEnforcingBroker(config), "nats://host:4222"
            )

        error = excinfo.value.error
        assert error["errorType"] == "BROKER_CANNOT_ENFORCE_SECURITY"
        assert error["details"]["unenforcedControls"] == list(control)

    def test_enforcing_transport_is_accepted(self):
        security = SecurityConfig("jwt", {"token": "t"}, require_links=True)
        config = Config(agent_id="a", broker_url="nats://host:4222", security=security)

        Agent._require_security_enforcement(
            config, _EnforcingBroker(config), "nats://host:4222"
        )  # must not raise

    def test_no_security_config_permits_any_transport(self):
        """Only a *configured* control can be silently dropped."""
        config = Config(agent_id="a", broker_url="nats://host:4222")

        Agent._require_security_enforcement(
            config, _NonEnforcingBroker(config), "nats://host:4222"
        )  # must not raise

    def test_security_config_without_enforcement_flags_is_permitted(self):
        """Credentials alone request nothing the transport must enforce."""
        security = SecurityConfig("jwt", {"token": "t"})
        config = Config(agent_id="a", broker_url="nats://host:4222", security=security)

        Agent._require_security_enforcement(
            config, _NonEnforcingBroker(config), "nats://host:4222"
        )  # must not raise

    def test_a_transport_declaring_nothing_is_treated_as_non_enforcing(self):
        """Absence of a declaration is not a claim of enforcement."""

        class _Silent:
            pass

        security = SecurityConfig("jwt", {"token": "t"}, require_links=True)
        # The URL is incidental here - what is under test is a broker that
        # declares nothing. It uses a real scheme because Config now refuses
        # unsupported ones (ADR-164).
        config = Config(agent_id="a", broker_url="nats://h", security=security)

        with pytest.raises(BrokerUnavailableError):
            Agent._require_security_enforcement(config, _Silent(), "nats://h")

    def test_all_requested_controls_are_named_in_the_error(self):
        security = SecurityConfig(
            "jwt", {"token": "t"}, require_links=True, strict_link_policy=True
        )
        config = Config(agent_id="a", broker_url="nats://h:4222", security=security)

        with pytest.raises(BrokerUnavailableError) as excinfo:
            Agent._require_security_enforcement(
                config, _NonEnforcingBroker(config), "nats://h:4222"
            )

        unenforced = excinfo.value.error["details"]["unenforcedControls"]
        assert set(unenforced) == {"require_links", "strict_link_policy"}


class TestInMemoryPathUnaffected:
    def test_memory_broker_with_security_still_constructs(self):
        security = SecurityConfig(
            "jwt", {"token": "t"}, require_links=True, strict_link_policy=True
        )
        agent = Agent(
            Config(agent_id="a", broker_url="memory://local", security=security)
        )
        assert isinstance(agent.broker, MessageBroker)
        assert agent.broker.security_config is security


class TestRoutabilityIsGatedOnTheCapability:
    """A transport can provide is_routable() and still be unable to answer it.

    The NATS client sees only its own subscriptions, so a remote agent reads
    as unroutable even while it is serving. Gating ``require_routable`` on
    ``hasattr`` would turn *gaining the method* into a source of false
    refusals - a regression created by an improvement (ADR-161).
    """

    class _CannotAnswer:
        CAPABILITIES = BrokerCapabilities(supports_routability_check=False)
        ENFORCES_SECURITY_POLICY = True

        def __init__(self):
            self.sent = []

        def is_routable(self, agent_id):
            return False  # it genuinely cannot tell

        def send(self, message):
            self.sent.append(message)
            return "id-1"

    class _CanAnswer(_CannotAnswer):
        CAPABILITIES = BrokerCapabilities(supports_routability_check=True)

    def _agent(self, broker):
        agent = object.__new__(Agent)
        agent.agent_id = "sender"
        agent.broker = broker
        agent.messages_sent = 0
        agent.messages_failed = 0
        return agent

    def test_a_transport_that_cannot_answer_is_not_consulted(self):
        broker = self._CannotAnswer()
        agent = self._agent(broker)

        result = Agent.send(
            agent,
            Message(message_type="X", receiver="remote", payload={}),
            require_routable=True,
        )

        assert result.is_ok(), (
            "a transport that declares it cannot check routability must not "
            "be allowed to veto the send"
        )
        assert len(broker.sent) == 1

    def test_a_transport_that_can_answer_still_refuses(self):
        broker = self._CanAnswer()
        agent = self._agent(broker)

        result = Agent.send(
            agent,
            Message(message_type="X", receiver="remote", payload={}),
            require_routable=True,
        )

        assert result.is_err()
        assert result.unwrap_err()["errorType"] == "UNROUTABLE"
        assert broker.sent == []
