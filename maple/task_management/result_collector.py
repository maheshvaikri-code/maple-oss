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
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from ..core.result import Result
from .task_queue import TaskQueue, Task, TaskStatus


class AggregationType(Enum):
    """Types of result aggregation."""
    COLLECT_ALL = "collect_all"  # Collect all results
    FIRST_COMPLETE = "first_complete"  # Return first completed result
    MAJORITY_VOTE = "majority_vote"  # Return majority consensus
    BEST_SCORE = "best_score"  # Return result with highest score
    AVERAGE = "average"  # Average numerical results
    WEIGHTED_AVERAGE = "weighted_average"  # Weighted average
    CUSTOM = "custom"  # Custom aggregation function


@dataclass
class TaskResult:
    """Result of a completed task."""
    task_id: str
    agent_id: str
    result_data: Any
    completion_time: float
    execution_time: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    confidence_score: Optional[float] = None
    error_info: Optional[str] = None


@dataclass
class AggregationGroup:
    """Group of related tasks for result aggregation."""
    group_id: str
    task_ids: List[str]
    aggregation_type: AggregationType
    expected_results: int
    collected_results: List[TaskResult] = field(default_factory=list)
    aggregated_result: Optional[Any] = None
    completion_callbacks: List[Callable[[str, Any], None]] = field(default_factory=list)
    timeout_seconds: Optional[float] = None
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    is_complete: bool = False
    
    # Configuration for specific aggregation types
    vote_threshold: float = 0.5  # For majority vote
    score_key: str = "score"  # Key for best score aggregation
    weights: Optional[Dict[str, float]] = None  # For weighted operations
    custom_aggregator: Optional[Callable[[List[TaskResult]], Any]] = None


