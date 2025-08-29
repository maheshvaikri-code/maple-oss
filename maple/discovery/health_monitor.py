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
from typing import Dict, List, Callable, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from ..core.result import Result
from .registry import AgentRegistry, AgentInfo


@dataclass
class HealthMetrics:
    """Health metrics for an agent."""
    agent_id: str
    timestamp: float
    cpu_usage: float = 0.0  # CPU usage percentage
    memory_usage: float = 0.0  # Memory usage percentage
    active_tasks: int = 0
    response_time: float = 0.0  # Average response time in ms
    error_rate: float = 0.0  # Error rate percentage
    uptime: float = 0.0  # Uptime in seconds


@dataclass
class HealthStatus:
    """Overall health status of an agent."""
    agent_id: str
    status: str  # healthy, degraded, unhealthy, offline
    score: float  # 0.0 to 1.0, higher is better
    last_check: float
    issues: List[str] = None  # List of health issues


class HealthMonitor:
    """Monitors agent health and manages heartbeats."""
    
    def __init__(self, registry: AgentRegistry, heartbeat_interval: int = 30):
        self.registry = registry
        self.heartbeat_interval = heartbeat_interval
        self.health_metrics: Dict[str, HealthMetrics] = {}
        self.health_history: Dict[str, List[HealthMetrics]] = {}
        self.health_callbacks: List[Callable[[str, HealthStatus], None]] = []
        
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()
        
        # Health thresholds
        self.cpu_threshold = 80.0
        self.memory_threshold = 85.0
        self.response_time_threshold = 5000.0  # 5 seconds
        self.error_rate_threshold = 10.0  # 10%
        self.heartbeat_timeout = heartbeat_interval * 2
    
    def start_monitoring(self):
        """Start the health monitoring system."""
        with self._lock:
            if self._monitoring:
                return
            
            self._monitoring = True
            self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self._monitor_thread.start()
    
    def stop_monitoring(self):
        """Stop the health monitoring system."""
        with self._lock:
            self._monitoring = False
            if self._monitor_thread:
                self._monitor_thread.join(timeout=5.0)
    
    def record_heartbeat(self, agent_id: str, metrics: Dict = None) -> Result[None, str]:
        """Record a heartbeat from an agent with optional metrics."""
        
        # Update registry heartbeat
        heartbeat_result = self.registry.heartbeat(agent_id)
        if heartbeat_result.is_err():
            return heartbeat_result
        
        # Record health metrics if provided
        if metrics:
            health_metrics = HealthMetrics(
                agent_id=agent_id,
                timestamp=time.time(),
                cpu_usage=metrics.get('cpu_usage', 0.0),
                memory_usage=metrics.get('memory_usage', 0.0),
                active_tasks=metrics.get('active_tasks', 0),
                response_time=metrics.get('response_time', 0.0),
                error_rate=metrics.get('error_rate', 0.0),
                uptime=metrics.get('uptime', 0.0)
            )
            
            with self._lock:
                self.health_metrics[agent_id] = health_metrics
                
                # Maintain history
                if agent_id not in self.health_history:
                    self.health_history[agent_id] = []
                
                self.health_history[agent_id].append(health_metrics)
                
                # Keep only last 100 entries
                if len(self.health_history[agent_id]) > 100:
                    self.health_history[agent_id] = self.health_history[agent_id][-100:]
        
        return Result.ok(None)
    
    def get_agent_health(self, agent_id: str) -> Result[HealthStatus, str]:
        """Get the current health status of an agent."""
        
        agent_result = self.registry.get_agent(agent_id)
        if agent_result.is_err():
            return Result.err(agent_result.unwrap_err())
        
        agent = agent_result.unwrap()
        current_time = time.time()
        
        # Check if agent is sending heartbeats
        time_since_heartbeat = current_time - agent.last_heartbeat
        
        if time_since_heartbeat > self.heartbeat_timeout:
            return Result.ok(HealthStatus(
                agent_id=agent_id,
                status="offline",
                score=0.0,
                last_check=current_time,
                issues=["No heartbeat received"]
            ))
        
        # Get latest metrics
        with self._lock:
            metrics = self.health_metrics.get(agent_id)
        
        if not metrics:
            # No metrics available, but agent is sending heartbeats
            return Result.ok(HealthStatus(
                agent_id=agent_id,
                status="healthy",
                score=0.8,  # Default score for active but no metrics
                last_check=current_time,
                issues=[]
            ))
        
        # Evaluate health based on metrics
        return self._evaluate_health(agent, metrics)
    
    def _evaluate_health(self, agent: AgentInfo, metrics: HealthMetrics) -> Result[HealthStatus, str]:
        """Evaluate the health of an agent based on metrics."""
        
        issues = []
        score_factors = []
        
        # CPU usage check
        if metrics.cpu_usage > self.cpu_threshold:
            issues.append(f"High CPU usage: {metrics.cpu_usage:.1f}%")
            score_factors.append(0.7)  # Reduce score
        else:
            score_factors.append(1.0)
        
        # Memory usage check
        if metrics.memory_usage > self.memory_threshold:
            issues.append(f"High memory usage: {metrics.memory_usage:.1f}%")
            score_factors.append(0.6)
        else:
            score_factors.append(1.0)
        
        # Response time check
        if metrics.response_time > self.response_time_threshold:
            issues.append(f"High response time: {metrics.response_time:.1f}ms")
            score_factors.append(0.8)
        else:
            score_factors.append(1.0)
        
        # Error rate check
        if metrics.error_rate > self.error_rate_threshold:
            issues.append(f"High error rate: {metrics.error_rate:.1f}%")
            score_factors.append(0.5)
        else:
            score_factors.append(1.0)
        
        # Task load check
        load_factor = min(metrics.active_tasks / agent.max_concurrent_tasks, 1.0)
        if load_factor > 0.9:
            issues.append(f"High task load: {metrics.active_tasks}/{agent.max_concurrent_tasks}")
            score_factors.append(0.7)
        else:
            score_factors.append(1.0)
        
        # Calculate overall health score
        base_score = sum(score_factors) / len(score_factors)
        
        # Determine status
        if base_score >= 0.8 and not issues:
            status = "healthy"
        elif base_score >= 0.6:
            status = "degraded"
        else:
            status = "unhealthy"
        
        return Result.ok(HealthStatus(
            agent_id=agent.agent_id,
            status=status,
            score=base_score,
            last_check=time.time(),
            issues=issues
        ))
    
    def get_system_health_summary(self) -> Dict:
        """Get a summary of overall system health."""
        
        agents = self.registry.list_agents()
        summary = {
            "total_agents": len(agents),
            "healthy": 0,
            "degraded": 0,
            "unhealthy": 0,
            "offline": 0,
            "average_score": 0.0,
            "timestamp": time.time()
        }
        
        total_score = 0.0
        
        for agent in agents:
            health_result = self.get_agent_health(agent.agent_id)
            if health_result.is_ok():
                health = health_result.unwrap()
                summary[health.status] += 1
                total_score += health.score
        
        if agents:
            summary["average_score"] = total_score / len(agents)
        
        return summary
    
    def add_health_callback(self, callback: Callable[[str, HealthStatus], None]):
        """Add a callback to be notified of health status changes."""
        self.health_callbacks.append(callback)
    
    def get_health_trend(self, agent_id: str, hours: int = 24) -> Result[List[HealthMetrics], str]:
        """Get health metrics trend for an agent over the specified time period."""
        
        with self._lock:
            if agent_id not in self.health_history:
                return Result.err(f"No health history for agent {agent_id}")
            
            # Filter metrics within the time range
            cutoff_time = time.time() - (hours * 3600)
            trend = [
                metric for metric in self.health_history[agent_id]
                if metric.timestamp >= cutoff_time
            ]
            
            return Result.ok(trend)
    
    def _monitor_loop(self):
        """Main monitoring loop running in background thread."""
        
        while self._monitoring:
            try:
                # Check all agents
                agents = self.registry.list_agents()
                
                for agent in agents:
                    health_result = self.get_agent_health(agent.agent_id)
                    
                    if health_result.is_ok():
                        health = health_result.unwrap()
                        
                        # Update agent status in registry
                        self.registry.update_agent_status(agent.agent_id, health.status)
                        
                        # Notify callbacks of health status
                        for callback in self.health_callbacks:
                            try:
                                callback(agent.agent_id, health)
                            except Exception as e:
                                # Don't let callback errors stop monitoring
                                pass
                
                time.sleep(self.heartbeat_interval / 2)  # Check twice per heartbeat interval
                
            except Exception as e:
                # Log error and continue monitoring
                time.sleep(1)
