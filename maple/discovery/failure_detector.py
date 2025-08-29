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
from typing import Dict, List, Callable, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
from ..core.result import Result
from .registry import AgentRegistry, AgentInfo
from .health_monitor import HealthMonitor, HealthStatus


class FailureType(Enum):
    """Types of failures that can be detected."""
    HEARTBEAT_TIMEOUT = "heartbeat_timeout"
    HEALTH_DEGRADATION = "health_degradation"
    RESPONSE_TIMEOUT = "response_timeout"
    ERROR_THRESHOLD_EXCEEDED = "error_threshold_exceeded"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    CRASH_DETECTED = "crash_detected"


@dataclass
class FailureEvent:
    """Represents a detected failure event."""
    agent_id: str
    failure_type: FailureType
    timestamp: float
    details: Dict = field(default_factory=dict)
    severity: str = "medium"  # low, medium, high, critical
    recovery_attempted: bool = False
    recovery_successful: bool = False


@dataclass
class RecoveryAction:
    """Defines a recovery action for a failure type."""
    failure_type: FailureType
    action_type: str  # restart, failover, degrade, ignore
    max_attempts: int = 3
    backoff_seconds: int = 10
    timeout_seconds: int = 60


class FailureDetector:
    """Detects and manages agent failures with recovery capabilities."""
    
    def __init__(self, registry: AgentRegistry, health_monitor: HealthMonitor):
        self.registry = registry
        self.health_monitor = health_monitor
        
        # Failure tracking
        self.failure_history: Dict[str, List[FailureEvent]] = {}
        self.recovery_attempts: Dict[str, Dict[FailureType, int]] = {}
        self.failure_callbacks: List[Callable[[FailureEvent], None]] = []
        
        # Recovery actions
        self.recovery_actions: Dict[FailureType, RecoveryAction] = {
            FailureType.HEARTBEAT_TIMEOUT: RecoveryAction(
                FailureType.HEARTBEAT_TIMEOUT, "restart", 2, 30, 120
            ),
            FailureType.HEALTH_DEGRADATION: RecoveryAction(
                FailureType.HEALTH_DEGRADATION, "degrade", 1, 10, 60
            ),
            FailureType.RESPONSE_TIMEOUT: RecoveryAction(
                FailureType.RESPONSE_TIMEOUT, "restart", 3, 15, 90
            ),
            FailureType.ERROR_THRESHOLD_EXCEEDED: RecoveryAction(
                FailureType.ERROR_THRESHOLD_EXCEEDED, "restart", 2, 20, 100
            ),
            FailureType.RESOURCE_EXHAUSTION: RecoveryAction(
                FailureType.RESOURCE_EXHAUSTION, "degrade", 1, 5, 30
            ),
            FailureType.CRASH_DETECTED: RecoveryAction(
                FailureType.CRASH_DETECTED, "restart", 3, 60, 300
            )
        }
        
        # Monitoring state
        self._detecting = False
        self._detector_thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()
        
        # Detection parameters
        self.heartbeat_timeout = 60  # seconds
        self.health_check_interval = 30  # seconds
        self.max_consecutive_failures = 3
        self.failure_rate_window = 300  # 5 minutes
    
    def start_detection(self):
        """Start the failure detection system."""
        with self._lock:
            if self._detecting:
                return
            
            self._detecting = True
            self._detector_thread = threading.Thread(target=self._detection_loop, daemon=True)
            self._detector_thread.start()
            
            # Register health monitor callback
            self.health_monitor.add_health_callback(self._on_health_status_change)
    
    def stop_detection(self):
        """Stop the failure detection system."""
        with self._lock:
            self._detecting = False
            if self._detector_thread:
                self._detector_thread.join(timeout=5.0)
    
    def detect_failures(self) -> List[FailureEvent]:
        """Manually trigger failure detection and return detected failures."""
        failures = []
        
        # Check for heartbeat timeouts
        stale_agents = self.registry.get_stale_agents(self.heartbeat_timeout)
        for agent in stale_agents:
            failure = FailureEvent(
                agent_id=agent.agent_id,
                failure_type=FailureType.HEARTBEAT_TIMEOUT,
                timestamp=time.time(),
                details={
                    "last_heartbeat": agent.last_heartbeat,
                    "timeout_seconds": self.heartbeat_timeout
                },
                severity="high"
            )
            failures.append(failure)
        
        # Check for health degradation
        agents = self.registry.list_agents(status="online")
        for agent in agents:
            health_result = self.health_monitor.get_agent_health(agent.agent_id)
            if health_result.is_ok():
                health = health_result.unwrap()
                
                if health.status in ["unhealthy", "degraded"] and health.score < 0.5:
                    failure = FailureEvent(
                        agent_id=agent.agent_id,
                        failure_type=FailureType.HEALTH_DEGRADATION,
                        timestamp=time.time(),
                        details={
                            "health_score": health.score,
                            "issues": health.issues
                        },
                        severity="medium" if health.status == "degraded" else "high"
                    )
                    failures.append(failure)
        
        # Record and process failures
        for failure in failures:
            self._record_failure(failure)
            self._attempt_recovery(failure)
        
        return failures
    
    def _record_failure(self, failure: FailureEvent):
        """Record a failure event."""
        with self._lock:
            if failure.agent_id not in self.failure_history:
                self.failure_history[failure.agent_id] = []
            
            self.failure_history[failure.agent_id].append(failure)
            
            # Keep only recent failures (last 24 hours)
            cutoff_time = time.time() - 86400  # 24 hours
            self.failure_history[failure.agent_id] = [
                f for f in self.failure_history[failure.agent_id]
                if f.timestamp >= cutoff_time
            ]
            
            # Notify callbacks
            for callback in self.failure_callbacks:
                try:
                    callback(failure)
                except Exception:
                    pass  # Don't let callback errors stop failure handling
    
    def _attempt_recovery(self, failure: FailureEvent) -> bool:
        """Attempt to recover from a failure."""
        
        if failure.failure_type not in self.recovery_actions:
            return False
        
        recovery_action = self.recovery_actions[failure.failure_type]
        
        with self._lock:
            # Initialize recovery tracking
            if failure.agent_id not in self.recovery_attempts:
                self.recovery_attempts[failure.agent_id] = {}
            
            if failure.failure_type not in self.recovery_attempts[failure.agent_id]:
                self.recovery_attempts[failure.agent_id][failure.failure_type] = 0
            
            # Check if we've exceeded max attempts
            attempts = self.recovery_attempts[failure.agent_id][failure.failure_type]
            if attempts >= recovery_action.max_attempts:
                return False
            
            # Increment attempt counter
            self.recovery_attempts[failure.agent_id][failure.failure_type] += 1
        
        # Execute recovery action
        success = self._execute_recovery_action(failure, recovery_action)
        
        # Update failure record
        failure.recovery_attempted = True
        failure.recovery_successful = success
        
        return success
    
    def _execute_recovery_action(self, failure: FailureEvent, recovery_action: RecoveryAction) -> bool:
        """Execute a specific recovery action."""
        
        try:
            if recovery_action.action_type == "restart":
                return self._restart_agent(failure.agent_id)
            elif recovery_action.action_type == "failover":
                return self._failover_agent(failure.agent_id)
            elif recovery_action.action_type == "degrade":
                return self._degrade_agent(failure.agent_id)
            elif recovery_action.action_type == "ignore":
                return True  # Successfully ignored
            else:
                return False
        except Exception:
            return False
    
    def _restart_agent(self, agent_id: str) -> bool:
        """Attempt to restart a failed agent."""
        
        # Mark agent as restarting
        result = self.registry.update_agent_status(agent_id, "restarting")
        if result.is_err():
            return False
        
        # In a real implementation, this would trigger an actual agent restart
        # For now, we simulate by marking the agent as online after a delay
        
        def delayed_restart():
            time.sleep(5)  # Simulate restart delay
            # Simulate successful restart
            self.registry.update_agent_status(agent_id, "online", load=0.0)
            
            # Reset recovery attempt counter on successful restart
            with self._lock:
                if agent_id in self.recovery_attempts:
                    self.recovery_attempts[agent_id].clear()
        
        threading.Thread(target=delayed_restart, daemon=True).start()
        return True
    
    def _failover_agent(self, agent_id: str) -> bool:
        """Failover tasks from a failed agent to healthy agents."""
        
        # Mark agent as failed
        result = self.registry.update_agent_status(agent_id, "failed")
        if result.is_err():
            return False
        
        # In a real implementation, this would:
        # 1. Find alternative agents with similar capabilities
        # 2. Redistribute the failed agent's tasks
        # 3. Update routing tables
        
        return True
    
    def _degrade_agent(self, agent_id: str) -> bool:
        """Degrade an agent's capabilities to reduce load."""
        
        # Mark agent as degraded
        result = self.registry.update_agent_status(agent_id, "degraded", load=0.3)
        if result.is_err():
            return False
        
        # In a real implementation, this would:
        # 1. Reduce the agent's task capacity
        # 2. Lower its priority in task assignment
        # 3. Monitor for recovery
        
        return True
    
    def _on_health_status_change(self, agent_id: str, health_status: HealthStatus):
        """Callback for health status changes."""
        
        # Trigger failure detection if health deteriorates
        if health_status.status in ["unhealthy", "offline"]:
            if health_status.status == "offline":
                failure_type = FailureType.HEARTBEAT_TIMEOUT
            else:
                failure_type = FailureType.HEALTH_DEGRADATION
            
            failure = FailureEvent(
                agent_id=agent_id,
                failure_type=failure_type,
                timestamp=time.time(),
                details={
                    "health_score": health_status.score,
                    "issues": health_status.issues or []
                },
                severity="high" if health_status.status == "offline" else "medium"
            )
            
            self._record_failure(failure)
            self._attempt_recovery(failure)
    
    def get_failure_history(self, agent_id: str, hours: int = 24) -> Result[List[FailureEvent], str]:
        """Get failure history for an agent."""
        
        with self._lock:
            if agent_id not in self.failure_history:
                return Result.ok([])
            
            cutoff_time = time.time() - (hours * 3600)
            recent_failures = [
                failure for failure in self.failure_history[agent_id]
                if failure.timestamp >= cutoff_time
            ]
            
            return Result.ok(recent_failures)
    
    def get_failure_statistics(self) -> Dict:
        """Get system-wide failure statistics."""
        
        with self._lock:
            total_failures = 0
            failures_by_type = {}
            successful_recoveries = 0
            failed_recoveries = 0
            
            for agent_failures in self.failure_history.values():
                for failure in agent_failures:
                    total_failures += 1
                    
                    if failure.failure_type.value not in failures_by_type:
                        failures_by_type[failure.failure_type.value] = 0
                    failures_by_type[failure.failure_type.value] += 1
                    
                    if failure.recovery_attempted:
                        if failure.recovery_successful:
                            successful_recoveries += 1
                        else:
                            failed_recoveries += 1
            
            recovery_rate = 0.0
            if successful_recoveries + failed_recoveries > 0:
                recovery_rate = successful_recoveries / (successful_recoveries + failed_recoveries)
            
            return {
                "total_failures": total_failures,
                "failures_by_type": failures_by_type,
                "successful_recoveries": successful_recoveries,
                "failed_recoveries": failed_recoveries,
                "recovery_rate": recovery_rate,
                "timestamp": time.time()
            }
    
    def add_failure_callback(self, callback: Callable[[FailureEvent], None]):
        """Add a callback to be notified of failure events."""
        self.failure_callbacks.append(callback)
    
    def configure_recovery_action(self, failure_type: FailureType, action: RecoveryAction):
        """Configure a custom recovery action for a failure type."""
        self.recovery_actions[failure_type] = action
    
    def _detection_loop(self):
        """Main failure detection loop."""
        
        while self._detecting:
            try:
                self.detect_failures()
                time.sleep(self.health_check_interval)
            except Exception:
                # Don't let errors stop the detection loop
                time.sleep(1)
