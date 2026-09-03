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

# mapl/broker/broker.py
# Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, cast

from ..core.message import Message
from ..core.types import MessageID

# SecurityError is defined once, in ..error.types. It used to be declared here
# as well, so `except maple.error.types.SecurityError` would not catch what the
# broker raised. Re-exported rather than redefined so both historical import
# paths name the same class (ADR-157).
from ..error.types import BrokerOverflowError, SecurityError
from .contract import BrokerCapabilities

# NOTE: a LIBRARY must not configure the root logger (that hijacks the host's logging
# and emits INFO noise). Use a module logger; the host owns logging config.
logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    # Import-time only. maple.agent.agent imports MessageBroker at module level,
    # so importing Config here at runtime would close an agent <-> broker cycle
    # that only happens to work because agent.config imports neither. Config is
    # used solely in annotations, so the type-checking guard costs nothing and
    # removes the fragility (ADR-158).
    from ..agent.config import Config

__all__ = ["MessageBroker", "SecurityError", "BrokerOverflowError"]


class MessageBroker:
    """
    Message broker for MAPL agent communication.

    This is a simple in-memory implementation for development/testing.
    Production implementations would use more robust messaging systems
    like RabbitMQ, Kafka, or NATS.
    """

    # Whether this broker actually enforces the security controls a
    # SecurityConfig can request (link policy, separation of duties,
    # authorization). Agent construction refuses a transport that cannot,
    # rather than accepting the configuration and ignoring it (ADR-161).
    ENFORCES_SECURITY_POLICY: bool = True

    #: What this transport guarantees (ADR-161). The in-memory broker is the
    #: reference implementation of the contract, and is deliberately honest
    #: about what it is not: single-process and non-durable.
    CAPABILITIES = BrokerCapabilities(
        enforces_security_policy=True,
        applies_backpressure=True,
        reports_undeliverable=True,
        supports_routability_check=True,
        durable=False,
        cross_process=False,
    )

    # One broker per scope. The scope key is the broker_url, which already
    # carries a namespace that used to be discarded: every URL returned the
    # same process-wide instance, so memory://tenant-a and memory://tenant-b
    # shared one bus and one set of handlers (ADR-160).
    _scopes: Dict[str, "MessageBroker"] = {}
    _scopes_lock = threading.Lock()

    # Declared for the type checker; set in __new__ before __init__ runs.
    _initialized: bool
    _scope_key: str

    @staticmethod
    def scope_key(broker_url: Optional[str]) -> str:
        """Normalise a broker_url into the scope it addresses.

        An absent or empty URL resolves to the default scope, so callers that
        never set one keep the single shared bus they have always had.
        """
        if not broker_url or not str(broker_url).strip():
            return "default"
        return str(broker_url).strip()

    @classmethod
    def reset_scopes(cls) -> None:
        """Drop every scope and its state. Test isolation helper.

        Replaces the manual surgery — resetting ``_instance`` and clearing five
        class-level dicts — that test modules previously had to perform,
        because that state now lives on the instance.
        """
        with cls._scopes_lock:
            cls._scopes.clear()

    def __new__(cls, config: Config) -> "MessageBroker":
        """Return the broker for this config's scope, creating it if needed."""
        key = cls.scope_key(getattr(config, "broker_url", None))
        with cls._scopes_lock:
            instance = cls._scopes.get(key)
            if instance is None:
                instance = super(MessageBroker, cls).__new__(cls)
                instance._initialized = False
                instance._scope_key = key
                cls._scopes[key] = instance
            return instance

    def __init__(self, config: Config) -> None:
        """Initialize the broker."""
        # Only initialize once. The broker is a process-wide singleton, so
        # every Agent constructs it with its own Config. Adopt a newly supplied
        # security context even on re-init, otherwise the guarantee would
        # depend on construction order and only the first agent's config would
        # ever attach one. See ADR-157.
        if self._initialized:
            self._refresh_security_context(config)
            return

        # Per-scope state. These were class attributes, which meant every
        # instance shared one set of queues and handlers regardless of the
        # URL it was constructed with (ADR-160).
        self._lock = threading.Lock()
        self._agent_queues: Dict[str, List[Message]] = {}
        self._agent_handlers: Dict[str, List[Callable[[Message], None]]] = {}
        self._temp_handlers: Dict[str, List[Callable[[Message], None]]] = {}
        self._topic_subscribers: Dict[str, List[str]] = {}
        self._topic_handlers: Dict[str, Dict[str, Callable[[str, Message], None]]] = {}
        self._registry: Optional[Any] = None

        self.config = config
        self.running = False
        self.delivery_thread: Optional[threading.Thread] = None
        #: Wakes the delivery loop when something is enqueued (ADR-166).
        #: Its own lock, not self._lock: the drain holds self._lock while
        #: copying queues, and mixing the two would tie waiting semantics to
        #: the drain's locking.
        self._wake = threading.Condition()
        #: Condition.notify() only wakes current waiters, so a message
        #: enqueued between the drain and the next wait() would be signalled
        #: to nobody. This flag carries that signal across the gap.
        self._wake_pending = False
        self.security_config = getattr(config, "security", None)
        # Separation-of-duties policy (fresh-context verifier preset), if any.
        # When set, send() enforces its sender allowlist + artifact-ref-only
        # payload policy as a runtime guarantee.
        self._separation_policy = getattr(
            self.security_config, "separation_policy", None
        )
        self.link_manager: Optional[Any] = None
        self._auth_manager: Optional[Any] = None
        self._build_security_components()

        # Admission limits (ADR-159). Process-wide, because the broker is a
        # process-wide singleton and these bound the process's memory.
        perf = getattr(config, "performance", None)
        self.max_queue_size: int = getattr(perf, "max_queue_size", 10000) or 10000
        self.max_message_bytes: int = (
            getattr(perf, "max_message_bytes", 1_048_576) or 1_048_576
        )

        # Delivery accounting. A message delivered to zero handlers used to
        # vanish silently; it is now counted, logged once per receiver, and
        # optionally handed to a dead-letter callback.
        self._delivered_count = 0
        self._undeliverable_count = 0
        self._refused_count = 0
        self._undeliverable_seen: set = set()
        self._undeliverable_handler: Optional[Callable[[str, Message], None]] = None

        # Initialize MessageQueue for priority-based delivery
        self._message_queue = None
        try:
            from .queue import MessageQueue, QueueType

            self._message_queue = MessageQueue(
                queue_type=QueueType.PRIORITY, max_size=self.max_queue_size
            )
        except Exception:
            logger.debug("MessageQueue not available, using basic queue")

        # Initialize MessageRouter for routing strategies
        self._message_router = None
        try:
            from .routing import MessageRouter

            self._message_router = MessageRouter()
        except Exception:
            logger.debug("MessageRouter not available, using direct routing")

        self._initialized = True
        logger.info("MessageBroker initialized")

    def get_registry(self) -> Any:
        """The AgentRegistry for this scope, created on first use.

        Discovery used to be a single process-wide registry held on
        ``Agent._shared_registry``, so agents on deliberately separate buses
        enumerated each other and capability matching selected across the
        boundary. The registry now belongs to the scope (ADR-160).
        """
        with self._lock:
            if self._registry is None:
                from ..discovery.registry import AgentRegistry

                self._registry = AgentRegistry()
            return self._registry

    def _build_security_components(self) -> None:
        """Construct the managers implied by the current ``security_config``.

        Idempotent — only builds what is missing — so adopting a security
        config on an already-initialized singleton never discards live state.
        """
        if not self.security_config:
            return

        if self.link_manager is None:
            try:
                from ..security.link import LinkManager

                self.link_manager = LinkManager()
            except ImportError:
                # Not a silent downgrade: send() refuses when require_links is
                # set and this is still None (see the fail-closed guard there).
                logger.warning(
                    "Link manager unavailable - link-enforced sends will be refused"
                )

        if self._auth_manager is None:
            try:
                from ..security.authorization import AuthorizationManager

                self._auth_manager = AuthorizationManager()
            except Exception:
                logger.debug("AuthorizationManager not available")

    def _refresh_security_context(self, config: Config) -> None:
        """Adopt a security context from a later config on the singleton.

        Only ever *adds* or *replaces* with a non-None config; never clears an
        existing one (a security-less config must not silently disable an
        active guarantee). Without this, the process-wide singleton would keep
        whichever config happened to construct it first and discard every
        later agent's ``SecurityConfig``. See ADR-157.
        """
        new_security = getattr(config, "security", None)
        if new_security is not None and new_security is not self.security_config:
            if self.security_config is not None:
                logger.warning(
                    "Replacing security configuration on shared broker singleton"
                )
            self.security_config = new_security
            self._build_security_components()

        self._refresh_separation_policy(config)

    def _refresh_separation_policy(self, config: Config) -> None:
        """Adopt a separation policy from a later config on the singleton.

        Only ever *adds* or *replaces* with a non-None policy; never clears an
        existing one (a policy-less config must not silently disable an active
        guarantee). Logs when replacing a different policy.
        """
        new_policy = getattr(
            getattr(config, "security", None), "separation_policy", None
        )
        if new_policy is not None and new_policy is not self._separation_policy:
            if self._separation_policy is not None:
                logger.warning(
                    "Replacing separation-of-duties policy on shared broker singleton"
                )
            self._separation_policy = new_policy

    def set_separation_policy(self, policy: Any) -> None:
        """Attach or replace the separation-of-duties policy on this broker.

        Explicit escape hatch for callers holding an already-initialized
        singleton (see ``_refresh_separation_policy`` for the automatic path).
        """
        self._separation_policy = policy

    def connect(self) -> None:
        """Connect to the broker."""
        logger.info(f"Connecting to broker at {self.config.broker_url}")
        self.running = True
        self.delivery_thread = threading.Thread(target=self._message_delivery_loop)
        self.delivery_thread.daemon = True
        self.delivery_thread.start()
        logger.info("Connected to broker")

    def disconnect(self) -> None:
        """Disconnect from the broker."""
        logger.info("Disconnecting from broker")
        self.running = False
        # Wake the loop out of its wait, or shutdown would take up to the
        # fallback interval - slower than the poll this replaced (ADR-166).
        self._signal_delivery()
        if self.delivery_thread:
            self.delivery_thread.join(timeout=5.0)
        logger.info("Disconnected from broker")

    def is_routable(self, agent_id: str) -> bool:
        """Whether a receiver is currently reachable (has a live subscription).

        A message can be enqueued for *any* name, but only a subscribed agent
        will ever process it — so ``send()`` returning Ok means "enqueued",
        not "delivered". This lets a caller distinguish the two before/at send
        time: ``is_routable`` is True once the receiver has called
        ``subscribe`` (which every started ``Agent`` does). It reflects
        reachability at check time, not a post-delivery acknowledgement.
        """
        if not agent_id:
            return False
        with self._lock:
            return bool(self._agent_handlers.get(agent_id))

    def _enforce_message_size(self, message: Message) -> None:
        """Refuse a payload larger than ``max_message_bytes``.

        This is admission control, not validation. The size is an *estimate*
        from a compact JSON encoding with ``default=str``, so values the JSON
        encoder cannot represent natively are measured by their string form
        rather than rejected outright - the goal is to stop one payload
        exhausting memory, not to duplicate what the serializer checks later.

        A payload that cannot be encoded even with that fallback is allowed
        through unmeasured; ``core/serialization.py`` still enforces its own
        1 MiB limits when the message is actually encoded.
        """
        try:
            size = len(
                json.dumps(message.payload, default=str, separators=(",", ":")).encode(
                    "utf-8"
                )
            )
        except (TypeError, ValueError):
            return

        if size > self.max_message_bytes:
            self._refused_count += 1
            raise BrokerOverflowError(
                {
                    "errorType": "MESSAGE_TOO_LARGE",
                    "message": (
                        f"Payload is {size} bytes, over the "
                        f"{self.max_message_bytes} byte limit."
                    ),
                    "details": {
                        "payloadBytes": size,
                        "maxMessageBytes": self.max_message_bytes,
                    },
                }
            )

    def set_undeliverable_handler(
        self, handler: Optional[Callable[[str, Message], None]]
    ) -> None:
        """Register a dead-letter callback for messages nobody handled.

        Called with ``(receiver, message)`` on the delivery thread whenever a
        message reaches zero handlers. Keep it fast and non-blocking: it runs
        in the delivery path. Pass ``None`` to clear.
        """
        self._undeliverable_handler = handler

    def send(self, message: Message) -> str:
        """Send a message to a specific agent with optional link validation."""
        logger.debug(
            f"Sending message of type {message.message_type} to {message.receiver}"
        )

        # Reject oversized payloads at the edge (ADR-159). A bounded queue
        # count is no protection if one message can be arbitrarily large.
        self._enforce_message_size(message)

        # Ensure the message has an ID
        if not message.message_id:
            message.message_id = MessageID(str(uuid.uuid4()))

        # Separation-of-duties enforcement (fresh-context verifier preset):
        # broker-enforced sender allowlist + artifact-ref-only payloads.
        if self._separation_policy is not None:
            sod_result = self._separation_policy.authorize_send(message)
            if sod_result.is_err():
                error = sod_result.unwrap_err()
                raise SecurityError(f"Separation-of-duties denied: {error['message']}")

        # Check if link validation is required
        if self.security_config and getattr(
            self.security_config, "require_links", False
        ):
            # Fail closed. This whole block used to be nested under
            # `if self.link_manager:`, so a broker without a link manager
            # skipped enforcement entirely and the send proceeded — a security
            # control silently disabling itself. A control that cannot run
            # must refuse, not wave the message through. See ADR-157.
            if self.link_manager is None:
                raise SecurityError(
                    "Link enforcement is required but no link manager is "
                    "available; refusing to send"
                )

            link_id = message.get_link_id()

            # If no link ID is provided, check if there's an existing link
            if not link_id:
                links_result = self.link_manager.get_links_for_agent(
                    cast(str, message.sender)
                )
                if links_result.is_ok():
                    links = links_result.unwrap()
                    for link in links:
                        if (
                            link.agent_a == message.receiver
                            or link.agent_b == message.receiver
                        ):
                            # Use existing link
                            message = message.with_link(link.link_id)
                            link_id = link.link_id
                            break

            # If still no link ID and strict policy, reject message
            if not link_id and getattr(
                self.security_config, "strict_link_policy", False
            ):
                raise SecurityError("No valid link exists between sender and receiver")

            # Validate the link if one is provided
            if link_id:
                link_result = self.link_manager.validate_link(
                    link_id, cast(str, message.sender), cast(str, message.receiver)
                )

                if link_result.is_err():
                    error = link_result.unwrap_err()
                    raise SecurityError(f"Link validation failed: {error['message']}")

        # Authorization check
        if self._auth_manager:
            try:
                auth_result = self._auth_manager.authorize_message(message)
                if auth_result.is_ok() and not auth_result.unwrap():
                    raise SecurityError("Message authorization denied")
            except SecurityError:
                raise
            except Exception as e:
                logger.debug(f"Authorization check skipped: {e}")

        # Enqueue for delivery in exactly ONE queue. Prefer the priority
        # MessageQueue (ordered delivery); fall back to the basic per-agent
        # queue only when the priority queue is unavailable or full. The
        # delivery loop drains both queues, so writing a direct message to
        # both would deliver it twice.
        enqueued = False
        if self._message_queue is not None:
            enq_result = self._message_queue.enqueue(message, priority=message.priority)
            enqueued = enq_result.is_ok()
            if enqueued:
                self._signal_delivery()
        if not enqueued:
            # Backpressure, not buffering (ADR-159). This path previously
            # appended to an unbounded list, so a full queue silently became a
            # memory leak and the caller was told the send had succeeded.
            with self._lock:
                receiver = cast(str, message.receiver)
                pending = self._agent_queues.setdefault(receiver, [])
                if (
                    self._message_queue is not None
                    or len(pending) >= self.max_queue_size
                ):
                    self._refused_count += 1
                    raise BrokerOverflowError(
                        {
                            "errorType": "QUEUE_FULL",
                            "message": (
                                "Broker queue is at capacity; refusing the "
                                "message rather than buffering without a bound."
                            ),
                            "details": {
                                "receiver": receiver,
                                "maxQueueSize": self.max_queue_size,
                            },
                        }
                    )
                pending.append(message)
        self._signal_delivery()

        logger.debug(
            f"Message {message.message_id} queued for delivery to {message.receiver}"
        )
        return str(message.message_id)  # Ensure we always return a string

    def publish(self, topic: str, message: Message) -> str:
        """Publish a message to a topic."""
        logger.debug(
            f"Publishing message of type {message.message_type} to topic {topic}"
        )

        # Ensure the message has an ID
        if not message.message_id:
            message.message_id = MessageID(str(uuid.uuid4()))

        # Send the message to all subscribers (thread-safe)
        with self._lock:
            subscribers = list(self._topic_subscribers.get(topic, []))

        # Separation-of-duties enforcement also covers topic fan-out: a topic
        # is not an escape hatch around the sender allowlist. Validate the
        # sender against every subscriber (and the payload policy) up front,
        # and reject the whole publish if any recipient is disallowed.
        if self._separation_policy is not None:
            for subscriber in subscribers:
                probe = message.with_receiver(subscriber)
                sod_result = self._separation_policy.authorize_send(probe)
                if sod_result.is_err():
                    error = sod_result.unwrap_err()
                    raise SecurityError(
                        f"Separation-of-duties denied: {error['message']}"
                    )

        for subscriber in subscribers:
            subscriber_message = Message(
                message_id=message.message_id,
                timestamp=message.timestamp,
                sender=message.sender,
                receiver=subscriber,
                priority=message.priority,
                message_type=message.message_type,
                payload=message.payload,
                metadata={**message.metadata, "topic": topic},
            )

            with self._lock:
                if subscriber not in self._agent_queues:
                    self._agent_queues[subscriber] = []
                self._agent_queues[subscriber].append(subscriber_message)

        if subscribers:
            self._signal_delivery()

        logger.debug(
            f"Message {message.message_id} published to topic {topic} with "
            f"{len(subscribers)} subscribers"
        )
        return str(message.message_id)  # Ensure we always return a string

    def subscribe(self, agent_id: str, handler: Callable[[Message], None]) -> None:
        """Subscribe an agent to receive messages."""
        logger.debug(f"Subscribing agent {agent_id} to receive messages")

        with self._lock:
            # Initialize queue and handlers if they don't exist
            if agent_id not in self._agent_queues:
                self._agent_queues[agent_id] = []

            if agent_id not in self._agent_handlers:
                self._agent_handlers[agent_id] = []

            # Add the handler
            self._agent_handlers[agent_id].append(handler)

        # Auto-assign 'agent' role for authorization
        if self._auth_manager:
            try:
                self._auth_manager.assign_role(agent_id, "agent")
            except Exception:
                pass  # Role assignment is best-effort

        logger.debug(f"Agent {agent_id} subscribed to receive messages")

    def unsubscribe(self, agent_id: str) -> None:
        """Unsubscribe an agent from receiving messages."""
        logger.debug(f"Unsubscribing agent {agent_id} from receiving messages")

        with self._lock:
            if agent_id in self._agent_handlers:
                del self._agent_handlers[agent_id]

            if agent_id in self._agent_queues:
                del self._agent_queues[agent_id]

        logger.debug(f"Agent {agent_id} unsubscribed from receiving messages")

    def subscribe_temporary(
        self, agent_id: str, handler: Callable[[Message], None]
    ) -> None:
        """Subscribe a temporary handler for an agent."""
        logger.debug(f"Subscribing temporary handler for agent {agent_id}")

        with self._lock:
            if agent_id not in self._temp_handlers:
                self._temp_handlers[agent_id] = []

            self._temp_handlers[agent_id].append(handler)

        logger.debug(f"Temporary handler subscribed for agent {agent_id}")

    def unsubscribe_temporary(
        self, agent_id: str, handler: Callable[[Message], None]
    ) -> None:
        """Unsubscribe a temporary handler for an agent."""
        logger.debug(f"Unsubscribing temporary handler for agent {agent_id}")

        with self._lock:
            if agent_id in self._temp_handlers:
                if handler in self._temp_handlers[agent_id]:
                    self._temp_handlers[agent_id].remove(handler)

        logger.debug(f"Temporary handler unsubscribed for agent {agent_id}")

    def subscribe_topic(
        self,
        topic: str,
        handler: Callable[[str, Message], None],
        agent_id: Optional[str] = None,
    ) -> None:
        """Subscribe to a topic."""
        logger.debug(f"Subscribing to topic {topic}")

        if not agent_id:
            # Infer agent_id from the calling context if not provided
            import inspect

            frame = inspect.currentframe()
            if frame is not None:
                frame = frame.f_back
            while frame:
                if "self" in frame.f_locals and hasattr(
                    frame.f_locals["self"], "agent_id"
                ):
                    agent_id = frame.f_locals["self"].agent_id
                    break
                frame = frame.f_back

        if not agent_id:
            raise ValueError("Agent ID could not be determined for topic subscription")

        with self._lock:
            # Initialize topic subscribers if it doesn't exist
            if topic not in self._topic_subscribers:
                self._topic_subscribers[topic] = []

            # Add the agent to subscribers if not already there
            if agent_id not in self._topic_subscribers[topic]:
                self._topic_subscribers[topic].append(agent_id)

            # Initialize topic handlers if they don't exist
            if topic not in self._topic_handlers:
                self._topic_handlers[topic] = {}

            # Add the handler
            self._topic_handlers[topic][agent_id] = handler

        logger.debug(f"Agent {agent_id} subscribed to topic {topic}")

    def unsubscribe_topic(self, topic: str, agent_id: str) -> None:
        """Unsubscribe from a topic."""
        logger.debug(f"Unsubscribing agent {agent_id} from topic {topic}")

        with self._lock:
            if (
                topic in self._topic_subscribers
                and agent_id in self._topic_subscribers[topic]
            ):
                self._topic_subscribers[topic].remove(agent_id)

            if (
                topic in self._topic_handlers
                and agent_id in self._topic_handlers[topic]
            ):
                del self._topic_handlers[topic][agent_id]

        logger.debug(f"Agent {agent_id} unsubscribed from topic {topic}")

    #: How long the delivery loop sleeps with no signal. Not the delivery
    #: path - insurance against an enqueue path that forgets to signal, which
    #: then costs latency rather than stalling (ADR-166).
    _IDLE_WAIT_SECONDS = 0.5

    def _signal_delivery(self) -> None:
        """Tell the delivery loop there is something to do."""
        with self._wake:
            self._wake_pending = True
            self._wake.notify_all()

    def _await_work(self) -> None:
        """Block until something is enqueued, shutdown, or the fallback."""
        with self._wake:
            if not self._wake_pending:
                self._wake.wait(timeout=self._IDLE_WAIT_SECONDS)
            self._wake_pending = False

    def _message_delivery_loop(self) -> None:
        """Background thread for delivering messages."""
        logger.info("Message delivery loop started")

        while self.running:
            try:
                # Wait for an enqueue rather than polling. The previous
                # time.sleep(0.01) cost every message half a poll on average:
                # measured p50 4.8ms, p95 10.0ms, max 16.6ms, paid per hop
                # (ADR-166).
                self._await_work()
                if not self.running:
                    break

                # Drain from MessageQueue first (priority-ordered)
                if self._message_queue:
                    while True:
                        dequeue_result = self._message_queue.dequeue(timeout=0)
                        if dequeue_result.is_err():
                            break
                        message = dequeue_result.unwrap()
                        if message and message.receiver:
                            self._deliver_message(message.receiver, message)
                            # Update router health tracking
                            if self._message_router:
                                self._message_router.update_agent_health(
                                    message.receiver, True
                                )

                # Also drain basic queues (fallback path + publish messages)
                with self._lock:
                    queues = {
                        agent_id: list(queue)
                        for agent_id, queue in self._agent_queues.items()
                    }
                    # Clear the queues
                    for agent_id in queues:
                        self._agent_queues[agent_id] = []

                # Deliver messages
                for agent_id, messages in queues.items():
                    for message in messages:
                        self._deliver_message(agent_id, message)
            except Exception as e:
                logger.error(f"Error in message delivery loop: {str(e)}")
                time.sleep(0.1)  # Avoid spinning on errors

    def _deliver_message(self, agent_id: str, message: Message) -> None:
        """Deliver a message to an agent, counting what nobody handled.

        Handler tables are snapshotted under ``self._lock`` and invoked after
        it is released (ADR-159). ``subscribe`` mutates those tables under the
        lock while this runs on the delivery thread, so reading them unlocked
        was a race; holding the lock across handler invocation would instead
        let one slow handler stall every subscribe and every other delivery.
        """
        logger.debug(f"Delivering message {message.message_id} to agent {agent_id}")

        topic = message.metadata.get("topic") if message.metadata else None

        with self._lock:
            temp_handlers = list(self._temp_handlers.get(agent_id, []))
            handlers = list(self._agent_handlers.get(agent_id, []))
            topic_handler = None
            if topic is not None:
                topic_handler = self._topic_handlers.get(topic, {}).get(agent_id)

        invoked = 0

        for handler in temp_handlers:
            try:
                handler(message)
                invoked += 1
            except Exception as e:
                invoked += 1  # it ran; it raised. That is not "undelivered".
                logger.error(f"Error in temporary handler: {str(e)}")

        for handler in handlers:
            try:
                handler(message)
                invoked += 1
            except Exception as e:
                invoked += 1
                logger.error(f"Error in handler: {str(e)}")

        if topic_handler is not None:
            try:
                topic_handler(cast(str, topic), message)
                invoked += 1
            except Exception as e:
                invoked += 1
                logger.error(f"Error in topic handler: {str(e)}")

        if invoked:
            with self._lock:
                self._delivered_count += 1
            return

        self._record_undeliverable(agent_id, message)

    def _record_undeliverable(self, agent_id: str, message: Message) -> None:
        """Account for a message that reached no handler.

        Before ADR-159 this path was silent: the message was dequeued,
        delivered to nobody, and discarded with no error, counter or log.
        """
        with self._lock:
            self._undeliverable_count += 1
            first_time = agent_id not in self._undeliverable_seen
            if first_time:
                self._undeliverable_seen.add(agent_id)
            handler = self._undeliverable_handler

        # Log once per receiver: a hot loop addressing an absent agent must
        # not be able to flood the log.
        if first_time:
            logger.warning(
                "No handler for receiver %r - message %s was not delivered. "
                "Further undeliverable messages for this receiver are counted "
                "in get_statistics() but not logged.",
                agent_id,
                message.message_id,
            )

        if handler is not None:
            try:
                handler(agent_id, message)
            except Exception as e:
                logger.error(f"Error in undeliverable handler: {str(e)}")

    def get_statistics(self) -> Dict[str, Any]:
        """Delivery accounting for operators (ADR-159).

        ``undeliverable`` counts messages that reached zero handlers - the
        loss that used to be invisible. ``refused`` counts messages the broker
        declined to accept as backpressure.
        """
        with self._lock:
            pending = sum(len(q) for q in self._agent_queues.values())
            return {
                "delivered": self._delivered_count,
                "undeliverable": self._undeliverable_count,
                "undeliverableReceivers": len(self._undeliverable_seen),
                "refused": self._refused_count,
                "pendingFallback": pending,
                "maxQueueSize": self.max_queue_size,
                "maxMessageBytes": self.max_message_bytes,
                "subscribedAgents": len(self._agent_handlers),
            }
