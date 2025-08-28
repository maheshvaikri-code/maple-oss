# Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)
# MAPLE - Multi Agent Protocol Language Engine

import unittest
import time
import threading
from maple.discovery.registry import AgentRegistry, AgentInfo
from maple.core.result import Result


class TestAgentRegistrationDeregistration(unittest.TestCase):
    """Test agent registration and deregistration functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.registry = AgentRegistry()
    
    def test_register_new_agent(self):
        """Test registering a new agent."""
        result = self.registry.register_agent(
            agent_id="test_agent_1",
            name="Test Agent 1",
            capabilities=["nlp", "data_processing"],
            metadata={"version": "1.0", "location": "us-east-1"},
            max_concurrent_tasks=5
        )
        
        self.assertTrue(result.is_ok())
        
        agent_info = result.unwrap()
        self.assertEqual(agent_info.agent_id, "test_agent_1")
        self.assertEqual(agent_info.name, "Test Agent 1")
        self.assertEqual(agent_info.capabilities, ["nlp", "data_processing"])
        self.assertEqual(agent_info.metadata["version"], "1.0")
        self.assertEqual(agent_info.max_concurrent_tasks, 5)
        self.assertEqual(agent_info.status, "online")
    
    def test_register_duplicate_agent(self):
        """Test registering an agent with duplicate ID fails."""
        # Register first agent
        result1 = self.registry.register_agent("duplicate_agent", "Agent 1")
        self.assertTrue(result1.is_ok())
        
        # Try to register agent with same ID
        result2 = self.registry.register_agent("duplicate_agent", "Agent 2")
        self.assertTrue(result2.is_err())
        self.assertIn("already registered", result2.unwrap_err())
    
    def test_get_registered_agent(self):
        """Test retrieving a registered agent."""
        # Register agent
        self.registry.register_agent("get_test_agent", "Get Test Agent")
        
        # Retrieve agent
        result = self.registry.get_agent("get_test_agent")
        self.assertTrue(result.is_ok())
        
        agent = result.unwrap()
        self.assertEqual(agent.agent_id, "get_test_agent")
        self.assertEqual(agent.name, "Get Test Agent")
    
    def test_get_nonexistent_agent(self):
        """Test retrieving a non-existent agent fails."""
        result = self.registry.get_agent("nonexistent_agent")
        self.assertTrue(result.is_err())
        self.assertIn("not found", result.unwrap_err())
    
    def test_deregister_agent(self):
        """Test deregistering an agent."""
        # Register agent
        self.registry.register_agent(
            "deregister_test",
            "Deregister Test",
            capabilities=["test_capability"]
        )
        
        # Verify agent exists
        result = self.registry.get_agent("deregister_test")
        self.assertTrue(result.is_ok())
        
        # Deregister agent
        dereg_result = self.registry.deregister_agent("deregister_test")
        self.assertTrue(dereg_result.is_ok())
        
        # Verify agent no longer exists
        get_result = self.registry.get_agent("deregister_test")
        self.assertTrue(get_result.is_err())
        
        # Verify capability index is cleaned up
        agents_with_capability = self.registry.find_agents_by_capability("test_capability")
        self.assertEqual(len(agents_with_capability), 0)
    
    def test_deregister_nonexistent_agent(self):
        """Test deregistering a non-existent agent fails."""
        result = self.registry.deregister_agent("nonexistent_agent")
        self.assertTrue(result.is_err())
        self.assertIn("not registered", result.unwrap_err())
    
    def test_list_agents(self):
        """Test listing all registered agents."""
        # Register multiple agents
        self.registry.register_agent("agent_1", "Agent 1")
        self.registry.register_agent("agent_2", "Agent 2") 
        self.registry.register_agent("agent_3", "Agent 3")
        
        # List all agents
        agents = self.registry.list_agents()
        self.assertEqual(len(agents), 3)
        
        agent_ids = [agent.agent_id for agent in agents]
        self.assertIn("agent_1", agent_ids)
        self.assertIn("agent_2", agent_ids)
        self.assertIn("agent_3", agent_ids)
    
    def test_list_agents_by_status(self):
        """Test listing agents filtered by status."""
        # Register agents
        self.registry.register_agent("online_agent", "Online Agent")
        self.registry.register_agent("offline_agent", "Offline Agent")
        
        # Set one agent offline
        self.registry.update_agent_status("offline_agent", "offline")
        
        # List online agents only
        online_agents = self.registry.list_agents(status="online")
        self.assertEqual(len(online_agents), 1)
        self.assertEqual(online_agents[0].agent_id, "online_agent")
        
        # List offline agents only
        offline_agents = self.registry.list_agents(status="offline")
        self.assertEqual(len(offline_agents), 1)
        self.assertEqual(offline_agents[0].agent_id, "offline_agent")
    
    def test_find_agents_by_capability(self):
        """Test finding agents by specific capabilities."""
        # Register agents with different capabilities
        self.registry.register_agent("nlp_agent", "NLP Agent", capabilities=["nlp", "text_analysis"])
        self.registry.register_agent("ml_agent", "ML Agent", capabilities=["machine_learning", "data_mining"])
        self.registry.register_agent("hybrid_agent", "Hybrid Agent", capabilities=["nlp", "machine_learning"])
        
        # Find agents with NLP capability
        nlp_agents = self.registry.find_agents_by_capability("nlp")
        self.assertEqual(len(nlp_agents), 2)
        nlp_agent_ids = [agent.agent_id for agent in nlp_agents]
        self.assertIn("nlp_agent", nlp_agent_ids)
        self.assertIn("hybrid_agent", nlp_agent_ids)
        
        # Find agents with machine learning capability
        ml_agents = self.registry.find_agents_by_capability("machine_learning")
        self.assertEqual(len(ml_agents), 2)
        ml_agent_ids = [agent.agent_id for agent in ml_agents]
        self.assertIn("ml_agent", ml_agent_ids)
        self.assertIn("hybrid_agent", ml_agent_ids)
        
        # Find agents with non-existent capability
        none_agents = self.registry.find_agents_by_capability("nonexistent")
        self.assertEqual(len(none_agents), 0)
    
    def test_update_agent_status(self):
        """Test updating agent status and load."""
        # Register agent
        self.registry.register_agent("status_test", "Status Test")
        
        # Update status
        result = self.registry.update_agent_status("status_test", "degraded", load=0.75)
        self.assertTrue(result.is_ok())
        
        # Verify status update
        agent = self.registry.get_agent("status_test").unwrap()
        self.assertEqual(agent.status, "degraded")
        self.assertEqual(agent.load, 0.75)
        
        # Test updating non-existent agent
        result = self.registry.update_agent_status("nonexistent", "offline")
        self.assertTrue(result.is_err())
    
    def test_heartbeat(self):
        """Test agent heartbeat functionality."""
        # Register agent
        self.registry.register_agent("heartbeat_test", "Heartbeat Test")
        
        # Get initial heartbeat time
        agent = self.registry.get_agent("heartbeat_test").unwrap()
        initial_heartbeat = agent.last_heartbeat
        
        # Wait a bit and send heartbeat
        time.sleep(0.1)
        result = self.registry.heartbeat("heartbeat_test")
        self.assertTrue(result.is_ok())
        
        # Verify heartbeat was updated
        updated_agent = self.registry.get_agent("heartbeat_test").unwrap()
        self.assertGreater(updated_agent.last_heartbeat, initial_heartbeat)
        
        # Test heartbeat for non-existent agent
        result = self.registry.heartbeat("nonexistent")
        self.assertTrue(result.is_err())
    
    def test_get_stale_agents(self):
        """Test identifying stale agents that haven't sent heartbeats."""
        # Register agents
        self.registry.register_agent("fresh_agent", "Fresh Agent")
        self.registry.register_agent("stale_agent", "Stale Agent")
        
        # Manually set stale agent's heartbeat to old time
        stale_agent = self.registry.agents["stale_agent"]
        stale_agent.last_heartbeat = time.time() - 60  # 60 seconds ago
        
        # Get stale agents with 30 second timeout
        stale_agents = self.registry.get_stale_agents(timeout_seconds=30)
        
        self.assertEqual(len(stale_agents), 1)
        self.assertEqual(stale_agents[0].agent_id, "stale_agent")
    
    def test_concurrent_registration(self):
        """Test concurrent agent registration is thread-safe."""
        results = []
        
        def register_agent(agent_id):
            result = self.registry.register_agent(f"concurrent_{agent_id}", f"Concurrent Agent {agent_id}")
            results.append(result)
        
        # Create multiple threads registering agents concurrently
        threads = []
        for i in range(10):
            thread = threading.Thread(target=register_agent, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all registrations succeeded
        self.assertEqual(len(results), 10)
        for result in results:
            self.assertTrue(result.is_ok())
        
        # Verify all agents are registered
        all_agents = self.registry.list_agents()
        self.assertEqual(len(all_agents), 10)


if __name__ == '__main__':
    unittest.main()
