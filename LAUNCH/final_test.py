#!/usr/bin/env python3
"""
FINAL MAPLE TEST - ALL FIXES APPLIED
Creator: Mahesh Vaikri

This script tests all the fixes and then runs the full test suite.
"""
import sys
import os

# Add the project root to Python path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

def final_validation():
    print("🎯 FINAL MAPLE VALIDATION")
    print("Creator: Mahesh Vaikri")
    print("=" * 50)
    
    tests_passed = 0
    tests_failed = 0
    
    # Test 1: Broker fix
    print("\n🔧 Testing Broker Fix...")
    try:
        from maple.broker.broker import MessageBroker
        from maple import Config, Message, Priority
        
        config = Config(agent_id="test", broker_url="memory://test")
        broker = MessageBroker(config)
        broker.connect()
        
        msg = Message(
            message_type="TEST",
            receiver="test_receiver",
            sender="test_sender", 
            priority=Priority.MEDIUM,
            payload={"test": "data"}
        )
        
        message_id = broker.send(msg)
        
        # Verify it's a string
        assert isinstance(message_id, str), f"Expected str, got {type(message_id)}"
        assert len(message_id) > 0, "Message ID should not be empty"
        
        broker.disconnect()
        print("✅ Broker fix working - returns string message ID")
        tests_passed += 1
        
    except Exception as e:
        print(f"❌ Broker test failed: {e}")
        tests_failed += 1
    
    # Test 2: Size parsing
    print("\n🔧 Testing Size Parsing...")
    try:
        from maple.core.types import Size
        
        result = Size.parse("4GB")
        expected = 4 * 1024 * 1024 * 1024
        assert result == expected
        
        print("✅ Size parsing working")
        tests_passed += 1
        
    except Exception as e:
        print(f"❌ Size parsing failed: {e}")
        tests_failed += 1
    
    # Test 3: Message builder
    print("\n🔧 Testing Message Builder...")
    try:
        msg = Message.builder().message_type("TEST").receiver("agent").build()
        assert msg.message_type == "TEST"
        
        print("✅ Message builder working")
        tests_passed += 1
        
    except Exception as e:
        print(f"❌ Message builder failed: {e}")
        tests_failed += 1
    
    # Test 4: Link methods
    print("\n🔧 Testing Link Methods...")
    try:
        msg = Message(message_type="TEST", payload={})
        linked = msg.with_link("test-123")
        assert linked.get_link_id() == "test-123"
        
        print("✅ Link methods working")
        tests_passed += 1
        
    except Exception as e:
        print(f"❌ Link methods failed: {e}")
        tests_failed += 1
    
    # Summary
    print(f"\n📊 VALIDATION RESULTS:")
    print(f"✅ Passed: {tests_passed}")
    print(f"❌ Failed: {tests_failed}")
    
    if tests_failed == 0:
        print("\n🎉 ALL FIXES SUCCESSFUL!")
        print("🚀 READY TO ACHIEVE 32/32 TESTS!")
        return True
    else:
        print(f"\n⚠️  Still {tests_failed} issues to resolve")
        return False

def run_full_tests():
    """Run the full test suite"""
    print("\n" + "="*50)
    print("🚀 RUNNING FULL MAPLE TEST SUITE")
    print("="*50)
    
    import subprocess
    
    try:
        # Change to parent directory and run tests
        os.chdir(parent_dir) 
        result = subprocess.run([
            sys.executable, "tests/comprehensive_test_suite.py"
        ], capture_output=True, text=True, timeout=300)
        
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
            
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print("❌ Test suite timed out after 5 minutes")
        return False
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return False

def main():
    """Main function"""
    success = final_validation()
    
    if success:
        print("\n🚀 Running comprehensive test suite...")
        full_success = run_full_tests()
        
        if full_success:
            print("\n🎯 PERFECT SUCCESS!")
            print("🏆 MAPLE ACHIEVED 32/32 TESTS!")
            return 0
        else:
            print("\n⚠️  Some tests still failing")
            return 1
    else:
        print("\n❌ Validation failed, not running full tests")
        return 1

if __name__ == "__main__":
    sys.exit(main())
