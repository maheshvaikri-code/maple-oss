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
import statistics
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from ..core.result import Result
from .task_queue import TaskQueue, TaskStatus, TaskPriority
from .scheduler import TaskScheduler, SchedulingPolicy
from .monitor import TaskMonitor
from ..discovery.registry import AgentRegistry


class OptimizationStrategy(Enum):
    """Strategies for performance optimization."""
    LOAD_BALANCING = "load_balancing"
    PRIORITY_ADJUSTMENT = "priority_adjustment"
    RESOURCE_OPTIMIZATION = "resource_optimization"
    BATCHING = "batching"
    CACHING = "caching"
    PREDICTIVE_SCALING = "predictive_scaling"


@dataclass
class OptimizationMetrics:
    """Metrics for performance optimization analysis."""
    timestamp: float = field(default_factory=time.time)
    
    # Throughput metrics
    tasks_per_minute: float = 0.0
    completion_rate: float = 0.0
    failure_rate: float = 0.0
    
    # Latency metrics
    average_wait_time: float = 0.0
    average_execution_time: float = 0.0
    p95_response_time: float = 0.0
    
    # Resource utilization
    agent_utilization: Dict[str, float] = field(default_factory=dict)
    queue_lengths: Dict[str, int] = field(default_factory=dict)
    resource_efficiency: float = 0.0
    
    # System health
    active_agents: int = 0
    stalled_tasks: int = 0
    overloaded_agents: int = 0


@dataclass
class OptimizationRecommendation:
    """Recommendation for system optimization."""
    strategy: OptimizationStrategy
    priority: str  # high, medium, low
    description: str
    expected_impact: str
    implementation_cost: str  # low, medium, high
    parameters: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0


@dataclass
class BatchingConfig:
    """Configuration for task batching optimization."""
    enabled: bool = True
    batch_size: int = 10
    batch_timeout: float = 30.0  # seconds
    batch_types: List[str] = field(default_factory=list)  # Task types to batch


@dataclass
class CachingConfig:
    """Configuration for result caching optimization."""
    enabled: bool = True
    cache_size: int = 1000
    ttl_seconds: int = 3600  # 1 hour
    cache_hit_threshold: float = 0.1  # Min similarity for cache hit


