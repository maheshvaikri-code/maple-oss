"""
Copyright (C) 2025 Mahesh Vaijainthymala Krishnamoorthy
(Mahesh Vaikri)

This file is part of MAPLE - Multi Agent Protocol Language Engine.

MAPLE - Multi Agent Protocol Language Engine is free software: you can
redistribute it and/or modify it under the terms of the GNU Affero General
Public License as published by the Free Software Foundation, either version 3
of the License, or (at your option) any later version.
MAPLE - Multi Agent Protocol Language Engine is distributed in the hope that
it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty
of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero
General Public License for more details. You should have received a copy of
the GNU Affero General Public License along with MAPLE - Multi Agent Protocol
Language Engine. If not, see <https://www.gnu.org/licenses/>.
"""

# maple/broker/nats_broker.py
# Creator: Mahesh Vaikri

# Production NATS Broker Implementation for MAPLE.
# Provides enterprise-grade message routing with NATS backend.

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import threading
import uuid
from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Coroutine,
    Dict,
    List,
    Optional,
    TypeVar,
)

from ..core.message import Message
from ..core.result import Result
from ..core.types import MessageID
from ..error.types import SecurityError
from .contract import BrokerCapabilities

try:
    from nats.aio.client import Client as _NATS  # noqa: F401
    from nats.aio.errors import ErrTimeout as _ErrTimeout  # noqa: F401

    NATS_AVAILABLE = True
except ImportError:
    NATS_AVAILABLE = False

NATS: Any = globals().get("_NATS")
ErrTimeout: Any = globals().get("_ErrTimeout", TimeoutError)

logger = logging.getLogger(__name__)

#: Result type of a coroutine handed to NATSBrokerSync._await.
_R = TypeVar("_R")

if TYPE_CHECKING:
    # Annotation-only; a runtime import here would re-close the
    # agent <-> broker cycle broken in ADR-158.
    from ..agent.config import Config


@dataclass
class NATSConfig:
    """Configuration for NATS broker."""

    servers: Optional[List[str]] = None
    cluster_name: str = "maple-cluster"
    client_id: Optional[str] = None
    max_reconnect_attempts: int = 10
    reconnect_time_wait: float = 2.0
    max_payload: int = 1024 * 1024  # 1MB

    def __post_init__(self) -> None:
        if self.servers is None:
            self.servers = ["nats://localhost:4222"]
        if self.client_id is None:
            self.client_id = f"maple-{uuid.uuid4().hex[:8]}"


