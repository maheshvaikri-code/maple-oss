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
import random
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
from ..core.result import Result
from .task_queue import TaskQueue, Task, TaskStatus
from .scheduler import TaskScheduler


class RetryStrategy(Enum):
    """Retry strategies for failed tasks."""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_INTERVAL = "fixed_interval"
    IMMEDIATE = "immediate"
    ADAPTIVE = "adaptive"


class FailureType(Enum):
    """Types of failures that can occur during task execution."""
    AGENT_FAILURE = "agent_failure"
    TIMEOUT = "timeout"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    VALIDATION_ERROR = "validation_error"
    NETWORK_ERROR = "network_error"
    DEPENDENCY_FAILURE = "dependency_failure"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class FaultTolerancePolicy:
    """Configuration for fault tolerance behavior."""
    max_retries: int = 3
    retry_strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    base_delay: float = 1.0  # seconds
    max_delay: float = 300.0  # 5 minutes max delay
    jitter: bool = True  # Add random jitter to delays
    failover_enabled: bool = True
    circuit_breaker_enabled: bool = True
    circuit_breaker_threshold: int = 5  # failures before opening
    circuit_breaker_timeout: float = 60.0  # seconds


@dataclass
class FailureRecord:
    """Record of a task failure."""
    task_id: str
    agent_id: str
    failure_type: FailureType
    error_message: str
    timestamp: float = field(default_factory=time.time)
    retry_attempt: int = 0
    recovery_action: Optional[str] = None


@dataclass
class CircuitBreakerState:
    """State of a circuit breaker for an agent."""
    agent_id: str
    failure_count: int = 0
    last_failure_time: float = 0.0
    state: str = "closed"  # closed, open, half_open
    next_attempt_time: float = 0.0


