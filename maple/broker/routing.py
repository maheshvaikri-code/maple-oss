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


# maple/broker/routing.py
# Creator: Mahesh Vaikri

"""
Message Routing for MAPLE Brokers
Provides intelligent message routing and load balancing
"""

import time
import random
import threading
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum

from ..core.message import Message
from ..core.result import Result

class RoutingStrategy(Enum):
    """Available routing strategies."""
    DIRECT = "direct"           # Direct routing to specific agent
    ROUND_ROBIN = "round_robin" # Round-robin load balancing
    LEAST_LOADED = "least_loaded" # Route to least loaded agent
    RANDOM = "random"           # Random selection
    BROADCAST = "broadcast"     # Send to all matching agents

@dataclass
class RouteEntry:
    """Represents a routing table entry."""
    pattern: str                # Route pattern (exact match or wildcard)
    agents: List[str]          # List of agents that can handle this route
    strategy: RoutingStrategy   # Routing strategy to use
    metadata: Dict[str, Any]   # Additional routing metadata
    
    def matches(self, destination: str) -> bool:
        """Check if this route matches a destination."""
        if self.pattern == "*":
            return True
        elif self.pattern.endswith("*"):
            prefix = self.pattern[:-1]
            return destination.startswith(prefix)
        else:
            return self.pattern == destination

