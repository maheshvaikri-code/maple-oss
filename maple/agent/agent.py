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

# maple/agent/agent.py
# Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

import logging
import os
import queue
import threading
import time
import uuid
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Optional,
    TypeVar,
    cast,
)

from ..broker.broker import MessageBroker
from ..core.message import Message
from ..core.result import Result
from ..core.types import Priority
from ..error.types import BrokerOverflowError, BrokerUnavailableError
from .config import Config

if TYPE_CHECKING:
    from ..communication.streaming import Stream

# Type variables for handlers
T = TypeVar("T")
E = TypeVar("E")

# NOTE: a LIBRARY must not configure the root logger (that hijacks the host's logging
# and emits INFO noise). Use a module logger; the host owns logging config.
logger = logging.getLogger(__name__)


class Agent:
    """
    Base class for MAPLE agents.
    """

    # Shared agent registry singleton
    _shared_registry: Optional[Any] = None

    def __init__(self, config: Config, broker: Optional[MessageBroker] = None) -> None:
        self.config = config
        self.agent_id = config.agent_id
        self.capabilities = getattr(config, "capabilities", [])
        self.registry: Optional[Any] = None
        self._crypto_manager: Optional[Any] = None

        # Auto-detect broker type from broker_url
        if broker:
            self.broker = broker
        else:
            self.broker = self._create_broker(config)

        self.running = False
        self.message_queue: queue.Queue[Message] = queue.Queue()
        self.handler_thread: Optional[threading.Thread] = None
        self._handling = False
        #: Set by stop(). A parked receive() checks it between slices, so
        #: shutting down wakes waiters instead of stranding them
        #: (ADR-165). Never set at construction: an agent that has not
        #: started yet still blocks exactly as it always did.
        self._shutdown = threading.Event()
        #: Messages discarded by the most recent stop() because the drain
        #: deadline passed. Reported rather than silently lost.
        self.messages_undrained = 0
        self.message_handlers: Dict[str, Callable[[Message], Optional[Message]]] = {}
        self.topic_handlers: Dict[str, Callable[[Message], Optional[Message]]] = {}
        self.stream_handlers: Dict[str, Callable[[Message], None]] = {}

        # Agent metrics
        self.messages_sent = 0
        self.messages_received = 0
        self.messages_failed = 0

    @staticmethod
    def _create_broker(config: Config) -> Any:
        """Build the broker the config asks for, or refuse.

        A scheme this method recognises is a promise about the transport. If
        the driver for it is missing, that promise cannot be kept, so it raises
        ``BrokerUnavailableError`` rather than substituting the in-memory
        broker. The previous fallback made a ``nats://`` agent with no
        ``nats-py`` installed look healthy while every send stayed in-process
        (ADR-157).
        """
        from ..broker.production_broker import BrokerType, ProductionBrokerManager

        broker_url = getattr(config, "broker_url", None) or ""
        schemes = {"nats://": BrokerType.NATS, "s2://": BrokerType.S2}

        # Matched case-insensitively: URI schemes are case-insensitive per
        # RFC 3986, and a case-sensitive startswith let "NATS://prod" miss this
        # dispatch entirely and fall back to the in-process broker - the exact
        # silent downgrade ADR-157 refuses, reachable by holding shift
        # (ADR-164).
        normalized = broker_url.lower()

        if normalized.startswith("file://"):
            # Multi-process on one host (ADR-167). No external infrastructure,
            # so it needs no driver check - the spool is a directory.
            from ..broker.file_broker import FileBroker

            broker = FileBroker(config)
            Agent._require_security_enforcement(config, broker, broker_url)
            return broker

        for scheme, broker_type in schemes.items():
            if normalized.startswith(scheme):
                result = ProductionBrokerManager.create_broker(config, broker_type)
                if result.is_err():
                    raise BrokerUnavailableError(broker_url, result.unwrap_err())
                broker = result.unwrap()
                Agent._require_security_enforcement(config, broker, broker_url)
                return broker

        return MessageBroker(config)

    @staticmethod
    def _require_security_enforcement(
        config: Config, broker: Any, broker_url: str
    ) -> None:
        """Refuse a transport that cannot honor the configured security controls.

        The NATS transport publishes straight to NATS and enforces none of
        ``SecurityConfig`` - no link policy, no separation of duties, no
        authorization. Accepting such a config and ignoring it is the same
        fail-open shape ADR-157 removed from the in-memory broker, so it is
        refused here instead (ADR-161).

        A transport that declares no opinion is treated as non-enforcing.
        """
        security = getattr(config, "security", None)
        if security is None:
            return

        requested = [
            name
            for name, value in (
                ("separation_policy", getattr(security, "separation_policy", None)),
                ("require_links", getattr(security, "require_links", False)),
                ("strict_link_policy", getattr(security, "strict_link_policy", False)),
            )
            if value
        ]
        if not requested:
            return

        if getattr(broker, "ENFORCES_SECURITY_POLICY", False):
            return

        raise BrokerUnavailableError(
            broker_url,
            {
                "errorType": "BROKER_CANNOT_ENFORCE_SECURITY",
                "message": (
                    f"{type(broker).__name__} does not enforce "
                    f"{', '.join(requested)}. Refusing to construct an agent "
                    "whose configured security controls would be silently "
                    "ignored."
                ),
                "details": {
                    "broker": type(broker).__name__,
                    "unenforcedControls": requested,
                },
            },
        )

    def start(self) -> None:
        """Start the agent."""
        logger.info(f"Starting agent {self.agent_id}")
        self.running = True
        self.broker.connect()
        self.broker.subscribe(self.agent_id, self._handle_message)

        # Auto-register with AgentRegistry
        self._auto_register()

        self.handler_thread = threading.Thread(target=self._message_handler_loop)
        self.handler_thread.daemon = True
        self.handler_thread.start()
        logger.info(f"Agent {self.agent_id} started")

    def _auto_register(self) -> None:
        """Auto-register this agent in the global AgentRegistry."""
        try:
            from ..discovery.registry import AgentRegistry

            # Prefer the scope's registry so discovery cannot see across
            # broker boundaries (ADR-160). Transports that predate scoping
            # fall back to the process-wide registry.
            if hasattr(self.broker, "get_registry"):
                self.registry = self.broker.get_registry()
            else:
                if Agent._shared_registry is None:
                    Agent._shared_registry = AgentRegistry()
                self.registry = Agent._shared_registry
            result = self.registry.register_agent(
                agent_id=self.agent_id,
                name=self.agent_id,
                capabilities=self.capabilities,
                metadata={"broker_url": self.config.broker_url},
            )
            if result.is_ok():
                logger.info(f"Agent {self.agent_id} auto-registered in AgentRegistry")
            else:
                logger.debug(
                    f"Agent {self.agent_id} registration note: {result.unwrap_err()}"
                )
        except Exception as e:
            logger.debug(f"Auto-registration skipped: {e}")

    #: Default seconds ``stop()`` will spend draining queued work.
    DEFAULT_DRAIN_TIMEOUT = 5.0

    def stop(self, drain_timeout: Optional[float] = None) -> int:
        """Stop the agent, draining queued work first.

        Measured before this existed: of 40 messages sent to an agent with a
        250ms handler, ``stop()`` discarded **38** with no error, no counter
        and no log, returning in 0.11s. Those messages had been accepted with
        an ``Ok`` result that promised nothing (ADR-163).

        Intake is closed first, then whatever is already queued is processed
        until the queue drains or ``drain_timeout`` elapses. An empty queue
        returns immediately, so the ordinary case costs nothing.

        Args:
            drain_timeout: Seconds to spend draining. ``None`` uses
                ``DEFAULT_DRAIN_TIMEOUT``. ``0`` skips the drain entirely,
                which is the pre-ADR-163 behaviour, chosen explicitly.

        Returns:
            The number of messages still queued when the deadline passed —
            ``0`` for a complete drain. Losing work on shutdown may be an
            acceptable trade; losing it silently never is.
        """
        logger.info(f"Stopping agent {self.agent_id}")
        # Wake anything parked in receive() before the drain, so a caller
        # blocked on this agent learns it is going away (ADR-165).
        self._shutdown.set()

        deadline = (
            self.DEFAULT_DRAIN_TIMEOUT if drain_timeout is None else drain_timeout
        )
        # The subscription stays open *through* the drain. Unsubscribing first
        # looks like the way to close intake, and it silently strands whatever
        # the broker already accepted for this agent: the delivery loop polls,
        # so a message sent moments earlier is still in the broker's queue and
        # never reaches this agent's. Measured, sending 25 then stopping
        # immediately: 0 delivered, and stop() reported a clean drain while the
        # broker counted 25 undeliverable.
        undrained = self._drain(deadline)
        self.messages_undrained = undrained

        # Intake closes once the drain is done, by unsubscribing *this* agent
        # rather than disconnecting. Brokers are scoped and shared (ADR-160),
        # so disconnect() would stop the delivery thread for every agent on the
        # same broker_url.
        if hasattr(self.broker, "unsubscribe"):
            try:
                self.broker.unsubscribe(self.agent_id)
            except Exception:  # pragma: no cover - intake closure is best effort
                logger.debug("Could not unsubscribe %s cleanly", self.agent_id)

        self.running = False
        if self.handler_thread:
            self.handler_thread.join(timeout=5.0)
        # Deregister from AgentRegistry
        if self.registry:
            try:
                self.registry.deregister_agent(self.agent_id)
            except Exception:
                pass
        self._disconnect_if_last_subscriber()
        logger.info(f"Agent {self.agent_id} stopped")
        return undrained

    def _disconnect_if_last_subscriber(self) -> None:
        """Tear the broker down only when nobody else is using it.

        Brokers are keyed by ``broker_url`` and shared across every agent in
        that scope (ADR-160), while ``disconnect()`` stops the scope's single
        delivery thread. Calling it unconditionally meant stopping **one**
        agent silently broke delivery for all of its peers.

        Measured on the unmodified tree, a peer receiving a message after an
        unrelated agent stopped: delivered in 1 run out of 3. Flaky rather
        than absent, which is why it went unnoticed.
        """
        try:
            remaining = len(getattr(self.broker, "_agent_handlers", {}))
        except Exception:  # pragma: no cover - defensive
            remaining = 0

        if remaining:
            logger.debug(
                "Leaving broker connected for %d remaining subscriber(s)",
                remaining,
            )
            return
        self.broker.disconnect()

    #: Consecutive idle polls required before a drain is called complete.
    #: The broker's delivery loop polls on its own interval, so an empty agent
    #: queue can simply mean "not handed over yet". One quiet sample is not
    #: evidence of an empty system.
    _DRAIN_QUIET_POLLS = 4
    _DRAIN_POLL_SECONDS = 0.005

    def _pending_upstream(self) -> int:
        """Messages the broker still holds that could be destined here.

        Best effort and deliberately conservative: the shared priority queue
        is not per-agent, so anything in it is treated as possibly ours. Being
        wrong here costs a few extra milliseconds of draining; being wrong the
        other way strands accepted work.
        """
        total = 0
        try:
            queue_obj = getattr(self.broker, "_message_queue", None)
            if queue_obj is not None:
                size = getattr(queue_obj, "size", None)
                total += size() if callable(size) else int(size or 0)
        except Exception:  # pragma: no cover - defensive
            pass
        try:
            pending = getattr(self.broker, "_agent_queues", {}).get(self.agent_id)
            total += len(pending or [])
        except Exception:  # pragma: no cover - defensive
            pass
        return total

    def _drain(self, timeout: float) -> int:
        """Let the handler loop finish accepted work, bounded by a deadline.

        Waits on both queues: this agent's, and whatever the broker still holds
        for it. Draining only the local one reports success while in-flight
        messages are stranded upstream.

        Returns the number of messages still outstanding when it gave up.
        """
        if timeout <= 0 or not self.running or self.handler_thread is None:
            return self.message_queue.qsize() + self._pending_upstream()

        # A duration, so it is measured on a clock that cannot step (ADR-163).
        end = time.perf_counter() + timeout
        quiet = 0
        while time.perf_counter() < end:
            idle = (
                self.message_queue.empty()
                and not self._handling
                and self._pending_upstream() == 0
            )
            quiet = quiet + 1 if idle else 0
            if quiet >= self._DRAIN_QUIET_POLLS:
                return 0
            time.sleep(self._DRAIN_POLL_SECONDS)

        remaining = self.message_queue.qsize() + self._pending_upstream()
        if remaining:
            logger.warning(
                "Agent %s stopped with %d message(s) still outstanding after a "
                "%.1fs drain; they are discarded. Raise drain_timeout, or stop "
                "accepting work sooner.",
                self.agent_id,
                remaining,
                timeout,
            )
        return remaining

    def send(
        self, message: Message, require_routable: bool = False
    ) -> Result[str, Dict[str, Any]]:
        """Send a message to another agent.

        By default this returns ``Ok`` once the message is *enqueued* — which
        is not the same as delivered (a message to a nonexistent agent still
        enqueues). Pass ``require_routable=True`` to first verify the receiver
        has a live subscription; if it does not, this returns
        ``Result.err`` with ``errorType`` ``UNROUTABLE`` instead of a
        misleading ``Ok``. (Reachability is checked at send time; it is not a
        post-delivery acknowledgement.)
        """
        # Set the sender if not already set
        if not message.sender:
            message.sender = self.agent_id

        if require_routable and hasattr(self.broker, "is_routable"):
            if not self.broker.is_routable(cast(str, message.receiver)):
                self.messages_failed += 1
                error = {
                    "errorType": "UNROUTABLE",
                    "message": (
                        f"No route to receiver '{message.receiver}': "
                        "no live subscription"
                    ),
                    "details": {
                        "messageType": message.message_type,
                        "receiver": message.receiver,
                    },
                }
                logger.warning(f"Refusing unroutable send: {error}")
                return Result.err(error)

        try:
            message_id = self.broker.send(message)
            self.messages_sent += 1
            return Result.ok(message_id)
        except BrokerOverflowError as e:
            # Backpressure, not a failure. Surface the broker's typed error
            # unchanged so callers can branch on QUEUE_FULL vs
            # MESSAGE_TOO_LARGE instead of parsing a message string (ADR-159).
            self.messages_failed += 1
            refusal: Dict[str, Any] = dict(e.error)
            refusal_details: Dict[str, Any] = dict(
                cast(Dict[str, Any], refusal.get("details") or {})
            )
            refusal_details["messageType"] = message.message_type
            refusal_details["receiver"] = message.receiver
            refusal["details"] = refusal_details
            logger.warning(f"Broker refused message: {refusal}")
            return Result.err(refusal)
        except Exception as e:
            self.messages_failed += 1
            error = {
                "errorType": "SEND_ERROR",
                "message": str(e),
                "details": {
                    "messageType": message.message_type,
                    "receiver": message.receiver,
                },
            }
            logger.error(f"Error sending message: {error}")
            return Result.err(error)

    def request(
        self, message: Message, timeout: str = "30s"
    ) -> Result[Message, Dict[str, Any]]:
        """Send a message and wait for a response."""
        # Set a correlation ID if not already set
        if "correlationId" not in message.metadata:
            message.metadata["correlationId"] = str(uuid.uuid4())

        correlation_id = message.metadata["correlationId"]

        # Create a response queue for this request
        response_queue: queue.Queue[Message] = queue.Queue()

        # Register a temporary handler for the response
        def response_handler(response: Message) -> None:
            if (
                "correlationId" in response.metadata
                and response.metadata["correlationId"] == correlation_id
            ):
                response_queue.put(response)

        # Subscribe to responses
        self.broker.subscribe_temporary(self.agent_id, response_handler)

        # Send the message
        send_result = self.send(message)
        if send_result.is_err():
            return Result.err(send_result.unwrap_err())

        # Wait for the response
        try:
            from ..core.types import Duration

            # Parse the timeout
            timeout_seconds = Duration.parse(timeout)

            # Wait for the response
            response = response_queue.get(timeout=timeout_seconds)
            return Result.ok(response)
        except queue.Empty:
            error = {
                "errorType": "TIMEOUT",
                "message": (
                    "Timed out waiting for response to message " f"{message.message_id}"
                ),
                "details": {
                    "messageType": message.message_type,
                    "receiver": message.receiver,
                    "timeout": timeout,
                },
            }
            logger.error(f"Request timeout: {error}")
            return Result.err(error)
        finally:
            # Unsubscribe the temporary handler
            self.broker.unsubscribe_temporary(self.agent_id, response_handler)

    #: How long a parked receive() sleeps between shutdown checks. Not a
    #: deadline - the call still blocks indefinitely while the agent runs.
    _WAIT_SLICE_SECONDS = 0.05

    def _get_until_shutdown(self) -> Optional[Message]:
        """Block for a message until one arrives or the agent stops.

        Returns ``None`` when the agent stopped first. Before this existed a
        parked ``receive()`` never woke: stop() returned cleanly in 0.13s and
        left the thread wedged with no error and no way to learn why
        (ADR-165).
        """
        while True:
            try:
                return self.message_queue.get(timeout=self._WAIT_SLICE_SECONDS)
            except queue.Empty:
                if self._shutdown.is_set():
                    # One last look: a message may have landed in the same
                    # slice the stop did, and it should not be lost to a race.
                    try:
                        return self.message_queue.get_nowait()
                    except queue.Empty:
                        return None

    def _stopped_error(self) -> Dict[str, Any]:
        return {
            "errorType": "AGENT_STOPPED",
            "message": (
                f"Agent '{self.agent_id}' stopped while waiting for a message."
            ),
            "details": {"agentId": self.agent_id},
        }

    def receive(self, timeout: Optional[str] = None) -> Result[Message, Dict[str, Any]]:
        """Receive a message from the queue."""
        try:
            if timeout:
                from ..core.types import Duration

                timeout_seconds = Duration.parse(timeout)
                message = self.message_queue.get(timeout=timeout_seconds)
            else:
                pending = self._get_until_shutdown()
                if pending is None:
                    return Result.err(self._stopped_error())
                message = pending

            return Result.ok(message)
        except queue.Empty:
            error = {
                "errorType": "TIMEOUT",
                "message": "Timed out waiting for message",
                "details": {"timeout": timeout},
            }
            return Result.err(error)

    def receive_filtered(
        self,
        filter: Callable[[Message], bool],
        timeout: Optional[str] = None,
    ) -> Result[Message, Dict[str, Any]]:
        """Receive a message that matches a filter."""
        if timeout:
            from ..core.types import Duration

            timeout_seconds = Duration.parse(timeout)
            # A receive deadline is a duration, so it is measured on the
            # monotonic clock: an NTP correction must not cut the wait short
            # or extend it by an hour (ADR-163).
            end_time = time.perf_counter() + timeout_seconds
        else:
            end_time = None

        while end_time is None or time.perf_counter() < end_time:
            remaining_time = end_time - time.perf_counter() if end_time else None

            try:
                if remaining_time:
                    message = self.message_queue.get(timeout=remaining_time)
                else:
                    pending = self._get_until_shutdown()
                    if pending is None:
                        return Result.err(self._stopped_error())
                    message = pending

                if filter(message):
                    return Result.ok(message)

                # Put the message back in the queue if it doesn't match
                self.message_queue.put(message)

                # Sleep briefly to avoid busy waiting
                time.sleep(0.01)
            except queue.Empty:
                error = {
                    "errorType": "TIMEOUT",
                    "message": "Timed out waiting for filtered message",
                    "details": {"timeout": timeout},
                }
                return Result.err(error)

        error = {
            "errorType": "TIMEOUT",
            "message": "Timed out waiting for filtered message",
            "details": {"timeout": timeout},
        }
        return Result.err(error)

    def broadcast(
        self, recipients: List[str], message: Message
    ) -> Dict[str, Result[str, Dict[str, Any]]]:
        """Broadcast a message to multiple recipients."""
        results = {}

        for recipient in recipients:
            # Create a copy of the message for each recipient
            recipient_message = message.with_receiver(recipient)
            results[recipient] = self.send(recipient_message)

        return results

    def publish(self, topic: str, message: Message) -> Result[str, Dict[str, Any]]:
        """Publish a message to a topic."""
        try:
            message_id = self.broker.publish(topic, message)
            return Result.ok(message_id)
        except Exception as e:
            error = {
                "errorType": "PUBLISH_ERROR",
                "message": str(e),
                "details": {"messageType": message.message_type, "topic": topic},
            }
            logger.error(f"Error publishing message: {error}")
            return Result.err(error)

    def subscribe(self, topic: str) -> Result[None, Dict[str, Any]]:
        """Subscribe to a topic."""
        try:
            self.broker.subscribe_topic(topic, self._handle_topic_message)
            return Result.ok(None)
        except Exception as e:
            error = {
                "errorType": "SUBSCRIBE_ERROR",
                "message": str(e),
                "details": {"topic": topic},
            }
            logger.error(f"Error subscribing to topic: {error}")
            return Result.err(error)

    def establish_link(
        self, agent_id: str, lifetime_seconds: int = 3600
    ) -> Result[str, Dict[str, Any]]:
        """Establish a secure communication link with another agent."""
        logger.info(f"Establishing link with agent {agent_id}")

        try:
            # Generate a nonce
            nonce_a = os.urandom(16).hex()

            # Get security config
            security_config = getattr(self.config, "security", None)
            if not security_config:
                return Result.err(
                    {
                        "errorType": "NO_SECURITY_CONFIG",
                        "message": (
                            "Security configuration required for link establishment"
                        ),
                    }
                )

            # Create a link request message
            request = Message(
                message_type="LINK_REQUEST",
                receiver=agent_id,
                priority=Priority.HIGH,
                payload={
                    "publicKey": getattr(security_config, "public_key", ""),
                    "nonce": nonce_a,
                    "supportedCiphers": ["AES256-GCM", "ChaCha20-Poly1305"],
                },
            )

            # Send the request
            self.send(request)

            # Wait for a challenge response
            response_result = self.receive_filtered(
                lambda m: m.message_type == "LINK_CHALLENGE" and m.sender == agent_id,
                timeout="10s",
            )

            if response_result.is_err():
                logger.error(
                    f"Failed to receive link challenge: {response_result.unwrap_err()}"
                )
                return Result.err(
                    {
                        "errorType": "LINK_TIMEOUT",
                        "message": "Timed out waiting for link challenge",
                    }
                )

            challenge = response_result.unwrap()

            # Verify the challenge contains our nonce
            if not self._verify_nonce(challenge.payload["encryptedNonce"], nonce_a):
                logger.error("Failed to verify nonce in link challenge")
                return Result.err(
                    {
                        "errorType": "LINK_VERIFICATION_FAILED",
                        "message": "Failed to verify nonce in link challenge",
                    }
                )

            # Extract the link ID and other parameters
            link_id = challenge.payload["linkId"]
            nonce_b = challenge.payload["nonce"]

            # Create link parameters
            link_params = {
                "cipherSuite": "AES256-GCM",
                "keyRotationInterval": "1h",
                "compressionEnabled": True,
            }

            # Create a confirmation message
            confirmation = Message(
                message_type="LINK_CONFIRM",
                receiver=agent_id,
                priority=Priority.HIGH,
                payload={
                    "linkId": link_id,
                    "encryptedNonce": self._encrypt_nonce(nonce_b),
                    "linkParams": link_params,
                },
            )

            # Send the confirmation
            self.send(confirmation)

            # Wait for establishment confirmation
            establish_result = self.receive_filtered(
                lambda m: m.message_type == "LINK_ESTABLISHED" and m.sender == agent_id,
                timeout="10s",
            )

            if establish_result.is_err():
                logger.error(
                    "Failed to receive link established: "
                    f"{establish_result.unwrap_err()}"
                )
                return Result.err(
                    {
                        "errorType": "LINK_TIMEOUT",
                        "message": "Timed out waiting for link establishment",
                    }
                )

            established = establish_result.unwrap()

            # Verify the link parameters
            if not self._verify_link_params(
                established.payload["encryptedParams"], link_params
            ):
                logger.error("Failed to verify link parameters")
                return Result.err(
                    {
                        "errorType": "LINK_VERIFICATION_FAILED",
                        "message": "Failed to verify link parameters",
                    }
                )

            logger.info(f"Link established with agent {agent_id}: {link_id}")
            return Result.ok(link_id)

        except Exception as e:
            logger.error(f"Error establishing link: {str(e)}")
            return Result.err(
                {"errorType": "LINK_ESTABLISHMENT_ERROR", "message": str(e)}
            )

    def send_with_link(
        self, message: Message, agent_id: str
    ) -> Result[str, Dict[str, Any]]:
        """Send a message using an established link, creating one if needed."""
        # Check if we already have a link
        link_id = None

        # Check if message already has a link
        if "linkId" in message.metadata:
            link_id = message.metadata["linkId"]
        else:
            # Find an existing link
            links_result = cast(Any, self.broker.link_manager).get_links_for_agent(
                self.agent_id
            )
            if links_result.is_ok():
                links = links_result.unwrap()
                for link in links:
                    if link.agent_a == agent_id or link.agent_b == agent_id:
                        link_id = link.link_id
                        break

        # If no link exists, establish one
        if not link_id:
            link_result = self.establish_link(agent_id)
            if link_result.is_err():
                return link_result
            link_id = link_result.unwrap()

        # Add the link ID to the message
        linked_message = message.with_link(link_id)

        # Send the message
        return self.send(linked_message)

    def _get_crypto_manager(self) -> Any:
        """Get or create a CryptographyManager for this agent."""
        if self._crypto_manager is None:
            try:
                from ..security.cryptography_impl import (
                    CRYPTO_AVAILABLE,
                    CryptographyManager,
                )

                if CRYPTO_AVAILABLE:
                    self._crypto_manager = CryptographyManager()
            except (ImportError, Exception):
                pass
        return self._crypto_manager

    def _verify_nonce(self, encrypted_nonce: str, original_nonce: str) -> bool:
        """Verify encrypted nonce with real crypto when available."""
        crypto = self._get_crypto_manager()
        if crypto is not None:
            try:
                security_config = getattr(self.config, "security", None)
                if security_config and security_config.private_key:
                    result = crypto.decrypt_data(
                        encrypted_nonce, security_config.private_key
                    )
                    if result.is_ok():
                        return bool(result.unwrap() == original_nonce)
            except Exception:
                pass
        # Fallback to base64 for compatibility
        try:
            import base64

            decoded = base64.b64decode(encrypted_nonce.encode()).decode()
            return decoded == original_nonce
        except Exception:
            return False

    def _encrypt_nonce(self, nonce: str) -> str:
        """Encrypt a nonce for link establishment using real crypto when available."""
        crypto = self._get_crypto_manager()
        if crypto is not None:
            try:
                security_config = getattr(self.config, "security", None)
                if security_config and security_config.public_key:
                    result = crypto.encrypt_data(nonce, security_config.public_key)
                    if result.is_ok():
                        return cast(str, result.unwrap())
            except Exception:
                pass
        # Fallback to base64 for compatibility
        try:
            import base64

            return base64.b64encode(nonce.encode()).decode()
        except Exception:
            return nonce

    def _verify_link_params(
        self, encrypted_params: str, params: Dict[str, Any]
    ) -> bool:
        """Verify link parameters by decrypting and comparing."""
        try:
            import base64
            import json

            decoded = base64.b64decode(encrypted_params.encode()).decode()
            decoded_params = json.loads(decoded)
            return bool(decoded_params == params)
        except Exception:
            return False

    def create_stream(self, name: str) -> Result["Stream", Dict[str, Any]]:
        """Create a new stream."""
        try:
            from ..communication.streaming import Stream

            stream = Stream(self, name)
            return Result.ok(stream)
        except Exception as e:
            error = {
                "errorType": "STREAM_CREATE_ERROR",
                "message": str(e),
                "details": {"name": name},
            }
            logger.error(f"Error creating stream: {error}")
            return Result.err(error)

    def connect_stream(self, name: str) -> Result["Stream", Dict[str, Any]]:
        """Connect to an existing stream."""
        try:
            from ..communication.streaming import Stream

            stream = Stream.connect(self, name)
            return Result.ok(stream)
        except Exception as e:
            error = {
                "errorType": "STREAM_CONNECT_ERROR",
                "message": str(e),
                "details": {"name": name},
            }
            logger.error(f"Error connecting to stream: {error}")
            return Result.err(error)

    def register_handler(
        self,
        message_type: str,
        handler: Callable[[Message], Optional[Message]],
    ) -> None:
        """Register a handler for a specific message type.

        The key is normalized to upper-case to match ``Message``, which
        upper-cases every ``message_type`` on construction. Without this, a
        handler registered as ``"work.package"`` would silently never fire for
        an incoming ``WORK.PACKAGE`` (the "case trap").
        """
        normalized = (
            message_type.upper() if isinstance(message_type, str) else message_type
        )
        self.message_handlers[normalized] = handler
        logger.info(f"Registered handler for message type {normalized}")

    def register_topic_handler(
        self, topic: str, handler: Callable[[Message], Optional[Message]]
    ) -> None:
        """Register a handler for a specific topic."""
        self.topic_handlers[topic] = handler
        logger.info(f"Registered handler for topic {topic}")

    def register_stream_handler(
        self, stream_name: str, handler: Callable[[Message], None]
    ) -> None:
        """Register a handler for a stream."""
        self.stream_handlers[stream_name] = handler
        logger.info(f"Registered handler for stream {stream_name}")

    def _message_handler_loop(self) -> None:
        """Background thread for handling messages."""
        logger.info(f"Message handler loop started for agent {self.agent_id}")

        while self.running:
            try:
                # Get a message from the queue, blocking with timeout
                try:
                    message = self.message_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                # Process the message. The flag lets stop() distinguish an
                # empty queue from an empty queue with a handler still running,
                # so a drain does not declare victory mid-message (ADR-163).
                self._handling = True
                try:
                    self._process_message(message)
                finally:
                    self._handling = False

                # Mark the message as processed
                self.message_queue.task_done()
            except Exception as e:
                logger.error(f"Error in message handler loop: {str(e)}")
                time.sleep(0.1)  # Avoid spinning on errors

    def _process_message(self, message: Message) -> None:
        """Process a message by calling the appropriate handler."""
        # Find the appropriate handler
        handler = self.message_handlers.get(message.message_type)

        if handler:
            logger.debug(f"Processing message of type {message.message_type}")

            try:
                # Call the handler
                response = handler(message)

                # Send the response if one was returned
                if response:
                    response.receiver = message.sender
                    if "correlationId" in message.metadata:
                        response.metadata["correlationId"] = message.metadata[
                            "correlationId"
                        ]

                    self.send(response)
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}")

                # Send an error response
                if message.sender:
                    error_response = Message.error(
                        error_type="HANDLER_ERROR",
                        message=f"Error processing message: {str(e)}",
                        receiver=message.sender,
                        correlation_id=message.metadata.get("correlationId"),
                    )
                    self.send(error_response)
        else:
            logger.warning(f"No handler found for message type {message.message_type}")

    def _handle_message(self, message: Message) -> None:
        """Handle a message received from the broker."""
        self.messages_received += 1
        # Put the message in the queue for processing
        self.message_queue.put(message)

    def _handle_topic_message(self, topic: str, message: Message) -> None:
        """Handle a message received on a topic."""
        handler = self.topic_handlers.get(topic)

        if handler:
            logger.debug(f"Processing message on topic {topic}")

            try:
                # Call the handler
                response = handler(message)

                # Send the response if one was returned
                if response:
                    response.receiver = message.sender
                    if "correlationId" in message.metadata:
                        response.metadata["correlationId"] = message.metadata[
                            "correlationId"
                        ]

                    self.send(response)
            except Exception as e:
                logger.error(f"Error processing topic message: {str(e)}")
        else:
            logger.warning(f"No handler found for topic {topic}")

    def handler(self, message_type: str) -> Callable[
        [Callable[[Message], Optional[Message]]],
        Callable[[Message], Optional[Message]],
    ]:
        """Decorator for registering message handlers."""

        def decorator(
            func: Callable[[Message], Optional[Message]],
        ) -> Callable[[Message], Optional[Message]]:
            self.register_handler(message_type, func)
            return func

        return decorator

    def topic_handler(self, topic: str) -> Callable[
        [Callable[[Message], Optional[Message]]],
        Callable[[Message], Optional[Message]],
    ]:
        """Decorator for registering topic handlers."""

        def decorator(
            func: Callable[[Message], Optional[Message]],
        ) -> Callable[[Message], Optional[Message]]:
            self.register_topic_handler(topic, func)
            return func

        return decorator

    def stream_handler(
        self, stream_name: str
    ) -> Callable[[Callable[[Message], None]], Callable[[Message], None]]:
        """Decorator for registering stream handlers."""

        def decorator(func: Callable[[Message], None]) -> Callable[[Message], None]:
            self.register_stream_handler(stream_name, func)
            return func

        return decorator
