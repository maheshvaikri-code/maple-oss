"""Offline tests for NATS configuration and fail-closed transport behavior."""

import asyncio

import pytest

from maple.agent.config import Config
from maple.broker.nats_broker import NATS_AVAILABLE, NATSBroker, NATSConfig
from maple.core.message import Message


def test_nats_config_supplies_bounded_defaults() -> None:
    config = NATSConfig()

    assert config.servers == ["nats://localhost:4222"]
    assert config.client_id is not None
    assert config.client_id.startswith("maple-")


@pytest.mark.skipif(not NATS_AVAILABLE, reason="nats-py is not installed")
def test_nats_send_fails_closed_without_connection() -> None:
    broker = NATSBroker(Config(agent_id="agent-a", broker_url="nats://localhost:4222"))

    result = asyncio.run(
        broker.send(
            Message(
                message_type="TEST",
                sender="agent-a",
                receiver="agent-b",
            )
        )
    )

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "NATS_NOT_CONNECTED"
