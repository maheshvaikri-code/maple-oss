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

import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from queue import Empty, PriorityQueue
from typing import Any, Callable, Dict, List, Optional

from ..core.result import Result

_MAX_TASK_QUEUE_SIZE = 100_000
_MAX_TASK_ERROR_BYTES = 8_192


class TaskStatus(Enum):
    """Status of a task."""

    PENDING = "pending"
    QUEUED = "queued"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class TaskPriority(Enum):
    """Task priority levels."""

    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    BACKGROUND = 5


@dataclass
class Task:
    """Represents a task in the system."""

    task_id: str
    task_type: str
    payload: Dict[str, Any]
    priority: TaskPriority = TaskPriority.NORMAL
    requirements: List[str] = field(default_factory=list)  # Required capabilities
    timeout_seconds: int = 300  # 5 minutes default
    max_retries: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Execution tracking
    status: TaskStatus = TaskStatus.PENDING
    assigned_agent: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    retry_count: int = 0

    # Results
    result: Optional[Any] = None
    error: Optional[str] = None

    # Host-owned activity telemetry. This is not a lease or liveness verdict.
    heartbeat_at: Optional[float] = None

    def __lt__(self, other: "Task") -> bool:
        """For priority queue ordering."""
        return self.priority.value < other.priority.value


@dataclass
class QueueStats:
    """Statistics about a task queue."""

    total_tasks: int = 0
    pending_tasks: int = 0
    running_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    average_wait_time: float = 0.0
    average_execution_time: float = 0.0
    throughput_per_minute: float = 0.0


