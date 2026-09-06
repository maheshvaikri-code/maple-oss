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
import time
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
from ..error.types import BrokerOverflowError, SecurityError
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

    #: Honest declaration (ADR-161, ADR-168, ADR-170). Routability and
    #: undeliverable reporting come from presence; backpressure comes from a
    #: bounded outbound queue MAPLE owns, because core NATS publish has
    #: nothing to be full. Security enforcement remains absent and is refused
    #: rather than accepted.
    CAPABILITIES = BrokerCapabilities(
        enforces_security_policy=False,
        applies_backpressure=True,
        reports_undeliverable=True,
        supports_routability_check=True,
        durable=False,
        cross_process=True,
    )

    #: Subject prefix agents announce themselves on.
    PRESENCE_PREFIX = "maple.presence"
    #: How often a subscribed agent re-announces.
    PRESENCE_HEARTBEAT_SECONDS = 1.0
    #: How long a beacon stays valid. Several heartbeats wide on purpose: one
    #: lost beacon must not evict a live agent, because a false eviction costs
    #: a message counted undeliverable and *not sent* (ADR-168).
    PRESENCE_TTL_SECONDS = 6.0

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
        self._undeliverable = 0
        #: agent_id -> monotonic reading of the last beacon heard (ADR-168).
        #: perf_counter, not the wall clock: this is an elapsed-time question
        #: and an NTP step must not evict a live agent (ADR-163).
        self._presence: Dict[str, float] = {}
        self._presence_sub: Any = None
        self._heartbeat_task: Any = None
        #: Bounded outbound queue (ADR-170). Core NATS publish has nothing to
        #: be full, so the bound is MAPLE's own - it says the client is
        #: producing faster than it can hand off, not anything about the
        #: server's capacity.
        self._outbound: List[Message] = []
        performance = getattr(config, "performance", None)
        self.max_queue_size = int(
            getattr(performance, "max_queue_size", 10000) or 10000
        )
        self.max_message_bytes = int(
            getattr(performance, "max_message_bytes", 1_048_576) or 1_048_576
        )
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
            await self._start_presence()
            # Sends made before connect() were queued, not lost.
            await self._drain_outbound()
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

        await self._stop_presence()
        if self.nc and self.nc.is_connected:
            # Close all subscriptions
            for subscription in self.subscriptions.values():
                await subscription.unsubscribe()

            await self.nc.close()
            logger.info("Disconnected from NATS cluster")

    # ------------------------------------------------------------ presence

    async def _start_presence(self) -> None:
        """Watch every agent's beacons and start announcing our own.

        Presence rides the transport it describes: if NATS is reachable, so is
        presence. No second piece of infrastructure to fail separately
        (ADR-168).
        """
        if self.nc is None or self._presence_sub is not None:
            return

        async def _beacon(msg: Any) -> None:
            agent_id = msg.subject.rsplit(".", 1)[-1]
            if agent_id:
                self._presence[agent_id] = time.perf_counter()

        self._presence_sub = await self.nc.subscribe(
            f"{self.PRESENCE_PREFIX}.>", cb=_beacon
        )
        self._heartbeat_task = asyncio.ensure_future(self._heartbeat_loop())

    async def _heartbeat_loop(self) -> None:
        try:
            while self.running:
                await self._announce_all()
                await asyncio.sleep(self.PRESENCE_HEARTBEAT_SECONDS)
        except asyncio.CancelledError:  # pragma: no cover - shutdown path
            raise
        except Exception:  # noqa: BLE001 - presence must not kill the client
            logger.exception("NATS presence heartbeat stopped")

    async def _announce_all(self) -> None:
        for agent_id in list(self.subscriptions):
            await self._announce(agent_id)

    async def _announce(self, agent_id: str) -> None:
        """Publish one beacon. Called on subscribe so an agent is visible as
        soon as it exists, rather than at the next heartbeat."""
        if self.nc is None or not self.nc.is_connected:
            return
        try:
            await self.nc.publish(f"{self.PRESENCE_PREFIX}.{agent_id}", b"1")
            # Our own presence is known without a round trip.
            self._presence[agent_id] = time.perf_counter()
        except Exception:  # noqa: BLE001 - a missed beacon is not fatal
            logger.debug("Presence beacon for %s failed", agent_id)

    async def _stop_presence(self) -> None:
        task = self._heartbeat_task
        self._heartbeat_task = None
        if task is not None:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        sub = self._presence_sub
        self._presence_sub = None
        if sub is not None:
            try:
                await sub.unsubscribe()
            except Exception:  # noqa: BLE001 - teardown is best effort
                pass
        self._presence.clear()

    def _is_present(self, agent_id: str) -> bool:
        """Whether any broker on the cluster is serving this agent.

        An agent we serve ourselves is known directly - no cache lookup that
        cannot fail, and no liveness window for the single-process case.
        """
        if agent_id in self.subscriptions:
            return True
        last_seen = self._presence.get(agent_id)
        if last_seen is None:
            return False
        return (time.perf_counter() - last_seen) <= self.PRESENCE_TTL_SECONDS

    def _report_undeliverable(self, receiver: str, message: Message) -> None:
        self._undeliverable += 1
        logger.warning(
            "No agent is serving %r; message dead-lettered rather than " "published.",
            receiver,
        )
        hook = self._undeliverable_handler
        if hook is not None:
            try:
                hook(receiver, message)
            except Exception:  # noqa: BLE001 - a bad hook is not fatal
                logger.exception("Undeliverable handler raised")

    def unsubscribe_local(self, agent_id: str) -> None:
        """Forget an agent's subscription record.

        The NATS-side unsubscribe is awaited by ``NATSBrokerSync.unsubscribe``;
        this is the bookkeeping half, kept separate so it is callable without
        an event loop.
        """
        self.subscriptions.pop(agent_id, None)

    def is_routable(self, agent_id: str) -> bool:
        """Whether any broker on the cluster is serving ``agent_id``.

        Answered from presence beacons (ADR-168), so this now sees remote
        subscribers rather than only our own - which is why
        ``CAPABILITIES.supports_routability_check`` is ``True`` and
        ``Agent.send(require_routable=True)`` is meaningful over NATS.

        Bounded by a liveness window: an agent that has just appeared, or
        whose beacons were lost, reads as absent until its next beacon.
        """
        if not agent_id or not str(agent_id).strip():
            return False
        return self._is_present(str(agent_id))

    def set_undeliverable_handler(
        self, handler: Optional[Callable[[str, Message], None]]
    ) -> None:
        """Register a dead-letter hook.

        It fires for real now: presence tells us when nobody serves a receiver,
        and such a message is dead-lettered rather than published (ADR-168).
        """
        self._undeliverable_handler = handler

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
            "undeliverable": self._undeliverable,
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

    async def send(self, message: Message) -> str:
        """Admit a message for delivery, or refuse it.

        Returns the message id and **raises** on refusal, matching the
        in-memory broker and what ``Agent.send()`` already expects. It used to
        return ``Result``, which produced ``Result.ok(Result.ok(id))`` through
        Agent and - worse - wrapped a failed send as a success (ADR-170).

        Admission order is fixed: **size, then policy, then presence, then
        capacity.** Too-large is refused whatever the queue depth, and a
        message nobody can receive is dead-lettered rather than occupying a
        slot.
        """
        self._enforce_message_size(message)

        if not message.message_id:
            message.message_id = MessageID(str(uuid.uuid4()))

        if self._separation_policy is not None:
            decision = self._separation_policy.authorize_send(message)
            if decision.is_err():
                raise SecurityError(
                    f"Separation-of-duties denied: {decision.unwrap_err()['message']}"
                )

        receiver = str(message.receiver or "")
        connected = bool(self.nc and getattr(self.nc, "is_connected", False))

        # Presence is only meaningful once connected; before that nobody has
        # had a chance to announce, so queue rather than dead-letter.
        if connected and not self._is_present(receiver):
            self._report_undeliverable(receiver, message)
            return str(message.message_id)

        if len(self._outbound) >= self.max_queue_size:
            self._refused += 1
            raise BrokerOverflowError(
                {
                    "errorType": "QUEUE_FULL",
                    "message": (
                        "Outbound queue is at capacity; refusing the message "
                        "rather than buffering without a bound."
                    ),
                    "details": {
                        "receiver": receiver,
                        "maxQueueSize": self.max_queue_size,
                        "pending": len(self._outbound),
                    },
                }
            )

        self._outbound.append(message)
        if connected:
            await self._drain_outbound()
        return str(message.message_id)

    def _enforce_message_size(self, message: Message) -> None:
        """Refuse an oversized payload at the edge, as ADR-159 does for the
        in-memory broker: a bounded count is no protection if one message can
        be arbitrarily large."""
        try:
            size = len(
                json.dumps(message.payload, default=str, separators=(",", ":")).encode(
                    "utf-8"
                )
            )
        except (TypeError, ValueError):
            return
        if size > self.max_message_bytes:
            self._refused += 1
            raise BrokerOverflowError(
                {
                    "errorType": "MESSAGE_TOO_LARGE",
                    "message": (
                        f"Payload of {size} bytes exceeds the configured limit "
                        f"of {self.max_message_bytes} bytes."
                    ),
                    "details": {
                        "payloadBytes": size,
                        "maxMessageBytes": self.max_message_bytes,
                    },
                }
            )

    async def _drain_outbound(self) -> None:
        """Hand queued messages to NATS, oldest first.

        A message that cannot be published stays at the head rather than being
        dropped, so a transport hiccup costs latency instead of data.
        """
        while self._outbound:
            if not (self.nc and getattr(self.nc, "is_connected", False)):
                return
            message = self._outbound[0]
            try:
                await self._publish_one(message)
            except Exception:  # noqa: BLE001 - keep it queued and retry later
                logger.debug("Deferring %s; publish failed", message.message_id)
                return
            self._outbound.pop(0)
            self._published += 1

    async def _publish_one(self, message: Message) -> None:
        client = self.nc
        if client is None:  # pragma: no cover - guarded by the caller
            raise RuntimeError("not connected")
        subject = f"maple.agent.{message.receiver}"
        payload = json.dumps(message.to_dict()).encode("utf-8")
        if str(message.message_type).endswith("_REQUEST"):
            await client.publish(
                subject, payload, reply=f"maple.reply.{message.message_id}"
            )
        else:
            await client.publish(subject, payload)

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
            # Beacon immediately: an agent should be visible as soon as it
            # exists, not at the next heartbeat (ADR-168).
            await self._announce(agent_id)

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

    #: Mirrors NATSBroker.CAPABILITIES, which is the declaration that matters
    #: - this class wraps it. Kept in sync deliberately: a wrapper that
    #: advertises different capabilities from the thing it wraps is a lie in
    #: the direction callers cannot check (ADR-161, ADR-168).
    CAPABILITIES = NATSBroker.CAPABILITIES

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

    def send(self, message: Message) -> str:
        """Admit a message, returning its id or raising on refusal (ADR-170)."""
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
