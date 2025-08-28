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
MAPLE Demo Package Setup Script
Creator: Mahesh Vaikri

Simple setup script to prepare your environment for MAPLE demonstrations.
This script checks dependencies, validates the installation, and provides
guidance for running the demos.
"""

import sys
import os
import subprocess
import time

def print_header():
    """Print setup header."""
    print("MAPLE MAPLE Demo Package Setup")
    print("Creator: Mahesh Vaikri")
    print("=" * 50)

def check_python_version():
    """Check if Python version is compatible."""
    print("\n🐍 Checking Python Version...")
    
    version = sys.version_info
    print(f"   Current Python: {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("   [FAIL] Python 3.8+ required")
        print("   💡 Please upgrade Python to version 3.8 or higher")
        return False
    else:
        print("   [PASS] Python version compatible")
        return True

def check_maple_installation():
    """Check if MAPLE is properly installed."""
    print("\n📦 Checking MAPLE Installation...")
    
    try:
        # Try to import MAPLE
        import maple
        
        print(f"   [PASS] MAPLE imported successfully")
        print(f"   [LIST] Version: {maple.__version__}")
        print(f"   👤 Creator: {maple.__author__}")
        
        # Check core components
        from maple import Agent, Message, Priority, Result, ResourceManager
        print("   [PASS] Core components available")
        
        # Check feature availability
        version_info = maple.get_version_info()
        features = version_info.get('features', {})
        
        print("   [STATS] Feature Status:")
        for feature, available in features.items():
            status = "[PASS]" if available else "[WARN]"
            print(f"      {status} {feature}: {available}")
        
        return True
        
    except ImportError as e:
        print(f"   [FAIL] MAPLE not properly installed: {e}")
        print("   💡 Try: pip install -e . (from project root)")
        return False
    except Exception as e:
        print(f"   [FAIL] MAPLE installation issue: {e}")
        return False

def check_optional_dependencies():
    """Check optional dependencies for enhanced features."""
    print("\n[FIX] Checking Optional Dependencies...")
    
    optional_deps = [
        ("psutil", "System monitoring features"),
        ("cryptography", "Advanced encryption features"),
        ("nats-py", "NATS broker support")
    ]
    
    available_deps = []
    missing_deps = []
    
    for package, description in optional_deps:
        try:
            __import__(package.replace('-', '_'))
            print(f"   [PASS] {package}: Available - {description}")
            available_deps.append(package)
        except ImportError:
            print(f"   [WARN]  {package}: Missing - {description}")
            missing_deps.append(package)
    
    if missing_deps:
        print(f"\n   💡 Install optional features:")
        for package in missing_deps:
            print(f"      pip install {package}")
    
    return len(available_deps), len(missing_deps)

def test_basic_functionality():
    """Test basic MAPLE functionality."""
    print("\n[TEST] Testing Basic Functionality...")
    
    try:
        from maple import Message, Priority, Result, ResourceManager
        
        # Test message creation
        message = Message(
            message_type="SETUP_TEST",
            receiver="test_agent",
            priority=Priority.MEDIUM,
            payload={"test": "setup verification"}
        )
        print("   [PASS] Message creation working")
        
        # Test Result<T,E>
        success_result = Result.ok("test successful")
        error_result = Result.err("test error")
        
        assert success_result.is_ok()
        assert error_result.is_err()
        assert success_result.unwrap() == "test successful"
        assert error_result.unwrap_or("default") == "default"
        print("   [PASS] Result<T,E> pattern working")
        
        # Test resource manager
        resource_manager = ResourceManager()
        resource_manager.register_resource("cpu", 4)
        
        available = resource_manager.get_available_resources()
        assert available["cpu"] == 4
        print("   [PASS] Resource management working")
        
        # Test serialization
        json_str = message.to_json()
        reconstructed = Message.from_json(json_str)
        assert reconstructed.message_type == message.message_type
        print("   [PASS] Message serialization working")
        
        return True
        
    except Exception as e:
        print(f"   [FAIL] Basic functionality test failed: {e}")
        return False

def check_demo_files():
    """Check if demo files are present."""
    print("\n📁 Checking Demo Files...")
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    demo_files = [
        ("maple_demo.py", "Complete interactive demonstration"),
        ("quick_demo.py", "Quick 2-minute demo"),
        ("README.md", "Demo documentation"),
        ("examples/resource_management_example.py", "Resource management example"),
        ("examples/secure_link_example.py", "Secure link example")
    ]
    
    all_present = True
    
    for filename, description in demo_files:
        filepath = os.path.join(script_dir, filename)
        if os.path.exists(filepath):
            print(f"   [PASS] {filename}: {description}")
        else:
            print(f"   [FAIL] {filename}: Missing - {description}")
            all_present = False
    
    return all_present

def run_quick_verification():
    """Run a quick verification of MAPLE performance."""
    print("\n[FAST] Quick Performance Verification...")
    
    try:
        from maple import Message, Priority, Result
        
        # Test message creation speed
        start_time = time.time()
        messages = []
        
        for i in range(1000):
            msg = Message(
                message_type="PERF_TEST",
                receiver=f"agent_{i % 10}",
                priority=Priority.MEDIUM,
                payload={"index": i, "data": f"test_{i}"}
            )
            messages.append(msg)
        
        creation_time = time.time() - start_time
        rate = 1000 / creation_time
        
        print(f"   [STATS] Created 1,000 messages in {creation_time:.3f}s")
        print(f"   🔥 Rate: {rate:,.0f} messages/second")
        
        if rate > 10000:
            print("   [PASS] Performance: Excellent (>10K msg/sec)")
        elif rate > 5000:
            print("   [PASS] Performance: Good (>5K msg/sec)")
        else:
            print("   [WARN]  Performance: Acceptable")
        
        # Test Result operations
        start_time = time.time()
        
        for i in range(5000):
            if i % 2 == 0:
                result = Result.ok(i)
                mapped = result.map(lambda x: x * 2)
            else:
                result = Result.err("error")
                fallback = result.unwrap_or(0)
        
        result_time = time.time() - start_time
        result_rate = 5000 / result_time
        
        print(f"   [STATS] Processed 5,000 Result operations in {result_time:.3f}s")
        print(f"   🔥 Rate: {result_rate:,.0f} operations/second")
        
        return True
        
    except Exception as e:
        print(f"   [FAIL] Performance verification failed: {e}")
        return False

def provide_setup_guidance():
    """Provide guidance for running demos."""
    print("\n[TARGET] Demo Execution Guidance")
    print("=" * 40)
    
    print("\n[LAUNCH] Quick Start Options:")
    print("   1. Quick Demo (2 minutes):")
    print("      python quick_demo.py")
    print("")
    print("   2. Complete Demo (15 minutes):")
    print("      python maple_demo.py")
    print("")
    print("   3. Specific Examples:")
    print("      python examples/resource_management_example.py")
    print("      python examples/secure_link_example.py")
    
    print("\n[DOCS] What You'll See:")
    print("   [TARGET] Resource Management (UNIQUE to MAPLE)")
    print("   [SECURE] Link Identification Mechanism (UNIQUE to MAPLE)")
    print("   [FAST] Performance Superiority (25-100x faster)")
    print("   🌆 Real-world Smart City scenario")
    print("   [RESULT] Head-to-head competitive comparisons")
    
    print("\n💡 Demo Tips:")
    print("   • Run in a terminal for best experience")
    print("   • Allow network connections (for broker)")
    print("   • Have 15 minutes for the complete demo")
    print("   • Try examples for focused feature demos")
    
    print("\n[EVENT] Interactive Features:")
    print("   • Real-time performance metrics")
    print("   • Live agent communication")
    print("   • Security violation detection")
    print("   • Resource allocation visualization")

def main():
    """Run the setup script."""
    print_header()
    
    print("\n[STAR] Preparing your environment for MAPLE demonstrations...")
    print("This script will verify that everything is ready for the demo.")
    
    # Run all checks
    checks = [
        ("Python Version", check_python_version),
        ("MAPLE Installation", check_maple_installation),
        ("Basic Functionality", test_basic_functionality),
        ("Demo Files", check_demo_files),
        ("Performance Verification", run_quick_verification)
    ]
    
    passed_checks = 0
    total_checks = len(checks)
    
    for check_name, check_function in checks:
        print(f"\n{'='*50}")
        try:
            if check_function():
                passed_checks += 1
                print(f"[PASS] {check_name}: PASSED")
            else:
                print(f"[FAIL] {check_name}: FAILED")
        except Exception as e:
            print(f"[FAIL] {check_name}: ERROR - {e}")
    
    # Check optional dependencies (doesn't affect pass/fail)
    available_optional, missing_optional = check_optional_dependencies()
    
    # Final summary
    print(f"\n{'='*50}")
    print(f"[STATS] SETUP SUMMARY")
    print(f"[PASS] Core checks passed: {passed_checks}/{total_checks}")
    print(f"[FIX] Optional features: {available_optional}/{available_optional + missing_optional}")
    
    success_rate = passed_checks / total_checks
    
    if success_rate == 1.0:
        print(f"\n[SUCCESS] SETUP COMPLETE! All checks passed!")
        print(f"[LAUNCH] You're ready to experience MAPLE's revolutionary capabilities!")
        
        provide_setup_guidance()
        
        print(f"\nMAPLE Ready to see the future of agent communication?")
        
    elif success_rate >= 0.8:
        print(f"\n[PASS] SETUP MOSTLY COMPLETE!")
        print(f"[LAUNCH] You can run the demos with minor limitations.")
        
        provide_setup_guidance()
        
    else:
        print(f"\n[WARN]  SETUP NEEDS ATTENTION")
        print(f"💡 Please resolve the failed checks before running demos.")
        
        print(f"\n[FIX] Common Solutions:")
        print(f"   • Install MAPLE: pip install -e . (from project root)")
        print(f"   • Upgrade Python: Use Python 3.8 or higher")
        print(f"   • Check file permissions and paths")
    
    print(f"\nMAPLE MAPLE Demo Package Setup Complete")
    print(f"Creator: Mahesh Vaikri")
    print(f"Ready to revolutionize multi-agent communication!")

if __name__ == "__main__":
    main()