class MessageRouter:
    """
    Handles intelligent message routing for MAPLE brokers.
    
    Features:
    - Multiple routing strategies
    - Load balancing
    - Route discovery
    - Health monitoring
    - Performance tracking
    """
    
    def __init__(self):
        """Initialize the message router."""
        self.routes: List[RouteEntry] = []
        self.route_lock = threading.RLock()
        
        # Agent health tracking
        self.agent_health: Dict[str, Dict[str, Any]] = {}
        self.health_lock = threading.RLock()
        
        # Performance tracking
        self.performance_stats: Dict[str, Dict[str, Any]] = {}
        self.stats_lock = threading.RLock()
        
        # Round-robin state
        self.round_robin_state: Dict[str, int] = {}
        self.rr_lock = threading.RLock()
    
    def add_route(
        self,
        pattern: str,
        agents: List[str],
        strategy: RoutingStrategy = RoutingStrategy.DIRECT,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add a routing entry.
        
        Args:
            pattern: Route pattern (supports wildcards)
            agents: List of agents that can handle this route
            strategy: Routing strategy to use
            metadata: Additional routing metadata
        """
        route = RouteEntry(
            pattern=pattern,
            agents=agents.copy(),
            strategy=strategy,
            metadata=metadata or {}
        )
        
        with self.route_lock:
            # Remove existing routes with same pattern
            self.routes = [r for r in self.routes if r.pattern != pattern]
            self.routes.append(route)
        
        # Initialize health tracking for new agents
        with self.health_lock:
            for agent in agents:
                if agent not in self.agent_health:
                    self.agent_health[agent] = {
                        'healthy': True,
                        'last_seen': time.time(),
                        'message_count': 0,
                        'error_count': 0
                    }
    
    def remove_route(self, pattern: str) -> bool:
        """
        Remove a routing entry.
        
        Args:
            pattern: Route pattern to remove
            
        Returns:
            True if route was removed, False if not found
        """
        with self.route_lock:
            original_count = len(self.routes)
            self.routes = [r for r in self.routes if r.pattern != pattern]
            return len(self.routes) < original_count
    
    def route_message(self, message: Message) -> Result[List[str], Dict[str, Any]]:
        """
        Route a message to appropriate agents.
        
        Args:
            message: Message to route
            
        Returns:
            Result containing list of target agents or error
        """
        if not message.receiver:
            return Result.err({
                'errorType': 'MISSING_RECEIVER',
                'message': 'Message has no receiver specified'
            })
        
        try:
            # Find matching routes
            matching_routes = self._find_matching_routes(message.receiver)
            
            if not matching_routes:
                # Default: try direct routing if agent exists
                with self.health_lock:
                    if message.receiver in self.agent_health:
                        return Result.ok([message.receiver])
                
                return Result.err({
                    'errorType': 'NO_ROUTE_FOUND',
                    'message': f'No route found for destination: {message.receiver}',
                    'details': {'destination': message.receiver}
                })
            
            # Use the first matching route (most specific)
            route = matching_routes[0]
            target_agents = self._select_agents(route, message)
            
            # Update performance stats
            self._update_stats(target_agents, message)
            
            return Result.ok(target_agents)
            
        except Exception as e:
            return Result.err({
                'errorType': 'ROUTING_ERROR',
                'message': f'Error routing message: {str(e)}',
                'details': {'destination': message.receiver}
            })
    
    def _find_matching_routes(self, destination: str) -> List[RouteEntry]:
        """Find routes that match the destination."""
        with self.route_lock:
            matching = []
            for route in self.routes:
                if route.matches(destination):
                    matching.append(route)
            
            # Sort by specificity (more specific patterns first)
            matching.sort(key=lambda r: (
                0 if r.pattern == destination else
                1 if not r.pattern.endswith("*") else
                2
            ))
            
            return matching
    
    def _select_agents(self, route: RouteEntry, message: Message) -> List[str]:
        """Select target agents based on routing strategy."""
        available_agents = self._get_healthy_agents(route.agents)
        
        if not available_agents:
            # Fall back to all agents if none are healthy
            available_agents = route.agents
        
        if route.strategy == RoutingStrategy.DIRECT:
            # For direct routing, return the first available agent
            return available_agents[:1]
        
        elif route.strategy == RoutingStrategy.ROUND_ROBIN:
            return self._round_robin_select(route.pattern, available_agents)
        
        elif route.strategy == RoutingStrategy.LEAST_LOADED:
            return self._least_loaded_select(available_agents)
        
        elif route.strategy == RoutingStrategy.RANDOM:
            if available_agents:
                return [random.choice(available_agents)]
            return []
        
        elif route.strategy == RoutingStrategy.BROADCAST:
            return available_agents
        
        else:
            # Default to first available agent
            return available_agents[:1]
    
    def _get_healthy_agents(self, agents: List[str]) -> List[str]:
        """Get list of healthy agents."""
        with self.health_lock:
            healthy = []
            for agent in agents:
                health_info = self.agent_health.get(agent, {})
                if health_info.get('healthy', True):
                    healthy.append(agent)
            return healthy
    
    def _round_robin_select(self, pattern: str, agents: List[str]) -> List[str]:
        """Select agent using round-robin strategy."""
        if not agents:
            return []
        
        with self.rr_lock:
            current_index = self.round_robin_state.get(pattern, 0)
            selected_agent = agents[current_index % len(agents)]
            self.round_robin_state[pattern] = (current_index + 1) % len(agents)
            return [selected_agent]
    
    def _least_loaded_select(self, agents: List[str]) -> List[str]:
        """Select least loaded agent."""
        if not agents:
            return []
        
        with self.health_lock:
            min_load = float('inf')
            least_loaded = agents[0]
            
            for agent in agents:
                health_info = self.agent_health.get(agent, {})
                load = health_info.get('message_count', 0)
                if load < min_load:
                    min_load = load
                    least_loaded = agent
            
            return [least_loaded]
    
    def _update_stats(self, target_agents: List[str], message: Message) -> None:
        """Update performance statistics."""
        with self.stats_lock:
            for agent in target_agents:
                if agent not in self.performance_stats:
                    self.performance_stats[agent] = {
                        'messages_routed': 0,
                        'last_routed': 0,
                        'total_size': 0
                    }
                
                stats = self.performance_stats[agent]
                stats['messages_routed'] += 1
                stats['last_routed'] = time.time()
                
                # Estimate message size
                message_size = len(str(message.payload)) if message.payload else 0
                stats['total_size'] += message_size
        
        # Update agent health
        with self.health_lock:
            for agent in target_agents:
                if agent in self.agent_health:
                    self.agent_health[agent]['message_count'] += 1
                    self.agent_health[agent]['last_seen'] = time.time()
    
    def update_agent_health(self, agent_id: str, healthy: bool, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Update agent health status.
        
        Args:
            agent_id: Agent to update
            healthy: Whether the agent is healthy
            metadata: Additional health metadata
        """
        with self.health_lock:
            if agent_id not in self.agent_health:
                self.agent_health[agent_id] = {
                    'healthy': True,
                    'last_seen': time.time(),
                    'message_count': 0,
                    'error_count': 0
                }
            
            health_info = self.agent_health[agent_id]
            health_info['healthy'] = healthy
            health_info['last_seen'] = time.time()
            
            if not healthy:
                health_info['error_count'] += 1
            
            if metadata:
                health_info.update(metadata)
    
    def get_routes(self) -> List[Dict[str, Any]]:
        """Get all current routes."""
        with self.route_lock:
            return [
                {
                    'pattern': route.pattern,
                    'agents': route.agents,
                    'strategy': route.strategy.value,
                    'metadata': route.metadata
                }
                for route in self.routes
            ]
    
    def get_agent_health(self) -> Dict[str, Dict[str, Any]]:
        """Get health status of all agents."""
        with self.health_lock:
            return {
                agent_id: health_info.copy()
                for agent_id, health_info in self.agent_health.items()
            }
    
    def get_performance_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get performance statistics."""
        with self.stats_lock:
            return {
                agent_id: stats.copy()
                for agent_id, stats in self.performance_stats.items()
            }
    
    def cleanup_stale_agents(self, timeout_seconds: float = 300.0) -> int:
        """
        Clean up agents that haven't been seen recently.
        
        Args:
            timeout_seconds: Timeout for considering an agent stale
            
        Returns:
            Number of agents cleaned up
        """
        current_time = time.time()
        cleaned_count = 0
        
        with self.health_lock:
            stale_agents = []
            for agent_id, health_info in self.agent_health.items():
                if current_time - health_info['last_seen'] > timeout_seconds:
                    stale_agents.append(agent_id)
            
            for agent_id in stale_agents:
                del self.agent_health[agent_id]
                cleaned_count += 1
        
        # Also clean up from performance stats
        with self.stats_lock:
            for agent_id in stale_agents:
                self.performance_stats.pop(agent_id, None)
        
        return cleaned_count
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get routing statistics."""
        with self.route_lock:
            route_count = len(self.routes)
        
        with self.health_lock:
            agent_count = len(self.agent_health)
            healthy_count = sum(1 for h in self.agent_health.values() if h.get('healthy', True))
        
        with self.stats_lock:
            total_messages = sum(s.get('messages_routed', 0) for s in self.performance_stats.values())
        
        return {
            'routes_configured': route_count,
            'agents_tracked': agent_count,
            'healthy_agents': healthy_count,
            'total_messages_routed': total_messages,
            'routing_strategies': [strategy.value for strategy in RoutingStrategy]
        }
