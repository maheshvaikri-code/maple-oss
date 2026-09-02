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
"""
MAPLE Message System
Created by: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

Core message handling for MAPLE's perfect communication protocol.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union

from .types import AgentID, MessageID, Priority, TypeValidator


class Message:
    """
    MAPLE message with standardized structure.
    """

    def __init__(
        self,
        message_type: str,
        receiver: Optional[Union[str, AgentID]] = None,
        priority: Priority = Priority.MEDIUM,
        payload: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        message_id: Optional[Union[str, MessageID]] = None,
        sender: Optional[Union[str, AgentID]] = None,
        timestamp: Optional[datetime] = None,
    ) -> None:
        # Validate and set message ID
        if message_id is None:
            self.message_id = MessageID()
        elif isinstance(message_id, str):
            self.message_id = MessageID(message_id)
        else:
            self.message_id = message_id

        # Set timestamp. datetime.utcnow() is deprecated (Python 3.12+); this is the
        # non-deprecated equivalent that keeps the SAME naive-UTC value, so the
        # `.isoformat() + "Z"` serialization below is unchanged (owner may modernize to
        # timezone-aware datetimes separately -- see the improvements doc).
        self.timestamp = timestamp or datetime.now(timezone.utc).replace(tzinfo=None)

        # Validate and set sender/receiver
        self.sender = self._validate_agent_id(sender) if sender else None
        self.receiver = self._validate_agent_id(receiver) if receiver else None

        # Validate priority
        if isinstance(priority, str):
            self.priority = Priority(priority)
        else:
            self.priority = priority

        # Validate message type
        self.message_type = TypeValidator.validate_string(
            message_type, max_len=128
        ).upper()

        # Set payload and metadata
        self.payload = payload or {}
        self.metadata = metadata or {}

    def _validate_agent_id(self, agent_id: Union[str, AgentID]) -> str:
        """Validate and normalize agent ID."""
        if isinstance(agent_id, AgentID):
            return agent_id.id
        elif isinstance(agent_id, str):
            if AgentID.validate(agent_id):
                return agent_id
            raise ValueError(f"Invalid agent ID: {agent_id}")
        else:
            raise TypeError(f"Expected AgentID or str, got {type(agent_id)}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary for serialization."""
        return {
            "header": {
                "messageId": str(self.message_id),
                "timestamp": self.timestamp.isoformat() + "Z",
                "sender": self.sender,
                "receiver": self.receiver,
                "priority": self.priority.value,
                "messageType": self.message_type,
            },
            "payload": self.payload,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """Create message from dictionary."""
        header = data.get("header", {})

        # Parse timestamp
        timestamp_str = header.get("timestamp")
        timestamp = None
        if timestamp_str:
            # Remove 'Z' suffix and parse
            if timestamp_str.endswith("Z"):
                timestamp_str = timestamp_str[:-1]
            timestamp = datetime.fromisoformat(timestamp_str)

        return cls(
            message_id=header.get("messageId"),
            timestamp=timestamp,
            sender=header.get("sender"),
            receiver=header.get("receiver"),
            priority=Priority(header.get("priority", "MEDIUM")),
            message_type=header.get("messageType"),
            payload=data.get("payload", {}),
            metadata=data.get("metadata", {}),
        )

    def to_json(self) -> str:
        """Convert message to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, json_str: str) -> "Message":
        """Create message from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)

    def with_receiver(self, receiver: Union[str, AgentID]) -> "Message":
        """Create a copy with different receiver."""
        return Message(
            message_id=str(self.message_id),
            timestamp=self.timestamp,
            sender=self.sender,
            receiver=receiver,
            priority=self.priority,
            message_type=self.message_type,
            payload=self.payload.copy(),
            metadata=self.metadata.copy(),
        )

    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata to the message."""
        self.metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata value."""
        return self.metadata.get(key, default)

    @classmethod
    def error(
        cls,
        error_type: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        severity: str = "HIGH",
        recoverable: bool = False,
        receiver: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> "Message":
        """Create an error message."""
        metadata = {}
        if correlation_id:
            metadata["correlationId"] = correlation_id

        return cls(
            message_type="ERROR",
            receiver=receiver,
            priority=Priority.HIGH,
            payload={
                "errorType": error_type,
                "message": message,
                "details": details or {},
                "severity": severity,
                "recoverable": recoverable,
            },
            metadata=metadata,
        )

    @classmethod
    def ack(
        cls, correlation_id: Optional[str] = None, receiver: Optional[str] = None
    ) -> "Message":
        """Create an acknowledgment message."""
        metadata = {}
        if correlation_id:
            metadata["correlationId"] = correlation_id

        return cls(
            message_type="ACK",
            receiver=receiver,
            priority=Priority.MEDIUM,
            payload={},
            metadata=metadata,
        )

    def __repr__(self) -> str:
        return (
            f"Message(type={self.message_type}, "
            f"id={self.message_id}, "
            f"sender={self.sender}, "
            f"receiver={self.receiver})"
        )

    def with_link(self, link_id: str) -> "Message":
        """Create a copy of this message with a link ID."""
        new_message = Message(
            message_id=str(self.message_id),
            timestamp=self.timestamp,
            sender=self.sender,
            receiver=self.receiver,
            priority=self.priority,
            message_type=self.message_type,
            payload=self.payload.copy(),
            metadata={**self.metadata, "linkId": link_id},
        )
        return new_message

    def get_link_id(self) -> Optional[str]:
        """Get the link ID for this message, if any."""
        return self.metadata.get("linkId")

    class Builder:
        """Builder pattern for creating messages."""

        def __init__(self) -> None:
            self._message_id: Optional[str] = None
            self._timestamp: Optional[datetime] = None
            self._sender: Optional[str] = None
            self._receiver: Optional[str] = None
            self._priority = Priority.MEDIUM
            self._message_type: Optional[str] = None
            self._payload: Dict[str, Any] = {}
            self._metadata: Dict[str, Any] = {}

        def message_id(self, message_id: str) -> "Message.Builder":
            self._message_id = message_id
            return self

        def timestamp(self, timestamp: datetime) -> "Message.Builder":
            self._timestamp = timestamp
            return self

        def sender(self, sender: str) -> "Message.Builder":
            self._sender = sender
            return self

        def receiver(self, receiver: str) -> "Message.Builder":
            self._receiver = receiver
            return self

        def priority(self, priority: Priority) -> "Message.Builder":
            self._priority = priority
            return self

        def message_type(self, message_type: str) -> "Message.Builder":
            self._message_type = message_type
            return self

        def payload(self, payload: Dict[str, Any]) -> "Message.Builder":
            self._payload = payload
            return self

        def metadata(self, metadata: Dict[str, Any]) -> "Message.Builder":
            self._metadata = metadata
            return self

        def correlation_id(self, correlation_id: str) -> "Message.Builder":
            self._metadata["correlationId"] = correlation_id
            return self

        def build(self) -> "Message":
            if not self._message_type:
                raise ValueError("Message type is required")

            return Message(
                message_id=self._message_id,
                timestamp=self._timestamp,
                sender=self._sender,
                receiver=self._receiver,
                priority=self._priority,
                message_type=self._message_type,
                payload=self._payload,
                metadata=self._metadata,
            )

    @classmethod
    def builder(cls) -> Builder:
        """Create a message builder."""
        return cls.Builder()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Message):
            return False
        return (
            self.message_id == other.message_id
            and self.message_type == other.message_type
            and self.sender == other.sender
            and self.receiver == other.receiver
            and self.payload == other.payload
        )
