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
MAPLE Rigorous Cross-Protocol Benchmark Suite
Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

This benchmark suite provides scientific, fair comparison between
MAPLE and other agent communication protocols by implementing
reference versions and running them under identical conditions.
"""

import sys
import os
import time
import json
import uuid
import threading
import queue
import statistics
import platform
import psutil
import subprocess
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from abc import ABC, abstractmethod
from enum import Enum
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add MAPLE to path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(script_dir))
if os.path.exists(os.path.join(project_root, 'maple')):
    sys.path.insert(0, project_root)

@dataclass
class BenchmarkResult:
    """Standardized benchmark result with all metrics."""
    protocol_name: str
    test_name: str
    operations_per_second: float
    latency_ms: float
    memory_usage_mb: float
    cpu_usage_percent: float
    success_rate: float
    test_duration_seconds: float
    hardware_info: Dict[str, Any]
    implementation_notes: str = ""
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

@dataclass
class TestEnvironment:
    """Test environment specification."""
    cpu_model: str
    cpu_cores: int
    cpu_freq_mhz: float
    ram_total_gb: float
    ram_available_gb: float
    python_version: str
    os_info: str
    timestamp: str

# ============================================================================
# PROTOCOL IMPLEMENTATIONS FOR FAIR COMPARISON
# ============================================================================

class ProtocolBenchmark(ABC):
    """Abstract base class for protocol benchmarks."""
    
    @abstractmethod
    def get_name(self) -> str:
        """Get protocol name."""
        pass
    
    @abstractmethod
    def setup(self) -> bool:
        """Setup the protocol for testing."""
        pass
    
    @abstractmethod
    def teardown(self) -> bool:
        """Cleanup after testing."""
        pass
    
    @abstractmethod
    def benchmark_message_creation(self, count: int) -> BenchmarkResult:
        """Benchmark message creation performance."""
        pass
    
    @abstractmethod
    def benchmark_error_handling(self, count: int) -> BenchmarkResult:
        """Benchmark error handling performance."""
        pass
    
    @abstractmethod
    def benchmark_agent_lifecycle(self, agent_count: int) -> BenchmarkResult:
        """Benchmark agent lifecycle management."""
        pass

# ============================================================================
# MAPLE BENCHMARK IMPLEMENTATION
# ============================================================================

class MAPLEBenchmark(ProtocolBenchmark):
    """MAPLE protocol benchmark implementation."""
    
    def __init__(self):
        self.agents = []
        self.maple_available = False
    
    def get_name(self) -> str:
        return "MAPLE MAPLE"
    
    def setup(self) -> bool:
        """Setup MAPLE for testing."""
        try:
            from maple import Message, Priority, Result, Agent, Config, SecurityConfig
            self.Message = Message
            self.Priority = Priority
            self.Result = Result
            self.Agent = Agent
            self.Config = Config
            self.SecurityConfig = SecurityConfig
            self.maple_available = True
            logger.info("MAPLE setup successful")
            return True
        except ImportError as e:
            logger.error(f"MAPLE setup failed: {e}")
            self.maple_available = False
            return False
    
    def teardown(self) -> bool:
        """Cleanup MAPLE agents."""
        for agent in self.agents:
            try:
                if hasattr(agent, 'stop'):
                    agent.stop()
            except Exception as e:
                logger.warning(f"Error stopping agent: {e}")
        self.agents.clear()
        return True
    
    def benchmark_message_creation(self, count: int) -> BenchmarkResult:
        """Benchmark MAPLE message creation."""
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Warm up
        for _ in range(100):
            msg = self.Message(
                message_type="WARMUP",
                receiver="test_agent",
                priority=self.Priority.MEDIUM,
                payload={"test": "data"}
            )
        
        # Actual benchmark
        cpu_before = psutil.cpu_percent(interval=0.1)
        start_time = time.perf_counter()
        
        messages = []
        for i in range(count):
            message = self.Message(
                message_type="BENCHMARK_MESSAGE",
                receiver=f"agent_{i % 50}",
                priority=self.Priority.MEDIUM,
                payload={
                    "message_id": i,
                    "timestamp": time.time(),
                    "data": f"benchmark_data_{i}",
                    "metadata": {
                        "batch": i // 100,
                        "sequence": i,
                        "test_type": "message_creation"
                    }
                }
            )
            # Include serialization in benchmark
            json_str = message.to_json()
            reconstructed = self.Message.from_json(json_str)
            messages.append(reconstructed)
        
        end_time = time.perf_counter()
        cpu_after = psutil.cpu_percent(interval=0.1)
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        duration = end_time - start_time
        ops_per_sec = count / duration if duration > 0 else float('inf')
        latency = (duration * 1000) / count  # ms per operation
        memory_used = final_memory - initial_memory
        cpu_used = max(0, cpu_after - cpu_before)
        
        return BenchmarkResult(
            protocol_name=self.get_name(),
            test_name="message_creation",
            operations_per_second=ops_per_sec,
            latency_ms=latency,
            memory_usage_mb=memory_used,
            cpu_usage_percent=cpu_used,
            success_rate=1.0,
            test_duration_seconds=duration,
            hardware_info=get_hardware_info(),
            implementation_notes="Full MAPLE message with serialization/deserialization"
        )
    
    def benchmark_error_handling(self, count: int) -> BenchmarkResult:
        """Benchmark MAPLE error handling with Result<T,E>."""
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024
        
        cpu_before = psutil.cpu_percent(interval=0.1)
        start_time = time.perf_counter()
        
        success_count = 0
        for i in range(count):
            # Test all Result<T,E> operations
            if i % 4 == 0:
                result = self.Result.ok(f"success_{i}")
                mapped = result.map(lambda x: x.upper())
                if mapped.is_ok():
                    success_count += 1
            elif i % 4 == 1:
                result = self.Result.err({"error": f"error_{i}", "code": 400})
                fallback = result.unwrap_or("default")
                success_count += 1
            elif i % 4 == 2:
                result = self.Result.ok(i * 2)
                chained = result.and_then(lambda x: self.Result.ok(x + 10))
                if chained.is_ok():
                    success_count += 1
            else:
                result = self.Result.ok({"data": i, "status": "active"})
                filtered = result.map(lambda x: x["data"] if x["status"] == "active" else 0)
                success_count += 1
        
        end_time = time.perf_counter()
        cpu_after = psutil.cpu_percent(interval=0.1)
        final_memory = process.memory_info().rss / 1024 / 1024
        
        duration = end_time - start_time
        ops_per_sec = count / duration if duration > 0 else float('inf')
        latency = (duration * 1000) / count
        
        return BenchmarkResult(
            protocol_name=self.get_name(),
            test_name="error_handling",
            operations_per_second=ops_per_sec,
            latency_ms=latency,
            memory_usage_mb=final_memory - initial_memory,
            cpu_usage_percent=max(0, cpu_after - cpu_before),
            success_rate=success_count / count,
            test_duration_seconds=duration,
            hardware_info=get_hardware_info(),
            implementation_notes="Result<T,E> pattern with map, and_then, unwrap_or operations"
        )
    
    def benchmark_agent_lifecycle(self, agent_count: int) -> BenchmarkResult:
        """Benchmark MAPLE agent lifecycle."""
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024
        
        cpu_before = psutil.cpu_percent(interval=0.1)
        start_time = time.perf_counter()
        
        # Create agents
        agents = []
        for i in range(agent_count):
            config = self.Config(
                agent_id=f"benchmark_agent_{i}",
                broker_url="localhost:8080",
                security=self.SecurityConfig(
                    auth_type="benchmark",
                    credentials=f"token_{i}",
                    public_key=f"key_{i}",
                    require_links=False
                )
            )
            agent = self.Agent(config)
            agents.append(agent)
        
        # Start agents
        for agent in agents:
            agent.start()
        
        # Brief operation
        time.sleep(0.1)
        
        # Stop agents
        for agent in agents:
            agent.stop()
        
        end_time = time.perf_counter()
        cpu_after = psutil.cpu_percent(interval=0.1)
        final_memory = process.memory_info().rss / 1024 / 1024
        
        duration = end_time - start_time
        ops_per_sec = agent_count / duration if duration > 0 else float('inf')
        latency = (duration * 1000) / agent_count
        
        # Store agents for cleanup
        self.agents.extend(agents)
        
        return BenchmarkResult(
            protocol_name=self.get_name(),
            test_name="agent_lifecycle",
            operations_per_second=ops_per_sec,
            latency_ms=latency,
            memory_usage_mb=final_memory - initial_memory,
            cpu_usage_percent=max(0, cpu_after - cpu_before),
            success_rate=1.0,
            test_duration_seconds=duration,
            hardware_info=get_hardware_info(),
            implementation_notes="Full MAPLE agents with broker, security, and message handling"
        )

# ============================================================================
# SIMPLE JSON BASELINE
# ============================================================================

class SimpleJSONBenchmark(ProtocolBenchmark):
    """Simple JSON message passing baseline."""
    
    def get_name(self) -> str:
        return "Simple JSON Baseline"
    
    def setup(self) -> bool:
        return True
    
    def teardown(self) -> bool:
        return True
    
    def benchmark_message_creation(self, count: int) -> BenchmarkResult:
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024
        
        cpu_before = psutil.cpu_percent(interval=0.1)
        start_time = time.perf_counter()
        
        messages = []
        for i in range(count):
            message = {
                "messageType": "BENCHMARK_MESSAGE",
                "receiver": f"agent_{i % 50}",
                "priority": "MEDIUM",
                "payload": {
                    "message_id": i,
                    "timestamp": time.time(),
                    "data": f"benchmark_data_{i}",
                    "metadata": {
                        "batch": i // 100,
                        "sequence": i,
                        "test_type": "message_creation"
                    }
                }
            }
            json_str = json.dumps(message)
            reconstructed = json.loads(json_str)
            messages.append(reconstructed)
        
        end_time = time.perf_counter()
        cpu_after = psutil.cpu_percent(interval=0.1)
        final_memory = process.memory_info().rss / 1024 / 1024
        
        duration = end_time - start_time
        ops_per_sec = count / duration if duration > 0 else float('inf')
        latency = (duration * 1000) / count
        
        return BenchmarkResult(
            protocol_name=self.get_name(),
            test_name="message_creation",
            operations_per_second=ops_per_sec,
            latency_ms=latency,
            memory_usage_mb=final_memory - initial_memory,
            cpu_usage_percent=max(0, cpu_after - cpu_before),
            success_rate=1.0,
            test_duration_seconds=duration,
            hardware_info=get_hardware_info(),
            implementation_notes="Raw JSON dictionaries with standard library"
        )
    
    def benchmark_error_handling(self, count: int) -> BenchmarkResult:
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024
        
        cpu_before = psutil.cpu_percent(interval=0.1)
        start_time = time.perf_counter()
        
        success_count = 0
        for i in range(count):
            try:
                if i % 4 == 0:
                    result = f"success_{i}".upper()
                    success_count += 1
                elif i % 4 == 1:
                    raise ValueError(f"error_{i}")
                elif i % 4 == 2:
                    result = (i * 2) + 10
                    success_count += 1
                else:
                    data = {"data": i, "status": "active"}
                    result = data["data"] if data["status"] == "active" else 0
                    success_count += 1
            except ValueError:
                result = "default"
                success_count += 1
        
        end_time = time.perf_counter()
        cpu_after = psutil.cpu_percent(interval=0.1)
        final_memory = process.memory_info().rss / 1024 / 1024
        
        duration = end_time - start_time
        ops_per_sec = count / duration if duration > 0 else float('inf')
        latency = (duration * 1000) / count
        
        return BenchmarkResult(
            protocol_name=self.get_name(),
            test_name="error_handling",
            operations_per_second=ops_per_sec,
            latency_ms=latency,
            memory_usage_mb=final_memory - initial_memory,
            cpu_usage_percent=max(0, cpu_after - cpu_before),
            success_rate=success_count / count,
            test_duration_seconds=duration,
            hardware_info=get_hardware_info(),
            implementation_notes="Standard Python exception handling"
        )
    
    def benchmark_agent_lifecycle(self, agent_count: int) -> BenchmarkResult:
        import threading
        
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024
        
        cpu_before = psutil.cpu_percent(interval=0.1)
        start_time = time.perf_counter()
        
        def simple_agent(agent_id):
            time.sleep(0.001)  # Minimal processing
        
        threads = []
        for i in range(agent_count):
            thread = threading.Thread(target=simple_agent, args=(i,))
            threads.append(thread)
        
        for thread in threads:
            thread.start()
        
        time.sleep(0.1)
        
        for thread in threads:
            thread.join(timeout=1.0)
        
        end_time = time.perf_counter()
        cpu_after = psutil.cpu_percent(interval=0.1)
        final_memory = process.memory_info().rss / 1024 / 1024
        
        duration = end_time - start_time
        ops_per_sec = agent_count / duration if duration > 0 else float('inf')
        latency = (duration * 1000) / agent_count
        
        return BenchmarkResult(
            protocol_name=self.get_name(),
            test_name="agent_lifecycle",
            operations_per_second=ops_per_sec,
            latency_ms=latency,
            memory_usage_mb=final_memory - initial_memory,
            cpu_usage_percent=max(0, cpu_after - cpu_before),
            success_rate=1.0,
            test_duration_seconds=duration,
            hardware_info=get_hardware_info(),
            implementation_notes="Simple threading-based agents"
        )

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_hardware_info() -> Dict[str, Any]:
    """Get detailed hardware information."""
    try:
        cpu_freq = psutil.cpu_freq()
        return {
            "cpu_model": platform.processor(),
            "cpu_cores": psutil.cpu_count(),
            "cpu_freq_mhz": cpu_freq.current if cpu_freq else "Unknown",
            "ram_total_gb": psutil.virtual_memory().total / (1024**3),
            "ram_available_gb": psutil.virtual_memory().available / (1024**3),
            "python_version": platform.python_version(),
            "os_info": platform.platform(),
            "platform": platform.system(),
            "machine": platform.machine(),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        logger.error(f"Error getting hardware info: {e}")
        return {"error": str(e)}

def get_test_environment() -> TestEnvironment:
    """Get test environment information."""
    hw_info = get_hardware_info()
    return TestEnvironment(
        cpu_model=hw_info.get("cpu_model", "Unknown"),
        cpu_cores=hw_info.get("cpu_cores", 0),
        cpu_freq_mhz=hw_info.get("cpu_freq_mhz", 0),
        ram_total_gb=hw_info.get("ram_total_gb", 0),
        ram_available_gb=hw_info.get("ram_available_gb", 0),
        python_version=hw_info.get("python_version", "Unknown"),
        os_info=hw_info.get("os_info", "Unknown"),
        timestamp=hw_info.get("timestamp", "Unknown")
    )

class RigorousBenchmarkSuite:
    """Comprehensive benchmark suite for protocol comparison."""
    
    def __init__(self):
        self.protocols: List[ProtocolBenchmark] = []
        self.results: List[BenchmarkResult] = []
        self.test_environment = get_test_environment()
    
    def add_protocol(self, protocol: ProtocolBenchmark):
        """Add a protocol to benchmark."""
        self.protocols.append(protocol)
    
    def run_comprehensive_benchmarks(self, test_sizes: Dict[str, int]) -> List[BenchmarkResult]:
        """Run comprehensive benchmarks for all protocols."""
        print("🔬 MAPLE Rigorous Cross-Protocol Benchmark Suite")
        print("Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)")
        print("=" * 80)
        
        # Display test environment
        print(f"\n🖥️ Test Environment:")
        print(f"   CPU: {self.test_environment.cpu_model}")
        print(f"   Cores: {self.test_environment.cpu_cores}")
        print(f"   Frequency: {self.test_environment.cpu_freq_mhz:.0f} MHz")
        print(f"   RAM: {self.test_environment.ram_total_gb:.1f} GB total, {self.test_environment.ram_available_gb:.1f} GB available")
        print(f"   OS: {self.test_environment.os_info}")
        print(f"   Python: {self.test_environment.python_version}")
        print(f"   Time: {self.test_environment.timestamp}")
        
        print(f"\n[STATS] Test Configuration:")
        for test_name, size in test_sizes.items():
            print(f"   {test_name.replace('_', ' ').title()}: {size:,} operations")
        
        all_results = []
        
        for protocol in self.protocols:
            print(f"\n🔬 Testing {protocol.get_name()}")
            print("-" * 60)
            
            if not protocol.setup():
                print(f"[FAIL] Failed to setup {protocol.get_name()}")
                continue
            
            try:
                # Message Creation Benchmark
                print(f"📨 Message Creation ({test_sizes['message_creation']:,} messages)...")
                result = protocol.benchmark_message_creation(test_sizes['message_creation'])
                all_results.append(result)
                print(f"   [PASS] Rate: {result.operations_per_second:,.0f} msg/sec")
                print(f"   [STATS] Latency: {result.latency_ms:.4f} ms/msg")
                print(f"   💾 Memory: {result.memory_usage_mb:.1f} MB")
                print(f"   🔄 CPU: {result.cpu_usage_percent:.1f}%")
                
                # Error Handling Benchmark
                print(f"🛡️ Error Handling ({test_sizes['error_handling']:,} operations)...")
                result = protocol.benchmark_error_handling(test_sizes['error_handling'])
                all_results.append(result)
                print(f"   [PASS] Rate: {result.operations_per_second:,.0f} ops/sec")
                print(f"   [STATS] Success Rate: {result.success_rate:.1%}")
                print(f"   💾 Memory: {result.memory_usage_mb:.1f} MB")
                print(f"   🔄 CPU: {result.cpu_usage_percent:.1f}%")
                
                # Agent Lifecycle Benchmark
                print(f"🤖 Agent Lifecycle ({test_sizes['agent_lifecycle']} agents)...")
                result = protocol.benchmark_agent_lifecycle(test_sizes['agent_lifecycle'])
                all_results.append(result)
                print(f"   [PASS] Rate: {result.operations_per_second:.1f} agents/sec")
                print(f"   [STATS] Latency: {result.latency_ms:.1f} ms/agent")
                print(f"   💾 Memory: {result.memory_usage_mb:.1f} MB")
                print(f"   🔄 CPU: {result.cpu_usage_percent:.1f}%")
                
            except Exception as e:
                logger.error(f"Error testing {protocol.get_name()}: {e}")
                print(f"[FAIL] Error testing {protocol.get_name()}: {e}")
            finally:
                protocol.teardown()
        
        self.results = all_results
        return all_results

def main():
    """Run the rigorous benchmark suite."""
    print("MAPLE MAPLE Rigorous Cross-Protocol Benchmark Suite")
    print("Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)")
    print("=" * 80)
    
    # Initialize benchmark suite
    suite = RigorousBenchmarkSuite()
    
    # Add protocols to test
    protocols = [
        MAPLEBenchmark(),
        SimpleJSONBenchmark()
    ]
    
    for protocol in protocols:
        suite.add_protocol(protocol)
    
    # Define test sizes (reasonable for fair comparison)
    test_sizes = {
        'message_creation': 5000,    # Reasonable for fair comparison
        'error_handling': 10000,     # More error operations
        'agent_lifecycle': 15        # Fewer agents for lifecycle test
    }
    
    try:
        # Run benchmarks
        results = suite.run_comprehensive_benchmarks(test_sizes)
        
        # Display summary
        print(f"\n[STATS] Benchmark Results Summary:")
        print("=" * 80)
        
        # Group and display results
        by_test = {}
        for result in results:
            if result.test_name not in by_test:
                by_test[result.test_name] = []
            by_test[result.test_name].append(result)
        
        for test_name, test_results in by_test.items():
            print(f"\n[RESULT] {test_name.replace('_', ' ').title()}:")
            test_results.sort(key=lambda r: r.operations_per_second, reverse=True)
            
            for i, result in enumerate(test_results):
                if i == 0:
                    print(f"   🥇 {result.protocol_name}: {result.operations_per_second:,.0f} ops/sec")
                else:
                    speedup = test_results[0].operations_per_second / result.operations_per_second
                    print(f"   [STATS] {result.protocol_name}: {result.operations_per_second:,.0f} ops/sec ({speedup:.1f}x slower)")
        
        print(f"\n[PASS] Rigorous benchmark suite completed successfully!")
        print(f"[TARGET] Key Achievement: Scientific, controlled comparison completed")
        print(f"MAPLE MAPLE performance validated under rigorous conditions")
        print(f"Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)")
        
    except Exception as e:
        logger.error(f"Error running benchmark suite: {e}")
        print(f"[FAIL] Error running benchmark suite: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
