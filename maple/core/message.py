"""
Copyright (C) 2025 Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

This file is part of MAPLE - Multi Agent Protocol Language Engine. 

MAPLE - Multi Agent Protocol Language Engine is free software: you can redistribute it and/or 
modify it under the terms of the GNU Affero General Public License as published by the Free Software 
Foundation, either version 3 of the License, or (at your option) any later version. 
MAPLE - Multi Agent Protocol Language Engine is distributed in the hope that it will be useful, 
but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A 
PARTICULAR PURPOSE. See the GNU Affero General Public License for more details. You should have 
received a copy of the GNU Affero General Public License along with MAPLE - Multi Agent Protocol 
Language Engine. If not, see <https://www.gnu.org/licenses/>.
"""


# maple/core/message.py
# Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

from typing import Any, Dict, Optional
from datetime import datetime
import uuid
import json

from .types import Priority, AgentID, MessageID, Timestamp

class Message:
    """
    Represents a MAPLE message with standardized structure.
    """
    
    def __init__(
        self,
        message_type: str,
        receiver: Optional[str] = None,
        priority: Priority = Priority.MEDIUM,
        payload: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        message_id: Optional[str] = None,
        sender: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ):
        self.message_id = message_id or str(uuid.uuid4())
        self.timestamp = timestamp or datetime.utcnow()
        self.sender = sender
        self.receiver = receiver
        self.priority = priority
        self.message_type = message_type
        self.payload = payload or {}
        self.metadata = metadata or {}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """Create a message from a dictionary."""
        header = data.get('header', {})
        
        return cls(
            message_id=header.get('messageId'),
            timestamp=Timestamp.validate(header.get('timestamp')) if 'timestamp' in header else None,
            sender=header.get('sender'),
            receiver=header.get('receiver'),
            priority=Priority(header.get('priority', 'MEDIUM')),
            message_type=header.get('messageType'),
            payload=data.get('payload', {}),
            metadata=data.get('metadata', {})
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the message to a dictionary."""
        return {
            'header': {
                'messageId': self.message_id,
                'timestamp': self.timestamp.isoformat() + 'Z',
                'sender': self.sender,
                'receiver': self.receiver,
                'priority': self.priority.value,
                'messageType': self.message_type
            },
            'payload': self.payload,
            'metadata': self.metadata
        }
    
    def to_json(self) -> str:
        """Convert the message to a JSON string."""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Message':
        """Create a message from a JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def with_receiver(self, receiver: str) -> 'Message':
        """Create a new message with a different receiver."""
        new_message = Message(
            message_id=self.message_id,
            timestamp=self.timestamp,
            sender=self.sender,
            receiver=receiver,
            priority=self.priority,
            message_type=self.message_type,
            payload=self.payload,
            metadata=self.metadata
        )
        return new_message
    
    @classmethod
    def error(
        cls,
        error_type: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        severity: str = "HIGH",
        recoverable: bool = False,
        suggestion: Optional[Dict[str, Any]] = None,
        receiver: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> 'Message':
        """Create an error message."""
        metadata = {}
        if correlation_id:
            metadata['correlationId'] = correlation_id
        
        return cls(
            message_type="ERROR",
            receiver=receiver,
            priority=Priority.HIGH,
            payload={
                'errorType': error_type,
                'message': message,
                'details': details or {},
                'severity': severity,
                'recoverable': recoverable,
                'suggestion': suggestion or {}
            },
            metadata=metadata
        )
    
    @classmethod
    def ack(cls, correlation_id: Optional[str] = None) -> 'Message':
        """Create an acknowledgment message."""
        metadata = {}
        if correlation_id:
            metadata['correlationId'] = correlation_id
        
        return cls(
            message_type="ACK",
            priority=Priority.MEDIUM,
            payload={},
            metadata=metadata
        )
    
    
    def with_link(self, link_id: str) -> 'Message':
        """Create a copy of this message with a link ID."""
        new_message = Message(
            message_id=self.message_id,
            timestamp=self.timestamp,
            sender=self.sender,
            receiver=self.receiver,
            priority=self.priority,
            message_type=self.message_type,
            payload=self.payload,
            metadata={**self.metadata, 'linkId': link_id}
        )
        return new_message
    
    def get_link_id(self) -> Optional[str]:
        """Get the link ID for this message, if any."""
        return self.metadata.get('linkId')
    

    class Builder:
        """Builder for creating messages."""
        
        def __init__(self):
            self._message_id = None
            self._timestamp = None
            self._sender = None
            self._receiver = None
            self._priority = Priority.MEDIUM
            self._message_type = None
            self._payload = {}
            self._metadata = {}
        
        def message_id(self, message_id: str) -> 'Message.Builder':
            self._message_id = message_id
            return self
        
        def timestamp(self, timestamp: datetime) -> 'Message.Builder':
            self._timestamp = timestamp
            return self
        
        def sender(self, sender: str) -> 'Message.Builder':
            self._sender = sender
            return self
        
        def receiver(self, receiver: str) -> 'Message.Builder':
            self._receiver = receiver
            return self
        
        def priority(self, priority: Priority) -> 'Message.Builder':
            self._priority = priority
            return self
        
        def message_type(self, message_type: str) -> 'Message.Builder':
            self._message_type = message_type
            return self
        
        def payload(self, payload: Dict[str, Any]) -> 'Message.Builder':
            self._payload = payload
            return self
        
        def metadata(self, metadata: Dict[str, Any]) -> 'Message.Builder':
            self._metadata = metadata
            return self
        
        def correlation_id(self, correlation_id: str) -> 'Message.Builder':
            if 'correlationId' not in self._metadata:
                self._metadata['correlationId'] = correlation_id
            return self
        
        def build(self) -> 'Message':
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
                metadata=self._metadata
            )
    
    @classmethod
    def builder(cls) -> Builder:
        """Create a message builder."""
        return cls.Builder()