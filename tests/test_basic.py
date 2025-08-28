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
Basic MAPLE Functionality Test
Creator: Mahesh Vaikri

Tests core MAPLE components to ensure they work correctly.
"""

import sys
import traceback

def test_imports():
    """Test that all MAPLE components can be imported."""
    print("[TEST] Testing MAPLE imports...")
    
    try:
        from maple.core.types import Priority, Size, Duration, Boolean, Integer, String
        from maple.core.result import Result
        from maple.core.message import Message
        from maple.agent.config import Config, SecurityConfig
        print("[PASS] Core imports successful")
        return True
    except Exception as e:
        print(f"[FAIL] Import failed: {e}")
        traceback.print_exc()
        return False

def test_types():
    """Test the type system."""
    print("[TEST] Testing type system...")
    
    try:
        from maple.core.types import Boolean, Integer, String, Size, Duration, Priority
        
        # Test basic types
        assert Boolean.validate(True) == True
        assert Integer.validate(42) == 42
        assert String.validate("hello") == "hello"
        
        # Test size parsing with various formats
        assert Size.parse("4GB") == 4 * 1024 * 1024 * 1024
        assert Size.parse("1KB") == 1024
        assert Size.parse("4gb") == 4 * 1024 * 1024 * 1024  # Test case insensitive
        assert Size.parse("100") == 100  # Test plain number
        
        # Test duration parsing
        assert Duration.parse("30s") == 30.0
        assert Duration.parse("5m") == 300.0
        
        # Test priority enum
        assert Priority.HIGH.value == "HIGH"
        
        print("[PASS] Type system tests passed")
        return True
    except Exception as e:
        print(f"[FAIL] Type system test failed: {e}")
        traceback.print_exc()
        return False

def test_result():
    """Test the Result<T,E> type."""
    print("[TEST] Testing Result<T,E> type...")
    
    try:
        from maple.core.result import Result
        
        # Test Ok result
        ok_result = Result.ok("success")
        assert ok_result.is_ok() == True
        assert ok_result.is_err() == False
        assert ok_result.unwrap() == "success"
        
        # Test Err result
        err_result = Result.err("error")
        assert err_result.is_ok() == False
        assert err_result.is_err() == True
        assert err_result.unwrap_err() == "error"
        
        # Test map
        mapped = ok_result.map(lambda x: x.upper())
        assert mapped.unwrap() == "SUCCESS"
        
        # Test unwrap_or
        assert err_result.unwrap_or("default") == "default"
        
        print("[PASS] Result<T,E> tests passed")
        return True
    except Exception as e:
        print(f"[FAIL] Result<T,E> test failed: {e}")
        traceback.print_exc()
        return False

def test_message():
    """Test message creation and serialization."""
    print("[TEST] Testing message system...")
    
    try:
        from maple.core.message import Message
        from maple.core.types import Priority
        
        # Test message creation
        msg = Message(
            message_type="TEST",
            receiver="test_agent",
            priority=Priority.MEDIUM,
            payload={"data": "test"}
        )
        
        assert msg.message_type == "TEST"
        assert msg.receiver == "test_agent"
        assert msg.priority == Priority.MEDIUM
        assert msg.payload["data"] == "test"
        
        # Test serialization
        msg_dict = msg.to_dict()
        assert "header" in msg_dict
        assert "payload" in msg_dict
        assert msg_dict["header"]["messageType"] == "TEST"
        
        # Test JSON serialization
        json_str = msg.to_json()
        assert isinstance(json_str, str)
        assert "TEST" in json_str
        
        # Test from_dict
        reconstructed = Message.from_dict(msg_dict)
        assert reconstructed.message_type == msg.message_type
        assert reconstructed.payload == msg.payload
        
        print("[PASS] Message system tests passed")
        return True
    except Exception as e:
        print(f"[FAIL] Message test failed: {e}")
        traceback.print_exc()
        return False

def test_config():
    """Test configuration system."""
    print("[TEST] Testing configuration system...")
    
    try:
        from maple.agent.config import Config, SecurityConfig, LinkConfig
        
        # Test basic config
        config = Config(
            agent_id="test_agent",
            broker_url="localhost:8080"
        )
        
        assert config.agent_id == "test_agent"
        assert config.broker_url == "localhost:8080"
        
        # Test security config
        security = SecurityConfig(
            auth_type="test",
            credentials="test_token",
            public_key="test_key"
        )
        
        assert security.auth_type == "test"
        assert security.public_key == "test_key"
        
        # Test link config
        link_config = LinkConfig(
            enabled=True,
            default_lifetime=3600
        )
        
        assert link_config.enabled == True
        assert link_config.default_lifetime == 3600
        
        print("[PASS] Configuration tests passed")
        return True
    except Exception as e:
        print(f"[FAIL] Configuration test failed: {e}")
        traceback.print_exc()
        return False

def test_link_management():
    """Test link management system."""
    print("[TEST] Testing link management...")
    
    try:
        from maple.security.link import LinkManager, Link, LinkState
        
        # Test link creation
        link = Link("agent_a", "agent_b")
        assert link.agent_a == "agent_a"
        assert link.agent_b == "agent_b"
        assert link.state == LinkState.INITIATING
        
        # Test link manager
        manager = LinkManager()
        initiated_link = manager.initiate_link("agent_a", "agent_b")
        
        assert initiated_link.agent_a == "agent_a"
        assert initiated_link.agent_b == "agent_b"
        
        # Test link establishment
        result = manager.establish_link(initiated_link.link_id)
        assert result.is_ok()
        
        established_link = result.unwrap()
        assert established_link.state == LinkState.ESTABLISHED
        
        print("[PASS] Link management tests passed")
        return True
    except Exception as e:
        print(f"[FAIL] Link management test failed: {e}")
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("MAPLE MAPLE Basic Functionality Tests")
    print("Creator: Mahesh Vaikri")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_types,
        test_result,
        test_message, 
        test_config,
        test_link_management
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"[FAIL] Test {test.__name__} crashed: {e}")
            failed += 1
        print()  # Add spacing between tests
    
    print("=" * 50)
    print(f"[STATS] Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("[SUCCESS] All tests passed! MAPLE is working correctly.")
        return 0
    else:
        print("[WARN]  Some tests failed. Check the output above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
