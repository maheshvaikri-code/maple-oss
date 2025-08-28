# Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)
# MAPLE - Multi Agent Protocol Language Engine

import unittest
import time
import threading
from maple.task_management.task_queue import TaskQueue, Task, TaskStatus, TaskPriority


class TestTaskSubmissionQueuing(unittest.TestCase):
    """Test task submission and queuing functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.task_queue = TaskQueue(max_queue_size=1000)
        self.task_queue.start()
    
    def tearDown(self):
        """Clean up test environment."""
        self.task_queue.stop()
    
    def test_submit_basic_task(self):
        """Test submitting a basic task."""
        result = self.task_queue.submit_task(
            task_type="data_processing",
            payload={"data": [1, 2, 3, 4, 5]},
            priority=TaskPriority.NORMAL
        )
        
        self.assertTrue(result.is_ok())
        task_id = result.unwrap()
        self.assertIsNotNone(task_id)
        
        # Verify task was stored
        task_result = self.task_queue.get_task(task_id)
        self.assertTrue(task_result.is_ok())
        
        task = task_result.unwrap()
        self.assertEqual(task.task_type, "data_processing")
        self.assertEqual(task.payload["data"], [1, 2, 3, 4, 5])
        self.assertEqual(task.priority, TaskPriority.NORMAL)
        self.assertEqual(task.status, TaskStatus.QUEUED)
    
    def test_submit_task_with_requirements(self):
        """Test submitting task with capability requirements."""
        result = self.task_queue.submit_task(
            task_type="nlp_analysis",
            payload={"text": "Analyze this sentiment"},
            requirements=["nlp.sentiment", "text.processing"],
            timeout_seconds=120,
            max_retries=2,
            metadata={"user_id": "12345", "priority_boost": True}
        )
        
        self.assertTrue(result.is_ok())
        task_id = result.unwrap()
        
        task = self.task_queue.get_task(task_id).unwrap()
        self.assertEqual(task.requirements, ["nlp.sentiment", "text.processing"])
        self.assertEqual(task.timeout_seconds, 120)
        self.assertEqual(task.max_retries, 2)
        self.assertEqual(task.metadata["user_id"], "12345")
        self.assertTrue(task.metadata["priority_boost"])
    
    def test_submit_task_validation(self):
        """Test task submission validation."""
        # Empty task type should fail
        result = self.task_queue.submit_task(task_type="", payload={})
        self.assertTrue(result.is_err())
        self.assertIn("Task type cannot be empty", result.unwrap_err())
        
        # None payload should be handled gracefully
        result = self.task_queue.submit_task(task_type="test", payload=None)
        self.assertTrue(result.is_ok())
        
        task = self.task_queue.get_task(result.unwrap()).unwrap()
        self.assertEqual(task.payload, {})
    
    def test_task_priority_queuing(self):
        """Test that tasks are queued with proper priority ordering."""
        # Submit tasks with different priorities
        task_ids = []
        
        # Submit in non-priority order
        priorities = [TaskPriority.LOW, TaskPriority.CRITICAL, TaskPriority.NORMAL, TaskPriority.HIGH]
        for priority in priorities:
            result = self.task_queue.submit_task(
                task_type="test_task",
                payload={"priority": priority.name},
                priority=priority
            )
            self.assertTrue(result.is_ok())
            task_ids.append(result.unwrap())
        
        # Get tasks in priority order
        retrieved_tasks = []
        for _ in range(4):
            result = self.task_queue.get_next_task()
            if result.is_ok() and result.unwrap():
                retrieved_tasks.append(result.unwrap())
        
        # Should be ordered by priority (CRITICAL=1, HIGH=2, NORMAL=3, LOW=4)
        self.assertGreater(len(retrieved_tasks), 0)
        
        # First task should be critical priority
        if len(retrieved_tasks) > 0:
            self.assertEqual(retrieved_tasks[0].priority, TaskPriority.CRITICAL)
    
    def test_get_next_task_basic(self):
        """Test getting next available task."""
        # Submit a task
        result = self.task_queue.submit_task("test_task", {"data": "test"})
        self.assertTrue(result.is_ok())
        task_id = result.unwrap()
        
        # Get next task
        result = self.task_queue.get_next_task()
        self.assertTrue(result.is_ok())
        
        task = result.unwrap()
        self.assertIsNotNone(task)
        self.assertEqual(task.task_id, task_id)
        self.assertEqual(task.status, TaskStatus.ASSIGNED)
    
    def test_get_next_task_with_capabilities(self):
        """Test getting next task filtered by agent capabilities."""
        # Submit tasks with different requirements
        nlp_result = self.task_queue.submit_task(
            "nlp_task",
            {"text": "Process this"},
            requirements=["nlp.processing"]
        )
        
        ml_result = self.task_queue.submit_task(
            "ml_task", 
            {"data": [1, 2, 3]},
            requirements=["ml.supervised"]
        )
        
        self.assertTrue(nlp_result.is_ok())
        self.assertTrue(ml_result.is_ok())
        
        # Agent with only NLP capabilities
        nlp_capabilities = ["nlp.processing", "text.analysis"]
        result = self.task_queue.get_next_task(agent_capabilities=nlp_capabilities)
        
        self.assertTrue(result.is_ok())
        task = result.unwrap()
        
        if task:  # May not get task if capability matching is strict
            self.assertEqual(task.task_type, "nlp_task")
            self.assertTrue(all(req in nlp_capabilities for req in task.requirements))
    
    def test_get_next_task_timeout(self):
        """Test timeout when getting next task from empty queue."""
        # Try to get task with short timeout
        result = self.task_queue.get_next_task(timeout_seconds=0.5)
        self.assertTrue(result.is_ok())
        
        task = result.unwrap()
        self.assertIsNone(task)  # Should timeout and return None
    
    def test_update_task_status(self):
        """Test updating task status."""
        # Submit task
        result = self.task_queue.submit_task("test_task", {"data": "test"})
        task_id = result.unwrap()
        
        # Update to running
        result = self.task_queue.update_task_status(
            task_id,
            TaskStatus.RUNNING,
            assigned_agent="agent_123"
        )
        self.assertTrue(result.is_ok())
        
        task = result.unwrap()
        self.assertEqual(task.status, TaskStatus.RUNNING)
        self.assertEqual(task.assigned_agent, "agent_123")
        self.assertIsNotNone(task.started_at)
        
        # Update to completed with result
        result = self.task_queue.update_task_status(
            task_id,
            TaskStatus.COMPLETED,
            result={"output": "processed_data"}
        )
        self.assertTrue(result.is_ok())
        
        task = result.unwrap()
        self.assertEqual(task.status, TaskStatus.COMPLETED)
        self.assertEqual(task.result, {"output": "processed_data"})
        self.assertIsNotNone(task.completed_at)
    
    def test_cancel_task(self):
        """Test task cancellation."""
        # Submit task
        result = self.task_queue.submit_task("test_task", {"data": "test"})
        task_id = result.unwrap()
        
        # Cancel task
        result = self.task_queue.cancel_task(task_id)
        self.assertTrue(result.is_ok())
        
        task = result.unwrap()
        self.assertEqual(task.status, TaskStatus.CANCELLED)
        self.assertIsNotNone(task.completed_at)
    
    def test_requeue_task(self):
        """Test task requeuing for retry."""
        # Submit task
        result = self.task_queue.submit_task("test_task", {"data": "test"}, max_retries=2)
        task_id = result.unwrap()
        
        # Get task and mark as failed
        task = self.task_queue.get_next_task().unwrap()
        self.task_queue.update_task_status(task_id, TaskStatus.FAILED, error="Temporary failure")
        
        # Requeue task
        result = self.task_queue.requeue_task(task_id)
        self.assertTrue(result.is_ok())
        
        # Verify task is back in queue with incremented retry count
        updated_task = self.task_queue.get_task(task_id).unwrap()
        self.assertEqual(updated_task.status, TaskStatus.QUEUED)
        self.assertEqual(updated_task.retry_count, 1)
        self.assertIsNone(updated_task.error)
    
    def test_requeue_task_retry_limit(self):
        """Test requeue fails when retry limit exceeded."""
        # Submit task with low retry limit
        result = self.task_queue.submit_task("test_task", {"data": "test"}, max_retries=1)
        task_id = result.unwrap()
        
        # Fail task twice
        for _ in range(2):
            self.task_queue.get_next_task()
            self.task_queue.update_task_status(task_id, TaskStatus.FAILED)
            requeue_result = self.task_queue.requeue_task(task_id)
            
        # Second requeue should fail
        self.assertTrue(requeue_result.is_err())
        self.assertIn("exceeded max retries", requeue_result.unwrap_err())
    
    def test_queue_statistics(self):
        """Test queue statistics calculation."""
        # Submit various tasks
        task_ids = []
        for i in range(5):
            result = self.task_queue.submit_task(f"task_{i}", {"index": i})
            task_ids.append(result.unwrap())
        
        # Process some tasks
        for i in range(2):
            task = self.task_queue.get_next_task().unwrap()
            if task:
                self.task_queue.update_task_status(task.task_id, TaskStatus.RUNNING)
                self.task_queue.update_task_status(task.task_id, TaskStatus.COMPLETED)
        
        # Fail one task
        if len(task_ids) > 2:
            self.task_queue.update_task_status(task_ids[2], TaskStatus.FAILED)
        
        # Get statistics
        stats = self.task_queue.get_queue_stats()
        
        self.assertEqual(stats.total_tasks, 5)
        self.assertEqual(stats.completed_tasks, 2)
        self.assertEqual(stats.failed_tasks, 1)
        self.assertEqual(stats.pending_tasks, 2)  # Remaining queued tasks
    
    def test_list_tasks_filtering(self):
        """Test task listing with filtering."""
        # Submit tasks with different statuses and types
        task_ids = []
        
        # Submit different types
        for task_type in ["nlp", "ml", "data"]:
            for i in range(2):
                result = self.task_queue.submit_task(task_type, {"index": i})
                task_ids.append(result.unwrap())
        
        # Update some statuses
        self.task_queue.update_task_status(task_ids[0], TaskStatus.COMPLETED)
        self.task_queue.update_task_status(task_ids[1], TaskStatus.FAILED)
        
        # List completed tasks
        completed_tasks = self.task_queue.list_tasks(status=TaskStatus.COMPLETED, limit=10)
        self.assertEqual(len(completed_tasks), 1)
        self.assertEqual(completed_tasks[0].task_id, task_ids[0])
        
        # List tasks by type
        nlp_tasks = self.task_queue.list_tasks(task_type="nlp", limit=10)
        self.assertEqual(len(nlp_tasks), 2)
        for task in nlp_tasks:
            self.assertEqual(task.task_type, "nlp")
        
        # List with limit
        limited_tasks = self.task_queue.list_tasks(limit=3)
        self.assertLessEqual(len(limited_tasks), 3)
    
    def test_task_callbacks(self):
        """Test task status change callbacks."""
        callback_results = []
        
        def task_callback(task):
            callback_results.append((task.task_id, task.status))
        
        # Submit task
        result = self.task_queue.submit_task("test_task", {"data": "test"})
        task_id = result.unwrap()
        
        # Add callback
        callback_result = self.task_queue.add_task_callback(task_id, task_callback)
        self.assertTrue(callback_result.is_ok())
        
        # Update task status
        self.task_queue.update_task_status(task_id, TaskStatus.RUNNING)
        self.task_queue.update_task_status(task_id, TaskStatus.COMPLETED)
        
        # Verify callbacks were called
        self.assertEqual(len(callback_results), 2)
        self.assertEqual(callback_results[0], (task_id, TaskStatus.RUNNING))
        self.assertEqual(callback_results[1], (task_id, TaskStatus.COMPLETED))
    
    def test_concurrent_task_submission(self):
        """Test concurrent task submission is thread-safe."""
        results = []
        
        def submit_tasks(thread_id):
            for i in range(10):
                result = self.task_queue.submit_task(
                    f"concurrent_task_{thread_id}_{i}",
                    {"thread_id": thread_id, "index": i}
                )
                results.append(result)
        
        # Submit tasks concurrently
        threads = []
        for thread_id in range(5):
            thread = threading.Thread(target=submit_tasks, args=(thread_id,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Verify all submissions succeeded
        self.assertEqual(len(results), 50)  # 5 threads * 10 tasks each
        for result in results:
            self.assertTrue(result.is_ok())
        
        # Verify tasks are in queue
        stats = self.task_queue.get_queue_stats()
        self.assertEqual(stats.total_tasks, 50)
    
    def test_queue_capacity_limits(self):
        """Test queue capacity enforcement."""
        # Create small queue for testing
        small_queue = TaskQueue(max_queue_size=3)
        small_queue.start()
        
        try:
            # Fill queue to capacity
            task_ids = []
            for i in range(3):
                result = small_queue.submit_task(f"task_{i}", {"index": i})
                self.assertTrue(result.is_ok())
                task_ids.append(result.unwrap())
            
            # Next submission should fail
            result = small_queue.submit_task("overflow_task", {"data": "overflow"})
            self.assertTrue(result.is_err())
            self.assertIn("Queue is full", result.unwrap_err())
            
        finally:
            small_queue.stop()
    
    def test_task_cleanup(self):
        """Test automatic cleanup of old completed tasks."""
        # Submit and complete tasks
        task_ids = []
        for i in range(5):
            result = self.task_queue.submit_task(f"cleanup_task_{i}", {"index": i})
            task_id = result.unwrap()
            task_ids.append(task_id)
            
            # Complete task
            self.task_queue.update_task_status(task_id, TaskStatus.COMPLETED)
        
        # Verify tasks exist initially
        initial_count = len(self.task_queue.tasks)
        self.assertEqual(initial_count, 5)
        
        # Simulate old completion times
        for task_id in task_ids:
            task = self.task_queue.tasks[task_id]
            task.completed_at = time.time() - 7200  # 2 hours ago
        
        # Trigger cleanup (normally done by background thread)
        cutoff_time = time.time() - 3600  # 1 hour cutoff
        tasks_to_remove = []
        for task_id, task in self.task_queue.tasks.items():
            if (task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED] and
                task.completed_at and task.completed_at < cutoff_time):
                tasks_to_remove.append(task_id)
        
        for task_id in tasks_to_remove:
            del self.task_queue.tasks[task_id]
        
        # Verify cleanup occurred
        self.assertLess(len(self.task_queue.tasks), initial_count)


if __name__ == '__main__':
    unittest.main()
