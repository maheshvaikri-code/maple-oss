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
from typing import Dict, List, Optional, Callable, Tuple
from dataclasses import dataclass
from ..core.result import Result
from ..discovery.registry import AgentRegistry, AgentInfo
from ..discovery.capability_matcher import CapabilityMatcher, CapabilityRequirement, CapabilityMatch
from .task_queue import TaskQueue, Task, TaskStatus, TaskPriority


@dataclass
class SchedulingPolicy:
    """Configuration for task scheduling policies."""
    load_balancing: str = "least_loaded"  # least_loaded, round_robin, capability_weighted
    capability_matching: str = "best_match"  # best_match, first_match, weighted_score
    retry_strategy: str = "exponential_backoff"  # exponential_backoff, linear, immediate
    max_concurrent_per_agent: int = 5
    scheduling_interval: float = 1.0  # seconds
    preemption_enabled: bool = False


@dataclass
class SchedulingMetrics:
    """Metrics about scheduling performance."""
    total_scheduled: int = 0
    successful_assignments: int = 0
    failed_assignments: int = 0
    average_scheduling_time: float = 0.0
    queue_length: int = 0
    active_agents: int = 0
    load_distribution: Dict[str, float] = None


class TaskScheduler:
    """Intelligent task scheduler with advanced assignment algorithms."""
    
    def __init__(
        self,
        task_queue: TaskQueue,
        agent_registry: AgentRegistry,
        capability_matcher: CapabilityMatcher,
        policy: SchedulingPolicy = None
    ):
        self.task_queue = task_queue
        self.agent_registry = agent_registry
        self.capability_matcher = capability_matcher
        self.policy = policy or SchedulingPolicy()
        
        # Scheduling state
        self.agent_loads: Dict[str, int] = {}  # agent_id -> current task count
        self.agent_assignments: Dict[str, List[str]] = {}  # agent_id -> list of task_ids
        self.scheduling_callbacks: List[Callable[[str, str], None]] = []  # task_id, agent_id
        
        # Round-robin state
        self._round_robin_index = 0
        
        # Threading
        self._lock = threading.RLock()
        self._scheduler_thread: Optional[threading.Thread] = None
        self._running = False
        
        # Metrics
        self._metrics = SchedulingMetrics()
        self._scheduling_times: List[float] = []
    
    def start_scheduler(self):
        """Start the automatic task scheduler."""
        with self._lock:
            if self._running:
                return
            
            self._running = True
            self._scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
            self._scheduler_thread.start()
    
    def stop_scheduler(self):
        """Stop the automatic task scheduler."""
        with self._lock:
            self._running = False
        
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=5.0)
    
    def schedule_task(self, task_id: str) -> Result[str, str]:
        """Manually schedule a specific task."""
        
        # Get the task
        task_result = self.task_queue.get_task(task_id)
        if task_result.is_err():
            return Result.err(task_result.unwrap_err())
        
        task = task_result.unwrap()
        
        # Find best agent for the task
        start_time = time.time()
        agent_result = self._find_best_agent(task)
        scheduling_time = time.time() - start_time
        
        # Track scheduling time
        with self._lock:
            self._scheduling_times.append(scheduling_time)
            if len(self._scheduling_times) > 1000:
                self._scheduling_times = self._scheduling_times[-500:]
        
        if agent_result.is_err():
            self._metrics.failed_assignments += 1
            return agent_result
        
        agent_id = agent_result.unwrap()
        
        # Assign task to agent
        assignment_result = self._assign_task_to_agent(task, agent_id)
        
        if assignment_result.is_ok():
            self._metrics.successful_assignments += 1
            self._metrics.total_scheduled += 1
            
            # Notify callbacks
            for callback in self.scheduling_callbacks:
                try:
                    callback(task_id, agent_id)
                except Exception:
                    pass
        else:
            self._metrics.failed_assignments += 1
        
        return assignment_result
    
    def _find_best_agent(self, task: Task) -> Result[str, str]:
        """Find the best agent to execute a task."""
        
        # Get available agents
        agents = self.agent_registry.list_agents(status="online")
        
        if not agents:
            return Result.err("No agents available")
        
        # Filter agents that aren't overloaded
        available_agents = []
        with self._lock:
            for agent in agents:
                current_load = self.agent_loads.get(agent.agent_id, 0)
                if current_load < self.policy.max_concurrent_per_agent:
                    available_agents.append(agent)
        
        if not available_agents:
            return Result.err("All agents are at capacity")
        
        # Convert task requirements to capability requirements
        capability_requirements = [
            CapabilityRequirement(capability=req, required=True)
            for req in task.requirements
        ]
        
        if self.policy.capability_matching == "first_match":
            return self._find_first_matching_agent(capability_requirements, available_agents)
        elif self.policy.capability_matching == "best_match":
            return self._find_best_matching_agent(capability_requirements, available_agents)
        elif self.policy.capability_matching == "weighted_score":
            return self._find_weighted_score_agent(capability_requirements, available_agents, task)
        else:
            return Result.err(f"Unknown capability matching strategy: {self.policy.capability_matching}")
    
    def _find_first_matching_agent(
        self,
        requirements: List[CapabilityRequirement],
        agents: List[AgentInfo]
    ) -> Result[str, str]:
        """Find the first agent that matches requirements."""
        
        if not requirements:
            # No requirements, use load balancing
            return self._apply_load_balancing(agents)
        
        # Find first agent with required capabilities
        matches_result = self.capability_matcher.match_capabilities(requirements, agents)
        if matches_result.is_err():
            return Result.err(matches_result.unwrap_err())
        
        matches = matches_result.unwrap()
        
        if not matches:
            return Result.err("No agents match the required capabilities")
        
        # Return first match
        return Result.ok(matches[0].agent_id)
    
    def _find_best_matching_agent(
        self,
        requirements: List[CapabilityRequirement],
        agents: List[AgentInfo]
    ) -> Result[str, str]:
        """Find the agent with the best capability match."""
        
        if not requirements:
            # No requirements, use load balancing
            return self._apply_load_balancing(agents)
        
        # Get all matches
        matches_result = self.capability_matcher.match_capabilities(requirements, agents)
        if matches_result.is_err():
            return Result.err(matches_result.unwrap_err())
        
        matches = matches_result.unwrap()
        
        if not matches:
            return Result.err("No agents match the required capabilities")
        
        # Find best match (highest availability score)
        best_match = max(matches, key=lambda m: m.availability_score)
        return Result.ok(best_match.agent_id)
    
    def _find_weighted_score_agent(
        self,
        requirements: List[CapabilityRequirement],
        agents: List[AgentInfo],
        task: Task
    ) -> Result[str, str]:
        """Find agent using weighted scoring algorithm."""
        
        if not requirements:
            return self._apply_load_balancing(agents)
        
        # Get capability matches
        matches_result = self.capability_matcher.match_capabilities(requirements, agents)
        if matches_result.is_err():
            return Result.err(matches_result.unwrap_err())
        
        matches = matches_result.unwrap()
        
        if not matches:
            return Result.err("No agents match the required capabilities")
        
        # Calculate weighted scores
        best_agent = None
        best_score = -1.0
        
        with self._lock:
            for match in matches:
                # Base score from capability matching
                capability_score = match.availability_score
                
                # Load balancing factor
                current_load = self.agent_loads.get(match.agent_id, 0)
                load_factor = 1.0 - (current_load / self.policy.max_concurrent_per_agent)
                
                # Priority boost for high-priority tasks
                priority_factor = 1.0
                if task.priority == TaskPriority.CRITICAL:
                    priority_factor = 1.5
                elif task.priority == TaskPriority.HIGH:
                    priority_factor = 1.2
                
                # Combined weighted score
                weighted_score = capability_score * 0.6 + load_factor * 0.3 + priority_factor * 0.1
                
                if weighted_score > best_score:
                    best_score = weighted_score
                    best_agent = match.agent_id
        
        if best_agent:
            return Result.ok(best_agent)
        else:
            return Result.err("Could not determine best agent")
    
    def _apply_load_balancing(self, agents: List[AgentInfo]) -> Result[str, str]:
        """Apply load balancing strategy when no specific requirements."""
        
        if self.policy.load_balancing == "least_loaded":
            return self._find_least_loaded_agent(agents)
        elif self.policy.load_balancing == "round_robin":
            return self._find_round_robin_agent(agents)
        elif self.policy.load_balancing == "capability_weighted":
            return self._find_capability_weighted_agent(agents)
        else:
            return Result.err(f"Unknown load balancing strategy: {self.policy.load_balancing}")
    
    def _find_least_loaded_agent(self, agents: List[AgentInfo]) -> Result[str, str]:
        """Find the agent with the least current load."""
        
        least_loaded_agent = None
        min_load = float('inf')
        
        with self._lock:
            for agent in agents:
                current_load = self.agent_loads.get(agent.agent_id, 0)
                if current_load < min_load:
                    min_load = current_load
                    least_loaded_agent = agent.agent_id
        
        if least_loaded_agent:
            return Result.ok(least_loaded_agent)
        else:
            return Result.err("No agents available for load balancing")
    
    def _find_round_robin_agent(self, agents: List[AgentInfo]) -> Result[str, str]:
        """Find agent using round-robin selection."""
        
        if not agents:
            return Result.err("No agents available")
        
        with self._lock:
            self._round_robin_index = (self._round_robin_index + 1) % len(agents)
            selected_agent = agents[self._round_robin_index]
            return Result.ok(selected_agent.agent_id)
    
    def _find_capability_weighted_agent(self, agents: List[AgentInfo]) -> Result[str, str]:
        """Find agent weighted by capability count."""
        
        # Prefer agents with more capabilities (more versatile)
        best_agent = None
        max_capabilities = -1
        min_load = float('inf')
        
        with self._lock:
            for agent in agents:
                capability_count = len(agent.capabilities)
                current_load = self.agent_loads.get(agent.agent_id, 0)
                
                # Prefer more capabilities, but consider load as tiebreaker
                if (capability_count > max_capabilities or
                    (capability_count == max_capabilities and current_load < min_load)):
                    max_capabilities = capability_count
                    min_load = current_load
                    best_agent = agent.agent_id
        
        if best_agent:
            return Result.ok(best_agent)
        else:
            return Result.err("No suitable agent found")
    
    def _assign_task_to_agent(self, task: Task, agent_id: str) -> Result[str, str]:
        """Assign a task to a specific agent."""
        
        # Update task status
        status_result = self.task_queue.update_task_status(
            task.task_id,
            TaskStatus.ASSIGNED,
            assigned_agent=agent_id
        )
        
        if status_result.is_err():
            return Result.err(f"Failed to update task status: {status_result.unwrap_err()}")
        
        # Update agent load tracking
        with self._lock:
            if agent_id not in self.agent_loads:
                self.agent_loads[agent_id] = 0
            
            self.agent_loads[agent_id] += 1
            
            if agent_id not in self.agent_assignments:
                self.agent_assignments[agent_id] = []
            
            self.agent_assignments[agent_id].append(task.task_id)
        
        return Result.ok(agent_id)
    
    def task_completed(self, task_id: str, agent_id: str) -> Result[None, str]:
        """Notify scheduler that a task has completed."""
        
        with self._lock:
            # Update agent load
            if agent_id in self.agent_loads:
                self.agent_loads[agent_id] = max(0, self.agent_loads[agent_id] - 1)
            
            # Remove from assignments
            if agent_id in self.agent_assignments:
                if task_id in self.agent_assignments[agent_id]:
                    self.agent_assignments[agent_id].remove(task_id)
        
        return Result.ok(None)
    
    def get_scheduling_metrics(self) -> SchedulingMetrics:
        """Get current scheduling metrics."""
        
        with self._lock:
            # Update current metrics
            self._metrics.queue_length = len(self.task_queue.list_tasks(TaskStatus.QUEUED))
            self._metrics.active_agents = len([
                agent for agent in self.agent_registry.list_agents(status="online")
            ])
            self._metrics.load_distribution = dict(self.agent_loads)
            
            # Calculate average scheduling time
            if self._scheduling_times:
                self._metrics.average_scheduling_time = sum(self._scheduling_times) / len(self._scheduling_times)
            
            return self._metrics
    
    def get_agent_load(self, agent_id: str) -> int:
        """Get current load for a specific agent."""
        with self._lock:
            return self.agent_loads.get(agent_id, 0)
    
    def rebalance_loads(self) -> Result[int, str]:
        """Rebalance task loads across agents if needed."""
        
        with self._lock:
            agents = self.agent_registry.list_agents(status="online")
            
            if len(agents) < 2:
                return Result.ok(0)  # No rebalancing needed
            
            # Calculate average load
            total_load = sum(self.agent_loads.values())
            average_load = total_load / len(agents)
            
            # Find overloaded and underloaded agents
            overloaded = []
            underloaded = []
            
            for agent in agents:
                load = self.agent_loads.get(agent.agent_id, 0)
                if load > average_load * 1.5:  # 50% above average
                    overloaded.append((agent.agent_id, load))
                elif load < average_load * 0.5:  # 50% below average
                    underloaded.append((agent.agent_id, load))
            
            # Rebalance by moving tasks from overloaded to underloaded agents
            moves = 0
            
            for overloaded_agent_id, load in overloaded:
                if not underloaded:
                    break
                
                # Find tasks that can be moved (not yet running)
                moveable_tasks = []
                if overloaded_agent_id in self.agent_assignments:
                    for task_id in self.agent_assignments[overloaded_agent_id]:
                        task_result = self.task_queue.get_task(task_id)
                        if task_result.is_ok():
                            task = task_result.unwrap()
                            if task.status == TaskStatus.ASSIGNED:
                                moveable_tasks.append(task)
                
                # Move tasks to underloaded agents
                for task in moveable_tasks:
                    if not underloaded:
                        break
                    
                    underloaded_agent_id, _ = underloaded.pop(0)
                    
                    # Reassign task
                    reassign_result = self._assign_task_to_agent(task, underloaded_agent_id)
                    if reassign_result.is_ok():
                        # Remove from old agent
                        self.agent_loads[overloaded_agent_id] -= 1
                        self.agent_assignments[overloaded_agent_id].remove(task.task_id)
                        moves += 1
            
            return Result.ok(moves)
    
    def add_scheduling_callback(self, callback: Callable[[str, str], None]):
        """Add callback for scheduling events."""
        self.scheduling_callbacks.append(callback)
    
    def _scheduler_loop(self):
        """Main scheduling loop."""
        
        while self._running:
            try:
                # Get next queued task
                task_result = self.task_queue.get_next_task(timeout_seconds=self.policy.scheduling_interval)
                
                if task_result.is_ok() and task_result.unwrap():
                    task = task_result.unwrap()
                    
                    # Schedule the task
                    schedule_result = self.schedule_task(task.task_id)
                    
                    if schedule_result.is_err():
                        # Failed to schedule, put task back
                        self.task_queue.update_task_status(task.task_id, TaskStatus.QUEUED)
                
                # Periodic rebalancing
                if int(time.time()) % 60 == 0:  # Every minute
                    self.rebalance_loads()
                
                time.sleep(0.1)  # Small delay to prevent busy loop
                
            except Exception:
                time.sleep(1)  # Error occurred, wait before retrying
