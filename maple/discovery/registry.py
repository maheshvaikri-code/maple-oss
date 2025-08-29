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

# Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)
# MAPLE - Multi Agent Protocol Language Engine

import time
import threading
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from ..core.result import Result
from ..core.types import Priority


@dataclass
class AgentInfo:
    """Information about a registered agent."""
    agent_id: str
    name: str
    capabilities: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    registered_at: float = field(default_factory=time.time)
    last_heartbeat: float = field(default_factory=time.time)
    status: str = "online"  # online, offline, degraded
    load: float = 0.0  # Current load percentage
    max_concurrent_tasks: int = 10


class AgentRegistry:
    """Registry for managing agent registration and discovery."""
    
    def __init__(self):
        self.agents: Dict[str, AgentInfo] = {}
        self._lock = threading.RLock()
        self._capability_index: Dict[str, Set[str]] = {}  # capability -> set of agent_ids
    
    def register_agent(
        self,
        agent_id: str,
        name: str,
        capabilities: List[str] = None,
        metadata: Dict = None,
        max_concurrent_tasks: int = 10
    ) -> Result[AgentInfo, str]:
        """Register a new agent in the system."""
        capabilities = capabilities or []
        metadata = metadata or {}
        
        with self._lock:
            if agent_id in self.agents:
                return Result.err(f"Agent {agent_id} is already registered")
            
            agent_info = AgentInfo(
                agent_id=agent_id,
                name=name,
                capabilities=capabilities,
                metadata=metadata,
                max_concurrent_tasks=max_concurrent_tasks
            )
            
            self.agents[agent_id] = agent_info
            
            # Update capability index
            for capability in capabilities:
                if capability not in self._capability_index:
                    self._capability_index[capability] = set()
                self._capability_index[capability].add(agent_id)
            
            return Result.ok(agent_info)
    
    def deregister_agent(self, agent_id: str) -> Result[None, str]:
        """Deregister an agent from the system."""
        with self._lock:
            if agent_id not in self.agents:
                return Result.err(f"Agent {agent_id} is not registered")
            
            agent_info = self.agents[agent_id]
            
            # Remove from capability index
            for capability in agent_info.capabilities:
                if capability in self._capability_index:
                    self._capability_index[capability].discard(agent_id)
                    if not self._capability_index[capability]:
                        del self._capability_index[capability]
            
            del self.agents[agent_id]
            return Result.ok(None)
    
    def get_agent(self, agent_id: str) -> Result[AgentInfo, str]:
        """Get information about a specific agent."""
        with self._lock:
            if agent_id not in self.agents:
                return Result.err(f"Agent {agent_id} not found")
            return Result.ok(self.agents[agent_id])
    
    def list_agents(self, status: str = None) -> List[AgentInfo]:
        """List all agents, optionally filtered by status."""
        with self._lock:
            if status:
                return [agent for agent in self.agents.values() if agent.status == status]
            return list(self.agents.values())
    
    def find_agents_by_capability(self, capability: str) -> List[AgentInfo]:
        """Find all agents that have a specific capability."""
        with self._lock:
            if capability not in self._capability_index:
                return []
            
            agent_ids = self._capability_index[capability]
            return [self.agents[agent_id] for agent_id in agent_ids if agent_id in self.agents]
    
    def update_agent_status(self, agent_id: str, status: str, load: float = None) -> Result[None, str]:
        """Update an agent's status and load."""
        with self._lock:
            if agent_id not in self.agents:
                return Result.err(f"Agent {agent_id} not found")
            
            self.agents[agent_id].status = status
            if load is not None:
                self.agents[agent_id].load = load
            
            return Result.ok(None)
    
    def heartbeat(self, agent_id: str) -> Result[None, str]:
        """Record a heartbeat from an agent."""
        with self._lock:
            if agent_id not in self.agents:
                return Result.err(f"Agent {agent_id} not found")
            
            self.agents[agent_id].last_heartbeat = time.time()
            if self.agents[agent_id].status == "offline":
                self.agents[agent_id].status = "online"
            
            return Result.ok(None)
    
    def get_stale_agents(self, timeout_seconds: int = 30) -> List[AgentInfo]:
        """Get agents that haven't sent a heartbeat within the timeout."""
        current_time = time.time()
        with self._lock:
            return [
                agent for agent in self.agents.values()
                if current_time - agent.last_heartbeat > timeout_seconds
            ]
