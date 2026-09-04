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
"""A file-backed broker: multi-process on one host (ADR-167).

Until this existed MAPLE was a single-process runtime. This is the second
implementation of the ``Broker`` contract, which is what makes the contract a
contract rather than a description of one class.

    agent = Agent(Config(agent_id="w", broker_url="file:///var/run/maple/spool"))

**Exclusion is by lock, not by rename.** Claim-by-``os.rename`` is the obvious
primitive and it was measured misbehaving across processes on a supported
platform - two racers each told they had won, 192 times in 200. MAPLE already
ships ``_InterProcessFileLock`` (``msvcrt.locking`` / ``fcntl.flock``), it
already backs ``FileTaskQueue``, and it was measured giving real mutual
exclusion on the same machine: 4 processes x 150 increments, zero lost updates.

**Latency is a poll interval, not a signal.** A condition variable does not
cross processes (ADR-166). On one host, prefer the in-memory broker; this one
trades latency for reach.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional
from urllib.parse import unquote, urlparse

from ..core.message import Message
from ..error.types import BrokerOverflowError
from ..resources.lease import _InterProcessFileLock
from .contract import BrokerCapabilities

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ..agent.config import Config

logger = logging.getLogger(__name__)

__all__ = ["FileBroker", "spool_path_from_url"]


def spool_path_from_url(broker_url: str) -> Path:
    """Turn ``file:///path/to/spool`` into a filesystem path.

    Accepts the POSIX form and the Windows form (``file:///C:/spool``), and
    tolerates a bare path so a caller can pass a directory directly.
    """
    text = (broker_url or "").strip()
    if not text:
        raise ValueError("a file broker needs a spool directory")
    if "://" not in text:
        return Path(text).expanduser()

    parsed = urlparse(text)
    raw = unquote(parsed.path or "")
    if parsed.netloc:
        # file://host/share - keep it as a UNC-ish path rather than dropping it
        raw = "//" + parsed.netloc + raw
    # /C:/spool -> C:/spool
    if os.name == "nt" and len(raw) > 2 and raw[0] == "/" and raw[2] == ":":
        raw = raw[1:]
    if not raw:
        raise ValueError(f"no spool directory in broker_url {broker_url!r}")
    return Path(raw).expanduser()


class FileBroker:
    """A broker whose queue is a directory (ADR-167)."""

    #: Declared honestly. `durable` is False: messages are files and so
    #: outlive a process, but there is no replication, no ordering across
    #: agents, and no exactly-once claim - and a capability flag is a promise.
    CAPABILITIES = BrokerCapabilities(
        enforces_security_policy=False,
        applies_backpressure=True,
        reports_undeliverable=True,
        supports_routability_check=True,
        durable=False,
        cross_process=True,
    )
    #: This transport does not implement SecurityConfig, and ADR-157 refuses a
    #: transport that accepts controls it will ignore. Saying so here is what
    #: makes that refusal happen instead of a silent downgrade.
    ENFORCES_SECURITY_POLICY = False

    #: How often the delivery loop looks at the spool.
    POLL_SECONDS = 0.02
    #: How long a subscriber's presence file stays valid without a refresh. A
    #: crashed process's messages become undeliverable once this expires,
    #: rather than filling an inbox nobody reads.
    PRESENCE_TTL_SECONDS = 5.0
    #: A message is not judged undeliverable before this, so a subscriber
    #: starting a moment later is not raced. Must stay well under the 0.4s the
    #: conformance suite allows for undeliverable reporting.
    UNDELIVERABLE_GRACE_SECONDS = 0.05
    #: Bound on how long any spool mutation waits for the lock.
    LOCK_TIMEOUT_SECONDS = 10.0

    def __init__(self, config: "Config") -> None:
        self.config = config
        self.root = spool_path_from_url(getattr(config, "broker_url", "") or "")
        self.agents_dir = self.root / "agents"
        self.inbox_dir = self.root / "inbox"
        self.topics_dir = self.root / "topics"
        for directory in (self.root, self.agents_dir, self.inbox_dir, self.topics_dir):
            directory.mkdir(parents=True, exist_ok=True)
        self._lock_path = self.root / "spool.lock"

        performance = getattr(config, "performance", None)
        self.max_queue_size = int(
            getattr(performance, "max_queue_size", 10000) or 10000
        )
        self.max_message_bytes = int(
            getattr(performance, "max_message_bytes", 1_048_576) or 1_048_576
        )

        self.running = False
        self.delivery_thread: Optional[threading.Thread] = None
        self._local = threading.RLock()
        self._handlers: Dict[str, Callable[[Message], None]] = {}
        self._topic_handlers: Dict[str, Dict[str, Callable[[str, Message], None]]] = {}
        self._undeliverable_handler: Optional[Callable[[str, Message], None]] = None
        self._separation_policy: Any = None

        self._delivered = 0
        self._undeliverable = 0
        self._refused = 0
        self._sent = 0
        self._instance = uuid.uuid4().hex

    # ---------------------------------------------------------------- locking

    def _spool_lock(self) -> _InterProcessFileLock:
        return _InterProcessFileLock(self._lock_path, self.LOCK_TIMEOUT_SECONDS)

    # --------------------------------------------------------------- presence

    def _presence_path(self, agent_id: str) -> Path:
        """This process's presence file for an agent.

        Per *instance*, not per agent: several processes may serve the same
        agent id - that is the competing-consumers case this transport exists
        for - and a shared path means concurrent writers. On Windows
        ``os.replace`` onto a destination another process holds open fails
        with ``PermissionError``, which CI caught and a local run did not.
        """
        return self.agents_dir / f"{_safe_name(agent_id)}.{self._instance}.live"

    def _presence_glob(self, agent_id: str) -> str:
        return f"{_safe_name(agent_id)}.*.live"

    def _touch_presence(self, agent_id: str) -> None:
        path = self._presence_path(agent_id)
        payload = json.dumps({"agent": agent_id, "instance": self._instance})
        _atomic_write(path, payload)

    def _is_present(self, agent_id: str) -> bool:
        """Whether some process is currently serving this agent.

        Presence is what makes "undeliverable" decidable across processes. An
        empty inbox cannot distinguish *nobody is listening* from *nobody has
        looked yet* (ADR-167).
        """
        now = time.time()
        try:
            candidates = list(self.agents_dir.glob(self._presence_glob(agent_id)))
        except OSError:
            return False
        for path in candidates:
            try:
                age = now - path.stat().st_mtime
            except OSError:
                continue
            if age <= self.PRESENCE_TTL_SECONDS:
                return True
        return False

    # ------------------------------------------------------------------ paths

    def _inbox(self, agent_id: str) -> Path:
        return self.inbox_dir / _safe_name(agent_id)

    def _pending_count(self, agent_id: str) -> int:
        try:
            return sum(1 for _ in self._inbox(agent_id).glob("*.json"))
        except OSError:
            return 0

    # ---------------------------------------------------------------- lifecycle

    def connect(self) -> None:
        """Start delivering. Idempotent."""
        with self._local:
            if self.running:
                return
            self.running = True
            self.delivery_thread = threading.Thread(
                target=self._delivery_loop, daemon=True
            )
            self.delivery_thread.start()
        logger.info("FileBroker connected to spool %s", self.root)

    def disconnect(self) -> None:
        """Stop delivering and drop presence. Safe before connect, and
        idempotent."""
        with self._local:
            was_running = self.running
            self.running = False
            thread = self.delivery_thread
            self.delivery_thread = None
            agents = list(self._handlers)
        if thread is not None:
            thread.join(timeout=5.0)
        for agent_id in agents:
            _remove(self._presence_path(agent_id))
        if was_running:
            logger.info("FileBroker disconnected from spool %s", self.root)

    # -------------------------------------------------------------- subscribe

    def subscribe(self, agent_id: str, handler: Callable[[Message], None]) -> None:
        with self._local:
            self._handlers[agent_id] = handler
        self._inbox(agent_id).mkdir(parents=True, exist_ok=True)
        self._touch_presence(agent_id)

    def unsubscribe(self, agent_id: str) -> None:
        """Stop serving an agent. Idempotent."""
        with self._local:
            self._handlers.pop(agent_id, None)
        _remove(self._presence_path(agent_id))

    def subscribe_topic(
        self,
        topic: str,
        handler: Callable[[str, Message], None],
        agent_id: Optional[str] = None,
    ) -> None:
        name = agent_id or f"anon-{uuid.uuid4().hex[:8]}"
        with self._local:
            self._topic_handlers.setdefault(topic, {})[name] = handler
        _atomic_write(
            self.topics_dir
            / f"{_safe_name(topic)}__{_safe_name(name)}.{self._instance}.sub",
            json.dumps({"topic": topic, "agent": name}),
        )
        self._inbox(name).mkdir(parents=True, exist_ok=True)
        self._touch_presence(name)

    def unsubscribe_topic(self, topic: str, agent_id: str) -> None:
        with self._local:
            self._topic_handlers.get(topic, {}).pop(agent_id, None)
        _remove(
            self.topics_dir
            / f"{_safe_name(topic)}__{_safe_name(agent_id)}.{self._instance}.sub"
        )

    def is_routable(self, agent_id: str) -> bool:
        if not agent_id or not str(agent_id).strip():
            return False
        return self._is_present(str(agent_id))

    # ------------------------------------------------------------------- send

    def send(self, message: Message) -> str:
        self._enforce_message_size(message)
        if not message.message_id:
            message.message_id = str(uuid.uuid4())  # type: ignore[assignment]

        if self._separation_policy is not None:
            result = self._separation_policy.authorize_send(message)
            if result.is_err():
                from ..error.types import SecurityError

                raise SecurityError(
                    f"Separation-of-duties denied: {result.unwrap_err()['message']}"
                )

        receiver = str(message.receiver or "")
        with self._spool_lock():
            pending = self._pending_count(receiver)
            if pending >= self.max_queue_size:
                self._refused += 1
                raise BrokerOverflowError(
                    {
                        "errorType": "QUEUE_FULL",
                        "message": (
                            "Spool queue is at capacity; refusing the message "
                            "rather than buffering without a bound."
                        ),
                        "details": {
                            "receiver": receiver,
                            "maxQueueSize": self.max_queue_size,
                            "pending": pending,
                        },
                    }
                )
            self._write_message(receiver, message)
        self._sent += 1
        return str(message.message_id)

    def publish(self, topic: str, message: Message) -> str:
        """Fan a message out to a topic's subscribers."""
        self._enforce_message_size(message)
        if not message.message_id:
            message.message_id = str(uuid.uuid4())  # type: ignore[assignment]

        prefix = f"{_safe_name(topic)}__"
        with self._spool_lock():
            seen = set()
            subscribers = []
            for path in self.topics_dir.glob(f"{prefix}*.sub"):
                try:
                    agent = json.loads(path.read_text("utf-8"))["agent"]
                except (OSError, ValueError, KeyError):
                    continue
                # One agent may be served by several processes; it still gets
                # the message once.
                if agent not in seen:
                    seen.add(agent)
                    subscribers.append(agent)
            for agent_id in subscribers:
                fanned = message.with_receiver(agent_id)
                fanned.metadata = {**(message.metadata or {}), "topic": topic}
                self._write_message(agent_id, fanned, topic=topic)
        return str(message.message_id)

    def _write_message(
        self, receiver: str, message: Message, topic: Optional[str] = None
    ) -> None:
        """Write one message file. Caller holds the spool lock."""
        inbox = self._inbox(receiver)
        inbox.mkdir(parents=True, exist_ok=True)
        name = f"{time.time():017.6f}-{uuid.uuid4().hex}.json"
        body = json.dumps(
            {
                "receiver": receiver,
                "topic": topic,
                "message": json.loads(message.to_json()),
            }
        )
        _atomic_write(inbox / name, body)

    def _enforce_message_size(self, message: Message) -> None:
        """Refuse an oversized payload at the edge, as the in-memory broker
        does (ADR-159): a bounded file count is no protection if one message
        can be arbitrarily large."""
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

    # --------------------------------------------------------------- delivery

    def _delivery_loop(self) -> None:
        logger.info("FileBroker delivery loop started for %s", self.root)
        while self.running:
            try:
                self._refresh_presence()
                claimed = self._claim_batch()
                for receiver, topic, message in claimed:
                    self._dispatch(receiver, topic, message)
                self._reap_undeliverable()
            except Exception:  # noqa: BLE001 - delivery must not die
                logger.exception("FileBroker delivery loop error")
            time.sleep(self.POLL_SECONDS)

    def _refresh_presence(self) -> None:
        with self._local:
            agents = list(self._handlers) + [
                name for subs in self._topic_handlers.values() for name in subs
            ]
        for agent_id in agents:
            self._touch_presence(agent_id)

    def _claim_batch(self) -> List[Any]:
        """Take this process's messages out of the spool, under the lock.

        Reading and removing happen together so no other process can see the
        same message. Handlers run afterwards, outside the lock, so a slow
        handler cannot block the spool.
        """
        with self._local:
            mine = list(self._handlers) + [
                name for subs in self._topic_handlers.values() for name in subs
            ]
        if not mine:
            return []

        claimed: List[Any] = []
        with self._spool_lock():
            for agent_id in mine:
                inbox = self._inbox(agent_id)
                try:
                    files = sorted(inbox.glob("*.json"))
                except OSError:
                    continue
                for path in files:
                    record = _read_json(path)
                    _remove(path)
                    if record is None:
                        continue
                    try:
                        message = Message.from_dict(record["message"])
                    except Exception:  # noqa: BLE001 - a corrupt file is not fatal
                        logger.warning("Discarding unreadable spool file %s", path)
                        continue
                    claimed.append((agent_id, record.get("topic"), message))
        return claimed

    def _dispatch(self, receiver: str, topic: Optional[str], message: Message) -> None:
        with self._local:
            handler = self._handlers.get(receiver)
            topic_handler = (
                self._topic_handlers.get(topic, {}).get(receiver) if topic else None
            )
        try:
            if topic_handler is not None:
                topic_handler(topic, message)  # type: ignore[arg-type]
                self._delivered += 1
            elif handler is not None:
                handler(message)
                self._delivered += 1
            else:
                self._count_undeliverable(receiver, message)
        except Exception:  # noqa: BLE001 - a handler must not kill delivery
            logger.exception("Handler for %s raised", receiver)

    def _reap_undeliverable(self) -> None:
        """Dead-letter messages for agents nobody is serving.

        Done under the lock so exactly one process reaps each message, and
        only after a grace period so a subscriber starting a moment later is
        not raced.
        """
        now = time.time()
        with self._spool_lock():
            try:
                inboxes = [p for p in self.inbox_dir.iterdir() if p.is_dir()]
            except OSError:
                return
            stranded = []
            for inbox in inboxes:
                agent_id = inbox.name
                if self._is_present(agent_id):
                    continue
                try:
                    files = sorted(inbox.glob("*.json"))
                except OSError:
                    continue
                for path in files:
                    try:
                        age = now - path.stat().st_mtime
                    except OSError:
                        continue
                    if age < self.UNDELIVERABLE_GRACE_SECONDS:
                        continue
                    record = _read_json(path)
                    _remove(path)
                    if record is None:
                        continue
                    stranded.append((agent_id, record))

        for agent_id, record in stranded:
            try:
                message = Message.from_dict(record["message"])
            except Exception:  # noqa: BLE001
                continue
            self._count_undeliverable(record.get("receiver", agent_id), message)

    def _count_undeliverable(self, receiver: str, message: Message) -> None:
        self._undeliverable += 1
        logger.warning("No handler for %s; message dead-lettered", receiver)
        hook = self._undeliverable_handler
        if hook is not None:
            try:
                hook(receiver, message)
            except Exception:  # noqa: BLE001 - a bad hook is not fatal
                logger.exception("Undeliverable handler raised")

    # ------------------------------------------------------------------ hooks

    def set_undeliverable_handler(
        self, handler: Optional[Callable[[str, Message], None]]
    ) -> None:
        self._undeliverable_handler = handler

    def set_separation_policy(self, policy: Any) -> None:
        self._separation_policy = policy

    # ------------------------------------------------------------ statistics

    def get_statistics(self) -> Dict[str, Any]:
        pending = 0
        try:
            for inbox in self.inbox_dir.iterdir():
                if inbox.is_dir():
                    pending += sum(1 for _ in inbox.glob("*.json"))
        except OSError:
            pass
        with self._local:
            subscribed = len(self._handlers)
        return {
            "delivered": self._delivered,
            "undeliverable": self._undeliverable,
            "refused": self._refused,
            "sent": self._sent,
            "pendingSpool": pending,
            "maxQueueSize": self.max_queue_size,
            "maxMessageBytes": self.max_message_bytes,
            "subscribedAgents": subscribed,
        }


# ------------------------------------------------------------------ helpers


def _safe_name(value: str) -> str:
    """A filesystem-safe stand-in for an agent id or topic."""
    text = str(value)
    keep = "".join(c if (c.isalnum() or c in "-_.") else "_" for c in text)
    return keep[:120] or "_"


def _atomic_write(path: Path, text: str) -> None:
    """Write via a temporary file so a reader never sees a partial record."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    with tmp.open("w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text("utf-8"))  # type: ignore[no-any-return]
    except (OSError, ValueError):
        return None


def _remove(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass
