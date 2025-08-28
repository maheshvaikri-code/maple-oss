# Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)
# MAPLE - Multi Agent Protocol Language Engine

import unittest
from maple.discovery.capability_matcher import CapabilityMatcher, CapabilityRequirement, CapabilityMatch
from maple.discovery.registry import AgentRegistry, AgentInfo


class TestCapabilityMatchingValidation(unittest.TestCase):
    """Test capability matching and validation functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.matcher = CapabilityMatcher()
        self.registry = AgentRegistry()
        
        # Register test agents with various capabilities
        self.registry.register_agent(
            "nlp_agent",
            "NLP Specialist",
            capabilities=["nlp.sentiment", "nlp.classification", "text.processing"]
        )
        
        self.registry.register_agent(
            "ml_agent", 
            "ML Specialist",
            capabilities=["ml.supervised", "ml.unsupervised", "data.analysis"]
        )
        
        self.registry.register_agent(
            "hybrid_agent",
            "Hybrid Agent", 
            capabilities=["nlp.sentiment", "ml.supervised", "api.integration", "data.processing"]
        )
        
        self.registry.register_agent(
            "overloaded_agent",
            "Overloaded Agent",
            capabilities=["nlp.sentiment", "data.processing"]
        )
        
        # Set one agent as overloaded
        self.registry.update_agent_status("overloaded_agent", "online", load=0.95)
    
    def test_exact_capability_match(self):
        """Test exact capability matching."""
        requirements = [
            CapabilityRequirement(capability="nlp.sentiment", required=True)
        ]
        
        agents = self.registry.list_agents()
        result = self.matcher.match_capabilities(requirements, agents)
        
        self.assertTrue(result.is_ok())
        matches = result.unwrap()
        
        # Should find nlp_agent and hybrid_agent
        self.assertEqual(len(matches), 2)
        agent_ids = [match.agent_id for match in matches]
        self.assertIn("nlp_agent", agent_ids)
        self.assertIn("hybrid_agent", agent_ids)
    
    def test_multiple_required_capabilities(self):
        """Test matching multiple required capabilities."""
        requirements = [
            CapabilityRequirement(capability="nlp.sentiment", required=True),
            CapabilityRequirement(capability="ml.supervised", required=True)
        ]
        
        agents = self.registry.list_agents()
        result = self.matcher.match_capabilities(requirements, agents)
        
        self.assertTrue(result.is_ok())
        matches = result.unwrap()
        
        # Only hybrid_agent has both capabilities
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].agent_id, "hybrid_agent")
        self.assertEqual(len(matches[0].matched_capabilities), 2)
    
    def test_optional_capabilities(self):
        """Test matching with optional capabilities."""
        requirements = [
            CapabilityRequirement(capability="nlp.sentiment", required=True),
            CapabilityRequirement(capability="api.integration", required=False)
        ]
        
        agents = self.registry.list_agents()
        result = self.matcher.match_capabilities(requirements, agents)
        
        self.assertTrue(result.is_ok())
        matches = result.unwrap()
        
        # Should find agents with required capability
        self.assertGreater(len(matches), 0)
        
        # hybrid_agent should score higher due to optional capability
        hybrid_match = next((m for m in matches if m.agent_id == "hybrid_agent"), None)
        nlp_match = next((m for m in matches if m.agent_id == "nlp_agent"), None)
        
        self.assertIsNotNone(hybrid_match)
        self.assertIsNotNone(nlp_match)
        self.assertGreater(hybrid_match.match_score, nlp_match.match_score)
    
    def test_weighted_capabilities(self):
        """Test weighted capability matching."""
        requirements = [
            CapabilityRequirement(capability="nlp.sentiment", required=True, weight=1.0),
            CapabilityRequirement(capability="data.processing", required=False, weight=2.0)
        ]
        
        agents = self.registry.list_agents()
        result = self.matcher.match_capabilities(requirements, agents)
        
        self.assertTrue(result.is_ok())
        matches = result.unwrap()
        
        # Find matches with data.processing capability
        matches_with_data_processing = [
            m for m in matches if "data.processing" in m.matched_capabilities
        ]
        
        self.assertGreater(len(matches_with_data_processing), 0)
        
        # These should have higher scores due to weight
        for match in matches_with_data_processing:
            other_matches = [m for m in matches if m.agent_id != match.agent_id]
            for other_match in other_matches:
                if "data.processing" not in other_match.matched_capabilities:
                    self.assertGreaterEqual(match.match_score, other_match.match_score)
    
    def test_load_balancing_in_matching(self):
        """Test that load balancing affects availability scores."""
        requirements = [
            CapabilityRequirement(capability="nlp.sentiment", required=True)
        ]
        
        agents = self.registry.list_agents()
        result = self.matcher.match_capabilities(requirements, agents, max_load_threshold=0.8)
        
        self.assertTrue(result.is_ok())
        matches = result.unwrap()
        
        # overloaded_agent should be excluded or have lower availability score
        overloaded_match = next((m for m in matches if m.agent_id == "overloaded_agent"), None)
        
        if overloaded_match:
            # If included, should have very low availability score
            self.assertLess(overloaded_match.availability_score, 0.1)
        
        # Other agents should have higher availability scores
        other_matches = [m for m in matches if m.agent_id != "overloaded_agent"]
        for match in other_matches:
            self.assertGreater(match.availability_score, 0.5)
    
    def test_hierarchical_capability_matching(self):
        """Test hierarchical capability matching (e.g., nlp.* matches nlp.sentiment)."""
        # Register pattern for hierarchical matching
        self.matcher.register_capability_pattern("nlp", r"nlp\..*")
        
        requirements = [
            CapabilityRequirement(capability="nlp", required=True)
        ]
        
        agents = self.registry.list_agents()
        result = self.matcher.match_capabilities(requirements, agents)
        
        self.assertTrue(result.is_ok())
        matches = result.unwrap()
        
        # Should match agents with any nlp.* capabilities
        agent_ids = [match.agent_id for match in matches]
        self.assertIn("nlp_agent", agent_ids)
        self.assertIn("hybrid_agent", agent_ids)
    
    def test_no_matching_agents(self):
        """Test behavior when no agents match requirements."""
        requirements = [
            CapabilityRequirement(capability="quantum.computing", required=True)
        ]
        
        agents = self.registry.list_agents()
        result = self.matcher.match_capabilities(requirements, agents)
        
        self.assertTrue(result.is_ok())
        matches = result.unwrap()
        self.assertEqual(len(matches), 0)
    
    def test_empty_requirements(self):
        """Test behavior with empty capability requirements."""
        requirements = []
        agents = self.registry.list_agents()
        result = self.matcher.match_capabilities(requirements, agents)
        
        self.assertTrue(result.is_err())
        self.assertIn("No capability requirements", result.unwrap_err())
    
    def test_no_available_agents(self):
        """Test behavior with no available agents."""
        requirements = [
            CapabilityRequirement(capability="nlp.sentiment", required=True)
        ]
        
        result = self.matcher.match_capabilities(requirements, [])
        
        self.assertTrue(result.is_err())
        self.assertIn("No agents available", result.unwrap_err())
    
    def test_capability_format_validation(self):
        """Test capability format validation."""
        # Valid capability formats
        valid_capabilities = [
            "nlp",
            "nlp.sentiment",
            "machine_learning",
            "api-integration",
            "data.processing.advanced"
        ]
        
        for capability in valid_capabilities:
            result = self.matcher.validate_capability_format(capability)
            self.assertTrue(result.is_ok(), f"Should validate: {capability}")
        
        # Invalid capability formats
        invalid_capabilities = [
            "",  # Empty
            "a",  # Too short
            "capability with spaces",  # Spaces
            "capability@invalid",  # Invalid characters
            "x" * 101,  # Too long
            None,  # None
            123  # Not string
        ]
        
        for capability in invalid_capabilities:
            result = self.matcher.validate_capability_format(capability)
            self.assertTrue(result.is_err(), f"Should reject: {capability}")
    
    def test_capability_suggestions(self):
        """Test capability suggestion functionality."""
        available_capabilities = {
            "nlp.sentiment",
            "nlp.classification", 
            "nlp.entity_extraction",
            "ml.supervised",
            "ml.unsupervised",
            "data.processing",
            "api.integration"
        }
        
        # Test prefix matching
        suggestions = self.matcher.suggest_capabilities("nlp", available_capabilities)
        self.assertEqual(len(suggestions), 3)
        for suggestion in suggestions:
            self.assertTrue(suggestion.startswith("nlp"))
        
        # Test partial matching
        suggestions = self.matcher.suggest_capabilities("process", available_capabilities)
        self.assertIn("data.processing", suggestions)
        
        # Test empty partial returns all
        suggestions = self.matcher.suggest_capabilities("", available_capabilities)
        self.assertEqual(len(suggestions), len(available_capabilities))
    
    def test_compatibility_matrix(self):
        """Test capability compatibility matrix generation."""
        agents = self.registry.list_agents()
        matrix = self.matcher.get_capability_compatibility_matrix(agents)
        
        # Verify matrix structure
        self.assertIsInstance(matrix, dict)
        
        # Check that all capabilities are included
        all_capabilities = set()
        for agent in agents:
            all_capabilities.update(agent.capabilities)
        
        for capability in all_capabilities:
            self.assertIn(capability, matrix)
            
            # Check agent mappings
            for agent in agents:
                expected_has_capability = capability in agent.capabilities
                actual_has_capability = matrix[capability][agent.agent_id]
                self.assertEqual(expected_has_capability, actual_has_capability)
    
    def test_match_scoring_accuracy(self):
        """Test accuracy of match scoring algorithm."""
        requirements = [
            CapabilityRequirement(capability="nlp.sentiment", required=True, weight=2.0),
            CapabilityRequirement(capability="data.processing", required=False, weight=1.0)
        ]
        
        agents = self.registry.list_agents()
        result = self.matcher.match_capabilities(requirements, agents)
        
        self.assertTrue(result.is_ok())
        matches = result.unwrap()
        
        # Verify scoring is consistent
        for match in matches:
            expected_score = 0.0
            total_weight = 3.0  # 2.0 + 1.0
            
            # Calculate expected score
            if "nlp.sentiment" in match.matched_capabilities:
                expected_score += 2.0
            if "data.processing" in match.matched_capabilities:
                expected_score += 1.0
            
            expected_score /= total_weight
            self.assertAlmostEqual(match.match_score, expected_score, places=2)
    
    def test_availability_score_calculation(self):
        """Test availability score calculation including load factor."""
        requirements = [
            CapabilityRequirement(capability="nlp.sentiment", required=True)
        ]
        
        agents = self.registry.list_agents()
        result = self.matcher.match_capabilities(requirements, agents)
        
        self.assertTrue(result.is_ok())
        matches = result.unwrap()
        
        # Find matches for agents with different loads
        normal_load_match = next((m for m in matches if m.agent_id == "nlp_agent"), None)
        high_load_match = next((m for m in matches if m.agent_id == "overloaded_agent"), None)
        
        if normal_load_match and high_load_match:
            # Normal load agent should have higher availability score
            self.assertGreater(
                normal_load_match.availability_score, 
                high_load_match.availability_score
            )
    
    def test_concurrent_matching(self):
        """Test that capability matching is thread-safe."""
        import threading
        
        requirements = [
            CapabilityRequirement(capability="nlp.sentiment", required=True)
        ]
        
        agents = self.registry.list_agents()
        results = []
        
        def perform_matching():
            result = self.matcher.match_capabilities(requirements, agents)
            results.append(result)
        
        # Run multiple matching operations concurrently
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=perform_matching)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Verify all results are consistent
        self.assertEqual(len(results), 10)
        for result in results:
            self.assertTrue(result.is_ok())
            
        # All results should be identical
        first_result = results[0].unwrap()
        for result in results[1:]:
            matches = result.unwrap()
            self.assertEqual(len(matches), len(first_result))


if __name__ == '__main__':
    unittest.main()