class TaskQueue:
    """High-performance task queue with priority support."""

    def __init__(self, max_queue_size: int = 10000) -> None:
        if (
            isinstance(max_queue_size, bool)
            or not isinstance(max_queue_size, int)
            or not 1 <= max_queue_size <= _MAX_TASK_QUEUE_SIZE
        ):
            raise ValueError(
                "max_queue_size must be an integer from 1 to " f"{_MAX_TASK_QUEUE_SIZE}"
            )
        self.max_queue_size = max_queue_size

        # Multiple priority queues for different priority levels
        self.priority_queues: Dict[TaskPriority, PriorityQueue] = {
            priority: PriorityQueue(maxsize=max_queue_size) for priority in TaskPriority
        }

        # Task storage and tracking
        self.tasks: Dict[str, Task] = {}  # task_id -> Task
        self.task_callbacks: Dict[str, List[Callable[[Task], None]]] = {}
        self._queued_count = 0

        # Threading and synchronization
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)

        # Statistics tracking
        self._stats_lock = threading.Lock()
        self._completed_times: List[float] = []  # Track completion times for stats
        self._wait_times: List[float] = []  # Track wait times for stats

        # Background cleanup
        self._cleanup_thread: Optional[threading.Thread] = None
        self._running = False
        # Signalled on stop() so the cleanup loop wakes immediately instead of
        # sleeping out its full interval (otherwise stop() blocks on join).
        self._stop_event = threading.Event()

    def start(self) -> None:
        """Start the task queue background processing."""
        with self._lock:
            if self._running:
                return

            self._running = True
            self._stop_event.clear()
            self._cleanup_thread = threading.Thread(
                target=self._cleanup_loop, daemon=True
            )
            self._cleanup_thread.start()

    def stop(self) -> None:
        """Stop the task queue."""
        with self._lock:
            self._running = False
            self._condition.notify_all()

        # Wake the cleanup loop out of its sleep so join() returns promptly.
        self._stop_event.set()
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5.0)

    def submit_task(
        self,
        task_type: str,
        payload: Dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL,
        requirements: Optional[List[str]] = None,
        timeout_seconds: int = 300,
        max_retries: int = 3,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Result[str, str]:
        """Submit a new task to the queue."""

        # Validate inputs
        if not task_type:
            return Result.err("Task type cannot be empty")

        if payload is None:
            payload = {}

        # Create task
        task = Task(
            task_id=str(uuid.uuid4()),
            task_type=task_type,
            payload=payload,
            priority=priority,
            requirements=requirements or [],
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            metadata=metadata or {},
        )

        return self._enqueue_task(task)

    def _enqueue_task(self, task: Task) -> Result[str, str]:
        """Internal method to enqueue a task."""

        with self._lock:
            # Check queue capacity
            queue = self.priority_queues[task.priority]
            if self._queued_count >= self.max_queue_size or queue.full():
                return Result.err(f"Queue is full (max size: {self.max_queue_size})")

            # Store task
            self.tasks[task.task_id] = task
            task.status = TaskStatus.QUEUED

            # Add to appropriate priority queue
            queue.put((task.priority.value, task.created_at, task))
            self._queued_count += 1

            # Notify waiting consumers
            self._condition.notify()

            return Result.ok(task.task_id)

    def get_next_task(
        self,
        agent_capabilities: Optional[List[str]] = None,
        timeout_seconds: Optional[float] = None,
    ) -> Result[Optional[Task], str]:
        """Get the next available task that matches agent capabilities."""

        agent_capabilities = agent_capabilities or []

        with self._condition:
            end_time = (
                time.time() + timeout_seconds if timeout_seconds is not None else None
            )

            while self._running:
                # Try to get a task from priority queues (highest priority first)
                for priority in TaskPriority:
                    queue = self.priority_queues[priority]

                    try:
                        # Non-blocking get
                        _, _, task = queue.get_nowait()
                        self._queued_count -= 1

                        # Status changes can leave a stale tuple in the
                        # priority queue; never hand such a task to an agent.
                        if task.status != TaskStatus.QUEUED:
                            continue

                        # Check if agent can handle this task
                        if self._can_agent_handle_task(task, agent_capabilities):
                            task.status = TaskStatus.ASSIGNED

                            # Track wait time
                            wait_time = time.time() - task.created_at
                            with self._stats_lock:
                                self._wait_times.append(wait_time)
                                # Keep only recent wait times
                                if len(self._wait_times) > 1000:
                                    self._wait_times = self._wait_times[-500:]

                            return Result.ok(task)
                        else:
                            # Put task back in queue
                            queue.put((priority.value, task.created_at, task))
                            self._queued_count += 1

                    except Empty:
                        continue

                # No suitable task found, wait for new tasks
                if timeout_seconds is None:
                    self._condition.wait()
                else:
                    assert end_time is not None
                    remaining = end_time - time.time()
                    if remaining <= 0:
                        return Result.ok(None)  # Timeout

                    if not self._condition.wait(timeout=remaining):
                        return Result.ok(None)  # Timeout

            return Result.ok(None)  # Queue stopped

    def _can_agent_handle_task(self, task: Task, agent_capabilities: List[str]) -> bool:
        """Check if an agent can handle a task based on requirements."""

        if not task.requirements:
            return True  # No requirements, any agent can handle

        # Check if agent has all required capabilities
        for requirement in task.requirements:
            if requirement not in agent_capabilities:
                return False

        return True

    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        assigned_agent: Optional[str] = None,
        result: Any = None,
        error: Optional[str] = None,
    ) -> Result[Task, str]:
        """Update the status of a task."""

        with self._lock:
            if task_id not in self.tasks:
                return Result.err(f"Task {task_id} not found")

            task = self.tasks[task_id]
            old_status = task.status
            task.status = status

            if assigned_agent:
                task.assigned_agent = assigned_agent

            if result is not None:
                task.result = result

            if error:
                task.error = error

            # Update timestamps
            current_time = time.time()

            if status == TaskStatus.RUNNING and old_status != TaskStatus.RUNNING:
                task.started_at = current_time

            if status in [
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
                TaskStatus.CANCELLED,
                TaskStatus.TIMEOUT,
            ]:
                task.completed_at = current_time

                # Track execution time
                if task.started_at:
                    execution_time = current_time - task.started_at
                    with self._stats_lock:
                        self._completed_times.append(execution_time)
                        # Keep only recent completion times
                        if len(self._completed_times) > 1000:
                            self._completed_times = self._completed_times[-500:]

            # Notify callbacks
            self._notify_task_callbacks(task_id, task)

            return Result.ok(task)

    def get_task(self, task_id: str) -> Result[Task, str]:
        """Get a task by ID."""
        with self._lock:
            if task_id not in self.tasks:
                return Result.err(f"Task {task_id} not found")
            return Result.ok(self.tasks[task_id])

    def assign_task(self, task_id: str, assigned_agent: str) -> Result[Task, str]:
        """Atomically claim a queued task for one agent."""

        with self._lock:
            if not assigned_agent:
                return Result.err("Assigned agent cannot be empty")
            if task_id not in self.tasks:
                return Result.err(f"Task {task_id} not found")

            task = self.tasks[task_id]
            if task.status not in (TaskStatus.QUEUED, TaskStatus.ASSIGNED):
                return Result.err(
                    f"Task {task_id} is not schedulable from status "
                    f"{task.status.value}"
                )
            if task.status == TaskStatus.ASSIGNED and task.assigned_agent:
                return Result.err(f"Task {task_id} is already assigned")

            task.status = TaskStatus.ASSIGNED
            task.assigned_agent = assigned_agent
            task.heartbeat_at = None
            self._notify_task_callbacks(task_id, task)
            return Result.ok(task)

    def start_task(self, task_id: str, assigned_agent: str) -> Result[Task, str]:
        """Start an assigned task after checking its owner."""

        with self._lock:
            if not assigned_agent:
                return Result.err("Assigned agent cannot be empty")
            if task_id not in self.tasks:
                return Result.err(f"Task {task_id} not found")

            task = self.tasks[task_id]
            if task.assigned_agent != assigned_agent:
                return Result.err(f"Task {task_id} is not assigned to {assigned_agent}")
            if task.status != TaskStatus.ASSIGNED:
                return Result.err(
                    f"Task {task_id} cannot be started from status "
                    f"{task.status.value}"
                )

            return self.update_task_status(task_id, TaskStatus.RUNNING)

    def heartbeat_task(self, task_id: str, assigned_agent: str) -> Result[Task, str]:
        """Record an owner-authenticated activity timestamp for active work."""

        with self._lock:
            if not assigned_agent:
                return Result.err("Assigned agent cannot be empty")
            if task_id not in self.tasks:
                return Result.err(f"Task {task_id} not found")

            task = self.tasks[task_id]
            if task.assigned_agent != assigned_agent:
                return Result.err(f"Task {task_id} is not assigned to {assigned_agent}")
            if task.status not in (TaskStatus.ASSIGNED, TaskStatus.RUNNING):
                return Result.err(
                    f"Task {task_id} cannot be heartbeated from status "
                    f"{task.status.value}"
                )

            observed_at = time.time()
            if task.heartbeat_at is None or observed_at > task.heartbeat_at:
                task.heartbeat_at = observed_at
            return Result.ok(task)

    def complete_task(
        self, task_id: str, assigned_agent: str, result: Any = None
    ) -> Result[Task, str]:
        """Complete an assigned task after checking its owner."""

        with self._lock:
            if not assigned_agent:
                return Result.err("Assigned agent cannot be empty")
            if task_id not in self.tasks:
                return Result.err(f"Task {task_id} not found")

            task = self.tasks[task_id]
            if task.assigned_agent != assigned_agent:
                return Result.err(f"Task {task_id} is not assigned to {assigned_agent}")
            if task.status not in (TaskStatus.ASSIGNED, TaskStatus.RUNNING):
                return Result.err(
                    f"Task {task_id} cannot be completed from status "
                    f"{task.status.value}"
                )

            return self.update_task_status(task_id, TaskStatus.COMPLETED, result=result)

    def reassign_task(
        self, task_id: str, current_agent: str, new_agent: str
    ) -> Result[Task, str]:
        """Transfer an assigned but not running task to another agent."""

        with self._lock:
            if not current_agent or not new_agent:
                return Result.err("Task reassignment agents cannot be empty")
            if current_agent == new_agent:
                return Result.err("Task reassignment requires a different agent")
            if task_id not in self.tasks:
                return Result.err(f"Task {task_id} not found")

            task = self.tasks[task_id]
            if task.status != TaskStatus.ASSIGNED:
                return Result.err(
                    f"Task {task_id} cannot be reassigned from status "
                    f"{task.status.value}"
                )
            if task.assigned_agent != current_agent:
                return Result.err(f"Task {task_id} is not assigned to {current_agent}")

            task.assigned_agent = new_agent
            task.heartbeat_at = None
            self._notify_task_callbacks(task_id, task)
            return Result.ok(task)

    def fail_task(
        self, task_id: str, assigned_agent: str, error: str
    ) -> Result[Task, str]:
        """Fail an assigned task after checking its owner and error bound."""

        with self._lock:
            if not assigned_agent:
                return Result.err("Assigned agent cannot be empty")
            if (
                not isinstance(error, str)
                or not error
                or len(error.encode("utf-8")) > _MAX_TASK_ERROR_BYTES
            ):
                return Result.err(
                    "Task failure error must be a non-empty string of at most "
                    f"{_MAX_TASK_ERROR_BYTES} bytes"
                )
            if task_id not in self.tasks:
                return Result.err(f"Task {task_id} not found")

            task = self.tasks[task_id]
            if task.assigned_agent != assigned_agent:
                return Result.err(f"Task {task_id} is not assigned to {assigned_agent}")
            if task.status not in (TaskStatus.ASSIGNED, TaskStatus.RUNNING):
                return Result.err(
                    f"Task {task_id} cannot be failed from status "
                    f"{task.status.value}"
                )

            return self.update_task_status(task_id, TaskStatus.FAILED, error=error)

    def cancel_task(
        self, task_id: str, assigned_agent: Optional[str] = None
    ) -> Result[Task, str]:
        """Cancel a task, optionally enforcing its recorded owner."""
        if assigned_agent is None:
            return self.update_task_status(task_id, TaskStatus.CANCELLED)

        with self._lock:
            if not isinstance(assigned_agent, str) or not assigned_agent:
                return Result.err("Assigned agent cannot be empty")
            if task_id not in self.tasks:
                return Result.err(f"Task {task_id} not found")

            task = self.tasks[task_id]
            if task.status == TaskStatus.QUEUED:
                if (
                    task.assigned_agent is not None
                    and task.assigned_agent != assigned_agent
                ):
                    return Result.err(
                        f"Task {task_id} is not assigned to {assigned_agent}"
                    )
            elif task.status in (TaskStatus.ASSIGNED, TaskStatus.RUNNING):
                if task.assigned_agent != assigned_agent:
                    return Result.err(
                        f"Task {task_id} is not assigned to {assigned_agent}"
                    )
            else:
                return Result.err(
                    f"Task {task_id} cannot be cancelled from status "
                    f"{task.status.value}"
                )

            return self.update_task_status(task_id, TaskStatus.CANCELLED)

    def requeue_task(
        self, task_id: str, assigned_agent: Optional[str] = None
    ) -> Result[None, str]:
        """Requeue a failed task, optionally enforcing its recorded owner."""

        with self._lock:
            if task_id not in self.tasks:
                return Result.err(f"Task {task_id} not found")

            task = self.tasks[task_id]
            if assigned_agent is not None:
                if not isinstance(assigned_agent, str) or not assigned_agent:
                    return Result.err("Assigned agent cannot be empty")
                if task.status != TaskStatus.FAILED:
                    return Result.err(
                        f"Task {task_id} cannot be retried from status "
                        f"{task.status.value}"
                    )
                if task.assigned_agent != assigned_agent:
                    return Result.err(
                        f"Task {task_id} is not assigned to {assigned_agent}"
                    )

            # Check retry limit
            if task.retry_count >= task.max_retries:
                return Result.err(
                    f"Task {task_id} has exceeded max retries ({task.max_retries})"
                )

            # Capacity failure must leave the failed task retryable and
            # unchanged; callers can retry after another queued task drains.
            queue = self.priority_queues[task.priority]
            if self._queued_count >= self.max_queue_size or queue.full():
                return Result.err(f"Queue is full (max size: {self.max_queue_size})")

            # Reset task state for retry
            task.status = TaskStatus.QUEUED
            task.assigned_agent = None
            task.started_at = None
            task.heartbeat_at = None
            task.completed_at = None
            task.retry_count += 1
            task.error = None

            # Re-enqueue
            queue.put((task.priority.value, time.time(), task))
            self._queued_count += 1

            self._condition.notify()

            return Result.ok(None)

    def get_queue_stats(self) -> QueueStats:
        """Get current queue statistics."""

        with self._lock:
            stats = QueueStats()

            # Count tasks by status
            for task in self.tasks.values():
                stats.total_tasks += 1

                if (
                    task.status == TaskStatus.PENDING
                    or task.status == TaskStatus.QUEUED
                ):
                    stats.pending_tasks += 1
                elif task.status in [TaskStatus.ASSIGNED, TaskStatus.RUNNING]:
                    stats.running_tasks += 1
                elif task.status == TaskStatus.COMPLETED:
                    stats.completed_tasks += 1
                elif task.status in [
                    TaskStatus.FAILED,
                    TaskStatus.CANCELLED,
                    TaskStatus.TIMEOUT,
                ]:
                    stats.failed_tasks += 1

            # Calculate averages
            with self._stats_lock:
                if self._wait_times:
                    stats.average_wait_time = sum(self._wait_times) / len(
                        self._wait_times
                    )

                if self._completed_times:
                    stats.average_execution_time = sum(self._completed_times) / len(
                        self._completed_times
                    )

                # Calculate throughput (tasks completed in last minute)
                cutoff_time = time.time() - 60
                recent_completions = [
                    task
                    for task in self.tasks.values()
                    if task.completed_at
                    and task.completed_at >= cutoff_time
                    and task.status == TaskStatus.COMPLETED
                ]
                stats.throughput_per_minute = len(recent_completions)

            return stats

    def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        task_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Task]:
        """List tasks with optional filtering."""

        with self._lock:
            tasks = list(self.tasks.values())

            # Apply filters
            if status:
                tasks = [task for task in tasks if task.status == status]

            if task_type:
                tasks = [task for task in tasks if task.task_type == task_type]

            # Sort by creation time (newest first) and limit
            tasks.sort(key=lambda t: t.created_at, reverse=True)
            return tasks[:limit]

    def add_task_callback(
        self, task_id: str, callback: Callable[[Task], None]
    ) -> Result[None, str]:
        """Add a callback to be notified of task status changes."""

        with self._lock:
            if task_id not in self.tasks:
                return Result.err(f"Task {task_id} not found")

            if task_id not in self.task_callbacks:
                self.task_callbacks[task_id] = []

            self.task_callbacks[task_id].append(callback)
            return Result.ok(None)

    def _notify_task_callbacks(self, task_id: str, task: Task) -> None:
        """Notify callbacks of task status change."""

        if task_id in self.task_callbacks:
            for callback in self.task_callbacks[task_id]:
                try:
                    callback(task)
                except Exception:
                    pass  # Don't let callback errors affect task processing

    def _cleanup_loop(self) -> None:
        """Background cleanup of completed tasks."""

        while self._running:
            try:
                current_time = time.time()
                cleanup_cutoff = current_time - 3600  # Keep tasks for 1 hour

                with self._lock:
                    tasks_to_remove = []

                    for task_id, task in self.tasks.items():
                        # Remove old completed/failed tasks
                        if (
                            task.status
                            in [
                                TaskStatus.COMPLETED,
                                TaskStatus.FAILED,
                                TaskStatus.CANCELLED,
                                TaskStatus.TIMEOUT,
                            ]
                            and task.completed_at
                            and task.completed_at < cleanup_cutoff
                        ):
                            tasks_to_remove.append(task_id)

                    # Remove old tasks
                    for task_id in tasks_to_remove:
                        del self.tasks[task_id]
                        if task_id in self.task_callbacks:
                            del self.task_callbacks[task_id]

                # Cleanup every 5 minutes, but wake immediately on stop().
                if self._stop_event.wait(timeout=300):
                    break

            except Exception:
                # Error occurred, back off — but still wake promptly on stop().
                if self._stop_event.wait(timeout=60):
                    break
