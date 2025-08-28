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


# mapl/resources/negotiation.py

from typing import Dict, Any, Optional, List, Callable
import logging
import uuid
import time
import threading
import queue

from ..core.result import Result
from ..core.message import Message
from ..core.types import Priority
from .specification import ResourceRequest, ResourceRange, TimeConstraint

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ResourceNegotiator:
    """
    Handles resource negotiation between agents.
    """
    
    def __init__(self, agent):
        """
        Initialize the negotiator.
        
        Args:
            agent: The agent that owns this negotiator.
        """
        self.agent = agent
        self.pending_requests = {}
        self.pending_offers = {}
        self._lock = threading.RLock()
    
    def request_resources(self, request: ResourceRequest, agent_id: str, timeout: str = "30s") -> Result[Dict[str, Any], Dict[str, Any]]:
        """
        Request resources from another agent.
        
        Args:
            request: The resource request.
            agent_id: The ID of the agent to request from.
            timeout: Timeout for the request.
        
        Returns:
            A Result containing either the allocated resources or an error.
        """
        logger.info(f"Requesting resources from {agent_id}")
        
        # Create a request ID
        request_id = str(uuid.uuid4())
        
        # Create a queue for the response
        response_queue = queue.Queue()
        
        with self._lock:
            self.pending_requests[request_id] = response_queue
        
        # Create the request message
        message = Message(
            message_type="RESOURCE_REQUEST",
            receiver=agent_id,
            priority=Priority.HIGH,
            payload={
                'request_id': request_id,
                'resources': request.to_dict()
            }
        )
        
        # Send the request
        send_result = self.agent.send(message)
        
        if send_result.is_err():
            logger.error(f"Failed to send resource request: {send_result.unwrap_err()}")
            return send_result
        
        # Wait for the response
        try:
            from ..core.types import Duration
            timeout_seconds = Duration.parse(timeout)
            
            response = response_queue.get(timeout=timeout_seconds)
            
            # Check the response type
            if response.message_type == "RESOURCE_OFFER":
                # Accept the offer
                acceptance = Message(
                    message_type="RESOURCE_ACCEPTANCE",
                    receiver=agent_id,
                    priority=Priority.HIGH,
                    payload={
                        'request_id': request_id,
                        'accepted': True
                    }
                )
                
                self.agent.send(acceptance)
                
                # Return the resources
                return Result.ok(response.payload['resources'])
            elif response.message_type == "RESOURCE_REJECTION":
                # Return the error
                return Result.err({
                    'errorType': 'RESOURCE_REJECTED',
                    'message': 'Resource request rejected',
                    'details': response.payload.get('details', {})
                })
            else:
                # Unexpected response
                return Result.err({
                    'errorType': 'UNEXPECTED_RESPONSE',
                    'message': f'Unexpected response type: {response.message_type}',
                    'details': {
                        'response': response.to_dict()
                    }
                })
        except queue.Empty:
            # Timeout
            return Result.err({
                'errorType': 'TIMEOUT',
                'message': 'Timed out waiting for resource response',
                'details': {
                    'timeout': timeout
                }
            })
        finally:
            # Clean up
            with self._lock:
                if request_id in self.pending_requests:
                    del self.pending_requests[request_id]
    
    def handle_request(self, message: Message, evaluator: Callable[[ResourceRequest], Result[Dict[str, Any], Dict[str, Any]]]) -> Message:
        """
        Handle a resource request.
        
        Args:
            message: The request message.
            evaluator: A function that evaluates whether the request can be satisfied.
        
        Returns:
            A response message.
        """
        logger.info(f"Handling resource request from {message.sender}")
        
        # Extract the request
        request_id = message.payload['request_id']
        resources = message.payload['resources']
        
        # Convert to ResourceRequest
        request = ResourceRequest.from_dict(resources)
        
        # Evaluate the request
        result = evaluator(request)
        
        if result.is_ok():
            # Create an offer
            offer = Message(
                message_type="RESOURCE_OFFER",
                receiver=message.sender,
                priority=Priority.HIGH,
                payload={
                    'request_id': request_id,
                    'resources': result.unwrap()
                }
            )
            
            # Store the pending offer
            with self._lock:
                self.pending_offers[request_id] = {
                    'request': request,
                    'offered_resources': result.unwrap()
                }
            
            return offer
        else:
            # Create a rejection
            rejection = Message(
                message_type="RESOURCE_REJECTION",
                receiver=message.sender,
                priority=Priority.HIGH,
                payload={
                    'request_id': request_id,
                    'reason': result.unwrap_err().get('message', 'Resource request rejected'),
                    'details': result.unwrap_err().get('details', {})
                }
            )
            
            return rejection
    
    def handle_acceptance(self, message: Message, allocator: Callable[[str, Dict[str, Any]], None]) -> Message:
        """
        Handle a resource acceptance.
        
        Args:
            message: The acceptance message.
            allocator: A function that allocates the resources.
        
        Returns:
            An acknowledgment message.
        """
        logger.info(f"Handling resource acceptance from {message.sender}")
        
        # Extract the request ID
        request_id = message.payload['request_id']
        accepted = message.payload['accepted']
        
        # Check if we have a pending offer for this request
        with self._lock:
            if request_id in self.pending_offers:
                offer = self.pending_offers[request_id]
                
                if accepted:
                    # Allocate the resources
                    allocator(request_id, offer['offered_resources'])
                    logger.info(f"Resources allocated for request {request_id}")
                else:
                    logger.info(f"Resource offer declined for request {request_id}")
                
                # Clean up
                del self.pending_offers[request_id]
                
                # Acknowledge
                return Message.ack()
            else:
                logger.warning(f"No pending offer found for request {request_id}")
                
                # Send an error
                return Message.error(
                    error_type="UNKNOWN_REQUEST",
                    message=f"No pending offer found for request {request_id}"
                )
    
    def handle_message(self, message: Message) -> Optional[Message]:
        """
        Handle resource-related messages.
        
        Args:
            message: The message to handle.
        
        Returns:
            A response message, or None if the message wasn't handled.
        """
        # Check if this is a response to a pending request
        if message.message_type in ["RESOURCE_OFFER", "RESOURCE_REJECTION"]:
            request_id = message.payload.get('request_id')
            
            if request_id:
                with self._lock:
                    if request_id in self.pending_requests:
                        # Put the response in the queue
                        self.pending_requests[request_id].put(message)
                        
                        # Acknowledge receipt
                        return Message.ack()
        
        # Not handled
        return None