class NATSBroker:
    """
    Production NATS-based message broker for MAPLE.

    Features:
    - Distributed message routing
    - Cluster support
    - Automatic failover and reconnection
    - High throughput (100K+ messages/sec)
    - Persistent message delivery
    """

    # This transport publishes straight to NATS and enforces none of the
    # SecurityConfig controls - no link policy, no separation of duties, no
    # authorization. Declared so Agent construction refuses it rather than
    # silently dropping a guarantee the caller configured (ADR-161).
    ENFORCES_SECURITY_POLICY: bool = False

    #: Honest declaration (ADR-161). This transport crosses processes and
    #: hosts, and provides none of the delivery or security guarantees the
    #: in-memory broker does. It does not yet satisfy the Broker contract.
    CAPABILITIES = BrokerCapabilities(
        enforces_security_policy=False,
        applies_backpressure=False,
        reports_undeliverable=False,
        supports_routability_check=False,
        durable=False,
        cross_process=True,
    )

    def __init__(
        self, config: Config, nats_config: Optional[NATSConfig] = None
    ) -> None:
        if not NATS_AVAILABLE:
            raise ImportError(
                "NATS is not installed. Install with: pip install nats-py"
            )

        self.config = config
        # broker_url has to reach the client. Without this, NATSConfig.servers
        # defaulted to localhost:4222 and the URL the operator configured was
        # discarded - so Agent(Config(broker_url="nats://prod:4222")) quietly
        # connected somewhere else and looked healthy. That is the defect
        # class ADR-157 exists to close, in a transport nobody could execute.
        #
        # An explicitly supplied NATSConfig still wins: a caller who built one
        # knows more than the URL does.
        if nats_config is not None:
            self.nats_config = nats_config
        else:
            url = str(getattr(config, "broker_url", "") or "").strip()
            servers = [url] if url.lower().startswith("nats://") else None
            self.nats_config = NATSConfig(servers=servers)
        self.nc: Optional[Any] = None
        self.subscriptions: Dict[str, Any] = {}
        self._undeliverable_handler: Optional[Callable[[str, Message], None]] = None
        self._separation_policy: Any = None
        self._published = 0
        self._refused = 0
        self.running = False

        # Message handlers
        self.agent_handlers: Dict[str, List[Callable[[Message], None]]] = {}
        self.topic_handlers: Dict[str, Dict[str, Callable[[str, Message], None]]] = {}

        logger.info(f"NATS Broker initialized with servers: {self.nats_config.servers}")

    async def connect(self) -> Result[None, Dict[str, Any]]:
        """Connect to NATS cluster."""
        try:
            self.nc = NATS()

            # max_payload is NOT passed here. In NATS it is advertised by the
            # *server* and read from the client; nats-py's connect() has no
            # such parameter, so passing it raised TypeError and every single
            # connection attempt failed. This transport could never connect,
            # and nothing caught it because its code was inspected rather than
            # executed until CI gained a live server.
            await self.nc.connect(
                servers=self.nats_config.servers,
                name=self.nats_config.client_id,
                max_reconnect_attempts=self.nats_config.max_reconnect_attempts,
                reconnect_time_wait=self.nats_config.reconnect_time_wait,
                error_cb=self._error_callback,
                disconnected_cb=self._disconnected_callback,
                reconnected_cb=self._reconnected_callback,
            )
            self._warn_if_server_payload_is_smaller()

            self.running = True
            logger.info(f"Connected to NATS cluster: {self.nc.connected_url}")
            return Result.ok(None)

        except Exception as e:
            error = {
                "errorType": "NATS_CONNECTION_ERROR",
                "message": f"Failed to connect to NATS: {str(e)}",
                "details": {"servers": self.nats_config.servers},
            }
            logger.error(f"NATS connection error: {error}")
            return Result.err(error)

    async def disconnect(self) -> None:
        """Disconnect from NATS cluster."""
        self.running = False

        if self.nc and self.nc.is_connected:
            # Close all subscriptions
            for subscription in self.subscriptions.values():
                await subscription.unsubscribe()

            await self.nc.close()
            logger.info("Disconnected from NATS cluster")

    def unsubscribe_local(self, agent_id: str) -> None:
        """Forget an agent's subscription record.

        The NATS-side unsubscribe is awaited by ``NATSBrokerSync.unsubscribe``;
        this is the bookkeeping half, kept separate so it is callable without
        an event loop.
        """
        self.subscriptions.pop(agent_id, None)

    def is_routable(self, agent_id: str) -> bool:
        """Whether this broker knows of a subscription for ``agent_id``.

        **Only local subscriptions are visible.** A NATS publish is
        fire-and-forget: the client cannot see who is subscribed elsewhere on
        the cluster, so a remote agent reads as not routable even when it is.

        That is why ``CAPABILITIES.supports_routability_check`` is ``False``,
        and why callers must consult the flag rather than the method
        (ADR-161). Returning a confident answer this transport cannot know
        would be worse than declaring the limit.
        """
        if not agent_id or not str(agent_id).strip():
            return False
        return str(agent_id) in self.subscriptions

    def set_undeliverable_handler(
        self, handler: Optional[Callable[[str, Message], None]]
    ) -> None:
        """Record a dead-letter hook this transport cannot yet call.

        NATS publishes into a subject; nobody reports back that no subscriber
        existed. The hook is stored so the member exists and the contract is
        satisfied structurally, and a warning is logged because a hook that
        silently never fires is precisely the class of defect ADR-159 and
        ADR-162 exist to close.
        """
        self._undeliverable_handler = handler
        if handler is not None:
            logger.warning(
                "NATS transport accepted an undeliverable handler but reports "
                "no undeliverable messages (CAPABILITIES."
                "reports_undeliverable is False); it will not be called."
            )

    def set_separation_policy(self, policy: Any) -> None:
        """Refuse a separation-of-duties policy this transport cannot enforce.

        Accepting it would be the exact pattern ADR-157 forbids: a security
        control taken and then ignored, leaving a caller believing a boundary
        exists. A control that cannot run must refuse.
        """
        if policy is None:
            self._separation_policy = None
            return
        raise SecurityError(
            "The NATS transport cannot enforce a separation-of-duties policy. "
            "Refusing it rather than accepting a control that would be "
            "silently ignored."
        )

    def get_statistics(self) -> Dict[str, Any]:
        """Local counters. ``delivered`` counts what this client handed to
        NATS, not what any subscriber received - NATS does not tell us."""
        return {
            "delivered": self._published,
            "undeliverable": 0,
            "refused": self._refused,
            "subscribedAgents": len(self.subscriptions),
            "connected": bool(self.nc and getattr(self.nc, "is_connected", False)),
        }

    def _warn_if_server_payload_is_smaller(self) -> None:
        """Compare the configured payload ceiling against the server's.

        ``NATSConfig.max_payload`` is a statement of intent MAPLE cannot
        impose - the server decides. Rather than let the value sit unused,
        say so when the server will refuse messages the configuration says
        are fine.
        """
        server_limit = getattr(self.nc, "max_payload", None)
        configured = getattr(self.nats_config, "max_payload", None)
        if not isinstance(server_limit, int) or not isinstance(configured, int):
            return
        if configured > server_limit:
            logger.warning(
                "Configured max_payload (%d bytes) exceeds what this NATS "
                "server accepts (%d bytes); larger messages will be rejected "
                "by the server, not by MAPLE.",
                configured,
                server_limit,
            )

    async def send(self, message: Message) -> Result[str, Dict[str, Any]]:
        """Send a message to a specific agent via NATS."""
        if not self.nc or not self.nc.is_connected:
            return Result.err(
                {
                    "errorType": "NATS_NOT_CONNECTED",
                    "message": "NATS client is not connected",
                }
            )

        try:
            # Ensure message has ID
            if not message.message_id:
                message.message_id = MessageID(str(uuid.uuid4()))

            # Create NATS subject for direct agent communication
            subject = f"maple.agent.{message.receiver}"

            # Serialize message
            payload = json.dumps(message.to_dict()).encode("utf-8")

            # Send with optional reply subject for responses
            if message.message_type.endswith("_REQUEST"):
                reply_subject = f"maple.reply.{message.message_id}"
                await self.nc.publish(subject, payload, reply=reply_subject)
            else:
                await self.nc.publish(subject, payload)

            self._published += 1
            logger.debug(f"Message {message.message_id} sent to {subject}")
            return Result.ok(str(message.message_id))

        except Exception as e:
            error = {
                "errorType": "NATS_SEND_ERROR",
                "message": f"Failed to send message: {str(e)}",
                "details": {
                    "messageId": message.message_id,
                    "receiver": message.receiver,
                },
            }
            logger.error(f"NATS send error: {error}")
            return Result.err(error)

    async def publish(
        self, topic: str, message: Message
    ) -> Result[str, Dict[str, Any]]:
        """Publish a message to a topic via NATS."""
        if not self.nc or not self.nc.is_connected:
            return Result.err(
                {
                    "errorType": "NATS_NOT_CONNECTED",
                    "message": "NATS client is not connected",
                }
            )

        try:
            # Ensure message has ID
            if not message.message_id:
                message.message_id = MessageID(str(uuid.uuid4()))

            # Create NATS subject for topic
            subject = f"maple.topic.{topic}"

            # Add topic to message metadata
            message.metadata["topic"] = topic

            # Serialize and publish
            payload = json.dumps(message.to_dict()).encode("utf-8")
            await self.nc.publish(subject, payload)

            logger.debug(f"Message {message.message_id} published to topic {topic}")
            return Result.ok(str(message.message_id))

        except Exception as e:
            error = {
                "errorType": "NATS_PUBLISH_ERROR",
                "message": f"Failed to publish message: {str(e)}",
                "details": {"messageId": message.message_id, "topic": topic},
            }
            logger.error(f"NATS publish error: {error}")
            return Result.err(error)

    async def subscribe(
        self, agent_id: str, handler: Callable[[Message], None]
    ) -> Result[None, Dict[str, Any]]:
        """Subscribe an agent to receive messages via NATS."""
        if not self.nc or not self.nc.is_connected:
            return Result.err(
                {
                    "errorType": "NATS_NOT_CONNECTED",
                    "message": "NATS client is not connected",
                }
            )

        try:
            subject = f"maple.agent.{agent_id}"

            async def message_handler(msg: Any) -> None:
                try:
                    # Deserialize message
                    data = json.loads(msg.data.decode("utf-8"))
                    message = Message.from_dict(data)

                    # Call the handler
                    handler(message)

                except Exception as e:
                    logger.error(f"Error processing message: {str(e)}")

            # Create subscription
            sub = await self.nc.subscribe(subject, cb=message_handler)
            self.subscriptions[agent_id] = sub

            # Track handler
            if agent_id not in self.agent_handlers:
                self.agent_handlers[agent_id] = []
            self.agent_handlers[agent_id].append(handler)

            logger.info(f"Agent {agent_id} subscribed to subject {subject}")
            return Result.ok(None)

        except Exception as e:
            error = {
                "errorType": "NATS_SUBSCRIBE_ERROR",
                "message": f"Failed to subscribe: {str(e)}",
                "details": {"agentId": agent_id},
            }
            logger.error(f"NATS subscribe error: {error}")
            return Result.err(error)

    async def subscribe_topic(
        self, topic: str, handler: Callable[[str, Message], None], agent_id: str
    ) -> Result[None, Dict[str, Any]]:
        """Subscribe to a topic via NATS."""
        if not self.nc or not self.nc.is_connected:
            return Result.err(
                {
                    "errorType": "NATS_NOT_CONNECTED",
                    "message": "NATS client is not connected",
                }
            )

        try:
            subject = f"maple.topic.{topic}"
            subscription_key = f"{agent_id}:{topic}"

            async def topic_handler(msg: Any) -> None:
                try:
                    # Deserialize message
                    data = json.loads(msg.data.decode("utf-8"))
                    message = Message.from_dict(data)

                    # Call the handler
                    handler(topic, message)

                except Exception as e:
                    logger.error(f"Error processing topic message: {str(e)}")

            # Create subscription
            sub = await self.nc.subscribe(subject, cb=topic_handler)
            self.subscriptions[subscription_key] = sub

            # Track handler
            if topic not in self.topic_handlers:
                self.topic_handlers[topic] = {}
            self.topic_handlers[topic][agent_id] = handler

            logger.info(f"Agent {agent_id} subscribed to topic {topic}")
            return Result.ok(None)

        except Exception as e:
            error = {
                "errorType": "NATS_TOPIC_SUBSCRIBE_ERROR",
                "message": f"Failed to subscribe to topic: {str(e)}",
                "details": {"agentId": agent_id, "topic": topic},
            }
            logger.error(f"NATS topic subscribe error: {error}")
            return Result.err(error)

    async def request(
        self, message: Message, timeout: float = 30.0
    ) -> Result[Message, Dict[str, Any]]:
        """Send a request and wait for a response via NATS."""
        if not self.nc or not self.nc.is_connected:
            return Result.err(
                {
                    "errorType": "NATS_NOT_CONNECTED",
                    "message": "NATS client is not connected",
                }
            )

        try:
            # Ensure message has ID
            if not message.message_id:
                message.message_id = MessageID(str(uuid.uuid4()))

            subject = f"maple.agent.{message.receiver}"
            payload = json.dumps(message.to_dict()).encode("utf-8")

            # Send request and wait for response
            response = await self.nc.request(subject, payload, timeout=timeout)

            # Deserialize response
            response_data = json.loads(response.data.decode("utf-8"))
            response_message = Message.from_dict(response_data)

            logger.debug(f"Received response for message {message.message_id}")
            return Result.ok(response_message)

        except ErrTimeout:
            error = {
                "errorType": "NATS_REQUEST_TIMEOUT",
                "message": f"Request timed out after {timeout}s",
                "details": {
                    "messageId": message.message_id,
                    "receiver": message.receiver,
                    "timeout": timeout,
                },
            }
            return Result.err(error)
        except Exception as e:
            error = {
                "errorType": "NATS_REQUEST_ERROR",
                "message": f"Request failed: {str(e)}",
                "details": {
                    "messageId": message.message_id,
                    "receiver": message.receiver,
                },
            }
            logger.error(f"NATS request error: {error}")
            return Result.err(error)

    async def get_cluster_info(self) -> Dict[str, Any]:
        """Get information about the NATS cluster."""
        if not self.nc or not self.nc.is_connected:
            return {"connected": False}

        return {
            "connected": True,
            "servers": self.nats_config.servers,
            "connected_url": (
                self.nc.connected_url.netloc if self.nc.connected_url else None
            ),
            "client_id": self.nats_config.client_id,
            "cluster_name": self.nats_config.cluster_name,
            "max_payload": self.nats_config.max_payload,
            "subscriptions": len(self.subscriptions),
        }

    # Callback methods for NATS connection events
    async def _error_callback(self, error: Any) -> None:
        """Handle NATS errors."""
        logger.error(f"NATS error: {error}")

    async def _disconnected_callback(self) -> None:
        """Handle NATS disconnection."""
        logger.warning("NATS disconnected - attempting to reconnect...")

    async def _reconnected_callback(self) -> None:
        """Handle NATS reconnection."""
        logger.info("NATS reconnected successfully")


