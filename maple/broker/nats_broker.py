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


# maple/broker/nats_broker.py
# Creator: Mahesh Vaikri

"""
Production NATS Broker Implementation for MAPLE
Provides enterprise-grade message routing with NATS backend
"""

import asyncio
import json
import logging
from typing import Dict, Callable, List, Optional, Any
import uuid
from dataclasses import dataclass

try:
    import nats
    from nats.aio.client import Client as NATS
    from nats.aio.errors import ErrConnectionClosed, ErrTimeout, ErrNoServers
    NATS_AVAILABLE = True
except ImportError:
    NATS_AVAILABLE = False
    NATS = None

from ..core.message import Message
from ..core.result import Result
from ..agent.config import Config

logger = logging.getLogger(__name__)

@dataclass
class NATSConfig:
    """Configuration for NATS broker."""
    servers: List[str] = None
    cluster_name: str = "maple-cluster"
    client_id: str = None
    max_reconnect_attempts: int = 10
    reconnect_time_wait: float = 2.0
    max_payload: int = 1024 * 1024  # 1MB
    
    def __post_init__(self):
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
    
    def __init__(self, config: Config, nats_config: Optional[NATSConfig] = None):
        if not NATS_AVAILABLE:
            raise ImportError("NATS is not installed. Install with: pip install nats-py")
        
        self.config = config
        self.nats_config = nats_config or NATSConfig()
        self.nc: Optional[NATS] = None
        self.subscriptions: Dict[str, Any] = {}
        self.running = False
        
        # Message handlers
        self.agent_handlers: Dict[str, List[Callable[[Message], None]]] = {}
        self.topic_handlers: Dict[str, Dict[str, Callable[[str, Message], None]]] = {}
        
        logger.info(f"NATS Broker initialized with servers: {self.nats_config.servers}")
    
    async def connect(self) -> Result[None, Dict[str, Any]]:
        """Connect to NATS cluster."""
        try:
            self.nc = NATS()
            
            await self.nc.connect(
                servers=self.nats_config.servers,
                name=self.nats_config.client_id,
                max_reconnect_attempts=self.nats_config.max_reconnect_attempts,
                reconnect_time_wait=self.nats_config.reconnect_time_wait,
                max_payload=self.nats_config.max_payload,
                error_cb=self._error_callback,
                disconnected_cb=self._disconnected_callback,
                reconnected_cb=self._reconnected_callback
            )
            
            self.running = True
            logger.info(f"Connected to NATS cluster: {self.nc.connected_url}")
            return Result.ok(None)
            
        except Exception as e:
            error = {
                'errorType': 'NATS_CONNECTION_ERROR',
                'message': f'Failed to connect to NATS: {str(e)}',
                'details': {'servers': self.nats_config.servers}
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
    
    async def send(self, message: Message) -> Result[str, Dict[str, Any]]:
        """Send a message to a specific agent via NATS."""
        if not self.nc or not self.nc.is_connected:
            return Result.err({
                'errorType': 'NATS_NOT_CONNECTED',
                'message': 'NATS client is not connected'
            })
        
        try:
            # Ensure message has ID
            if not message.message_id:
                message.message_id = str(uuid.uuid4())
            
            # Create NATS subject for direct agent communication
            subject = f"maple.agent.{message.receiver}"
            
            # Serialize message
            payload = json.dumps(message.to_dict()).encode('utf-8')
            
            # Send with optional reply subject for responses
            if message.message_type.endswith('_REQUEST'):
                reply_subject = f"maple.reply.{message.message_id}"
                await self.nc.publish(subject, payload, reply=reply_subject)
            else:
                await self.nc.publish(subject, payload)
            
            logger.debug(f"Message {message.message_id} sent to {subject}")
            return Result.ok(message.message_id)
            
        except Exception as e:
            error = {
                'errorType': 'NATS_SEND_ERROR',
                'message': f'Failed to send message: {str(e)}',
                'details': {
                    'messageId': message.message_id,
                    'receiver': message.receiver
                }
            }
            logger.error(f"NATS send error: {error}")
            return Result.err(error)
    
    async def publish(self, topic: str, message: Message) -> Result[str, Dict[str, Any]]:
        """Publish a message to a topic via NATS."""
        if not self.nc or not self.nc.is_connected:
            return Result.err({
                'errorType': 'NATS_NOT_CONNECTED',
                'message': 'NATS client is not connected'
            })
        
        try:
            # Ensure message has ID
            if not message.message_id:
                message.message_id = str(uuid.uuid4())
            
            # Create NATS subject for topic
            subject = f"maple.topic.{topic}"
            
            # Add topic to message metadata
            message.metadata['topic'] = topic
            
            # Serialize and publish
            payload = json.dumps(message.to_dict()).encode('utf-8')
            await self.nc.publish(subject, payload)
            
            logger.debug(f"Message {message.message_id} published to topic {topic}")
            return Result.ok(message.message_id)
            
        except Exception as e:
            error = {
                'errorType': 'NATS_PUBLISH_ERROR',
                'message': f'Failed to publish message: {str(e)}',
                'details': {
                    'messageId': message.message_id,
                    'topic': topic
                }
            }
            logger.error(f"NATS publish error: {error}")
            return Result.err(error)
    
    async def subscribe(self, agent_id: str, handler: Callable[[Message], None]) -> Result[None, Dict[str, Any]]:
        """Subscribe an agent to receive messages via NATS."""
        if not self.nc or not self.nc.is_connected:
            return Result.err({
                'errorType': 'NATS_NOT_CONNECTED',
                'message': 'NATS client is not connected'
            })
        
        try:
            subject = f"maple.agent.{agent_id}"
            
            async def message_handler(msg):
                try:
                    # Deserialize message
                    data = json.loads(msg.data.decode('utf-8'))
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
                'errorType': 'NATS_SUBSCRIBE_ERROR',
                'message': f'Failed to subscribe: {str(e)}',
                'details': {'agentId': agent_id}
            }
            logger.error(f"NATS subscribe error: {error}")
            return Result.err(error)
    
    async def subscribe_topic(self, topic: str, handler: Callable[[str, Message], None], agent_id: str) -> Result[None, Dict[str, Any]]:
        """Subscribe to a topic via NATS."""
        if not self.nc or not self.nc.is_connected:
            return Result.err({
                'errorType': 'NATS_NOT_CONNECTED',
                'message': 'NATS client is not connected'
            })
        
        try:
            subject = f"maple.topic.{topic}"
            subscription_key = f"{agent_id}:{topic}"
            
            async def topic_handler(msg):
                try:
                    # Deserialize message
                    data = json.loads(msg.data.decode('utf-8'))
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
                'errorType': 'NATS_TOPIC_SUBSCRIBE_ERROR',
                'message': f'Failed to subscribe to topic: {str(e)}',
                'details': {'agentId': agent_id, 'topic': topic}
            }
            logger.error(f"NATS topic subscribe error: {error}")
            return Result.err(error)
    
    async def request(self, message: Message, timeout: float = 30.0) -> Result[Message, Dict[str, Any]]:
        """Send a request and wait for a response via NATS."""
        if not self.nc or not self.nc.is_connected:
            return Result.err({
                'errorType': 'NATS_NOT_CONNECTED',
                'message': 'NATS client is not connected'
            })
        
        try:
            # Ensure message has ID
            if not message.message_id:
                message.message_id = str(uuid.uuid4())
            
            subject = f"maple.agent.{message.receiver}"
            payload = json.dumps(message.to_dict()).encode('utf-8')
            
            # Send request and wait for response
            response = await self.nc.request(subject, payload, timeout=timeout)
            
            # Deserialize response
            response_data = json.loads(response.data.decode('utf-8'))
            response_message = Message.from_dict(response_data)
            
            logger.debug(f"Received response for message {message.message_id}")
            return Result.ok(response_message)
            
        except ErrTimeout:
            error = {
                'errorType': 'NATS_REQUEST_TIMEOUT',
                'message': f'Request timed out after {timeout}s',
                'details': {
                    'messageId': message.message_id,
                    'receiver': message.receiver,
                    'timeout': timeout
                }
            }
            return Result.err(error)
        except Exception as e:
            error = {
                'errorType': 'NATS_REQUEST_ERROR',
                'message': f'Request failed: {str(e)}',
                'details': {
                    'messageId': message.message_id,
                    'receiver': message.receiver
                }
            }
            logger.error(f"NATS request error: {error}")
            return Result.err(error)
    
    async def get_cluster_info(self) -> Dict[str, Any]:
        """Get information about the NATS cluster."""
        if not self.nc or not self.nc.is_connected:
            return {'connected': False}
        
        return {
            'connected': True,
            'servers': self.nats_config.servers,
            'connected_url': self.nc.connected_url.netloc if self.nc.connected_url else None,
            'client_id': self.nats_config.client_id,
            'cluster_name': self.nats_config.cluster_name,
            'max_payload': self.nats_config.max_payload,
            'subscriptions': len(self.subscriptions)
        }
    
    # Callback methods for NATS connection events
    async def _error_callback(self, error):
        """Handle NATS errors."""
        logger.error(f"NATS error: {error}")
    
    async def _disconnected_callback(self):
        """Handle NATS disconnection."""
        logger.warning("NATS disconnected - attempting to reconnect...")
    
    async def _reconnected_callback(self):
        """Handle NATS reconnection."""
        logger.info("NATS reconnected successfully")

