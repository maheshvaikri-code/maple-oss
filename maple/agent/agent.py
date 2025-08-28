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


# maple/agent/agent.py
# Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

import os
from typing import Dict, Any, Optional, Callable, List, Type, TypeVar, Union
import threading
import queue
import time
import logging
from concurrent.futures import ThreadPoolExecutor
import uuid

from maple.communication.streaming import Stream

# Stream import handled in create_stream method

from ..core.message import Message
from ..core.result import Result
from ..core.types import Priority
from .config import Config
from ..broker.broker import MessageBroker

# Type variables for handlers
T = TypeVar('T')
E = TypeVar('E')

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Agent:
    """
    Base class for MAPLE agents.
    """
    
    def __init__(self, config: Config, broker: Optional[MessageBroker] = None):
        self.config = config
        self.agent_id = config.agent_id
        self.broker = broker or MessageBroker(config)
        self.running = False
        self.message_queue = queue.Queue()
        self.handler_thread = None
        self.message_handlers = {}
        self.topic_handlers = {}
        self.stream_handlers = {}
        self.executor = ThreadPoolExecutor(max_workers=10)
    
    def start(self) -> None:
        """Start the agent."""
        logger.info(f"Starting agent {self.agent_id}")
        self.running = True
        self.broker.connect()
        self.broker.subscribe(self.agent_id, self._handle_message)
        self.handler_thread = threading.Thread(target=self._message_handler_loop)
        self.handler_thread.daemon = True
        self.handler_thread.start()
        logger.info(f"Agent {self.agent_id} started")
    
    def stop(self) -> None:
        """Stop the agent."""
        logger.info(f"Stopping agent {self.agent_id}")
        self.running = False
        if self.handler_thread:
            self.handler_thread.join(timeout=5.0)
        self.broker.disconnect()
        self.executor.shutdown(wait=False)
        logger.info(f"Agent {self.agent_id} stopped")
    
    def send(self, message: Message) -> Result[str, Dict[str, Any]]:
        """Send a message to another agent."""
        # Set the sender if not already set
        if not message.sender:
            message.sender = self.agent_id
        
        try:
            message_id = self.broker.send(message)
            return Result.ok(message_id)
        except Exception as e:
            error = {
                'errorType': 'SEND_ERROR',
                'message': str(e),
                'details': {
                    'messageType': message.message_type,
                    'receiver': message.receiver
                }
            }
            logger.error(f"Error sending message: {error}")
            return Result.err(error)
    
    def request(self, message: Message, timeout: str = "30s") -> Result[Message, Dict[str, Any]]:
        """Send a message and wait for a response."""
        # Set a correlation ID if not already set
        if 'correlationId' not in message.metadata:
            message.metadata['correlationId'] = str(uuid.uuid4())
        
        correlation_id = message.metadata['correlationId']
        
        # Create a response queue for this request
        response_queue = queue.Queue()
        
        # Register a temporary handler for the response
        def response_handler(response: Message) -> None:
            if 'correlationId' in response.metadata and response.metadata['correlationId'] == correlation_id:
                response_queue.put(response)
        
        # Subscribe to responses
        self.broker.subscribe_temporary(self.agent_id, response_handler)
        
        # Send the message
        send_result = self.send(message)
        if send_result.is_err():
            return Result.err(send_result.unwrap_err())
        
        # Wait for the response
        try:
            import re
            from ..core.types import Duration
            
            # Parse the timeout
            timeout_seconds = Duration.parse(timeout)
            
            # Wait for the response
            response = response_queue.get(timeout=timeout_seconds)
            return Result.ok(response)
        except queue.Empty:
            error = {
                'errorType': 'TIMEOUT',
                'message': f"Timed out waiting for response to message {message.message_id}",
                'details': {
                    'messageType': message.message_type,
                    'receiver': message.receiver,
                    'timeout': timeout
                }
            }
            logger.error(f"Request timeout: {error}")
            return Result.err(error)
        finally:
            # Unsubscribe the temporary handler
            self.broker.unsubscribe_temporary(self.agent_id, response_handler)
    
    def receive(self, timeout: Optional[str] = None) -> Result[Message, Dict[str, Any]]:
        """Receive a message from the queue."""
        try:
            if timeout:
                from ..core.types import Duration
                timeout_seconds = Duration.parse(timeout)
                message = self.message_queue.get(timeout=timeout_seconds)
            else:
                message = self.message_queue.get()
            
            return Result.ok(message)
        except queue.Empty:
            error = {
                'errorType': 'TIMEOUT',
                'message': f"Timed out waiting for message",
                'details': {
                    'timeout': timeout
                }
            }
            return Result.err(error)
    
    def receive_filtered(self, filter: Callable[[Message], bool], timeout: Optional[str] = None) -> Result[Message, Dict[str, Any]]:
        """Receive a message that matches a filter."""
        if timeout:
            from ..core.types import Duration
            timeout_seconds = Duration.parse(timeout)
            end_time = time.time() + timeout_seconds
        else:
            end_time = None
        
        while end_time is None or time.time() < end_time:
            remaining_time = end_time - time.time() if end_time else None
            
            try:
                if remaining_time:
                    message = self.message_queue.get(timeout=remaining_time)
                else:
                    message = self.message_queue.get()
                
                if filter(message):
                    return Result.ok(message)
                
                # Put the message back in the queue if it doesn't match
                self.message_queue.put(message)
                
                # Sleep briefly to avoid busy waiting
                time.sleep(0.01)
            except queue.Empty:
                error = {
                    'errorType': 'TIMEOUT',
                    'message': f"Timed out waiting for filtered message",
                    'details': {
                        'timeout': timeout
                    }
                }
                return Result.err(error)
        
        error = {
            'errorType': 'TIMEOUT',
            'message': f"Timed out waiting for filtered message",
            'details': {
                'timeout': timeout
            }
        }
        return Result.err(error)
    
    def broadcast(self, recipients: List[str], message: Message) -> Dict[str, Result[str, Dict[str, Any]]]:
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
                'errorType': 'PUBLISH_ERROR',
                'message': str(e),
                'details': {
                    'messageType': message.message_type,
                    'topic': topic
                }
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
                'errorType': 'SUBSCRIBE_ERROR',
                'message': str(e),
                'details': {
                    'topic': topic
                }
            }
            logger.error(f"Error subscribing to topic: {error}")
            return Result.err(error)
    
    def establish_link(self, agent_id: str, lifetime_seconds: int = 3600) -> Result[str, Dict[str, Any]]:
        """Establish a secure communication link with another agent."""
        logger.info(f"Establishing link with agent {agent_id}")
        
        try:
            # Generate a nonce
            nonce_a = os.urandom(16).hex()
            
            # Get security config
            security_config = getattr(self.config, 'security', None)
            if not security_config:
                return Result.err({
                    'errorType': 'NO_SECURITY_CONFIG',
                    'message': 'Security configuration required for link establishment'
                })
            
            # Create a link request message
            request = Message(
                message_type="LINK_REQUEST",
                receiver=agent_id,
                priority=Priority.HIGH,
                payload={
                    'publicKey': getattr(security_config, 'public_key', 'demo_key'),
                    'nonce': nonce_a,
                    'supportedCiphers': ['AES256-GCM', 'ChaCha20-Poly1305']
                }
            )
            
            # Send the request
            self.send(request)
            
            # Wait for a challenge response
            response_result = self.receive_filtered(
                lambda m: m.message_type == "LINK_CHALLENGE" and m.sender == agent_id,
                timeout="10s"
            )
            
            if response_result.is_err():
                logger.error(f"Failed to receive link challenge: {response_result.unwrap_err()}")
                return Result.err({
                    'errorType': 'LINK_TIMEOUT',
                    'message': 'Timed out waiting for link challenge'
                })
            
            challenge = response_result.unwrap()
            
            # Verify the challenge contains our nonce
            if not self._verify_nonce(challenge.payload['encryptedNonce'], nonce_a):
                logger.error("Failed to verify nonce in link challenge")
                return Result.err({
                    'errorType': 'LINK_VERIFICATION_FAILED',
                    'message': 'Failed to verify nonce in link challenge'
                })
            
            # Extract the link ID and other parameters
            link_id = challenge.payload['linkId']
            nonce_b = challenge.payload['nonce']
            
            # Create link parameters
            link_params = {
                'cipherSuite': 'AES256-GCM',
                'keyRotationInterval': '1h',
                'compressionEnabled': True
            }
            
            # Create a confirmation message
            confirmation = Message(
                message_type="LINK_CONFIRM",
                receiver=agent_id,
                priority=Priority.HIGH,
                payload={
                    'linkId': link_id,
                    'encryptedNonce': self._encrypt_nonce(nonce_b),
                    'linkParams': link_params
                }
            )
            
            # Send the confirmation
            self.send(confirmation)
            
            # Wait for establishment confirmation
            establish_result = self.receive_filtered(
                lambda m: m.message_type == "LINK_ESTABLISHED" and m.sender == agent_id,
                timeout="10s"
            )
            
            if establish_result.is_err():
                logger.error(f"Failed to receive link established: {establish_result.unwrap_err()}")
                return Result.err({
                    'errorType': 'LINK_TIMEOUT',
                    'message': 'Timed out waiting for link establishment'
                })
            
            established = establish_result.unwrap()
            
            # Verify the link parameters
            if not self._verify_link_params(established.payload['encryptedParams'], link_params):
                logger.error("Failed to verify link parameters")
                return Result.err({
                    'errorType': 'LINK_VERIFICATION_FAILED',
                    'message': 'Failed to verify link parameters'
                })
            
            logger.info(f"Link established with agent {agent_id}: {link_id}")
            return Result.ok(link_id)
        
        except Exception as e:
            logger.error(f"Error establishing link: {str(e)}")
            return Result.err({
                'errorType': 'LINK_ESTABLISHMENT_ERROR',
                'message': str(e)
            })
        
    def send_with_link(self, message: Message, agent_id: str) -> Result[str, Dict[str, Any]]:
        """Send a message using an established link, creating one if needed."""
        # Check if we already have a link
        link_id = None
        
        # Check if message already has a link
        if 'linkId' in message.metadata:
            link_id = message.metadata['linkId']
        else:
            # Find an existing link
            links_result = self.broker.link_manager.get_links_for_agent(self.agent_id)
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
    
    def _verify_nonce(self, encrypted_nonce: str, original_nonce: str) -> bool:
        """Verify that encrypted nonce matches original."""
        # Simplified verification for demo purposes
        # In production, use proper cryptographic verification
        try:
            # This is a placeholder - implement proper decryption
            return len(encrypted_nonce) > 0 and len(original_nonce) > 0
        except Exception:
            return False
    
    def _encrypt_nonce(self, nonce: str) -> str:
        """Encrypt a nonce for link establishment."""
        # Simplified encryption for demo purposes
        # In production, use proper cryptographic encryption
        try:
            import base64
            return base64.b64encode(nonce.encode()).decode()
        except Exception:
            return nonce
    
    def _verify_link_params(self, encrypted_params: str, params: dict) -> bool:
        """Verify link parameters."""
        # Simplified verification for demo purposes
        # In production, use proper cryptographic verification
        try:
            return len(encrypted_params) > 0 and len(params) > 0
        except Exception:
            return False



    def create_stream(self, name: str) -> Result['Stream', Dict[str, Any]]:
        """Create a new stream."""
        try:
            from ..communication.streaming import Stream
            stream = Stream(self, name)
            return Result.ok(stream)
        except Exception as e:
            error = {
                'errorType': 'STREAM_CREATE_ERROR',
                'message': str(e),
                'details': {
                    'name': name
                }
            }
            logger.error(f"Error creating stream: {error}")
            return Result.err(error)
    
    def connect_stream(self, name: str) -> Result['Stream', Dict[str, Any]]:
        """Connect to an existing stream."""
        try:
            from ..communication.streaming import Stream
            stream = Stream.connect(self, name)
            return Result.ok(stream)
        except Exception as e:
            error = {
                'errorType': 'STREAM_CONNECT_ERROR',
                'message': str(e),
                'details': {
                    'name': name
                }
            }
            logger.error(f"Error connecting to stream: {error}")
            return Result.err(error)
    
    def register_handler(self, message_type: str, handler: Callable[[Message], Optional[Message]]) -> None:
        """Register a handler for a specific message type."""
        self.message_handlers[message_type] = handler
        logger.info(f"Registered handler for message type {message_type}")
    
    def register_topic_handler(self, topic: str, handler: Callable[[Message], Optional[Message]]) -> None:
        """Register a handler for a specific topic."""
        self.topic_handlers[topic] = handler
        logger.info(f"Registered handler for topic {topic}")
    
    def register_stream_handler(self, stream_name: str, handler: Callable[[Message], None]) -> None:
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
                
                # Process the message
                self._process_message(message)
                
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
                    if 'correlationId' in message.metadata:
                        response.metadata['correlationId'] = message.metadata['correlationId']
                    
                    self.send(response)
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}")
                
                # Send an error response
                if message.sender:
                    error_response = Message.error(
                        error_type="HANDLER_ERROR",
                        message=f"Error processing message: {str(e)}",
                        receiver=message.sender,
                        correlation_id=message.metadata.get('correlationId')
                    )
                    self.send(error_response)
        else:
            logger.warning(f"No handler found for message type {message.message_type}")
    
    def _handle_message(self, message: Message) -> None:
        """Handle a message received from the broker."""
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
                    if 'correlationId' in message.metadata:
                        response.metadata['correlationId'] = message.metadata['correlationId']
                    
                    self.send(response)
            except Exception as e:
                logger.error(f"Error processing topic message: {str(e)}")
        else:
            logger.warning(f"No handler found for topic {topic}")
    
    def handler(self, message_type: str) -> Callable[[Callable[[Message], Optional[Message]]], Callable[[Message], Optional[Message]]]:
        """Decorator for registering message handlers."""
        def decorator(func: Callable[[Message], Optional[Message]]) -> Callable[[Message], Optional[Message]]:
            self.register_handler(message_type, func)
            return func
        return decorator
    
    def topic_handler(self, topic: str) -> Callable[[Callable[[Message], Optional[Message]]], Callable[[Message], Optional[Message]]]:
        """Decorator for registering topic handlers."""
        def decorator(func: Callable[[Message], Optional[Message]]) -> Callable[[Message], Optional[Message]]:
            self.register_topic_handler(topic, func)
            return func
        return decorator
    
    def stream_handler(self, stream_name: str) -> Callable[[Callable[[Message], None]], Callable[[Message], None]]:
        """Decorator for registering stream handlers."""
        def decorator(func: Callable[[Message], None]) -> Callable[[Message], None]:
            self.register_stream_handler(stream_name, func)
            return func
        return decorator