# Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)
# MAPLE - Multi Agent Protocol Language Engine

import unittest
import time
import threading
from maple.discovery.registry import AgentRegistry
from maple.discovery.health_monitor import HealthMonitor, HealthMetrics, HealthStatus


class TestHealthMonitoringHeartbeat(unittest.TestCase):
    """Test health monitoring and heartbeat functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.registry = AgentRegistry()
        self.monitor = HealthMonitor(self.registry, heartbeat_interval=2)
        
        # Register test agents
        self.registry.register_agent("healthy_agent", "Healthy Agent", max_concurrent_tasks=10)
        self.registry.register_agent("degraded_agent", "Degraded Agent", max_concurrent_tasks=10)
        self.registry.register_agent("unhealthy_agent", "Unhealthy Agent", max_concurrent_tasks=10)
        
        # Start monitoring
        self.monitor.start_monitoring()
    
    def tearDown(self):
        """Clean up test environment."""
        self.monitor.stop_monitoring()
    
    def test_record_heartbeat_basic(self):
        """Test basic heartbeat recording."""
        result = self.monitor.record_heartbeat("healthy_agent")
        self.assertTrue(result.is_ok())
        
        # Verify heartbeat was recorded in registry
        agent = self.registry.get_agent("healthy_agent").unwrap()
        self.assertAlmostEqual(agent.last_heartbeat, time.time(), delta=1.0)
    
    def test_record_heartbeat_with_metrics(self):
        """Test heartbeat recording with health metrics."""
        metrics = {
            "cpu_usage": 45.5,
            "memory_usage": 60.2,
            "active_tasks": 3,
            "response_time": 150.0,
            "error_rate": 2.1,
            "uptime": 3600.0
        }
        
        result = self.monitor.record_heartbeat("healthy_agent", metrics)
        self.assertTrue(result.is_ok())
        
        # Verify metrics were stored
        stored_metrics = self.monitor.health_metrics.get("healthy_agent")
        self.assertIsNotNone(stored_metrics)
        self.assertEqual(stored_metrics.cpu_usage, 45.5)
        self.assertEqual(stored_metrics.memory_usage, 60.2)
        self.assertEqual(stored_metrics.active_tasks, 3)
        self.assertEqual(stored_metrics.response_time, 150.0)
        self.assertEqual(stored_metrics.error_rate, 2.1)
        self.assertEqual(stored_metrics.uptime, 3600.0)
    
    def test_heartbeat_nonexistent_agent(self):
        """Test heartbeat for non-existent agent fails."""
        result = self.monitor.record_heartbeat("nonexistent_agent")
        self.assertTrue(result.is_err())
        self.assertIn("not found", result.unwrap_err())
    
    def test_health_status_healthy(self):
        """Test health status evaluation for healthy agent."""
        # Send heartbeat with good metrics
        metrics = {
            "cpu_usage": 30.0,
            "memory_usage": 40.0,
            "active_tasks": 2,
            "response_time": 100.0,
            "error_rate": 0.5,
            "uptime": 3600.0
        }
        
        self.monitor.record_heartbeat("healthy_agent", metrics)
        
        # Get health status
        result = self.monitor.get_agent_health("healthy_agent")
        self.assertTrue(result.is_ok())
        
        health = result.unwrap()
        self.assertEqual(health.status, "healthy")
        self.assertGreater(health.score, 0.8)
        self.assertEqual(len(health.issues), 0)
    
    def test_health_status_degraded(self):
        """Test health status evaluation for degraded agent."""
        # Send heartbeat with moderate issues
        metrics = {
            "cpu_usage": 85.0,  # High CPU
            "memory_usage": 70.0,
            "active_tasks": 8,
            "response_time": 2000.0,  # High response time
            "error_rate": 5.0,
            "uptime": 3600.0
        }
        
        self.monitor.record_heartbeat("degraded_agent", metrics)
        
        # Get health status
        result = self.monitor.get_agent_health("degraded_agent")
        self.assertTrue(result.is_ok())
        
        health = result.unwrap()
        self.assertEqual(health.status, "degraded")
        self.assertLess(health.score, 0.8)
        self.assertGreater(health.score, 0.5)
        self.assertGreater(len(health.issues), 0)
        
        # Check for expected issues
        issue_text = " ".join(health.issues)
        self.assertIn("High CPU usage", issue_text)
        self.assertIn("High response time", issue_text)
    
    def test_health_status_unhealthy(self):
        """Test health status evaluation for unhealthy agent."""
        # Send heartbeat with severe issues
        metrics = {
            "cpu_usage": 95.0,  # Critical CPU
            "memory_usage": 90.0,  # Critical memory
            "active_tasks": 10,  # At capacity
            "response_time": 8000.0,  # Very high response time
            "error_rate": 15.0,  # High error rate
            "uptime": 3600.0
        }
        
        self.monitor.record_heartbeat("unhealthy_agent", metrics)
        
        # Get health status
        result = self.monitor.get_agent_health("unhealthy_agent")
        self.assertTrue(result.is_ok())
        
        health = result.unwrap()
        self.assertEqual(health.status, "unhealthy")
        self.assertLess(health.score, 0.6)
        self.assertGreater(len(health.issues), 2)
        
        # Check for expected issues
        issue_text = " ".join(health.issues)
        self.assertIn("High CPU usage", issue_text)
        self.assertIn("High memory usage", issue_text)
        self.assertIn("High response time", issue_text)
        self.assertIn("High error rate", issue_text)
        self.assertIn("High task load", issue_text)
    
    def test_health_status_offline(self):
        """Test health status for agent without recent heartbeat."""
        # Don't send any heartbeat, or send old one
        agent = self.registry.agents["healthy_agent"]
        agent.last_heartbeat = time.time() - 120  # 2 minutes ago
        
        # Get health status with 60 second timeout
        self.monitor.heartbeat_timeout = 60
        result = self.monitor.get_agent_health("healthy_agent")
        self.assertTrue(result.is_ok())
        
        health = result.unwrap()
        self.assertEqual(health.status, "offline")
        self.assertEqual(health.score, 0.0)
        self.assertIn("No heartbeat received", health.issues)
    
    def test_health_status_no_metrics(self):
        """Test health status for agent with heartbeat but no metrics."""
        # Send heartbeat without metrics
        self.monitor.record_heartbeat("healthy_agent")
        
        result = self.monitor.get_agent_health("healthy_agent")
        self.assertTrue(result.is_ok())
        
        health = result.unwrap()
        self.assertEqual(health.status, "healthy")
        self.assertEqual(health.score, 0.8)  # Default score for active but no metrics
        self.assertEqual(len(health.issues), 0)
    
    def test_health_metrics_history(self):
        """Test health metrics history tracking."""
        agent_id = "healthy_agent"
        
        # Send multiple heartbeats with metrics
        for i in range(5):
            metrics = {
                "cpu_usage": 30.0 + i * 5,  # Increasing CPU
                "memory_usage": 40.0,
                "active_tasks": i,
                "response_time": 100.0,
                "error_rate": 0.5,
                "uptime": 3600.0 + i * 60
            }
            self.monitor.record_heartbeat(agent_id, metrics)
            time.sleep(0.1)  # Small delay between heartbeats
        
        # Check history was recorded
        self.assertIn(agent_id, self.monitor.health_history)
        history = self.monitor.health_history[agent_id]
        self.assertEqual(len(history), 5)
        
        # Verify history order and content
        for i, metrics in enumerate(history):
            self.assertEqual(metrics.cpu_usage, 30.0 + i * 5)
            self.assertEqual(metrics.active_tasks, i)
    
    def test_health_trend_analysis(self):
        """Test health trend analysis over time."""
        agent_id = "healthy_agent"
        
        # Send heartbeats over time
        for i in range(3):
            metrics = {"cpu_usage": 30.0 + i * 20}
            self.monitor.record_heartbeat(agent_id, metrics)
            time.sleep(0.1)
        
        # Get health trend
        result = self.monitor.get_health_trend(agent_id, hours=1)
        self.assertTrue(result.is_ok())
        
        trend = result.unwrap()
        self.assertEqual(len(trend), 3)
        
        # Verify trend shows increasing CPU usage
        self.assertEqual(trend[0].cpu_usage, 30.0)
        self.assertEqual(trend[1].cpu_usage, 50.0)
        self.assertEqual(trend[2].cpu_usage, 70.0)
    
    def test_system_health_summary(self):
        """Test system-wide health summary."""
        # Set up agents with different health states
        self.monitor.record_heartbeat("healthy_agent", {
            "cpu_usage": 30.0, "memory_usage": 40.0, "error_rate": 1.0
        })
        
        self.monitor.record_heartbeat("degraded_agent", {
            "cpu_usage": 85.0, "memory_usage": 70.0, "error_rate": 8.0
        })
        
        # Set one agent offline
        self.registry.agents["unhealthy_agent"].last_heartbeat = time.time() - 120
        
        # Get system summary
        summary = self.monitor.get_system_health_summary()
        
        self.assertEqual(summary["total_agents"], 3)
        self.assertEqual(summary["healthy"], 1)
        self.assertEqual(summary["degraded"], 1)
        self.assertEqual(summary["offline"], 1)
        self.assertGreater(summary["average_score"], 0.0)
        self.assertLess(summary["average_score"], 1.0)
    
    def test_health_callbacks(self):
        """Test health status change callbacks."""
        callback_results = []
        
        def health_callback(agent_id, health_status):
            callback_results.append((agent_id, health_status.status, health_status.score))
        
        self.monitor.add_health_callback(health_callback)
        
        # Trigger health status changes
        self.monitor.record_heartbeat("healthy_agent", {"cpu_usage": 30.0})
        
        # Wait for monitoring loop to process
        time.sleep(3)
        
        # Verify callback was called
        self.assertGreater(len(callback_results), 0)
        
        # Find callback for our agent
        agent_callbacks = [r for r in callback_results if r[0] == "healthy_agent"]
        self.assertGreater(len(agent_callbacks), 0)
    
    def test_concurrent_heartbeats(self):
        """Test concurrent heartbeat processing is thread-safe."""
        results = []
        
        def send_heartbeat(agent_id, metrics):
            result = self.monitor.record_heartbeat(f"agent_{agent_id}", metrics or {})
            results.append(result)
        
        # Register multiple agents
        for i in range(5):
            self.registry.register_agent(f"agent_{i}", f"Agent {i}")
        
        # Send concurrent heartbeats
        threads = []
        for i in range(5):
            metrics = {"cpu_usage": 30.0 + i * 10}
            thread = threading.Thread(target=send_heartbeat, args=(i, metrics))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Verify all heartbeats succeeded
        self.assertEqual(len(results), 5)
        for result in results:
            self.assertTrue(result.is_ok())
    
    def test_health_thresholds_configuration(self):
        """Test health threshold configuration."""
        # Configure custom thresholds
        self.monitor.cpu_threshold = 60.0
        self.monitor.memory_threshold = 70.0
        self.monitor.response_time_threshold = 2000.0
        self.monitor.error_rate_threshold = 5.0
        
        # Send metrics that exceed custom thresholds
        metrics = {
            "cpu_usage": 65.0,  # Above custom CPU threshold
            "memory_usage": 75.0,  # Above custom memory threshold
            "response_time": 2500.0,  # Above custom response time threshold
            "error_rate": 6.0  # Above custom error rate threshold
        }
        
        self.monitor.record_heartbeat("healthy_agent", metrics)
        
        # Get health status
        result = self.monitor.get_agent_health("healthy_agent")
        self.assertTrue(result.is_ok())
        
        health = result.unwrap()
        self.assertNotEqual(health.status, "healthy")
        self.assertGreater(len(health.issues), 3)  # Should have multiple issues
    
    def test_monitoring_loop_functionality(self):
        """Test that monitoring loop updates agent statuses."""
        # Send a good heartbeat initially
        self.monitor.record_heartbeat("healthy_agent", {"cpu_usage": 30.0})
        
        # Wait for monitoring loop to run
        time.sleep(3)
        
        # Verify agent status was updated in registry
        agent = self.registry.get_agent("healthy_agent").unwrap()
        self.assertEqual(agent.status, "healthy")


if __name__ == '__main__':
    unittest.main()
