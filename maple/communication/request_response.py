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


# maple/communication/request_response.py
# Creator: Mahesh Vaikri

"""
Request-Response Communication Pattern for MAPLE
Provides structured request-response interactions between agents
"""

import time
import uuid
import threading
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass

from ..core.message import Message
from ..core.result import Result
from ..core.types import Priority

@dataclass
class RequestConfig:
    """Configuration for request-response pattern."""
    timeout_seconds: float = 30.0
    max_retries: int = 3
    retry_delay: float = 1.0
    correlation_tracking: bool = True

class RequestResponsePattern:
    """
    Implements the request-response communication pattern for MAPLE agents.
    
    Features:
    - Automatic correlation ID management
    - Timeout handling
    - Retry mechanisms
    - Response tracking
    """
    
    def __init__(self, agent, config: Optional[RequestConfig] = None):
        """
        Initialize the request-response pattern.
        
        Args:
            agent: The agent instance
            config: Configuration for request-response behavior
        """
        self.agent = agent
        self.config = config or RequestConfig()
        self.pending_requests: Dict[str, Any] = {}
        self._lock = threading.RLock()
    
    def send_request(
        self,
        receiver: str,
        message_type: str,
        payload: Dict[str, Any],
        timeout: Optional[float] = None,
        priority: Priority = Priority.MEDIUM
    ) -> Result[Message, Dict[str, Any]]:
        """
        Send a request and wait for a response.
        
        Args:
            receiver: Agent ID to send the request to
            message_type: Type of the request message
            payload: Request payload
            timeout: Timeout in seconds (uses config default if None)
            priority: Message priority
            
        Returns:
            Result containing the response message or error
        """
        timeout = timeout or self.config.timeout_seconds
        correlation_id = str(uuid.uuid4())
        
        # Create request message
        request = Message(
            message_type=message_type,
            receiver=receiver,
            priority=priority,
            payload=payload,
            metadata={'correlationId': correlation_id, 'expectsResponse': True}
        )
        
        # Track the request
        response_event = threading.Event()
        request_info = {
            'event': response_event,
            'response': None,
            'error': None,
            'timestamp': time.time()
        }
        
        with self._lock:
            self.pending_requests[correlation_id] = request_info
        
        try:
            # Send the request
            send_result = self.agent.send(request)
            if send_result.is_err():
                return send_result
            
            # Wait for response
            if response_event.wait(timeout):
                # Response received
                if request_info['response']:
                    return Result.ok(request_info['response'])
                elif request_info['error']:
                    return Result.err(request_info['error'])
                else:
                    return Result.err({
                        'errorType': 'RESPONSE_ERROR',
                        'message': 'Response event set but no response or error found'
                    })
            else:
                # Timeout
                return Result.err({
                    'errorType': 'REQUEST_TIMEOUT',
                    'message': f'Request timed out after {timeout} seconds',
                    'details': {
                        'correlationId': correlation_id,
                        'receiver': receiver,
                        'messageType': message_type
                    }
                })
                
        finally:
            # Clean up
            with self._lock:
                self.pending_requests.pop(correlation_id, None)
    
    def handle_response(self, message: Message) -> bool:
        """
        Handle an incoming response message.
        
        Args:
            message: The response message
            
        Returns:
            True if the response was handled, False otherwise
        """
        correlation_id = message.metadata.get('correlationId')
        if not correlation_id:
            return False
        
        with self._lock:
            if correlation_id in self.pending_requests:
                request_info = self.pending_requests[correlation_id]
                
                if message.message_type == 'ERROR':
                    # Error response
                    request_info['error'] = {
                        'errorType': message.payload.get('errorType', 'REMOTE_ERROR'),
                        'message': message.payload.get('message', 'Remote agent returned an error'),
                        'details': message.payload.get('details', {})
                    }
                else:
                    # Success response
                    request_info['response'] = message
                
                # Signal that response is ready
                request_info['event'].set()
                return True
        
        return False
    
    def create_response(
        self,
        original_message: Message,
        response_type: str,
        payload: Dict[str, Any],
        priority: Priority = Priority.MEDIUM
    ) -> Message:
        """
        Create a response message for a request.
        
        Args:
            original_message: The original request message
            response_type: Type of the response message
            payload: Response payload
            priority: Message priority
            
        Returns:
            Response message with proper correlation
        """
        correlation_id = original_message.metadata.get('correlationId')
        
        response = Message(
            message_type=response_type,
            receiver=original_message.sender,
            priority=priority,
            payload=payload,
            metadata={'correlationId': correlation_id, 'isResponse': True}
        )
        
        return response
    
    def create_error_response(
        self,
        original_message: Message,
        error_type: str,
        error_message: str,
        details: Optional[Dict[str, Any]] = None
    ) -> Message:
        """
        Create an error response for a request.
        
        Args:
            original_message: The original request message
            error_type: Type of error
            error_message: Error message
            details: Additional error details
            
        Returns:
            Error response message
        """
        return self.create_response(
            original_message,
            'ERROR',
            {
                'errorType': error_type,
                'message': error_message,
                'details': details or {}
            },
            Priority.HIGH
        )
    
    def cleanup_expired_requests(self) -> int:
        """
        Clean up expired pending requests.
        
        Returns:
            Number of expired requests cleaned up
        """
        current_time = time.time()
        expired_requests = []
        
        with self._lock:
            for correlation_id, request_info in self.pending_requests.items():
                if current_time - request_info['timestamp'] > self.config.timeout_seconds * 2:
                    expired_requests.append(correlation_id)
            
            for correlation_id in expired_requests:
                request_info = self.pending_requests.pop(correlation_id)
                # Set error for any waiting threads
                request_info['error'] = {
                    'errorType': 'REQUEST_EXPIRED',
                    'message': 'Request expired during cleanup'
                }
                request_info['event'].set()
        
        return len(expired_requests)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about request-response operations."""
        with self._lock:
            pending_count = len(self.pending_requests)
            oldest_request = None
            
            if self.pending_requests:
                oldest_timestamp = min(req['timestamp'] for req in self.pending_requests.values())
                oldest_request = time.time() - oldest_timestamp
        
        return {
            'pending_requests': pending_count,
            'oldest_request_age': oldest_request,
            'config': {
                'timeout_seconds': self.config.timeout_seconds,
                'max_retries': self.config.max_retries,
                'retry_delay': self.config.retry_delay
            }
        }
