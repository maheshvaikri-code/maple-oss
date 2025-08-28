#!/usr/bin/env python3
"""
Quick test to verify MAPLE imports work for the killer demo
"""

import sys
import os

# Add MAPLE to path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if os.path.exists(os.path.join(project_root, 'maple')):
    sys.path.insert(0, project_root)

def test_imports():
    """Test the imports needed for the killer demo."""
    print("🧪 Testing MAPLE imports for killer demo...")
    
    try:
        from maple import Agent, Message, Priority, Config, Result
        print("✅ Core MAPLE imports successful")
        
        # Test Priority enum values
        print(f"✅ Priority.HIGH = {Priority.HIGH.value}")
        print(f"✅ Priority.MEDIUM = {Priority.MEDIUM.value}")
        print(f"✅ Priority.LOW = {Priority.LOW.value}")
        
        # Test basic Message creation
        msg = Message(
            message_type="TEST",
            receiver="test_agent",
            priority=Priority.HIGH,
            payload={"test": "data"}
        )
        print("✅ Message creation successful")
        
        # Test Result type
        result = Result.ok("test_data")
        print(f"✅ Result.ok successful: {result.is_ok()}")
        
        error_result = Result.err({"error": "test_error"})
        print(f"✅ Result.err successful: {error_result.is_err()}")
        
        from maple.resources import ResourceRequest, ResourceRange
        print("✅ Resource imports successful")
        
        from maple.security import LinkManager
        print("✅ Security imports successful")
        
        print("\n🎉 ALL IMPORTS SUCCESSFUL! Killer demo should work!")
        return True
        
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Test error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_imports()
    if success:
        print("\n🚀 Ready to run the killer demo!")
        print("Run: python killer_demo.py")
    else:
        print("\n⚠️ Fix imports before running killer demo")
