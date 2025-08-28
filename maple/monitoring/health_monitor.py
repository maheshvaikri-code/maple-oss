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


# maple/monitoring/health_monitor.py
# Creator: Mahesh Vaikri

"""
Health monitoring and metrics collection for MAPLE agents and brokers.
"""

import time
import threading
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
from collections import deque
import statistics

@dataclass
class HealthMetrics:
    """Health metrics for an agent or broker."""
    agent_id: str
    timestamp: float
    cpu_usage: float
    memory_usage: float
    message_rate: float
    error_rate: float
    response_time_avg: float
    uptime: float
    connection_status: str

class HealthMonitor:
    """
    Monitors health and performance of MAPLE components.
    """
    
    def __init__(self, component_id: str, collection_interval: float = 5.0):
        self.component_id = component_id
        self.collection_interval = collection_interval
        self.metrics_history = deque(maxlen=100)  # Keep last 100 metrics
        self.running = False
        self.monitor_thread = None
        self.callbacks = []
        
        # Performance tracking
        self.message_count = 0
        self.error_count = 0
        self.response_times = deque(maxlen=50)
        self.start_time = time.time()
        
    def start(self):
        """Start health monitoring."""
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        
    def stop(self):
        """Stop health monitoring."""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1.0)
    
    def record_message(self, processing_time: float = None):
        """Record a processed message."""
        self.message_count += 1
        if processing_time:
            self.response_times.append(processing_time)
    
    def record_error(self):
        """Record an error."""
        self.error_count += 1
    
    def add_callback(self, callback: Callable[[HealthMetrics], None]):
        """Add a callback for health metric updates."""
        self.callbacks.append(callback)
    
    def get_current_metrics(self) -> HealthMetrics:
        """Get current health metrics."""
        try:
            import psutil
            import os
            
            process = psutil.Process(os.getpid())
            cpu_usage = process.cpu_percent()
            memory_usage = process.memory_info().rss / 1024 / 1024  # MB
        except ImportError:
            cpu_usage = 0.0
            memory_usage = 0.0
        
        # Calculate rates
        uptime = time.time() - self.start_time
        message_rate = self.message_count / uptime if uptime > 0 else 0
        error_rate = self.error_count / uptime if uptime > 0 else 0
        
        # Calculate average response time
        if self.response_times:
            response_time_avg = statistics.mean(self.response_times)
        else:
            response_time_avg = 0.0
        
        return HealthMetrics(
            agent_id=self.component_id,
            timestamp=time.time(),
            cpu_usage=cpu_usage,
            memory_usage=memory_usage,
            message_rate=message_rate,
            error_rate=error_rate,
            response_time_avg=response_time_avg,
            uptime=uptime,
            connection_status="connected"  # Simplified for now
        )
    
    def _monitor_loop(self):
        """Background monitoring loop."""
        while self.running:
            try:
                metrics = self.get_current_metrics()
                self.metrics_history.append(metrics)
                
                # Call registered callbacks
                for callback in self.callbacks:
                    try:
                        callback(metrics)
                    except Exception as e:
                        print(f"Health monitor callback error: {e}")
                
                time.sleep(self.collection_interval)
            except Exception as e:
                print(f"Health monitor error: {e}")
                time.sleep(1.0)
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get a summary of health status."""
        if not self.metrics_history:
            return {"status": "no_data"}
        
        latest = self.metrics_history[-1]
        
        # Determine health status
        if latest.error_rate > 0.1:  # More than 10% error rate
            status = "unhealthy"
        elif latest.response_time_avg > 5.0:  # More than 5s response time
            status = "degraded"
        elif latest.memory_usage > 1000:  # More than 1GB memory
            status = "warning"
        else:
            status = "healthy"
        
        return {
            "status": status,
            "uptime": latest.uptime,
            "message_rate": latest.message_rate,
            "error_rate": latest.error_rate,
            "memory_usage_mb": latest.memory_usage,
            "cpu_usage_percent": latest.cpu_usage,
            "avg_response_time": latest.response_time_avg
        }
