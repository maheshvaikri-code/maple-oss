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


# mapl/broker/broker.py
# Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

from typing import Dict, Callable, List, Optional, Any
import threading
import time
import logging
import uuid
import json

class SecurityError(Exception):
    """Exception raised for security-related errors."""
    pass

from ..core.message import Message
from ..agent.config import Config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MessageBroker:
    """
    Message broker for MAPL agent communication.
    
    This is a simple in-memory implementation for development/testing.
    Production implementations would use more robust messaging systems
    like RabbitMQ, Kafka, or NATS.
    """
    
    # Class-level storage for the broker
    _instance = None
    _lock = threading.Lock()
    
    # Shared broker state
    _agent_queues: Dict[str, List[Message]] = {}
    _agent_handlers: Dict[str, List[Callable[[Message], None]]] = {}
    _temp_handlers: Dict[str, List[Callable[[Message], None]]] = {}
    _topic_subscribers: Dict[str, List[str]] = {}
    _topic_handlers: Dict[str, Dict[str, Callable[[str, Message], None]]] = {}
    
    def __new__(cls, config: Config):
        """Create or return a singleton instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(MessageBroker, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self, config: Config):
        """Initialize the broker."""
        # Only initialize once
        if self._initialized:
            return
        
        self.config = config
        self.running = False
        self.delivery_thread = None
        self.security_config = getattr(config, 'security', None)
        # Initialize link manager if security is enabled
        self.link_manager = None
        if self.security_config:
            try:
                from ..security.link import LinkManager
                self.link_manager = LinkManager()
            except ImportError:
                logger.warning("Link manager not available - security features disabled")
        self._initialized = True
        logger.info("MessageBroker initialized")
    
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
        if self.delivery_thread:
            self.delivery_thread.join(timeout=5.0)
        logger.info("Disconnected from broker")
    
    def send(self, message: Message) -> str:
        """Send a message to a specific agent with optional link validation."""
        logger.debug(f"Sending message of type {message.message_type} to {message.receiver}")
        
        # Ensure the message has an ID
        if not message.message_id:
            message.message_id = str(uuid.uuid4())
        
        # Check if link validation is required
        if self.security_config and getattr(self.security_config, 'require_links', False):
            if self.link_manager:
                link_id = message.get_link_id()
                
                # If no link ID is provided, check if there's an existing link
                if not link_id:
                    links_result = self.link_manager.get_links_for_agent(message.sender)
                    if links_result.is_ok():
                        links = links_result.unwrap()
                        for link in links:
                            if link.agent_a == message.receiver or link.agent_b == message.receiver:
                                # Use existing link
                                message = message.with_link(link.link_id)
                                link_id = link.link_id
                                break
                
                # If still no link ID and strict policy, reject message
                if not link_id and getattr(self.security_config, 'strict_link_policy', False):
                    raise SecurityError("No valid link exists between sender and receiver")
                
                # Validate the link if one is provided
                if link_id:
                    link_result = self.link_manager.validate_link(
                        link_id, message.sender, message.receiver)
                    
                    if link_result.is_err():
                        error = link_result.unwrap_err()
                        raise SecurityError(f"Link validation failed: {error['message']}")
        
        # Check if the receiver exists
        if message.receiver not in self._agent_queues:
            self._agent_queues[message.receiver] = []
        
        # Add the message to the receiver's queue
        self._agent_queues[message.receiver].append(message)
        
        logger.debug(f"Message {message.message_id} queued for delivery to {message.receiver}")
        return str(message.message_id)  # Ensure we always return a string
    
    def publish(self, topic: str, message: Message) -> str:
        """Publish a message to a topic."""
        logger.debug(f"Publishing message of type {message.message_type} to topic {topic}")
        
        # Ensure the message has an ID
        if not message.message_id:
            message.message_id = str(uuid.uuid4())
        
        # Get subscribers for this topic
        subscribers = self._topic_subscribers.get(topic, [])
        
        # Send the message to all subscribers
        for subscriber in subscribers:
            if subscriber not in self._agent_queues:
                self._agent_queues[subscriber] = []
            
            # Create a copy of the message for each subscriber
            subscriber_message = Message(
                message_id=message.message_id,
                timestamp=message.timestamp,
                sender=message.sender,
                receiver=subscriber,
                priority=message.priority,
                message_type=message.message_type,
                payload=message.payload,
                metadata={**message.metadata, 'topic': topic}
            )
            
            self._agent_queues[subscriber].append(subscriber_message)
        
        logger.debug(f"Message {message.message_id} published to topic {topic} with {len(subscribers)} subscribers")
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
    
    def subscribe_temporary(self, agent_id: str, handler: Callable[[Message], None]) -> None:
        """Subscribe a temporary handler for an agent."""
        logger.debug(f"Subscribing temporary handler for agent {agent_id}")
        
        with self._lock:
            if agent_id not in self._temp_handlers:
                self._temp_handlers[agent_id] = []
            
            self._temp_handlers[agent_id].append(handler)
        
        logger.debug(f"Temporary handler subscribed for agent {agent_id}")
    
    def unsubscribe_temporary(self, agent_id: str, handler: Callable[[Message], None]) -> None:
        """Unsubscribe a temporary handler for an agent."""
        logger.debug(f"Unsubscribing temporary handler for agent {agent_id}")
        
        with self._lock:
            if agent_id in self._temp_handlers:
                if handler in self._temp_handlers[agent_id]:
                    self._temp_handlers[agent_id].remove(handler)
        
        logger.debug(f"Temporary handler unsubscribed for agent {agent_id}")
    
    def subscribe_topic(self, topic: str, handler: Callable[[str, Message], None], agent_id: Optional[str] = None) -> None:
        """Subscribe to a topic."""
        logger.debug(f"Subscribing to topic {topic}")
        
        if not agent_id:
            # Infer agent_id from the calling context if not provided
            import inspect
            frame = inspect.currentframe().f_back
            while frame:
                if 'self' in frame.f_locals and hasattr(frame.f_locals['self'], 'agent_id'):
                    agent_id = frame.f_locals['self'].agent_id
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
            if topic in self._topic_subscribers and agent_id in self._topic_subscribers[topic]:
                self._topic_subscribers[topic].remove(agent_id)
            
            if topic in self._topic_handlers and agent_id in self._topic_handlers[topic]:
                del self._topic_handlers[topic][agent_id]
        
        logger.debug(f"Agent {agent_id} unsubscribed from topic {topic}")
    
    def _message_delivery_loop(self) -> None:
        """Background thread for delivering messages."""
        logger.info("Message delivery loop started")
        
        while self.running:
            try:
                # Sleep briefly to avoid spinning
                time.sleep(0.01)
                
                # Make a copy of the queue state to avoid holding the lock during delivery
                with self._lock:
                    queues = {agent_id: list(queue) for agent_id, queue in self._agent_queues.items()}
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
    


    # Link validation integrated into main send method above

    def _deliver_message(self, agent_id: str, message: Message) -> None:
        """Deliver a message to an agent."""
        logger.debug(f"Delivering message {message.message_id} to agent {agent_id}")
        
        try:
            # Deliver to temporary handlers first
            temp_handlers = self._temp_handlers.get(agent_id, [])
            for handler in temp_handlers:
                try:
                    handler(message)
                except Exception as e:
                    logger.error(f"Error in temporary handler: {str(e)}")
            
            # Then deliver to regular handlers
            handlers = self._agent_handlers.get(agent_id, [])
            for handler in handlers:
                try:
                    handler(message)
                except Exception as e:
                    logger.error(f"Error in handler: {str(e)}")
            
            # Check if this is a topic message
            if 'topic' in message.metadata:
                topic = message.metadata['topic']
                if topic in self._topic_handlers and agent_id in self._topic_handlers[topic]:
                    try:
                        self._topic_handlers[topic][agent_id](topic, message)
                    except Exception as e:
                        logger.error(f"Error in topic handler: {str(e)}")
        except Exception as e:
            logger.error(f"Error delivering message: {str(e)}")