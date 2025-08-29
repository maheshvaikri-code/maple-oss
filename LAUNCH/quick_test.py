#!/usr/bin/env python3
"""
Quick test runner to check our fixes
Creator: Mahesh Vaikri
"""

import sys
import os

# Add the project root to Python path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

def test_quick_fixes():
    """Test our quick fixes"""
    print("🔧 TESTING QUICK FIXES")
    print("=" * 50)
    
    # Test 1: Boolean import
    try:
        from maple.core.types import Boolean, Integer, String, Size, Duration
        print("✅ Boolean, Integer, String imports working")
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False
    
    # Test 2: Size parsing
    try:
        result = Size.parse("4GB")
        expected = 4 * 1024 * 1024 * 1024
        assert result == expected, f"Expected {expected}, got {result}"
        print("✅ Size parsing working: 4GB =", result)
    except Exception as e:
        print(f"❌ Size parsing failed: {e}")
        return False
    
    # Test 3: Message builder
    try:
        from maple.core.message import Message
        from maple.core.types import Priority
        
        builder_msg = Message.builder().message_type("TEST").receiver("test_agent").priority(Priority.HIGH).payload({"test": True}).build()
        
        assert builder_msg.message_type == "TEST"
        assert builder_msg.receiver == "test_agent"
        print("✅ Message builder working")
    except Exception as e:
        print(f"❌ Message builder failed: {e}")
        return False
    
    # Test 4: with_link method
    try:
        msg = Message(message_type="TEST", payload={"data": "test"})
        linked_msg = msg.with_link("test-link-123")
        assert linked_msg.get_link_id() == "test-link-123"
        print("✅ with_link method working")
    except Exception as e:
        print(f"❌ with_link method failed: {e}")
        return False
    
    print("🎉 ALL QUICK FIXES WORKING!")
    return True

if __name__ == "__main__":
    success = test_quick_fixes()
    print(f"\n🚀 Ready to run full test suite: {'YES' if success else 'NO'}")