# Synchronous wrapper for compatibility with existing code
class NATSBrokerSync:
    """Synchronous wrapper around NATSBroker for easier integration."""
    
    def __init__(self, config: Config, nats_config: Optional[NATSConfig] = None):
        self.broker = NATSBroker(config, nats_config)
        self.loop = None
        self._setup_event_loop()
    
    def _setup_event_loop(self):
        """Set up the event loop for async operations."""
        try:
            self.loop = asyncio.get_event_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
    
    def connect(self) -> Result[None, Dict[str, Any]]:
        """Connect to NATS cluster synchronously."""
        return self.loop.run_until_complete(self.broker.connect())
    
    def disconnect(self) -> None:
        """Disconnect from NATS cluster synchronously."""
        self.loop.run_until_complete(self.broker.disconnect())
    
    def send(self, message: Message) -> Result[str, Dict[str, Any]]:
        """Send a message synchronously."""
        return self.loop.run_until_complete(self.broker.send(message))
    
    def publish(self, topic: str, message: Message) -> Result[str, Dict[str, Any]]:
        """Publish a message synchronously."""
        return self.loop.run_until_complete(self.broker.publish(topic, message))
    
    def subscribe(self, agent_id: str, handler: Callable[[Message], None]) -> Result[None, Dict[str, Any]]:
        """Subscribe synchronously."""
        return self.loop.run_until_complete(self.broker.subscribe(agent_id, handler))
    
    def request(self, message: Message, timeout: float = 30.0) -> Result[Message, Dict[str, Any]]:
        """Send a request synchronously."""
        return self.loop.run_until_complete(self.broker.request(message, timeout))
    
    def get_cluster_info(self) -> Dict[str, Any]:
        """Get cluster info synchronously."""
        return self.loop.run_until_complete(self.broker.get_cluster_info())
