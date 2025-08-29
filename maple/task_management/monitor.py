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
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from ..core.result import Result
from .task_queue import TaskQueue, Task, TaskStatus


@dataclass
class TaskMetrics:
    """Real-time metrics for a task."""
    task_id: str
    agent_id: str
    start_time: float
    last_update: float
    progress_percentage: float = 0.0
    estimated_completion: Optional[float] = None
    current_step: str = "initializing"
    messages_processed: int = 0
    errors_encountered: int = 0
    memory_usage: float = 0.0  # MB
    cpu_usage: float = 0.0  # percentage
    custom_metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskAlert:
    """Alert for task monitoring issues."""
    task_id: str
    agent_id: str
    alert_type: str  # timeout, stalled, resource_limit, error_threshold
    severity: str  # low, medium, high, critical
    message: str
    timestamp: float = field(default_factory=time.time)
    acknowledged: bool = False


@dataclass
class MonitoringStats:
    """Overall monitoring statistics."""
    total_monitored_tasks: int = 0
    active_tasks: int = 0
    stalled_tasks: int = 0
    timeout_warnings: int = 0
    average_execution_time: float = 0.0
    success_rate: float = 0.0
    alerts_generated: int = 0


class TaskMonitor:
    """Real-time task execution monitor with alerting."""
    
    def __init__(self, task_queue: TaskQueue):
        self.task_queue = task_queue
        
        # Monitoring data
        self.task_metrics: Dict[str, TaskMetrics] = {}
        self.alerts: List[TaskAlert] = []
        self.alert_callbacks: List[Callable[[TaskAlert], None]] = []
        self.progress_callbacks: List[Callable[[str, float], None]] = []
        
        # Configuration
        self.stall_threshold = 300  # 5 minutes without progress
        self.timeout_warning_threshold = 0.8  # Warn at 80% of timeout
        self.error_threshold = 10  # Max errors before alert
        self.memory_limit_mb = 1000  # Memory limit in MB
        self.cpu_limit_percentage = 90  # CPU limit percentage
        
        # Threading
        self._lock = threading.RLock()
        self._monitor_thread: Optional[threading.Thread] = None
        self._running = False
        
        # Statistics
        self._execution_times: List[float] = []
        self._completed_tasks = 0
        self._failed_tasks = 0
    
    def start_monitoring(self):
        """Start the task monitoring system."""
        with self._lock:
            if self._running:
                return
            
            self._running = True
            self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self._monitor_thread.start()
    
    def stop_monitoring(self):
        """Stop the task monitoring system."""
        with self._lock:
            self._running = False
        
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5.0)
    
    def start_task_monitoring(
        self,
        task_id: str,
        agent_id: str,
        estimated_duration: Optional[float] = None
    ) -> Result[None, str]:
        """Start monitoring a specific task."""
        
        # Get task details
        task_result = self.task_queue.get_task(task_id)
        if task_result.is_err():
            return Result.err(task_result.unwrap_err())
        
        task = task_result.unwrap()
        
        with self._lock:
            # Create metrics tracking
            metrics = TaskMetrics(
                task_id=task_id,
                agent_id=agent_id,
                start_time=time.time(),
                last_update=time.time()
            )
            
            # Set estimated completion if provided
            if estimated_duration:
                metrics.estimated_completion = metrics.start_time + estimated_duration
            elif task.timeout_seconds:
                metrics.estimated_completion = metrics.start_time + task.timeout_seconds
            
            self.task_metrics[task_id] = metrics
        
        return Result.ok(None)
    
    def update_task_progress(
        self,
        task_id: str,
        progress_percentage: float,
        current_step: str = None,
        custom_metrics: Dict[str, Any] = None
    ) -> Result[None, str]:
        """Update progress for a monitored task."""
        
        with self._lock:
            if task_id not in self.task_metrics:
                return Result.err(f"Task {task_id} is not being monitored")
            
            metrics = self.task_metrics[task_id]
            old_progress = metrics.progress_percentage
            
            # Update metrics
            metrics.progress_percentage = max(0, min(100, progress_percentage))
            metrics.last_update = time.time()
            
            if current_step:
                metrics.current_step = current_step
            
            if custom_metrics:
                metrics.custom_metrics.update(custom_metrics)
            
            # Update estimated completion based on progress
            if progress_percentage > 0 and progress_percentage < 100:
                elapsed = time.time() - metrics.start_time
                estimated_total = elapsed / (progress_percentage / 100)
                metrics.estimated_completion = metrics.start_time + estimated_total
            
            # Notify progress callbacks
            for callback in self.progress_callbacks:
                try:
                    callback(task_id, progress_percentage)
                except Exception:
                    pass
        
        return Result.ok(None)
    
    def update_task_resources(
        self,
        task_id: str,
        memory_usage_mb: float = None,
        cpu_usage_percentage: float = None,
        messages_processed: int = None,
        errors_encountered: int = None
    ) -> Result[None, str]:
        """Update resource usage for a monitored task."""
        
        with self._lock:
            if task_id not in self.task_metrics:
                return Result.err(f"Task {task_id} is not being monitored")
            
            metrics = self.task_metrics[task_id]
            
            if memory_usage_mb is not None:
                metrics.memory_usage = memory_usage_mb
            
            if cpu_usage_percentage is not None:
                metrics.cpu_usage = cpu_usage_percentage
            
            if messages_processed is not None:
                metrics.messages_processed = messages_processed
            
            if errors_encountered is not None:
                metrics.errors_encountered = errors_encountered
            
            metrics.last_update = time.time()
            
            # Check for resource limit alerts
            self._check_resource_limits(task_id, metrics)
        
        return Result.ok(None)
    
    def stop_task_monitoring(self, task_id: str) -> Result[TaskMetrics, str]:
        """Stop monitoring a task and return final metrics."""
        
        with self._lock:
            if task_id not in self.task_metrics:
                return Result.err(f"Task {task_id} is not being monitored")
            
            metrics = self.task_metrics[task_id]
            
            # Calculate final execution time
            execution_time = time.time() - metrics.start_time
            self._execution_times.append(execution_time)
            
            # Keep only recent execution times
            if len(self._execution_times) > 1000:
                self._execution_times = self._execution_times[-500:]
            
            # Update completion counters
            task_result = self.task_queue.get_task(task_id)
            if task_result.is_ok():
                task = task_result.unwrap()
                if task.status == TaskStatus.COMPLETED:
                    self._completed_tasks += 1
                elif task.status in [TaskStatus.FAILED, TaskStatus.TIMEOUT, TaskStatus.CANCELLED]:
                    self._failed_tasks += 1
            
            # Remove from monitoring
            final_metrics = metrics
            del self.task_metrics[task_id]
            
            return Result.ok(final_metrics)
    
    def get_task_metrics(self, task_id: str) -> Result[TaskMetrics, str]:
        """Get current metrics for a task."""
        
        with self._lock:
            if task_id not in self.task_metrics:
                return Result.err(f"Task {task_id} is not being monitored")
            
            return Result.ok(self.task_metrics[task_id])
    
    def list_monitored_tasks(self) -> List[TaskMetrics]:
        """List all currently monitored tasks."""
        
        with self._lock:
            return list(self.task_metrics.values())
    
    def get_stalled_tasks(self) -> List[TaskMetrics]:
        """Get tasks that appear to be stalled."""
        
        current_time = time.time()
        stalled = []
        
        with self._lock:
            for metrics in self.task_metrics.values():
                time_since_update = current_time - metrics.last_update
                if time_since_update > self.stall_threshold:
                    stalled.append(metrics)
        
        return stalled
    
    def get_timeout_warnings(self) -> List[TaskMetrics]:
        """Get tasks approaching timeout."""
        
        current_time = time.time()
        warnings = []
        
        with self._lock:
            for metrics in self.task_metrics.values():
                if metrics.estimated_completion:
                    time_remaining = metrics.estimated_completion - current_time
                    total_time = metrics.estimated_completion - metrics.start_time
                    
                    if time_remaining > 0 and time_remaining < (total_time * (1 - self.timeout_warning_threshold)):
                        warnings.append(metrics)
        
        return warnings
    
    def get_monitoring_stats(self) -> MonitoringStats:
        """Get overall monitoring statistics."""
        
        with self._lock:
            stats = MonitoringStats()
            
            # Current state
            stats.total_monitored_tasks = len(self.task_metrics)
            stats.active_tasks = len([m for m in self.task_metrics.values() if m.progress_percentage < 100])
            stats.stalled_tasks = len(self.get_stalled_tasks())
            stats.timeout_warnings = len(self.get_timeout_warnings())
            stats.alerts_generated = len(self.alerts)
            
            # Calculate averages
            if self._execution_times:
                stats.average_execution_time = sum(self._execution_times) / len(self._execution_times)
            
            # Calculate success rate
            total_completed = self._completed_tasks + self._failed_tasks
            if total_completed > 0:
                stats.success_rate = self._completed_tasks / total_completed
            
            return stats
    
    def get_alerts(self, acknowledged: bool = None) -> List[TaskAlert]:
        """Get alerts, optionally filtered by acknowledgment status."""
        
        with self._lock:
            if acknowledged is None:
                return list(self.alerts)
            else:
                return [alert for alert in self.alerts if alert.acknowledged == acknowledged]
    
    def acknowledge_alert(self, alert_index: int) -> Result[None, str]:
        """Acknowledge an alert."""
        
        with self._lock:
            if 0 <= alert_index < len(self.alerts):
                self.alerts[alert_index].acknowledged = True
                return Result.ok(None)
            else:
                return Result.err("Invalid alert index")
    
    def add_alert_callback(self, callback: Callable[[TaskAlert], None]):
        """Add callback for new alerts."""
        self.alert_callbacks.append(callback)
    
    def add_progress_callback(self, callback: Callable[[str, float], None]):
        """Add callback for progress updates."""
        self.progress_callbacks.append(callback)
    
    def _check_resource_limits(self, task_id: str, metrics: TaskMetrics):
        """Check for resource limit violations and generate alerts."""
        
        # Memory limit check
        if metrics.memory_usage > self.memory_limit_mb:
            self._generate_alert(
                task_id,
                metrics.agent_id,
                "resource_limit",
                "high",
                f"Memory usage ({metrics.memory_usage:.1f}MB) exceeds limit ({self.memory_limit_mb}MB)"
            )
        
        # CPU limit check
        if metrics.cpu_usage > self.cpu_limit_percentage:
            self._generate_alert(
                task_id,
                metrics.agent_id,
                "resource_limit",
                "medium",
                f"CPU usage ({metrics.cpu_usage:.1f}%) exceeds limit ({self.cpu_limit_percentage}%)"
            )
        
        # Error threshold check
        if metrics.errors_encountered > self.error_threshold:
            self._generate_alert(
                task_id,
                metrics.agent_id,
                "error_threshold",
                "high",
                f"Error count ({metrics.errors_encountered}) exceeds threshold ({self.error_threshold})"
            )
    
    def _generate_alert(
        self,
        task_id: str,
        agent_id: str,
        alert_type: str,
        severity: str,
        message: str
    ):
        """Generate a new alert."""
        
        alert = TaskAlert(
            task_id=task_id,
            agent_id=agent_id,
            alert_type=alert_type,
            severity=severity,
            message=message
        )
        
        with self._lock:
            self.alerts.append(alert)
            
            # Keep only recent alerts (last 1000)
            if len(self.alerts) > 1000:
                self.alerts = self.alerts[-500:]
        
        # Notify callbacks
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception:
                pass
    
    def _monitor_loop(self):
        """Main monitoring loop."""
        
        while self._running:
            try:
                current_time = time.time()
                
                with self._lock:
                    tasks_to_check = list(self.task_metrics.items())
                
                for task_id, metrics in tasks_to_check:
                    # Check for stalled tasks
                    time_since_update = current_time - metrics.last_update
                    if time_since_update > self.stall_threshold:
                        self._generate_alert(
                            task_id,
                            metrics.agent_id,
                            "stalled",
                            "medium",
                            f"Task stalled: no progress for {time_since_update:.0f} seconds"
                        )
                    
                    # Check for timeout warnings
                    if metrics.estimated_completion:
                        time_remaining = metrics.estimated_completion - current_time
                        if time_remaining <= 0:
                            self._generate_alert(
                                task_id,
                                metrics.agent_id,
                                "timeout",
                                "critical",
                                "Task has exceeded estimated completion time"
                            )
                        else:
                            total_time = metrics.estimated_completion - metrics.start_time
                            if time_remaining < (total_time * (1 - self.timeout_warning_threshold)):
                                self._generate_alert(
                                    task_id,
                                    metrics.agent_id,
                                    "timeout",
                                    "medium",
                                    f"Task approaching timeout: {time_remaining:.0f} seconds remaining"
                                )
                
                time.sleep(30)  # Check every 30 seconds
                
            except Exception:
                time.sleep(5)  # Error occurred, wait before retrying
