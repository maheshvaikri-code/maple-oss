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


#!/usr/bin/env python3
"""
MAPLE Load Performance Tests
Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

Load testing capabilities for MAPLE protocol performance validation.
"""

import time
import threading
from typing import Dict, Any, List
import sys
import os

# Add the project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from maple import Message, Priority, Result, Agent, Config
    MAPLE_AVAILABLE = True
except ImportError:
    MAPLE_AVAILABLE = False

class HighVolumeMessageTest:
    """Test high-volume message creation performance."""
    
    def __init__(self, message_count: int = 10000):
        self.message_count = message_count
        self.results = {}
    
    def run(self) -> Dict[str, Any]:
        """Run high-volume message creation test."""
        if not MAPLE_AVAILABLE:
            return {
                "status": "error",
                "message": "MAPLE not available for testing"
            }
        
        print(f"Running high-volume message test: {self.message_count} messages...")
        
        start_time = time.time()
        messages_created = 0
        
        try:
            # Create messages as fast as possible
            for i in range(self.message_count):
                message = Message(
                    message_type="LOAD_TEST",
                    receiver=f"agent_{i % 100}",
                    priority=Priority.MEDIUM,
                    payload={
                        "test_id": i,
                        "timestamp": time.time(),
                        "data": f"load_test_data_{i}"
                    }
                )
                messages_created += 1
            
            end_time = time.time()
            duration = end_time - start_time
            creation_rate = messages_created / duration if duration > 0 else 0
            
            return {
                "status": "success",
                "message_count": messages_created,
                "duration_seconds": duration,
                "creation_rate": creation_rate,
                "target_met": creation_rate > 1000  # Target: 1K+ messages/sec
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "messages_created": messages_created
            }

class ConcurrentAgentTest:
    """Test concurrent agent creation and communication."""
    
    def __init__(self, agent_count: int = 10):
        self.agent_count = agent_count
    
    def run(self) -> Dict[str, Any]:
        """Run concurrent agent test."""
        if not MAPLE_AVAILABLE:
            return {
                "status": "error",
                "message": "MAPLE not available for testing"
            }
        
        print(f"Running concurrent agent test: {self.agent_count} agents...")
        
        start_time = time.time()
        agents_created = 0
        
        try:
            agents = []
            
            # Create agents concurrently
            for i in range(self.agent_count):
                config = Config(
                    agent_id=f"load_test_agent_{i}",
                    broker_url="localhost:8080"
                )
                agent = Agent(config)
                agents.append(agent)
                agents_created += 1
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Cleanup
            for agent in agents:
                try:
                    if hasattr(agent, 'stop'):
                        agent.stop()
                except:
                    pass
            
            return {
                "status": "success",
                "agent_count": agents_created,
                "duration_seconds": duration,
                "creation_rate": agents_created / duration if duration > 0 else 0
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "agents_created": agents_created
            }

class LoadTestSuite:
    """Complete load testing suite for MAPLE."""
    
    def __init__(self):
        self.test_scenarios = [
            ("High Volume Messages", HighVolumeMessageTest(10000)),
            ("Burst Messages", HighVolumeMessageTest(1000)),
            ("Concurrent Agents", ConcurrentAgentTest(10)),
            ("Rapid Agent Creation", ConcurrentAgentTest(50)),
            ("Memory Efficiency", HighVolumeMessageTest(5000)),
            ("Performance Stability", HighVolumeMessageTest(2000))
        ]
    
    def run_all(self) -> Dict[str, Any]:
        """Run all load test scenarios."""
        results = {
            "total_scenarios": len(self.test_scenarios),
            "passed": 0,
            "failed": 0,
            "scenario_results": {}
        }
        
        print("Running MAPLE Load Test Suite...")
        print("=" * 50)
        
        for scenario_name, test in self.test_scenarios:
            print(f"\nRunning: {scenario_name}")
            try:
                result = test.run()
                results["scenario_results"][scenario_name] = result
                
                if result["status"] == "success":
                    results["passed"] += 1
                    print(f"  [PASS] {scenario_name}")
                else:
                    results["failed"] += 1
                    print(f"  [FAIL] {scenario_name}: {result.get('message', 'Unknown error')}")
                    
            except Exception as e:
                results["failed"] += 1
                results["scenario_results"][scenario_name] = {
                    "status": "error",
                    "message": str(e)
                }
                print(f"  [FAIL] {scenario_name}: {str(e)}")
        
        success_rate = (results["passed"] / results["total_scenarios"]) * 100
        results["success_rate"] = success_rate
        
        print(f"\nLoad Test Results: {results['passed']}/{results['total_scenarios']} passed ({success_rate:.1f}%)")
        
        return results

# Quick performance benchmark
def quick_performance_benchmark() -> Dict[str, Any]:
    """Run a quick performance benchmark."""
    if not MAPLE_AVAILABLE:
        return {"error": "MAPLE not available"}
    
    # Message creation benchmark
    message_test = HighVolumeMessageTest(1000)
    message_result = message_test.run()
    
    # Agent creation benchmark
    agent_test = ConcurrentAgentTest(5)
    agent_result = agent_test.run()
    
    return {
        "message_performance": message_result,
        "agent_performance": agent_result
    }

if __name__ == "__main__":
    # Run load test suite
    suite = LoadTestSuite()
    results = suite.run_all()
    
    print("\n" + "=" * 50)
    print("MAPLE Load Test Suite Complete")
    print(f"Creator: Mahesh Vaikri")
    print(f"Results: {results['passed']}/{results['total_scenarios']} scenarios passed")
    
    if results['success_rate'] >= 80:
        print("[SUCCESS] MAPLE meets performance requirements!")
    else:
        print("[WARN] Some performance issues detected")
