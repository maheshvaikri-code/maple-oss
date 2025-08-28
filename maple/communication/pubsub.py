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


# maple/communication/pubsub.py
# Creator: Mahesh Vaikri

"""
Publish-Subscribe Communication Pattern for MAPLE
Provides event-driven messaging between agents
"""

import time
import threading
from typing import Dict, Any, List, Callable, Optional, Set
from dataclasses import dataclass
from enum import Enum

from ..core.message import Message
from ..core.result import Result
from ..core.types import Priority

class SubscriptionType(Enum):
    """Types of subscriptions."""
    EXACT = "exact"       # Exact topic match
    WILDCARD = "wildcard" # Wildcard matching
    PATTERN = "pattern"   # Regex pattern matching

@dataclass
class SubscriptionConfig:
    """Configuration for a subscription."""
    topic: str
    handler: Callable[[Message], None]
    subscription_type: SubscriptionType = SubscriptionType.EXACT
    filter_func: Optional[Callable[[Message], bool]] = None
    max_queue_size: int = 1000
    auto_ack: bool = True

class PublishSubscribePattern:
    """
    Implements the publish-subscribe communication pattern for MAPLE agents.
    
    Features:
    - Topic-based message routing
    - Wildcard and pattern subscriptions
    - Message filtering
    - Queue management
    - Event delivery guarantees
    """
    
    def __init__(self, agent):
        """
        Initialize the publish-subscribe pattern.
        
        Args:
            agent: The agent instance
        """
        self.agent = agent
        self.subscriptions: Dict[str, List[SubscriptionConfig]] = {}
        self.topic_subscribers: Dict[str, Set[str]] = {}  # topic -> set of agent IDs
        self.message_queues: Dict[str, List[Message]] = {}  # subscriber -> messages
        self._lock = threading.RLock()
        self._stats = {
            'messages_published': 0,
            'messages_delivered': 0,
            'subscriptions_active': 0
        }
    
    def publish(
        self,
        topic: str,
        payload: Dict[str, Any],
        priority: Priority = Priority.MEDIUM,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Result[str, Dict[str, Any]]:
        """
        Publish a message to a topic.
        
        Args:
            topic: Topic to publish to
            payload: Message payload
            priority: Message priority
            metadata: Additional metadata
            
        Returns:
            Result containing message ID or error
        """
        try:
            # Create publication message
            message = Message(
                message_type="TOPIC_PUBLICATION",
                priority=priority,
                payload=payload,
                metadata={
                    'topic': topic,
                    'publisher': self.agent.agent_id,
                    'publishedAt': time.time(),
                    **(metadata or {})
                }
            )
            
            # Use the broker's publish method if available
            if hasattr(self.agent.broker, 'publish'):
                result = self.agent.broker.publish(topic, message)
                if result.is_ok():
                    self._stats['messages_published'] += 1
                return result
            else:
                # Fallback to direct delivery
                return self._direct_publish(topic, message)
                
        except Exception as e:
            return Result.err({
                'errorType': 'PUBLISH_ERROR',
                'message': f'Failed to publish to topic {topic}: {str(e)}',
                'details': {'topic': topic}
            })
    
    def subscribe(
        self,
        topic: str,
        handler: Callable[[Message], None],
        subscription_type: SubscriptionType = SubscriptionType.EXACT,
        filter_func: Optional[Callable[[Message], bool]] = None
    ) -> Result[str, Dict[str, Any]]:
        """
        Subscribe to a topic.
        
        Args:
            topic: Topic to subscribe to
            handler: Message handler function
            subscription_type: Type of subscription
            filter_func: Optional message filter function
            
        Returns:
            Result containing subscription ID or error
        """
        try:
            subscription_id = f"{self.agent.agent_id}:{topic}:{int(time.time())}"
            
            subscription = SubscriptionConfig(
                topic=topic,
                handler=handler,
                subscription_type=subscription_type,
                filter_func=filter_func
            )
            
            with self._lock:
                if topic not in self.subscriptions:
                    self.subscriptions[topic] = []
                self.subscriptions[topic].append(subscription)
                
                # Track subscribers per topic
                if topic not in self.topic_subscribers:
                    self.topic_subscribers[topic] = set()
                self.topic_subscribers[topic].add(self.agent.agent_id)
                
                self._stats['subscriptions_active'] += 1
            
            # Subscribe with the broker if available
            if hasattr(self.agent.broker, 'subscribe_topic'):
                self.agent.broker.subscribe_topic(
                    topic, 
                    self._handle_topic_message,
                    self.agent.agent_id
                )
            
            return Result.ok(subscription_id)
            
        except Exception as e:
            return Result.err({
                'errorType': 'SUBSCRIBE_ERROR',
                'message': f'Failed to subscribe to topic {topic}: {str(e)}',
                'details': {'topic': topic}
            })
    
    def unsubscribe(self, topic: str) -> Result[None, Dict[str, Any]]:
        """
        Unsubscribe from a topic.
        
        Args:
            topic: Topic to unsubscribe from
            
        Returns:
            Result indicating success or error
        """
        try:
            with self._lock:
                if topic in self.subscriptions:
                    removed_count = len(self.subscriptions[topic])
                    del self.subscriptions[topic]
                    self._stats['subscriptions_active'] -= removed_count
                
                if topic in self.topic_subscribers:
                    self.topic_subscribers[topic].discard(self.agent.agent_id)
                    if not self.topic_subscribers[topic]:
                        del self.topic_subscribers[topic]
            
            # Unsubscribe with the broker if available
            if hasattr(self.agent.broker, 'unsubscribe_topic'):
                self.agent.broker.unsubscribe_topic(topic, self.agent.agent_id)
            
            return Result.ok(None)
            
        except Exception as e:
            return Result.err({
                'errorType': 'UNSUBSCRIBE_ERROR',
                'message': f'Failed to unsubscribe from topic {topic}: {str(e)}',
                'details': {'topic': topic}
            })
    
    def _direct_publish(self, topic: str, message: Message) -> Result[str, Dict[str, Any]]:
        """
        Directly publish a message when broker publish is not available.
        
        Args:
            topic: Topic to publish to
            message: Message to publish
            
        Returns:
            Result containing message ID or error
        """
        with self._lock:
            subscribers = self.topic_subscribers.get(topic, set())
            
            for subscriber_id in subscribers:
                # Send message to each subscriber
                subscriber_message = Message(
                    message_id=message.message_id,
                    timestamp=message.timestamp,
                    sender=message.sender or self.agent.agent_id,
                    receiver=subscriber_id,
                    priority=message.priority,
                    message_type=message.message_type,
                    payload=message.payload,
                    metadata=message.metadata
                )
                
                # Use the agent's send method
                self.agent.send(subscriber_message)
            
            self._stats['messages_published'] += 1
            return Result.ok(message.message_id)
    
    def _handle_topic_message(self, topic: str, message: Message) -> None:
        """
        Handle a message received on a subscribed topic.
        
        Args:
            topic: Topic the message was published to
            message: The received message
        """
        with self._lock:
            subscriptions = self.subscriptions.get(topic, [])
        
        for subscription in subscriptions:
            try:
                # Apply filter if configured
                if subscription.filter_func and not subscription.filter_func(message):
                    continue
                
                # Call the handler
                subscription.handler(message)
                self._stats['messages_delivered'] += 1
                
            except Exception as e:
                # Log handler errors but don't stop processing
                print(f"Error in topic handler for {topic}: {e}")
    
    def get_topics(self) -> List[str]:
        """Get list of currently subscribed topics."""
        with self._lock:
            return list(self.subscriptions.keys())
    
    def get_topic_subscribers(self, topic: str) -> List[str]:
        """Get list of subscribers for a topic."""
        with self._lock:
            return list(self.topic_subscribers.get(topic, set()))
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get publish-subscribe statistics."""
        with self._lock:
            return {
                'messages_published': self._stats['messages_published'],
                'messages_delivered': self._stats['messages_delivered'],
                'subscriptions_active': self._stats['subscriptions_active'],
                'topics_count': len(self.subscriptions),
                'subscribers_count': sum(len(subs) for subs in self.topic_subscribers.values())
            }
    
    def cleanup_inactive_subscriptions(self) -> int:
        """Clean up inactive or orphaned subscriptions."""
        # This would implement cleanup logic for subscriptions
        # that are no longer active or whose handlers have failed
        cleaned_count = 0
        
        with self._lock:
            # Implementation would go here
            # For now, just return 0
            pass
        
        return cleaned_count
