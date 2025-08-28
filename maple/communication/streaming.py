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


# mapl/communication/streaming.py
# Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

from typing import Dict, Any, Optional, Callable, List
import logging
import uuid
import threading
import queue
import time

from ..core.message import Message
from ..core.result import Result
from ..core.types import Priority

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class StreamOptions:
    """Options for streams."""
    
    def __init__(
        self,
        compression: bool = False,
        chunk_size: str = "1MB",
        buffer_size: str = "10MB"
    ):
        self.compression = compression
        self.chunk_size = chunk_size
        self.buffer_size = buffer_size

class Stream:
    """
    Represents a continuous stream of data between agents.
    """
    
    def __init__(self, agent, name: str, options: Optional[StreamOptions] = None):
        """
        Create a new stream.
        
        Args:
            agent: The agent that owns this stream.
            name: The name of the stream.
            options: Stream options.
        """
        self.agent = agent
        self.name = name
        self.options = options or StreamOptions()
        self.stream_id = str(uuid.uuid4())
        self.closed = False
        self.buffer = queue.Queue()
        self.subscribers = []
        
        # Register the stream with the agent
        self.agent.register_stream_handler(name, self._handle_message)
        
        logger.info(f"Created stream {name} with ID {self.stream_id}")
    
    @classmethod
    def connect(cls, agent, name: str, options: Optional[StreamOptions] = None) -> 'Stream':
        """
        Connect to an existing stream.
        
        Args:
            agent: The agent that wants to connect.
            name: The name of the stream.
            options: Stream options.
        
        Returns:
            A Stream object.
        """
        stream = cls(agent, name, options)
        
        # Subscribe to the stream
        subscription = Message(
            message_type="STREAM_SUBSCRIBE",
            payload={
                'stream_name': name,
                'stream_id': stream.stream_id
            }
        )
        
        # Send the subscription to all agents
        # This is a simplified approach; in a real system, you'd use a discovery mechanism
        agent.broadcast(agent.broker._agent_handlers.keys(), subscription)
        
        logger.info(f"Connected to stream {name}")
        return stream
    
    def send(self, data: Any) -> Result[None, Dict[str, Any]]:
        """
        Send data to the stream.
        
        Args:
            data: The data to send.
        
        Returns:
            A Result indicating success or failure.
        """
        if self.closed:
            return Result.err({
                'errorType': 'STREAM_CLOSED',
                'message': 'Cannot send to a closed stream',
                'details': {
                    'stream_name': self.name,
                    'stream_id': self.stream_id
                }
            })
        
        # Create a message
        message = Message(
            message_type="STREAM_DATA",
            priority=Priority.MEDIUM,
            payload={
                'stream_name': self.name,
                'stream_id': self.stream_id,
                'data': data,
                'timestamp': time.time()
            }
        )
        
        # Send to all subscribers
        for subscriber in self.subscribers:
            subscriber_message = message.with_receiver(subscriber)
            result = self.agent.send(subscriber_message)
            
            if result.is_err():
                logger.warning(f"Failed to send to subscriber {subscriber}: {result.unwrap_err()}")
        
        return Result.ok(None)
    
    def receive(self, timeout: Optional[float] = None) -> Result[Any, Dict[str, Any]]:
        """
        Receive data from the stream.
        
        Args:
            timeout: Timeout in seconds.
        
        Returns:
            A Result containing the data or an error.
        """
        try:
            if timeout is not None:
                data = self.buffer.get(timeout=timeout)
            else:
                data = self.buffer.get()
            
            return Result.ok(data)
        except queue.Empty:
            return Result.err({
                'errorType': 'TIMEOUT',
                'message': 'Timed out waiting for stream data',
                'details': {
                    'stream_name': self.name,
                    'stream_id': self.stream_id,
                    'timeout': timeout
                }
            })
    
    def close(self) -> Result[None, Dict[str, Any]]:
        """
        Close the stream.
        
        Returns:
            A Result indicating success or failure.
        """
        if self.closed:
            return Result.ok(None)  # Already closed
        
        self.closed = True
        
        # Send a close message to all subscribers
        close_message = Message(
            message_type="STREAM_CLOSE",
            priority=Priority.MEDIUM,
            payload={
                'stream_name': self.name,
                'stream_id': self.stream_id
            }
        )
        
        for subscriber in self.subscribers:
            subscriber_message = close_message.with_receiver(subscriber)
            self.agent.send(subscriber_message)
        
        # Unregister the stream handler
        self.agent.stream_handlers.pop(self.name, None)
        
        logger.info(f"Closed stream {self.name}")
        return Result.ok(None)
    
    def _handle_message(self, message: Message) -> None:
        """
        Handle a message received on this stream.
        
        Args:
            message: The message.
        """
        if message.message_type == "STREAM_DATA":
            # Extract the data
            data = message.payload['data']
            
            # Put it in the buffer
            self.buffer.put(data)
        elif message.message_type == "STREAM_SUBSCRIBE":
            # Add the subscriber
            if message.sender not in self.subscribers:
                self.subscribers.append(message.sender)
                logger.info(f"Added subscriber {message.sender} to stream {self.name}")
        elif message.message_type == "STREAM_CLOSE":
            # Mark as closed if it's from the creator
            stream_id = message.payload.get('stream_id')
            if stream_id == self.stream_id:
                self.closed = True
                logger.info(f"Stream {self.name} closed by creator")