class ResultCollector:
    """Advanced result collection and aggregation system."""
    
    def __init__(self, task_queue: TaskQueue):
        self.task_queue = task_queue
        
        # Result storage
        self.task_results: Dict[str, TaskResult] = {}  # task_id -> TaskResult
        self.aggregation_groups: Dict[str, AggregationGroup] = {}  # group_id -> AggregationGroup
        
        # Collection strategies
        self.collection_callbacks: List[Callable[[TaskResult], None]] = []
        self.aggregation_callbacks: List[Callable[[str, Any], None]] = []
        
        # Threading
        self._lock = threading.RLock()
        self._collector_thread: Optional[threading.Thread] = None
        self._running = False
        
        # Statistics
        self.stats = {
            "total_results_collected": 0,
            "successful_aggregations": 0,
            "failed_aggregations": 0,
            "average_collection_time": 0.0,
            "groups_created": 0
        }
        self._collection_times: List[float] = []
    
    def start_collector(self):
        """Start the result collector."""
        with self._lock:
            if self._running:
                return
            
            self._running = True
            self._collector_thread = threading.Thread(target=self._collector_loop, daemon=True)
            self._collector_thread.start()
    
    def stop_collector(self):
        """Stop the result collector."""
        with self._lock:
            self._running = False
        
        if self._collector_thread:
            self._collector_thread.join(timeout=5.0)
    
    def collect_task_result(
        self,
        task_id: str,
        agent_id: str,
        result_data: Any,
        metadata: Dict[str, Any] = None,
        confidence_score: float = None
    ) -> Result[TaskResult, str]:
        """Collect result from a completed task."""
        
        # Get task details
        task_result = self.task_queue.get_task(task_id)
        if task_result.is_err():
            return Result.err(task_result.unwrap_err())
        
        task = task_result.unwrap()
        
        # Calculate execution time
        execution_time = 0.0
        if task.started_at and task.completed_at:
            execution_time = task.completed_at - task.started_at
        
        # Create result record
        result_record = TaskResult(
            task_id=task_id,
            agent_id=agent_id,
            result_data=result_data,
            completion_time=task.completed_at or time.time(),
            execution_time=execution_time,
            metadata=metadata or {},
            confidence_score=confidence_score
        )
        
        # Store result
        with self._lock:
            self.task_results[task_id] = result_record
            self.stats["total_results_collected"] += 1
            
            # Track collection time
            if task.created_at:
                collection_time = time.time() - task.created_at
                self._collection_times.append(collection_time)
                
                # Keep only recent times
                if len(self._collection_times) > 1000:
                    self._collection_times = self._collection_times[-500:]
                
                # Update average
                if self._collection_times:
                    self.stats["average_collection_time"] = sum(self._collection_times) / len(self._collection_times)
        
        # Check for aggregation groups
        self._process_result_for_groups(result_record)
        
        # Notify callbacks
        for callback in self.collection_callbacks:
            try:
                callback(result_record)
            except Exception:
                pass
        
        return Result.ok(result_record)
    
    def create_aggregation_group(
        self,
        group_id: str,
        task_ids: List[str],
        aggregation_type: AggregationType,
        timeout_seconds: float = None,
        **kwargs
    ) -> Result[AggregationGroup, str]:
        """Create a group for aggregating results from multiple tasks."""
        
        with self._lock:
            if group_id in self.aggregation_groups:
                return Result.err(f"Aggregation group {group_id} already exists")
            
            group = AggregationGroup(
                group_id=group_id,
                task_ids=task_ids,
                aggregation_type=aggregation_type,
                expected_results=len(task_ids),
                timeout_seconds=timeout_seconds
            )
            
            # Set aggregation-specific parameters
            if aggregation_type == AggregationType.MAJORITY_VOTE:
                group.vote_threshold = kwargs.get('vote_threshold', 0.5)
            elif aggregation_type == AggregationType.BEST_SCORE:
                group.score_key = kwargs.get('score_key', 'score')
            elif aggregation_type == AggregationType.WEIGHTED_AVERAGE:
                group.weights = kwargs.get('weights', {})
            elif aggregation_type == AggregationType.CUSTOM:
                group.custom_aggregator = kwargs.get('custom_aggregator')
                if not group.custom_aggregator:
                    return Result.err("Custom aggregator function is required for CUSTOM aggregation")
            
            self.aggregation_groups[group_id] = group
            self.stats["groups_created"] += 1
            
            # Check if we already have results for any of these tasks
            for task_id in task_ids:
                if task_id in self.task_results:
                    self._add_result_to_group(group, self.task_results[task_id])
        
        return Result.ok(group)
    
    def _process_result_for_groups(self, result: TaskResult):
        """Process a result against all aggregation groups."""
        
        with self._lock:
            for group in self.aggregation_groups.values():
                if result.task_id in group.task_ids and not group.is_complete:
                    self._add_result_to_group(group, result)
    
    def _add_result_to_group(self, group: AggregationGroup, result: TaskResult):
        """Add a result to an aggregation group and check for completion."""
        
        # Add result if not already present
        if not any(r.task_id == result.task_id for r in group.collected_results):
            group.collected_results.append(result)
        
        # Check completion conditions
        should_complete = False
        
        if group.aggregation_type == AggregationType.FIRST_COMPLETE:
            should_complete = len(group.collected_results) >= 1
        elif group.aggregation_type == AggregationType.COLLECT_ALL:
            should_complete = len(group.collected_results) >= group.expected_results
        else:
            # For other types, we might complete early based on confidence or wait for all
            should_complete = len(group.collected_results) >= group.expected_results
        
        if should_complete and not group.is_complete:
            self._complete_aggregation_group(group)
    
    def _complete_aggregation_group(self, group: AggregationGroup):
        """Complete aggregation for a group."""
        
        try:
            # Perform aggregation
            aggregation_result = self._aggregate_results(group)
            
            if aggregation_result.is_ok():
                group.aggregated_result = aggregation_result.unwrap()
                group.is_complete = True
                group.completed_at = time.time()
                
                self.stats["successful_aggregations"] += 1
                
                # Notify completion callbacks
                for callback in group.completion_callbacks:
                    try:
                        callback(group.group_id, group.aggregated_result)
                    except Exception:
                        pass
                
                # Notify global aggregation callbacks
                for callback in self.aggregation_callbacks:
                    try:
                        callback(group.group_id, group.aggregated_result)
                    except Exception:
                        pass
            else:
                self.stats["failed_aggregations"] += 1
                
        except Exception as e:
            self.stats["failed_aggregations"] += 1
    
    def _aggregate_results(self, group: AggregationGroup) -> Result[Any, str]:
        """Aggregate results based on the group's aggregation type."""
        
        if not group.collected_results:
            return Result.err("No results to aggregate")
        
        if group.aggregation_type == AggregationType.COLLECT_ALL:
            return Result.ok([r.result_data for r in group.collected_results])
        
        elif group.aggregation_type == AggregationType.FIRST_COMPLETE:
            # Return the first result (chronologically)
            first_result = min(group.collected_results, key=lambda r: r.completion_time)
            return Result.ok(first_result.result_data)
        
        elif group.aggregation_type == AggregationType.MAJORITY_VOTE:
            return self._majority_vote_aggregation(group)
        
        elif group.aggregation_type == AggregationType.BEST_SCORE:
            return self._best_score_aggregation(group)
        
        elif group.aggregation_type == AggregationType.AVERAGE:
            return self._average_aggregation(group)
        
        elif group.aggregation_type == AggregationType.WEIGHTED_AVERAGE:
            return self._weighted_average_aggregation(group)
        
        elif group.aggregation_type == AggregationType.CUSTOM:
            return self._custom_aggregation(group)
        
        else:
            return Result.err(f"Unknown aggregation type: {group.aggregation_type}")
    
    def _majority_vote_aggregation(self, group: AggregationGroup) -> Result[Any, str]:
        """Perform majority vote aggregation."""
        
        # Count occurrences of each result
        vote_counts: Dict[Any, int] = {}
        total_votes = len(group.collected_results)
        
        for result in group.collected_results:
            key = str(result.result_data)  # Convert to string for hashing
            vote_counts[key] = vote_counts.get(key, 0) + 1
        
        # Find majority
        required_votes = int(total_votes * group.vote_threshold)
        
        for result_str, count in vote_counts.items():
            if count >= required_votes:
                # Find original result data
                for result in group.collected_results:
                    if str(result.result_data) == result_str:
                        return Result.ok(result.result_data)
        
        # No majority found, return most common result
        if vote_counts:
            most_common = max(vote_counts.items(), key=lambda x: x[1])
            for result in group.collected_results:
                if str(result.result_data) == most_common[0]:
                    return Result.ok(result.result_data)
        
        return Result.err("Could not determine majority vote")
    
    def _best_score_aggregation(self, group: AggregationGroup) -> Result[Any, str]:
        """Return result with the highest score."""
        
        best_result = None
        best_score = float('-inf')
        
        for result in group.collected_results:
            score = None
            
            # Try to get score from metadata
            if group.score_key in result.metadata:
                score = result.metadata[group.score_key]
            elif result.confidence_score is not None:
                score = result.confidence_score
            elif isinstance(result.result_data, dict) and group.score_key in result.result_data:
                score = result.result_data[group.score_key]
            
            if score is not None and score > best_score:
                best_score = score
                best_result = result
        
        if best_result:
            return Result.ok(best_result.result_data)
        else:
            return Result.err("No results with valid scores found")
    
    def _average_aggregation(self, group: AggregationGroup) -> Result[Any, str]:
        """Calculate average of numerical results."""
        
        numeric_results = []
        
        for result in group.collected_results:
            if isinstance(result.result_data, (int, float)):
                numeric_results.append(result.result_data)
            elif isinstance(result.result_data, dict):
                # Try to average dictionary values
                for key, value in result.result_data.items():
                    if isinstance(value, (int, float)):
                        numeric_results.append(value)
                        break
        
        if not numeric_results:
            return Result.err("No numeric results to average")
        
        average = sum(numeric_results) / len(numeric_results)
        return Result.ok(average)
    
    def _weighted_average_aggregation(self, group: AggregationGroup) -> Result[Any, str]:
        """Calculate weighted average of results."""
        
        if not group.weights:
            return Result.err("No weights specified for weighted average")
        
        weighted_sum = 0.0
        total_weight = 0.0
        
        for result in group.collected_results:
            weight = group.weights.get(result.agent_id, 1.0)
            
            if isinstance(result.result_data, (int, float)):
                weighted_sum += result.result_data * weight
                total_weight += weight
        
        if total_weight == 0:
            return Result.err("Total weight is zero")
        
        weighted_average = weighted_sum / total_weight
        return Result.ok(weighted_average)
    
    def _custom_aggregation(self, group: AggregationGroup) -> Result[Any, str]:
        """Apply custom aggregation function."""
        
        try:
            result = group.custom_aggregator(group.collected_results)
            return Result.ok(result)
        except Exception as e:
            return Result.err(f"Custom aggregation failed: {str(e)}")
    
    def get_task_result(self, task_id: str) -> Result[TaskResult, str]:
        """Get result for a specific task."""
        
        with self._lock:
            if task_id in self.task_results:
                return Result.ok(self.task_results[task_id])
            else:
                return Result.err(f"No result found for task {task_id}")
    
    def get_aggregation_group(self, group_id: str) -> Result[AggregationGroup, str]:
        """Get aggregation group by ID."""
        
        with self._lock:
            if group_id in self.aggregation_groups:
                return Result.ok(self.aggregation_groups[group_id])
            else:
                return Result.err(f"Aggregation group {group_id} not found")
    
    def add_completion_callback(
        self,
        group_id: str,
        callback: Callable[[str, Any], None]
    ) -> Result[None, str]:
        """Add callback for when aggregation group completes."""
        
        with self._lock:
            if group_id not in self.aggregation_groups:
                return Result.err(f"Aggregation group {group_id} not found")
            
            self.aggregation_groups[group_id].completion_callbacks.append(callback)
            return Result.ok(None)
    
    def list_results(
        self,
        agent_id: str = None,
        since_timestamp: float = None,
        limit: int = 100
    ) -> List[TaskResult]:
        """List collected results with optional filtering."""
        
        with self._lock:
            results = list(self.task_results.values())
            
            # Apply filters
            if agent_id:
                results = [r for r in results if r.agent_id == agent_id]
            
            if since_timestamp:
                results = [r for r in results if r.completion_time >= since_timestamp]
            
            # Sort by completion time (newest first) and limit
            results.sort(key=lambda r: r.completion_time, reverse=True)
            return results[:limit]
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get collection and aggregation statistics."""
        
        with self._lock:
            active_groups = len([g for g in self.aggregation_groups.values() if not g.is_complete])
            completed_groups = len([g for g in self.aggregation_groups.values() if g.is_complete])
            
            return {
                **self.stats,
                "active_groups": active_groups,
                "completed_groups": completed_groups,
                "pending_results": len(self.task_results),
                "aggregation_success_rate": (
                    self.stats["successful_aggregations"] / 
                    max(1, self.stats["successful_aggregations"] + self.stats["failed_aggregations"])
                )
            }
    
    def add_collection_callback(self, callback: Callable[[TaskResult], None]):
        """Add callback for when results are collected."""
        self.collection_callbacks.append(callback)
    
    def add_aggregation_callback(self, callback: Callable[[str, Any], None]):
        """Add callback for when aggregations complete."""
        self.aggregation_callbacks.append(callback)
    
    def cleanup_old_results(self, max_age_hours: int = 24):
        """Clean up old results and completed groups."""
        
        cutoff_time = time.time() - (max_age_hours * 3600)
        
        with self._lock:
            # Remove old results
            old_task_ids = [
                task_id for task_id, result in self.task_results.items()
                if result.completion_time < cutoff_time
            ]
            
            for task_id in old_task_ids:
                del self.task_results[task_id]
            
            # Remove completed groups older than cutoff
            old_group_ids = [
                group_id for group_id, group in self.aggregation_groups.items()
                if group.is_complete and group.completed_at and group.completed_at < cutoff_time
            ]
            
            for group_id in old_group_ids:
                del self.aggregation_groups[group_id]
    
    def _collector_loop(self):
        """Main collector loop for background processing."""
        
        while self._running:
            try:
                current_time = time.time()
                
                with self._lock:
                    # Check for timed out aggregation groups
                    for group in self.aggregation_groups.values():
                        if (not group.is_complete and
                            group.timeout_seconds and
                            current_time - group.created_at > group.timeout_seconds):
                            
                            # Force completion with available results
                            if group.collected_results:
                                self._complete_aggregation_group(group)
                
                # Cleanup old results periodically
                if int(current_time) % 3600 == 0:  # Every hour
                    self.cleanup_old_results()
                
                time.sleep(10)  # Check every 10 seconds
                
            except Exception:
                time.sleep(5)  # Error occurred, wait before retrying
