"""
Shared pytest fixtures for MAPLE test suites.
"""

import pytest
import time

from maple.core.result import Result
from maple.core.message import Message
from maple.core.types import Priority
from maple.agent.config import Config, SecurityConfig, LinkConfig
from maple.agent.agent import Agent
from maple.broker.broker import MessageBroker
from maple.state.store import StateStore, StorageBackend, ConsistencyLevel
from maple.security.link import LinkManager
from maple.security.encryption import EncryptionManager
from maple.resources.specification import ResourceRequest, ResourceRange, TimeConstraint


@pytest.fixture
def agent_config():
    """Basic agent Config with memory broker."""
    return Config(
        agent_id="test_agent",
        broker_url="memory://local"
    )


@pytest.fixture
def security_config():
    """SecurityConfig for testing."""
    return SecurityConfig(
        auth_type="token",
        credentials="test_token_secret",
        require_links=False
    )


@pytest.fixture
def secure_agent_config(security_config):
    """Agent Config with security enabled."""
    return Config(
        agent_id="secure_test_agent",
        broker_url="memory://local",
        security=security_config
    )


@pytest.fixture
def agent(agent_config):
    """A started Agent instance; stopped on teardown."""
    a = Agent(agent_config)
    a.start()
    yield a
    a.stop()


@pytest.fixture
def broker():
    """A MessageBroker instance."""
    return MessageBroker()


@pytest.fixture
def state_store():
    """StateStore with memory backend."""
    return StateStore(
        backend=StorageBackend.MEMORY,
        consistency=ConsistencyLevel.EVENTUAL
    )


@pytest.fixture
def link_manager():
    """LinkManager instance."""
    return LinkManager()


@pytest.fixture
def encryption_manager(agent_config):
    """EncryptionManager instance."""
    return EncryptionManager(agent_config)


@pytest.fixture
def sample_message():
    """Factory fixture for creating test messages."""
    def _make(
        message_type="TEST",
        receiver="other_agent",
        priority=Priority.MEDIUM,
        payload=None
    ):
        return Message(
            message_type=message_type,
            receiver=receiver,
            priority=priority,
            payload=payload or {"data": "test"}
        )
    return _make


@pytest.fixture
def resource_request():
    """Sample ResourceRequest."""
    return ResourceRequest(
        compute=ResourceRange(min=4, preferred=8, max=16),
        memory=ResourceRange(min="8GB", preferred="16GB"),
        time=TimeConstraint(timeout="120s"),
        priority="HIGH"
    )