# Synchronous wrapper for compatibility with existing code
class NATSBrokerSync:
    """Synchronous wrapper around NATSBroker for easier integration."""

    # This transport publishes straight to NATS and enforces none of the
    # SecurityConfig controls - no link policy, no separation of duties, no
    # authorization. Declared so Agent construction refuses it rather than
    # silently dropping a guarantee the caller configured (ADR-161).
    ENFORCES_SECURITY_POLICY: bool = False

    #: Honest declaration (ADR-161). This transport crosses processes and
    #: hosts, and provides none of the delivery or security guarantees the
    #: in-memory broker does. It does not yet satisfy the Broker contract.
    CAPABILITIES = BrokerCapabilities(
        enforces_security_policy=False,
        applies_backpressure=False,
        reports_undeliverable=False,
        supports_routability_check=False,
        durable=False,
        cross_process=True,
    )

    def __init__(self, config: Config, nats_config: Optional[NATSConfig] = None):
        self.broker = NATSBroker(config, nats_config)
        self.loop: asyncio.AbstractEventLoop
        self._setup_event_loop()

    #: How long a synchronous call waits for its coroutine.
    CALL_TIMEOUT_SECONDS = 30.0

    def _setup_event_loop(self) -> None:
        """Run a private event loop in a background thread.

        The loop has to keep running between calls. ``run_until_complete``
        drives it only for the duration of one call, so a subscription
        registered by ``subscribe()`` had nothing dispatching its callbacks
        afterwards and **no message was ever delivered** - measured against a
        live server: the publish succeeded and the subscriber never heard it.

        Handlers therefore run on this thread, not the caller's.
        """
        self.loop = asyncio.new_event_loop()
        self._loop_ready = threading.Event()
        self._loop_thread = threading.Thread(
            target=self._run_loop, name="maple-nats-loop", daemon=True
        )
        self._loop_thread.start()
        if not self._loop_ready.wait(timeout=10):
            raise RuntimeError("NATS event loop thread did not start")

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.call_soon(self._loop_ready.set)
        self.loop.run_forever()

    def _await(
        self, coro: Coroutine[Any, Any, _R], timeout: Optional[float] = None
    ) -> _R:
        """Run a coroutine on the loop thread and wait for its result.

        Generic so the Result types of the wrapped calls survive.
        """
        future: "concurrent.futures.Future[_R]" = asyncio.run_coroutine_threadsafe(
            coro, self.loop
        )
        return future.result(timeout=timeout or self.CALL_TIMEOUT_SECONDS)

    def _stop_loop(self) -> None:
        loop = getattr(self, "loop", None)
        thread = getattr(self, "_loop_thread", None)
        if loop is None or not loop.is_running():
            return
        loop.call_soon_threadsafe(loop.stop)
        if thread is not None:
            thread.join(timeout=5.0)

    def connect(self) -> Result[None, Dict[str, Any]]:
        """Connect to NATS cluster synchronously."""
        return self._await(self.broker.connect())

    def disconnect(self) -> None:
        """Disconnect from NATS cluster synchronously."""
        self._await(self.broker.disconnect())
        self._stop_loop()

    def send(self, message: Message) -> Result[str, Dict[str, Any]]:
        """Send a message synchronously."""
        return self._await(self.broker.send(message))

    def publish(self, topic: str, message: Message) -> Result[str, Dict[str, Any]]:
        """Publish a message synchronously."""
        return self._await(self.broker.publish(topic, message))

    def subscribe(
        self, agent_id: str, handler: Callable[[Message], None]
    ) -> Result[None, Dict[str, Any]]:
        """Subscribe synchronously."""
        return self._await(self.broker.subscribe(agent_id, handler))

    def unsubscribe(self, agent_id: str) -> None:
        """Stop receiving for an agent. Idempotent."""
        subscription = self.broker.subscriptions.get(agent_id)
        self.broker.unsubscribe_local(agent_id)
        if subscription is not None and hasattr(subscription, "unsubscribe"):
            try:
                self._await(subscription.unsubscribe())
            except Exception:  # noqa: BLE001 - teardown is best effort
                logger.debug("NATS unsubscribe for %s did not complete", agent_id)

    def is_routable(self, agent_id: str) -> bool:
        """Local subscriptions only - see ``NATSBroker.is_routable``.

        ``CAPABILITIES.supports_routability_check`` is ``False``; callers must
        consult the flag rather than trusting this answer.
        """
        return self.broker.is_routable(agent_id)

    def set_undeliverable_handler(
        self, handler: Optional[Callable[[str, Message], None]]
    ) -> None:
        self.broker.set_undeliverable_handler(handler)

    def set_separation_policy(self, policy: Any) -> None:
        """Refuses a policy it cannot enforce - see ``NATSBroker``."""
        self.broker.set_separation_policy(policy)

    def get_statistics(self) -> Dict[str, Any]:
        return self.broker.get_statistics()

    def request(
        self, message: Message, timeout: float = 30.0
    ) -> Result[Message, Dict[str, Any]]:
        """Send a request synchronously."""
        return self._await(self.broker.request(message, timeout), timeout=timeout + 5)

    def get_cluster_info(self) -> Dict[str, Any]:
        """Get cluster info synchronously."""
        return self._await(self.broker.get_cluster_info())