class FaultTolerantExecutor:
    """Advanced fault tolerance system with circuit breakers and intelligent retry."""
    
    def __init__(
        self,
        task_queue: TaskQueue,
        scheduler: TaskScheduler,
        policy: FaultTolerancePolicy = None
    ):
        self.task_queue = task_queue
        self.scheduler = scheduler
        self.policy = policy or FaultTolerancePolicy()
        
        # Failure tracking
        self.failure_history: Dict[str, List[FailureRecord]] = {}
        self.agent_circuit_breakers: Dict[str, CircuitBreakerState] = {}
        self.task_retry_counts: Dict[str, int] = {}
        
        # Recovery strategies
        self.recovery_handlers: Dict[FailureType, Callable[[Task, FailureRecord], bool]] = {}
        self.failure_callbacks: List[Callable[[FailureRecord], None]] = []
        
        # Threading
        self._lock = threading.RLock()
        self._executor_thread: Optional[threading.Thread] = None
        self._running = False
        
        # Statistics
        self._total_failures = 0
        self._successful_recoveries = 0
        self._failed_recoveries = 0
        
        # Initialize default recovery handlers
        self._initialize_default_handlers()
    
    def start_executor(self):
        """Start the fault-tolerant executor."""
        with self._lock:
            if self._running:
                return
            
            self._running = True
            self._executor_thread = threading.Thread(target=self._executor_loop, daemon=True)
            self._executor_thread.start()
    
    def stop_executor(self):
        """Stop the fault-tolerant executor."""
        with self._lock:
            self._running = False
        
        if self._executor_thread:
            self._executor_thread.join(timeout=5.0)
    
    def handle_task_failure(
        self,
        task_id: str,
        agent_id: str,
        failure_type: FailureType,
        error_message: str
    ) -> Result[str, str]:
        """Handle a task failure with appropriate recovery strategy."""
        
        # Get task details
        task_result = self.task_queue.get_task(task_id)
        if task_result.is_err():
            return Result.err(task_result.unwrap_err())
        
        task = task_result.unwrap()
        
        # Create failure record
        failure_record = FailureRecord(
            task_id=task_id,
            agent_id=agent_id,
            failure_type=failure_type,
            error_message=error_message,
            retry_attempt=self.task_retry_counts.get(task_id, 0)
        )
        
        # Record the failure
        self._record_failure(failure_record)
        
        # Update circuit breaker state
        if self.policy.circuit_breaker_enabled:
            self._update_circuit_breaker(agent_id)
        
        # Determine recovery strategy
        recovery_result = self._attempt_recovery(task, failure_record)
        
        # Update task status based on recovery result
        if recovery_result.is_ok():
            recovery_action = recovery_result.unwrap()
            failure_record.recovery_action = recovery_action
            
            if recovery_action in ["retry", "failover"]:
                return Result.ok(recovery_action)
            elif recovery_action == "abandon":
                self.task_queue.update_task_status(task_id, TaskStatus.FAILED, error=error_message)
                return Result.ok("abandoned")
        else:
            self.task_queue.update_task_status(task_id, TaskStatus.FAILED, error=error_message)
            return Result.err(f"Recovery failed: {recovery_result.unwrap_err()}")
        
        return Result.ok("handled")
    
    def _record_failure(self, failure_record: FailureRecord):
        """Record a failure for analysis and tracking."""
        
        with self._lock:
            # Add to failure history
            if failure_record.task_id not in self.failure_history:
                self.failure_history[failure_record.task_id] = []
            
            self.failure_history[failure_record.task_id].append(failure_record)
            
            # Update retry count
            self.task_retry_counts[failure_record.task_id] = failure_record.retry_attempt + 1
            
            # Update statistics
            self._total_failures += 1
            
            # Notify callbacks
            for callback in self.failure_callbacks:
                try:
                    callback(failure_record)
                except Exception:
                    pass
    
    def _attempt_recovery(self, task: Task, failure_record: FailureRecord) -> Result[str, str]:
        """Attempt to recover from a task failure."""
        
        # Check if we should retry
        if not self._should_retry(task, failure_record):
            return Result.ok("abandon")
        
        # Try specific recovery handler first
        if failure_record.failure_type in self.recovery_handlers:
            handler = self.recovery_handlers[failure_record.failure_type]
            
            try:
                if handler(task, failure_record):
                    self._successful_recoveries += 1
                    return Result.ok("custom_recovery")
                else:
                    self._failed_recoveries += 1
            except Exception as e:
                return Result.err(f"Recovery handler failed: {str(e)}")
        
        # Default recovery strategies
        if failure_record.failure_type == FailureType.AGENT_FAILURE:
            return self._handle_agent_failure(task, failure_record)
        elif failure_record.failure_type == FailureType.TIMEOUT:
            return self._handle_timeout(task, failure_record)
        elif failure_record.failure_type == FailureType.RESOURCE_EXHAUSTION:
            return self._handle_resource_exhaustion(task, failure_record)
        elif failure_record.failure_type == FailureType.NETWORK_ERROR:
            return self._handle_network_error(task, failure_record)
        else:
            return self._handle_generic_failure(task, failure_record)
    
    def _should_retry(self, task: Task, failure_record: FailureRecord) -> bool:
        """Determine if a task should be retried."""
        
        # Check maximum retries
        current_retries = self.task_retry_counts.get(task.task_id, 0)
        if current_retries >= min(task.max_retries, self.policy.max_retries):
            return False
        
        # Check circuit breaker
        if self.policy.circuit_breaker_enabled:
            cb_state = self.agent_circuit_breakers.get(failure_record.agent_id)
            if cb_state and cb_state.state == "open":
                return False
        
        # Some failures shouldn't be retried
        if failure_record.failure_type in [FailureType.VALIDATION_ERROR]:
            return False
        
        return True
    
    def _handle_agent_failure(self, task: Task, failure_record: FailureRecord) -> Result[str, str]:
        """Handle agent failure with failover."""
        
        if self.policy.failover_enabled:
            # Try to failover to another agent
            failover_result = self._failover_task(task, failure_record.agent_id)
            if failover_result.is_ok():
                return Result.ok("failover")
        
        # Fallback to retry with delay
        return self._schedule_retry(task, failure_record)
    
    def _handle_timeout(self, task: Task, failure_record: FailureRecord) -> Result[str, str]:
        """Handle timeout by extending deadline or retrying."""
        
        # For timeouts, we might want to extend the timeout or retry immediately
        if failure_record.retry_attempt < 2:  # First couple of retries
            # Extend timeout by 50%
            task.timeout_seconds = int(task.timeout_seconds * 1.5)
            return self._schedule_retry(task, failure_record)
        else:
            # Try failover after multiple timeouts
            if self.policy.failover_enabled:
                failover_result = self._failover_task(task, failure_record.agent_id)
                if failover_result.is_ok():
                    return Result.ok("failover")
            
            return self._schedule_retry(task, failure_record)
    
    def _handle_resource_exhaustion(self, task: Task, failure_record: FailureRecord) -> Result[str, str]:
        """Handle resource exhaustion by waiting or failing over."""
        
        # Wait longer for resource exhaustion
        delay = self._calculate_retry_delay(failure_record.retry_attempt) * 2
        
        return self._schedule_retry(task, failure_record, delay)
    
    def _handle_network_error(self, task: Task, failure_record: FailureRecord) -> Result[str, str]:
        """Handle network errors with immediate or short delay retry."""
        
        if failure_record.retry_attempt < 3:
            # Quick retry for network errors
            delay = min(self._calculate_retry_delay(failure_record.retry_attempt), 30)
            return self._schedule_retry(task, failure_record, delay)
        else:
            # Try failover after multiple network errors
            if self.policy.failover_enabled:
                failover_result = self._failover_task(task, failure_record.agent_id)
                if failover_result.is_ok():
                    return Result.ok("failover")
        
        return Result.ok("abandon")
    
    def _handle_generic_failure(self, task: Task, failure_record: FailureRecord) -> Result[str, str]:
        """Handle generic failures with standard retry logic."""
        
        return self._schedule_retry(task, failure_record)
    
    def _schedule_retry(
        self,
        task: Task,
        failure_record: FailureRecord,
        delay_override: float = None
    ) -> Result[str, str]:
        """Schedule a task for retry with appropriate delay."""
        
        if delay_override is not None:
            delay = delay_override
        else:
            delay = self._calculate_retry_delay(failure_record.retry_attempt)
        
        def retry_task():
            time.sleep(delay)
            
            # Requeue the task
            requeue_result = self.task_queue.requeue_task(task.task_id)
            
            if requeue_result.is_ok():
                self._successful_recoveries += 1
            else:
                self._failed_recoveries += 1
        
        # Schedule retry in background thread
        retry_thread = threading.Thread(target=retry_task, daemon=True)
        retry_thread.start()
        
        return Result.ok("retry")
    
    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculate delay for retry based on strategy."""
        
        if self.policy.retry_strategy == RetryStrategy.IMMEDIATE:
            base_delay = 0.0
        elif self.policy.retry_strategy == RetryStrategy.FIXED_INTERVAL:
            base_delay = self.policy.base_delay
        elif self.policy.retry_strategy == RetryStrategy.LINEAR_BACKOFF:
            base_delay = self.policy.base_delay * (attempt + 1)
        elif self.policy.retry_strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            base_delay = self.policy.base_delay * (2 ** attempt)
        elif self.policy.retry_strategy == RetryStrategy.ADAPTIVE:
            # Adaptive strategy considers recent failure rates
            base_delay = self._calculate_adaptive_delay(attempt)
        else:
            base_delay = self.policy.base_delay
        
        # Apply maximum delay limit
        delay = min(base_delay, self.policy.max_delay)
        
        # Add jitter if enabled
        if self.policy.jitter and delay > 0:
            jitter_amount = delay * 0.1  # 10% jitter
            jitter = random.uniform(-jitter_amount, jitter_amount)
            delay = max(0, delay + jitter)
        
        return delay
    
    def _calculate_adaptive_delay(self, attempt: int) -> float:
        """Calculate adaptive delay based on system load and failure patterns."""
        
        # Base exponential backoff
        base_delay = self.policy.base_delay * (2 ** attempt)
        
        # Adjust based on current system load
        with self._lock:
            total_active_tasks = len(self.scheduler.agent_assignments)
            if total_active_tasks > 50:  # High load
                base_delay *= 1.5
            elif total_active_tasks < 10:  # Low load
                base_delay *= 0.5
        
        # Adjust based on recent failure rate
        recent_failures = self._get_recent_failure_rate()
        if recent_failures > 0.3:  # High failure rate
            base_delay *= 2.0
        elif recent_failures < 0.1:  # Low failure rate
            base_delay *= 0.8
        
        return base_delay
    
    def _get_recent_failure_rate(self) -> float:
        """Calculate recent failure rate for adaptive strategies."""
        
        with self._lock:
            if self._total_failures == 0:
                return 0.0
            
            total_attempts = self._successful_recoveries + self._failed_recoveries
            if total_attempts == 0:
                return 0.0
            
            return self._failed_recoveries / total_attempts
    
    def _failover_task(self, task: Task, failed_agent_id: str) -> Result[str, str]:
        """Attempt to failover a task to another agent."""
        
        # Find alternative agents that can handle this task
        agents = self.scheduler.agent_registry.list_agents(status="online")
        alternative_agents = [
            agent for agent in agents
            if agent.agent_id != failed_agent_id and
            self._can_agent_handle_task(agent, task)
        ]
        
        if not alternative_agents:
            return Result.err("No alternative agents available")
        
        # Check circuit breakers for alternative agents
        if self.policy.circuit_breaker_enabled:
            available_agents = []
            for agent in alternative_agents:
                cb_state = self.agent_circuit_breakers.get(agent.agent_id)
                if not cb_state or cb_state.state != "open":
                    available_agents.append(agent)
            
            if not available_agents:
                return Result.err("All alternative agents have open circuit breakers")
            
            alternative_agents = available_agents
        
        # Select best alternative (least loaded)
        best_agent = min(
            alternative_agents,
            key=lambda a: self.scheduler.get_agent_load(a.agent_id)
        )
        
        # Reassign task
        assign_result = self.scheduler._assign_task_to_agent(task, best_agent.agent_id)
        
        if assign_result.is_ok():
            return Result.ok(best_agent.agent_id)
        else:
            return Result.err(f"Failed to assign task to alternative agent: {assign_result.unwrap_err()}")
    
    def _can_agent_handle_task(self, agent, task: Task) -> bool:
        """Check if an agent can handle a specific task."""
        
        if not task.requirements:
            return True
        
        for requirement in task.requirements:
            if requirement not in agent.capabilities:
                return False
        
        return True
    
    def _update_circuit_breaker(self, agent_id: str):
        """Update circuit breaker state for an agent."""
        
        with self._lock:
            if agent_id not in self.agent_circuit_breakers:
                self.agent_circuit_breakers[agent_id] = CircuitBreakerState(agent_id=agent_id)
            
            cb_state = self.agent_circuit_breakers[agent_id]
            current_time = time.time()
            
            if cb_state.state == "closed":
                cb_state.failure_count += 1
                cb_state.last_failure_time = current_time
                
                # Open circuit if threshold reached
                if cb_state.failure_count >= self.policy.circuit_breaker_threshold:
                    cb_state.state = "open"
                    cb_state.next_attempt_time = current_time + self.policy.circuit_breaker_timeout
            
            elif cb_state.state == "half_open":
                # Failure in half-open state reopens the circuit
                cb_state.state = "open"
                cb_state.failure_count += 1
                cb_state.last_failure_time = current_time
                cb_state.next_attempt_time = current_time + self.policy.circuit_breaker_timeout
    
    def reset_circuit_breaker(self, agent_id: str) -> Result[None, str]:
        """Manually reset a circuit breaker for an agent."""
        
        with self._lock:
            if agent_id in self.agent_circuit_breakers:
                cb_state = self.agent_circuit_breakers[agent_id]
                cb_state.state = "closed"
                cb_state.failure_count = 0
                cb_state.next_attempt_time = 0.0
                return Result.ok(None)
            else:
                return Result.err(f"No circuit breaker found for agent {agent_id}")
    
    def get_circuit_breaker_status(self, agent_id: str) -> Result[CircuitBreakerState, str]:
        """Get the current status of a circuit breaker."""
        
        with self._lock:
            if agent_id in self.agent_circuit_breakers:
                return Result.ok(self.agent_circuit_breakers[agent_id])
            else:
                return Result.err(f"No circuit breaker found for agent {agent_id}")
    
    def register_recovery_handler(
        self,
        failure_type: FailureType,
        handler: Callable[[Task, FailureRecord], bool]
    ):
        """Register a custom recovery handler for a failure type."""
        self.recovery_handlers[failure_type] = handler
    
    def add_failure_callback(self, callback: Callable[[FailureRecord], None]):
        """Add callback for failure events."""
        self.failure_callbacks.append(callback)
    
    def get_fault_tolerance_stats(self) -> Dict[str, Any]:
        """Get fault tolerance statistics."""
        
        with self._lock:
            return {
                "total_failures": self._total_failures,
                "successful_recoveries": self._successful_recoveries,
                "failed_recoveries": self._failed_recoveries,
                "recovery_rate": self._successful_recoveries / max(1, self._total_failures),
                "circuit_breakers": {
                    agent_id: {
                        "state": cb.state,
                        "failure_count": cb.failure_count,
                        "last_failure_time": cb.last_failure_time
                    }
                    for agent_id, cb in self.agent_circuit_breakers.items()
                },
                "active_tasks_with_failures": len(self.failure_history)
            }
    
    def _initialize_default_handlers(self):
        """Initialize default recovery handlers."""
        
        def handle_validation_error(task: Task, failure_record: FailureRecord) -> bool:
            # Validation errors usually shouldn't be retried
            return False
        
        def handle_dependency_failure(task: Task, failure_record: FailureRecord) -> bool:
            # Wait a bit longer for dependencies to recover
            time.sleep(30)
            return True
        
        self.recovery_handlers[FailureType.VALIDATION_ERROR] = handle_validation_error
        self.recovery_handlers[FailureType.DEPENDENCY_FAILURE] = handle_dependency_failure
    
    def _executor_loop(self):
        """Main executor loop for background circuit breaker management."""
        
        while self._running:
            try:
                current_time = time.time()
                
                with self._lock:
                    # Check circuit breakers for half-open transitions
                    for cb_state in self.agent_circuit_breakers.values():
                        if (cb_state.state == "open" and
                            current_time >= cb_state.next_attempt_time):
                            cb_state.state = "half_open"
                
                time.sleep(10)  # Check every 10 seconds
                
            except Exception:
                time.sleep(5)  # Error occurred, wait before retrying
