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


# maple/broker/queue.py
# Creator: Mahesh Vaikri

"""
Message Queue Management for MAPLE Brokers
Provides priority queuing and message persistence
"""

import time
import threading
import heapq
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging

from ..core.message import Message
from ..core.types import Priority
from ..core.result import Result

logger = logging.getLogger(__name__)

class QueueType(Enum):
    """Types of message queues."""
    MEMORY = "memory"           # In-memory queue
    PERSISTENT = "persistent"   # Disk-backed persistent queue
    PRIORITY = "priority"       # Priority-based queue

@dataclass
class QueuedMessage:
    """Represents a queued message with metadata."""
    message: Message
    priority: int  # Lower number = higher priority
    timestamp: float
    retry_count: int = 0
    max_retries: int = 3
    expires_at: Optional[float] = None
    
    def __lt__(self, other):
        """For priority queue ordering."""
        # First by priority, then by timestamp
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.timestamp < other.timestamp
    
    def is_expired(self) -> bool:
        """Check if the message has expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at
    
    def can_retry(self) -> bool:
        """Check if the message can be retried."""
        return self.retry_count < self.max_retries

class MessageQueue:
    """
    Manages message queuing with priority support and persistence options.
    
    Features:
    - Priority-based message ordering
    - Message expiration
    - Retry mechanisms
    - Queue statistics
    - Optional persistence
    """
    
    def __init__(
        self,
        queue_type: QueueType = QueueType.PRIORITY,
        max_size: int = 10000,
        default_ttl: Optional[float] = None
    ):
        """
        Initialize the message queue.
        
        Args:
            queue_type: Type of queue to create
            max_size: Maximum queue size
            default_ttl: Default time-to-live for messages in seconds
        """
        self.queue_type = queue_type
        self.max_size = max_size
        self.default_ttl = default_ttl
        
        # Priority queue using heapq
        self._priority_queue: List[QueuedMessage] = []
        self._queue_lock = threading.RLock()
        
        # Message tracking
        self._message_count = 0
        self._total_queued = 0
        self._total_dequeued = 0
        self._dropped_count = 0
        
        # Statistics
        self._stats_lock = threading.RLock()
        self._queue_stats = {
            'messages_queued': 0,
            'messages_dequeued': 0,
            'messages_dropped': 0,
            'messages_expired': 0,
            'messages_retried': 0,
            'average_wait_time': 0.0
        }
        
        logger.info(f"MessageQueue initialized: {queue_type.value}, max_size={max_size}")
    
    def enqueue(
        self,
        message: Message,
        priority: Optional[Priority] = None,
        ttl: Optional[float] = None,
        max_retries: int = 3
    ) -> Result[None, Dict[str, Any]]:
        """
        Add a message to the queue.
        
        Args:
            message: Message to queue
            priority: Message priority (uses message priority if None)
            ttl: Time-to-live in seconds
            max_retries: Maximum retry attempts
            
        Returns:
            Result indicating success or failure
        """
        try:
            with self._queue_lock:
                # Check queue capacity
                if len(self._priority_queue) >= self.max_size:
                    self._stats_lock and self._update_stats('messages_dropped', 1)
                    return Result.err({
                        'errorType': 'QUEUE_FULL',
                        'message': f'Queue is full (size: {len(self._priority_queue)})',
                        'details': {'max_size': self.max_size}
                    })
                
                # Determine priority
                msg_priority = priority or message.priority
                priority_value = self._priority_to_value(msg_priority)
                
                # Calculate expiration time
                expires_at = None
                effective_ttl = ttl or self.default_ttl
                if effective_ttl:
                    expires_at = time.time() + effective_ttl
                
                # Create queued message
                queued_msg = QueuedMessage(
                    message=message,
                    priority=priority_value,
                    timestamp=time.time(),
                    max_retries=max_retries,
                    expires_at=expires_at
                )
                
                # Add to priority queue
                heapq.heappush(self._priority_queue, queued_msg)
                self._message_count += 1
                self._total_queued += 1
            
            with self._stats_lock:
                self._queue_stats['messages_queued'] += 1
            
            logger.debug(f"Message queued: {message.message_id} with priority {priority_value}")
            return Result.ok(None)
            
        except Exception as e:
            return Result.err({
                'errorType': 'QUEUE_ERROR',
                'message': f'Failed to enqueue message: {str(e)}',
                'details': {'message_id': message.message_id}
            })
    
    def dequeue(self, timeout: Optional[float] = None) -> Result[Message, Dict[str, Any]]:
        """
        Remove and return the highest priority message from the queue.
        
        Args:
            timeout: Maximum time to wait for a message
            
        Returns:
            Result containing the message or error
        """
        start_time = time.time()
        
        while True:
            try:
                with self._queue_lock:
                    # Clean up expired messages
                    self._cleanup_expired()
                    
                    # Check if queue is empty
                    if not self._priority_queue:
                        if timeout is None:
                            return Result.err({
                                'errorType': 'QUEUE_EMPTY',
                                'message': 'Queue is empty'
                            })
                        
                        # Check timeout
                        if time.time() - start_time >= timeout:
                            return Result.err({
                                'errorType': 'QUEUE_TIMEOUT',
                                'message': f'Timed out waiting for message after {timeout}s'
                            })
                        
                        # Brief sleep before retrying
                        time.sleep(0.01)
                        continue
                    
                    # Get highest priority message
                    queued_msg = heapq.heappop(self._priority_queue)
                    self._message_count -= 1
                    self._total_dequeued += 1
                
                # Update statistics
                wait_time = time.time() - queued_msg.timestamp
                with self._stats_lock:
                    self._queue_stats['messages_dequeued'] += 1
                    # Update average wait time
                    current_avg = self._queue_stats['average_wait_time']
                    count = self._queue_stats['messages_dequeued']
                    self._queue_stats['average_wait_time'] = (current_avg * (count - 1) + wait_time) / count
                
                logger.debug(f"Message dequeued: {queued_msg.message.message_id} after {wait_time:.3f}s")
                return Result.ok(queued_msg.message)
                
            except Exception as e:
                return Result.err({
                    'errorType': 'DEQUEUE_ERROR',
                    'message': f'Failed to dequeue message: {str(e)}'
                })
    
    def peek(self) -> Result[Optional[Message], Dict[str, Any]]:
        """
        Look at the next message without removing it from the queue.
        
        Returns:
            Result containing the next message or None if queue is empty
        """
        try:
            with self._queue_lock:
                self._cleanup_expired()
                
                if not self._priority_queue:
                    return Result.ok(None)
                
                # Look at the highest priority message
                queued_msg = self._priority_queue[0]
                return Result.ok(queued_msg.message)
                
        except Exception as e:
            return Result.err({
                'errorType': 'PEEK_ERROR',
                'message': f'Failed to peek at queue: {str(e)}'
            })
    
    def size(self) -> int:
        """Get the current queue size."""
        with self._queue_lock:
            return len(self._priority_queue)
    
    def is_empty(self) -> bool:
        """Check if the queue is empty."""
        return self.size() == 0
    
    def is_full(self) -> bool:
        """Check if the queue is full."""
        return self.size() >= self.max_size
    
    def clear(self) -> int:
        """
        Clear all messages from the queue.
        
        Returns:
            Number of messages removed
        """
        with self._queue_lock:
            removed_count = len(self._priority_queue)
            self._priority_queue.clear()
            self._message_count = 0
        
        logger.info(f"Queue cleared: {removed_count} messages removed")
        return removed_count
    
    def retry_message(self, message: Message) -> Result[None, Dict[str, Any]]:
        """
        Retry a failed message by putting it back in the queue.
        
        Args:
            message: Message to retry
            
        Returns:
            Result indicating success or failure
        """
        try:
            # Find the message in our internal tracking if we kept it
            # For now, just re-enqueue with lower priority
            retry_priority = Priority.LOW  # Lower priority for retries
            
            result = self.enqueue(message, priority=retry_priority, max_retries=0)
            
            if result.is_ok():
                with self._stats_lock:
                    self._queue_stats['messages_retried'] += 1
            
            return result
            
        except Exception as e:
            return Result.err({
                'errorType': 'RETRY_ERROR',
                'message': f'Failed to retry message: {str(e)}',
                'details': {'message_id': message.message_id}
            })
    
    def _priority_to_value(self, priority: Priority) -> int:
        """Convert Priority enum to numeric value (lower = higher priority)."""
        priority_map = {
            Priority.HIGH: 1,
            Priority.MEDIUM: 2,
            Priority.LOW: 3
        }
        return priority_map.get(priority, 2)
    
    def _cleanup_expired(self) -> None:
        """Remove expired messages from the queue."""
        current_time = time.time()
        cleaned_messages = []
        
        # Rebuild the queue without expired messages
        while self._priority_queue:
            queued_msg = self._priority_queue[0]
            if queued_msg.is_expired():
                heapq.heappop(self._priority_queue)
                cleaned_messages.append(queued_msg)
                self._message_count -= 1
            else:
                break
        
        # Update statistics
        if cleaned_messages:
            with self._stats_lock:
                self._queue_stats['messages_expired'] += len(cleaned_messages)
            
            logger.debug(f"Cleaned up {len(cleaned_messages)} expired messages")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get queue statistics."""
        with self._stats_lock:
            stats = self._queue_stats.copy()
        
        with self._queue_lock:
            stats.update({
                'current_size': len(self._priority_queue),
                'max_size': self.max_size,
                'total_queued': self._total_queued,
                'total_dequeued': self._total_dequeued,
                'queue_type': self.queue_type.value,
                'utilization': len(self._priority_queue) / self.max_size if self.max_size > 0 else 0
            })
        
        return stats
    
    def get_queue_contents(self) -> List[Dict[str, Any]]:
        """Get information about current queue contents (for debugging)."""
        with self._queue_lock:
            contents = []
            for queued_msg in sorted(self._priority_queue):
                contents.append({
                    'message_id': queued_msg.message.message_id,
                    'message_type': queued_msg.message.message_type,
                    'priority': queued_msg.priority,
                    'timestamp': queued_msg.timestamp,
                    'retry_count': queued_msg.retry_count,
                    'expires_at': queued_msg.expires_at,
                    'is_expired': queued_msg.is_expired()
                })
            return contents
    
    def _update_stats(self, stat_name: str, increment: int) -> None:
        """Update a statistic counter."""
        with self._stats_lock:
            self._queue_stats[stat_name] += increment
