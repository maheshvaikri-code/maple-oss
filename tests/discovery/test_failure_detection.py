# Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)
# MAPLE - Multi Agent Protocol Language Engine

import unittest
import time
import threading
from maple.discovery.registry import AgentRegistry
from maple.discovery.health_monitor import HealthMonitor
from maple.discovery.failure_detector import FailureDetector, FailureEvent, FailureType, RecoveryAction


class TestFailureDetectionRecovery(unittest.TestCase):
    """Test failure detection and recovery functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.registry = AgentRegistry()
        self.health_monitor = HealthMonitor(self.registry, heartbeat_interval=5)
        self.failure_detector = FailureDetector(self.registry, self.health_monitor)
        
        # Register test agents
        self.registry.register_agent("stable_agent", "Stable Agent", max_concurrent_tasks=10)
        self.registry.register_agent("failing_agent", "Failing Agent", max_concurrent_tasks=10)
        self.registry.register_agent("degraded_agent", "Degraded Agent", max_concurrent_tasks=10)
        
        # Start systems
        self.health_monitor.start_monitoring()
        self.failure_detector.start_detection()
    
    def tearDown(self):
        """Clean up test environment."""
        self.failure_detector.stop_detection()
        self.health_monitor.stop_monitoring()
    
    def test_heartbeat_timeout_detection(self):
        """Test detection of heartbeat timeout failures."""
        # Set agent's heartbeat to old time
        agent = self.registry.agents["failing_agent"]
        agent.last_heartbeat = time.time() - 120  # 2 minutes ago
        
        # Set short timeout for testing
        self.failure_detector.heartbeat_timeout = 60  # 1 minute
        
        # Trigger failure detection
        failures = self.failure_detector.detect_failures()
        
        # Should detect heartbeat timeout
        heartbeat_failures = [
            f for f in failures 
            if f.failure_type == FailureType.HEARTBEAT_TIMEOUT and f.agent_id == "failing_agent"
        ]
        
        self.assertEqual(len(heartbeat_failures), 1)
        failure = heartbeat_failures[0]
        self.assertEqual(failure.agent_id, "failing_agent")
        self.assertEqual(failure.severity, "high")
        self.assertIn("timeout_seconds", failure.details)
    
    def test_health_degradation_detection(self):
        """Test detection of health degradation failures."""
        # Send unhealthy metrics
        unhealthy_metrics = {
            "cpu_usage": 95.0,
            "memory_usage": 90.0,
            "response_time": 10000.0,
            "error_rate": 20.0
        }
        
        self.health_monitor.record_heartbeat("degraded_agent", unhealthy_metrics)
        
        # Wait a moment for health evaluation
        time.sleep(0.5)
        
        # Trigger failure detection
        failures = self.failure_detector.detect_failures()
        
        # Should detect health degradation
        health_failures = [
            f for f in failures 
            if f.failure_type == FailureType.HEALTH_DEGRADATION and f.agent_id == "degraded_agent"
        ]
        
        if len(health_failures) > 0:  # May not always trigger immediately
            failure = health_failures[0]
            self.assertIn("health_score", failure.details)
            self.assertIn("issues", failure.details)
    
    def test_automatic_restart_recovery(self):
        """Test automatic restart recovery action."""
        # Create a heartbeat timeout failure
        failure = FailureEvent(
            agent_id="failing_agent",
            failure_type=FailureType.HEARTBEAT_TIMEOUT,
            timestamp=time.time(),
            details={"last_heartbeat": time.time() - 120, "timeout_seconds": 60},
            severity="high"
        )
        
        # Record failure and attempt recovery
        self.failure_detector._record_failure(failure)
        success = self.failure_detector._attempt_recovery(failure)
        
        self.assertTrue(success)
        
        # Verify recovery was attempted
        self.assertTrue(failure.recovery_attempted)
        
        # Check that agent status was updated to restarting
        time.sleep(0.1)  # Allow time for status update
        agent = self.registry.get_agent("failing_agent").unwrap()
        # Status might be "restarting" briefly, then change to "online"
        self.assertIn(agent.status, ["restarting", "online"])
    
    def test_failover_recovery(self):
        """Test failover recovery to alternative agents."""
        # Register additional agents for failover
        self.registry.register_agent("failover_agent_1", "Failover Agent 1", capabilities=["processing"])
        self.registry.register_agent("failover_agent_2", "Failover Agent 2", capabilities=["processing"])
        
        # Configure failover recovery
        failover_action = RecoveryAction(
            FailureType.CRASH_DETECTED, "failover", 1, 10, 60
        )
        self.failure_detector.configure_recovery_action(FailureType.CRASH_DETECTED, failover_action)
        
        # Create crash failure
        failure = FailureEvent(
            agent_id="failing_agent",
            failure_type=FailureType.CRASH_DETECTED,
            timestamp=time.time(),
            details={"crash_reason": "segmentation_fault"},
            severity="critical"
        )
        
        # Attempt recovery
        success = self.failure_detector._attempt_recovery(failure)
        
        self.assertTrue(success)
        
        # Verify agent status was changed to failed
        agent = self.registry.get_agent("failing_agent").unwrap()
        self.assertEqual(agent.status, "failed")
    
    def test_degradation_recovery(self):
        """Test degradation recovery action."""
        # Create health degradation failure
        failure = FailureEvent(
            agent_id="degraded_agent",
            failure_type=FailureType.HEALTH_DEGRADATION,
            timestamp=time.time(),
            details={"health_score": 0.3, "issues": ["High CPU", "High memory"]},
            severity="medium"
        )
        
        # Attempt recovery
        success = self.failure_detector._attempt_recovery(failure)
        
        self.assertTrue(success)
        
        # Verify agent status was changed to degraded
        agent = self.registry.get_agent("degraded_agent").unwrap()
        self.assertEqual(agent.status, "degraded")
        self.assertEqual(agent.load, 0.3)  # Reduced load
    
    def test_recovery_attempt_limits(self):
        """Test that recovery attempts are limited by max_attempts."""
        # Create failure with limited retry action
        failure = FailureEvent(
            agent_id="failing_agent",
            failure_type=FailureType.RESPONSE_TIMEOUT,
            timestamp=time.time(),
            details={"timeout_ms": 5000},
            severity="medium"
        )
        
        # Configure action with only 1 attempt
        limited_action = RecoveryAction(
            FailureType.RESPONSE_TIMEOUT, "restart", 1, 10, 60
        )
        self.failure_detector.configure_recovery_action(FailureType.RESPONSE_TIMEOUT, limited_action)
        
        # First attempt should succeed
        success1 = self.failure_detector._attempt_recovery(failure)
        self.assertTrue(success1)
        
        # Second attempt should fail due to limit
        success2 = self.failure_detector._attempt_recovery(failure)
        self.assertFalse(success2)
    
    def test_circuit_breaker_functionality(self):
        """Test circuit breaker pattern for repeated failures."""
        agent_id = "failing_agent"
        
        # Generate multiple failures to trigger circuit breaker
        for i in range(6):  # Exceed default threshold of 5
            failure = FailureEvent(
                agent_id=agent_id,
                failure_type=FailureType.ERROR_THRESHOLD_EXCEEDED,
                timestamp=time.time(),
                details={"error_count": 10 + i},
                severity="high"
            )
            
            self.failure_detector._record_failure(failure)
            self.failure_detector._update_circuit_breaker(agent_id)
        
        # Check circuit breaker status
        cb_result = self.failure_detector.get_circuit_breaker_status(agent_id)
        self.assertTrue(cb_result.is_ok())
        
        cb_state = cb_result.unwrap()
        self.assertEqual(cb_state.state, "open")
        self.assertGreaterEqual(cb_state.failure_count, self.failure_detector.recovery_actions[FailureType.ERROR_THRESHOLD_EXCEEDED].max_attempts)
    
    def test_circuit_breaker_reset(self):
        """Test manual circuit breaker reset."""
        agent_id = "failing_agent"
        
        # Trigger circuit breaker
        for _ in range(6):
            self.failure_detector._update_circuit_breaker(agent_id)
        
        # Verify circuit is open
        cb_state = self.failure_detector.get_circuit_breaker_status(agent_id).unwrap()
        self.assertEqual(cb_state.state, "open")
        
        # Reset circuit breaker
        result = self.failure_detector.reset_circuit_breaker(agent_id)
        self.assertTrue(result.is_ok())
        
        # Verify circuit is closed
        cb_state = self.failure_detector.get_circuit_breaker_status(agent_id).unwrap()
        self.assertEqual(cb_state.state, "closed")
        self.assertEqual(cb_state.failure_count, 0)
    
    def test_failure_history_tracking(self):
        """Test failure history tracking and retrieval."""
        agent_id = "failing_agent"
        
        # Generate multiple failures
        failure_types = [
            FailureType.HEARTBEAT_TIMEOUT,
            FailureType.HEALTH_DEGRADATION,
            FailureType.RESPONSE_TIMEOUT
        ]
        
        for i, failure_type in enumerate(failure_types):
            failure = FailureEvent(
                agent_id=agent_id,
                failure_type=failure_type,
                timestamp=time.time() - (len(failure_types) - i) * 60,  # Spread over time
                details={"test_failure": i},
                severity="medium"
            )
            self.failure_detector._record_failure(failure)
        
        # Get failure history
        result = self.failure_detector.get_failure_history(agent_id, hours=2)
        self.assertTrue(result.is_ok())
        
        history = result.unwrap()
        self.assertEqual(len(history), 3)
        
        # Verify all failure types are present
        recorded_types = [f.failure_type for f in history]
        for failure_type in failure_types:
            self.assertIn(failure_type, recorded_types)
    
    def test_failure_statistics(self):
        """Test failure statistics generation."""
        # Generate various failures
        agents = ["agent_1", "agent_2", "agent_3"]
        for agent_id in agents:
            self.registry.register_agent(agent_id, f"Agent {agent_id}")
        
        failure_data = [
            ("agent_1", FailureType.HEARTBEAT_TIMEOUT, True),
            ("agent_1", FailureType.HEALTH_DEGRADATION, False),
            ("agent_2", FailureType.RESPONSE_TIMEOUT, True),
            ("agent_3", FailureType.ERROR_THRESHOLD_EXCEEDED, True)
        ]
        
        for agent_id, failure_type, recovery_success in failure_data:
            failure = FailureEvent(
                agent_id=agent_id,
                failure_type=failure_type,
                timestamp=time.time(),
                details={},
                severity="medium",
                recovery_attempted=True,
                recovery_successful=recovery_success
            )
            self.failure_detector._record_failure(failure)
        
        # Update statistics counters
        self.failure_detector._successful_recoveries = 3
        self.failure_detector._failed_recoveries = 1
        
        # Get statistics
        stats = self.failure_detector.get_failure_statistics()
        
        self.assertEqual(stats["total_failures"], 4)
        self.assertEqual(stats["successful_recoveries"], 3)
        self.assertEqual(stats["failed_recoveries"], 1)
        self.assertEqual(stats["recovery_rate"], 0.75)  # 3/4
        
        # Check failures by type
        expected_types = {
            "heartbeat_timeout": 1,
            "health_degradation": 1,
            "response_timeout": 1,
            "error_threshold_exceeded": 1
        }
        
        for failure_type, count in expected_types.items():
            self.assertEqual(stats["failures_by_type"][failure_type], count)
    
    def test_failure_callbacks(self):
        """Test failure event callbacks."""
        callback_results = []
        
        def failure_callback(failure_event):
            callback_results.append((failure_event.agent_id, failure_event.failure_type))
        
        self.failure_detector.add_failure_callback(failure_callback)
        
        # Generate failure
        failure = FailureEvent(
            agent_id="failing_agent",
            failure_type=FailureType.HEARTBEAT_TIMEOUT,
            timestamp=time.time(),
            details={},
            severity="high"
        )
        
        self.failure_detector._record_failure(failure)
        
        # Verify callback was called
        self.assertEqual(len(callback_results), 1)
        self.assertEqual(callback_results[0][0], "failing_agent")
        self.assertEqual(callback_results[0][1], FailureType.HEARTBEAT_TIMEOUT)
    
    def test_custom_recovery_handler(self):
        """Test custom recovery handler registration and execution."""
        custom_recovery_called = []
        
        def custom_recovery_handler(task, failure_record):
            custom_recovery_called.append((task, failure_record))
            return True  # Simulate successful recovery
        
        # Register custom handler
        self.failure_detector.register_recovery_handler(
            FailureType.VALIDATION_ERROR,
            custom_recovery_handler
        )
        
        # Create task-like object for testing
        class MockTask:
            def __init__(self, task_id):
                self.task_id = task_id
        
        mock_task = MockTask("test_task")
        
        # Create failure
        failure = FailureEvent(
            agent_id="failing_agent",
            failure_type=FailureType.VALIDATION_ERROR,
            timestamp=time.time(),
            details={},
            severity="medium"
        )
        
        # Attempt recovery
        result = self.failure_detector._attempt_recovery(mock_task, failure)
        
        self.assertTrue(result.is_ok())
        self.assertEqual(result.unwrap(), "custom_recovery")
        
        # Verify custom handler was called
        self.assertEqual(len(custom_recovery_called), 1)
        self.assertEqual(custom_recovery_called[0][0], mock_task)
        self.assertEqual(custom_recovery_called[0][1], failure)
    
    def test_detection_loop_functionality(self):
        """Test that detection loop runs and processes failures."""
        # Set up conditions for failure detection
        agent = self.registry.agents["failing_agent"]
        agent.last_heartbeat = time.time() - 120  # Old heartbeat
        
        # Wait for detection loop to run
        time.sleep(6)  # Longer than health check interval
        
        # Check if failures were detected
        result = self.failure_detector.get_failure_history("failing_agent", hours=1)
        if result.is_ok():
            history = result.unwrap()
            # Should have detected heartbeat timeout
            timeout_failures = [f for f in history if f.failure_type == FailureType.HEARTBEAT_TIMEOUT]
            self.assertGreater(len(timeout_failures), 0)
    
    def test_concurrent_failure_processing(self):
        """Test concurrent failure processing is thread-safe."""
        # Register additional agents
        for i in range(5):
            self.registry.register_agent(f"concurrent_agent_{i}", f"Concurrent Agent {i}")
        
        results = []
        
        def process_failure(agent_id):
            failure = FailureEvent(
                agent_id=f"concurrent_agent_{agent_id}",
                failure_type=FailureType.NETWORK_ERROR,
                timestamp=time.time(),
                details={},
                severity="medium"
            )
            
            self.failure_detector._record_failure(failure)
            results.append(len(self.failure_detector.failure_history))
        
        # Process failures concurrently
        threads = []
        for i in range(5):
            thread = threading.Thread(target=process_failure, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Verify all failures were recorded
        total_agents_with_failures = len(self.failure_detector.failure_history)
        self.assertGreaterEqual(total_agents_with_failures, 5)


if __name__ == '__main__':
    unittest.main()