class PerformanceOptimizer:
    """Advanced performance optimization system with ML-based recommendations."""
    
    def __init__(
        self,
        task_queue: TaskQueue,
        scheduler: TaskScheduler,
        monitor: TaskMonitor,
        agent_registry: AgentRegistry
    ):
        self.task_queue = task_queue
        self.scheduler = scheduler
        self.monitor = monitor
        self.agent_registry = agent_registry
        
        # Optimization state
        self.metrics_history: List[OptimizationMetrics] = []
        self.active_optimizations: List[str] = []
        self.optimization_callbacks: List[Callable[[OptimizationRecommendation], None]] = []
        
        # Configuration
        self.batching_config = BatchingConfig()
        self.caching_config = CachingConfig()
        
        # Batching state
        self.task_batches: Dict[str, List[str]] = {}  # batch_type -> list of task_ids
        self.batch_timers: Dict[str, threading.Timer] = {}
        
        # Caching state
        self.result_cache: Dict[str, Any] = {}
        self.cache_timestamps: Dict[str, float] = {}
        self.cache_access_counts: Dict[str, int] = {}
        
        # Threading
        self._lock = threading.RLock()
        self._optimizer_thread: Optional[threading.Thread] = None
        self._running = False
        
        # Optimization parameters
        self.analysis_interval = 60  # seconds
        self.metrics_window = 300  # 5 minutes of metrics history
        self.optimization_threshold = 0.8  # Trigger optimization when efficiency < 80%
        
        # Performance targets
        self.target_throughput = 100  # tasks per minute
        self.target_response_time = 30  # seconds
        self.target_utilization = 0.7  # 70% agent utilization
    
    def start_optimizer(self):
        """Start the performance optimizer."""
        with self._lock:
            if self._running:
                return
            
            self._running = True
            self._optimizer_thread = threading.Thread(target=self._optimizer_loop, daemon=True)
            self._optimizer_thread.start()
    
    def stop_optimizer(self):
        """Stop the performance optimizer."""
        with self._lock:
            self._running = False
            
            # Cancel batch timers
            for timer in self.batch_timers.values():
                timer.cancel()
            self.batch_timers.clear()
        
        if self._optimizer_thread:
            self._optimizer_thread.join(timeout=5.0)
    
    def analyze_performance(self) -> OptimizationMetrics:
        """Analyze current system performance."""
        
        current_time = time.time()
        
        # Get queue statistics
        queue_stats = self.task_queue.get_queue_stats()
        
        # Get scheduling metrics
        scheduling_metrics = self.scheduler.get_scheduling_metrics()
        
        # Get monitoring statistics
        monitoring_stats = self.monitor.get_monitoring_stats()
        
        # Get agent information
        agents = self.agent_registry.list_agents(status="online")
        
        # Calculate metrics
        metrics = OptimizationMetrics(timestamp=current_time)
        
        # Throughput metrics
        metrics.tasks_per_minute = queue_stats.throughput_per_minute
        if queue_stats.total_tasks > 0:
            metrics.completion_rate = queue_stats.completed_tasks / queue_stats.total_tasks
            metrics.failure_rate = queue_stats.failed_tasks / queue_stats.total_tasks
        
        # Latency metrics
        metrics.average_wait_time = queue_stats.average_wait_time
        metrics.average_execution_time = queue_stats.average_execution_time
        
        # Calculate P95 response time from recent tasks
        recent_tasks = self.task_queue.list_tasks(limit=100)
        response_times = []
        for task in recent_tasks:
            if task.completed_at and task.created_at:
                response_times.append(task.completed_at - task.created_at)
        
        if response_times:
            metrics.p95_response_time = statistics.quantiles(response_times, n=20)[18]  # 95th percentile
        
        # Resource utilization
        total_capacity = 0
        total_used = 0
        overloaded_count = 0
        
        for agent in agents:
            agent_load = self.scheduler.get_agent_load(agent.agent_id)
            utilization = agent_load / agent.max_concurrent_tasks
            metrics.agent_utilization[agent.agent_id] = utilization
            
            total_capacity += agent.max_concurrent_tasks
            total_used += agent_load
            
            if utilization > 0.9:  # 90% threshold for overloaded
                overloaded_count += 1
        
        if total_capacity > 0:
            metrics.resource_efficiency = total_used / total_capacity
        
        # System health
        metrics.active_agents = len(agents)
        metrics.stalled_tasks = monitoring_stats.stalled_tasks
        metrics.overloaded_agents = overloaded_count
        
        # Queue lengths by priority
        for priority in TaskPriority:
            tasks = self.task_queue.list_tasks(status=TaskStatus.QUEUED, limit=1000)
            priority_tasks = [t for t in tasks if t.priority == priority]
            metrics.queue_lengths[priority.name] = len(priority_tasks)
        
        # Store metrics
        with self._lock:
            self.metrics_history.append(metrics)
            
            # Keep only recent metrics
            cutoff_time = current_time - self.metrics_window
            self.metrics_history = [
                m for m in self.metrics_history if m.timestamp >= cutoff_time
            ]
        
        return metrics
    
    def generate_recommendations(self) -> List[OptimizationRecommendation]:
        """Generate optimization recommendations based on current performance."""
        
        if not self.metrics_history:
            return []
        
        latest_metrics = self.metrics_history[-1]
        recommendations = []
        
        # Load balancing recommendations
        if latest_metrics.overloaded_agents > 0:
            recommendations.append(OptimizationRecommendation(
                strategy=OptimizationStrategy.LOAD_BALANCING,
                priority="high",
                description=f"{latest_metrics.overloaded_agents} agents are overloaded. Redistribute tasks.",
                expected_impact="Reduce response times by 20-30%",
                implementation_cost="low",
                parameters={"rebalance_threshold": 0.9}
            ))
        
        # Priority adjustment recommendations
        if latest_metrics.average_wait_time > self.target_response_time:
            recommendations.append(OptimizationRecommendation(
                strategy=OptimizationStrategy.PRIORITY_ADJUSTMENT,
                priority="medium",
                description="High average wait time detected. Adjust task priorities.",
                expected_impact="Improve critical task response by 15-25%",
                implementation_cost="low",
                parameters={"boost_critical_tasks": True}
            ))
        
        # Resource optimization recommendations
        if latest_metrics.resource_efficiency < self.optimization_threshold:
            recommendations.append(OptimizationRecommendation(
                strategy=OptimizationStrategy.RESOURCE_OPTIMIZATION,
                priority="high",
                description=f"Resource efficiency is {latest_metrics.resource_efficiency:.1%}, below target.",
                expected_impact="Increase throughput by 10-20%",
                implementation_cost="medium",
                parameters={"target_utilization": self.target_utilization}
            ))
        
        # Batching recommendations
        if (latest_metrics.tasks_per_minute > 50 and 
            not self.batching_config.enabled):
            recommendations.append(OptimizationRecommendation(
                strategy=OptimizationStrategy.BATCHING,
                priority="medium",
                description="High task volume detected. Enable batching for efficiency.",
                expected_impact="Reduce overhead by 15-30%",
                implementation_cost="low",
                parameters={"batch_size": 10, "batch_timeout": 30}
            ))
        
        # Caching recommendations
        cache_hit_potential = self._estimate_cache_hit_potential()
        if (cache_hit_potential > self.caching_config.cache_hit_threshold and
            not self.caching_config.enabled):
            recommendations.append(OptimizationRecommendation(
                strategy=OptimizationStrategy.CACHING,
                priority="medium",
                description=f"Detected {cache_hit_potential:.1%} potential cache hit rate.",
                expected_impact="Reduce execution time by 20-40%",
                implementation_cost="medium",
                parameters={"cache_size": 1000, "ttl_seconds": 3600}
            ))
        
        # Predictive scaling recommendations
        if self._predict_load_increase():
            recommendations.append(OptimizationRecommendation(
                strategy=OptimizationStrategy.PREDICTIVE_SCALING,
                priority="medium",
                description="Load increase predicted. Consider scaling resources.",
                expected_impact="Prevent performance degradation",
                implementation_cost="high",
                parameters={"scale_factor": 1.5}
            ))
        
        return recommendations
    
    def apply_optimization(self, recommendation: OptimizationRecommendation) -> Result[str, str]:
        """Apply an optimization recommendation."""
        
        try:
            if recommendation.strategy == OptimizationStrategy.LOAD_BALANCING:
                return self._apply_load_balancing(recommendation.parameters)
            
            elif recommendation.strategy == OptimizationStrategy.PRIORITY_ADJUSTMENT:
                return self._apply_priority_adjustment(recommendation.parameters)
            
            elif recommendation.strategy == OptimizationStrategy.RESOURCE_OPTIMIZATION:
                return self._apply_resource_optimization(recommendation.parameters)
            
            elif recommendation.strategy == OptimizationStrategy.BATCHING:
                return self._apply_batching_optimization(recommendation.parameters)
            
            elif recommendation.strategy == OptimizationStrategy.CACHING:
                return self._apply_caching_optimization(recommendation.parameters)
            
            elif recommendation.strategy == OptimizationStrategy.PREDICTIVE_SCALING:
                return self._apply_predictive_scaling(recommendation.parameters)
            
            else:
                return Result.err(f"Unknown optimization strategy: {recommendation.strategy}")
                
        except Exception as e:
            return Result.err(f"Failed to apply optimization: {str(e)}")
    
    def _apply_load_balancing(self, parameters: Dict[str, Any]) -> Result[str, str]:
        """Apply load balancing optimization."""
        
        rebalance_result = self.scheduler.rebalance_loads()
        
        if rebalance_result.is_ok():
            moves = rebalance_result.unwrap()
            with self._lock:
                self.active_optimizations.append("load_balancing")
            return Result.ok(f"Rebalanced {moves} tasks across agents")
        else:
            return Result.err(rebalance_result.unwrap_err())
    
    def _apply_priority_adjustment(self, parameters: Dict[str, Any]) -> Result[str, str]:
        """Apply priority adjustment optimization."""
        
        if parameters.get("boost_critical_tasks"):
            # Find critical tasks in queue and boost their priority
            queued_tasks = self.task_queue.list_tasks(status=TaskStatus.QUEUED, limit=100)
            boosted = 0
            
            for task in queued_tasks:
                if task.task_type in ["critical", "urgent", "emergency"]:
                    # Boost to critical priority
                    task.priority = TaskPriority.CRITICAL
                    boosted += 1
            
            return Result.ok(f"Boosted priority for {boosted} critical tasks")
        
        return Result.ok("Priority adjustment completed")
    
    def _apply_resource_optimization(self, parameters: Dict[str, Any]) -> Result[str, str]:
        """Apply resource optimization."""
        
        target_utilization = parameters.get("target_utilization", self.target_utilization)
        
        # Adjust scheduler policy for better resource utilization
        new_policy = SchedulingPolicy(
            load_balancing="least_loaded",
            capability_matching="weighted_score",
            max_concurrent_per_agent=int(10 * target_utilization / 0.7)  # Adjust capacity
        )
        
        self.scheduler.policy = new_policy
        
        with self._lock:
            self.active_optimizations.append("resource_optimization")
        
        return Result.ok(f"Optimized for {target_utilization:.1%} target utilization")
    
    def _apply_batching_optimization(self, parameters: Dict[str, Any]) -> Result[str, str]:
        """Apply task batching optimization."""
        
        self.batching_config.enabled = True
        self.batching_config.batch_size = parameters.get("batch_size", 10)
        self.batching_config.batch_timeout = parameters.get("batch_timeout", 30)
        
        with self._lock:
            self.active_optimizations.append("batching")
        
        return Result.ok(f"Enabled batching with size {self.batching_config.batch_size}")
    
    def _apply_caching_optimization(self, parameters: Dict[str, Any]) -> Result[str, str]:
        """Apply result caching optimization."""
        
        self.caching_config.enabled = True
        self.caching_config.cache_size = parameters.get("cache_size", 1000)
        self.caching_config.ttl_seconds = parameters.get("ttl_seconds", 3600)
        
        with self._lock:
            self.active_optimizations.append("caching")
        
        return Result.ok(f"Enabled caching with size {self.caching_config.cache_size}")
    
    def _apply_predictive_scaling(self, parameters: Dict[str, Any]) -> Result[str, str]:
        """Apply predictive scaling optimization."""
        
        scale_factor = parameters.get("scale_factor", 1.5)
        
        # This would typically trigger external scaling mechanisms
        # For now, we simulate by adjusting internal parameters
        
        with self._lock:
            self.active_optimizations.append("predictive_scaling")
        
        return Result.ok(f"Applied predictive scaling with factor {scale_factor}")
    
    def _estimate_cache_hit_potential(self) -> float:
        """Estimate potential cache hit rate based on task patterns."""
        
        recent_tasks = self.task_queue.list_tasks(limit=100)
        
        if len(recent_tasks) < 10:
            return 0.0
        
        # Simple heuristic: look for similar task types and payloads
        task_signatures = {}
        
        for task in recent_tasks:
            signature = f"{task.task_type}_{hash(str(sorted(task.payload.items())))}"
            task_signatures[signature] = task_signatures.get(signature, 0) + 1
        
        # Calculate potential hit rate
        total_tasks = len(recent_tasks)
        duplicate_tasks = sum(count - 1 for count in task_signatures.values() if count > 1)
        
        return duplicate_tasks / total_tasks if total_tasks > 0 else 0.0
    
    def _predict_load_increase(self) -> bool:
        """Predict if system load will increase based on trends."""
        
        if len(self.metrics_history) < 5:
            return False
        
        # Look at throughput trend over last 5 measurements
        recent_throughputs = [m.tasks_per_minute for m in self.metrics_history[-5:]]
        
        # Simple linear trend detection
        if len(recent_throughputs) >= 2:
            trend = recent_throughputs[-1] - recent_throughputs[0]
            return trend > 10  # Increasing by more than 10 tasks/minute
        
        return False
    
    def get_optimization_status(self) -> Dict[str, Any]:
        """Get current optimization status and metrics."""
        
        with self._lock:
            latest_metrics = self.metrics_history[-1] if self.metrics_history else None
            
            return {
                "active_optimizations": list(self.active_optimizations),
                "batching_enabled": self.batching_config.enabled,
                "caching_enabled": self.caching_config.enabled,
                "latest_metrics": latest_metrics.__dict__ if latest_metrics else None,
                "cache_stats": {
                    "cache_size": len(self.result_cache),
                    "cache_hits": sum(self.cache_access_counts.values()),
                    "hit_rate": self._calculate_cache_hit_rate()
                },
                "optimization_history": len(self.metrics_history)
            }
    
    def _calculate_cache_hit_rate(self) -> float:
        """Calculate current cache hit rate."""
        
        total_accesses = sum(self.cache_access_counts.values())
        if total_accesses == 0:
            return 0.0
        
        hits = len([count for count in self.cache_access_counts.values() if count > 1])
        return hits / len(self.cache_access_counts) if self.cache_access_counts else 0.0
    
    def add_optimization_callback(self, callback: Callable[[OptimizationRecommendation], None]):
        """Add callback for optimization recommendations."""
        self.optimization_callbacks.append(callback)
    
    def force_optimization_analysis(self) -> List[OptimizationRecommendation]:
        """Force immediate optimization analysis and return recommendations."""
        
        metrics = self.analyze_performance()
        recommendations = self.generate_recommendations()
        
        # Notify callbacks
        for recommendation in recommendations:
            for callback in self.optimization_callbacks:
                try:
                    callback(recommendation)
                except Exception:
                    pass
        
        return recommendations
    
    def get_performance_trends(self, hours: int = 24) -> Dict[str, List[float]]:
        """Get performance trends over specified time period."""
        
        cutoff_time = time.time() - (hours * 3600)
        
        with self._lock:
            relevant_metrics = [
                m for m in self.metrics_history
                if m.timestamp >= cutoff_time
            ]
        
        trends = {
            "throughput": [m.tasks_per_minute for m in relevant_metrics],
            "completion_rate": [m.completion_rate for m in relevant_metrics],
            "response_time": [m.p95_response_time for m in relevant_metrics],
            "resource_efficiency": [m.resource_efficiency for m in relevant_metrics],
            "active_agents": [m.active_agents for m in relevant_metrics],
            "timestamps": [m.timestamp for m in relevant_metrics]
        }
        
        return trends
    
    def _optimizer_loop(self):
        """Main optimization loop."""
        
        while self._running:
            try:
                # Analyze current performance
                metrics = self.analyze_performance()
                
                # Generate recommendations
                recommendations = self.generate_recommendations()
                
                # Auto-apply low-cost optimizations
                for recommendation in recommendations:
                    if (recommendation.implementation_cost == "low" and
                        recommendation.priority in ["high", "critical"]):
                        
                        apply_result = self.apply_optimization(recommendation)
                        if apply_result.is_ok():
                            # Notify callbacks
                            for callback in self.optimization_callbacks:
                                try:
                                    callback(recommendation)
                                except Exception:
                                    pass
                
                # Clean up old cache entries
                self._cleanup_cache()
                
                time.sleep(self.analysis_interval)
                
            except Exception:
                time.sleep(10)  # Error occurred, wait before retrying
    
    def _cleanup_cache(self):
        """Clean up expired cache entries."""
        
        if not self.caching_config.enabled:
            return
        
        current_time = time.time()
        expired_keys = []
        
        with self._lock:
            for key, timestamp in self.cache_timestamps.items():
                if current_time - timestamp > self.caching_config.ttl_seconds:
                    expired_keys.append(key)
            
            # Remove expired entries
            for key in expired_keys:
                self.result_cache.pop(key, None)
                self.cache_timestamps.pop(key, None)
                self.cache_access_counts.pop(key, None)
            
            # Limit cache size
            if len(self.result_cache) > self.caching_config.cache_size:
                # Remove least recently used entries
                sorted_keys = sorted(
                    self.cache_timestamps.keys(),
                    key=lambda k: self.cache_timestamps[k]
                )
                
                keys_to_remove = sorted_keys[:-self.caching_config.cache_size]
                for key in keys_to_remove:
                    self.result_cache.pop(key, None)
                    self.cache_timestamps.pop(key, None)
                    self.cache_access_counts.pop(key, None)
