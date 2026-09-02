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
"""The contract every MAPLE transport must satisfy (ADR-161).

Until this module existed the two shipped brokers shared no interface — no
ABC, no Protocol, no abstract method — and their surfaces had drifted six
methods apart. Two of those were security and observability controls, so
switching to the "production" transport silently reduced the guarantees a
caller had configured.

This module states what a broker *is*. The conformance suite in
``tests/broker/test_broker_conformance.py`` is what the statement is worth:
any implementation must pass it, including the in-memory broker that defines
the reference behavior.

**Delivery semantics are part of the contract, not an implementation detail.**
Each method below states what a caller may rely on. Where a transport cannot
provide a guarantee, it must refuse rather than silently omit it — see
``BrokerCapabilities``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Protocol, runtime_checkable

from ..core.message import Message

__all__ = ["BrokerCapabilities", "Broker", "describe_conformance"]


@dataclass(frozen=True)
class BrokerCapabilities:
    """What a transport can actually guarantee.

    A capability that is absent must cause construction to fail when the
    caller has configured something that depends on it. Declaring a capability
    falsely is worse than not implementing the transport at all: the caller
    believes a control is active and it is not.
    """

    #: Enforces the SecurityConfig controls: link policy, separation of
    #: duties, authorization. The NATS transport does not.
    enforces_security_policy: bool = False

    #: ``send`` refuses with QUEUE_FULL rather than buffering without bound.
    applies_backpressure: bool = False

    #: Messages reaching no handler are counted and offered to a dead-letter
    #: hook rather than discarded silently.
    reports_undeliverable: bool = False

    #: ``is_routable`` reflects live subscriptions rather than guessing.
    supports_routability_check: bool = False

    #: Messages survive a process restart.
    durable: bool = False

    #: Reaches agents in other processes.
    cross_process: bool = False


@runtime_checkable
class Broker(Protocol):
    """The operations MAPLE agents require of a transport.

    Implementations declare ``CAPABILITIES``; ``Agent`` construction consults
    it before accepting a transport for a given configuration.
    """

    CAPABILITIES: BrokerCapabilities

    def connect(self) -> Any:
        """Begin delivering. Idempotent: connecting twice is not an error."""

    def disconnect(self) -> Any:
        """Stop delivering. Idempotent, and safe without a prior connect."""

    def send(self, message: Message) -> Any:
        """Enqueue a message for one receiver.

        Returns the message id on acceptance. **Acceptance is not delivery** —
        a message addressed to an agent that never subscribes is accepted and
        then reported undeliverable.

        Raises ``BrokerOverflowError`` when the message is refused: the queue
        is at capacity (``QUEUE_FULL``) or the payload exceeds the configured
        limit (``MESSAGE_TOO_LARGE``). Refusal is backpressure, and a
        conforming transport must refuse rather than buffer without bound.

        Raises ``SecurityError`` when a configured control denies the send.
        """

    def publish(self, topic: str, message: Message) -> Any:
        """Fan a message out to a topic's subscribers."""

    def subscribe(self, agent_id: str, handler: Callable[[Message], None]) -> Any:
        """Register a handler for one agent. Multiple handlers may register."""

    def unsubscribe(self, agent_id: str) -> Any:
        """Remove every handler for an agent. Idempotent."""

    def is_routable(self, agent_id: str) -> bool:
        """Whether the receiver has a live subscription *at check time*.

        Not a delivery acknowledgement. A receiver can unsubscribe between the
        check and the send.
        """

    def get_statistics(self) -> Dict[str, Any]:
        """Delivery accounting for operators.

        Must include ``delivered``, ``undeliverable`` and ``refused``.
        """

    def set_undeliverable_handler(
        self, handler: Optional[Callable[[str, Message], None]]
    ) -> None:
        """Register a dead-letter callback, or clear it with ``None``."""

    def set_separation_policy(self, policy: Any) -> None:
        """Attach the separation-of-duties policy enforced on ``send``."""


def describe_conformance(broker: Any) -> Dict[str, Any]:
    """Report which contract members a transport provides.

    Diagnostic, not a gate — the conformance suite is the gate. Useful when a
    transport half-implements the contract and the failure needs naming.
    """
    required = [
        name
        for name in dir(Broker)
        if not name.startswith("_") and name != "CAPABILITIES"
    ]
    missing = [name for name in required if not hasattr(broker, name)]
    capabilities = getattr(broker, "CAPABILITIES", None)
    return {
        "broker": (
            type(broker).__name__ if not isinstance(broker, type) else broker.__name__
        ),
        "declaresCapabilities": capabilities is not None,
        "capabilities": capabilities,
        "missingMembers": missing,
        "conforms": not missing and capabilities is not None,
    }
