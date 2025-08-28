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
Quick Fix Verification Test
Creator: Mahesh Vaikri

Tests the specific issues that were fixed.
"""

def test_size_parsing():
    """Test the fixed Size.parse method."""
    print("[TEST] Testing Size.parse fixes...")
    
    try:
        from maple.core.types import Size
        
        # Test cases that were failing
        test_cases = [
            ("4GB", 4 * 1024 * 1024 * 1024),
            ("1KB", 1024),
            ("2MB", 2 * 1024 * 1024),
            ("1TB", 1024 * 1024 * 1024 * 1024),
            ("100B", 100),
            ("0.5GB", int(0.5 * 1024 * 1024 * 1024)),
            ("1024", 1024),  # Plain number
        ]
        
        for input_val, expected in test_cases:
            result = Size.parse(input_val)
            assert result == expected, f"Size.parse('{input_val}') = {result}, expected {expected}"
            print(f"  [PASS] {input_val} -> {result:,} bytes")
        
        print("[PASS] Size.parse fixes verified!")
        return True
        
    except Exception as e:
        print(f"[FAIL] Size.parse test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_security_imports():
    """Test the fixed security module imports."""
    print("[TEST] Testing security module imports...")
    
    try:
        from maple.security.link import LinkManager, Link, LinkState
        from maple.security.authentication import AuthenticationManager
        from maple.security.authorization import AuthorizationManager
        from maple.security.encryption import EncryptionManager
        
        # Test basic instantiation
        config = type('Config', (), {'permissions': {}})()
        
        auth_manager = AuthenticationManager(config)
        authz_manager = AuthorizationManager(config)
        encryption_manager = EncryptionManager(config)
        link_manager = LinkManager()
        
        print("  [PASS] All security classes imported and instantiated")
        
        # Test basic functionality
        link = Link("agent_a", "agent_b")
        assert link.agent_a == "agent_a"
        assert link.state == LinkState.INITIATING
        
        print("  [PASS] Link functionality works")
        
        # Test authentication
        auth_result = auth_manager.authenticate({'token': 'test'})
        assert auth_result.is_ok()
        
        print("  [PASS] Authentication works")
        
        print("[PASS] Security imports fixes verified!")
        return True
        
    except Exception as e:
        print(f"[FAIL] Security imports test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run the fix verification tests."""
    print("MAPLE MAPLE Fix Verification Tests")
    print("Creator: Mahesh Vaikri")
    print("=" * 50)
    
    tests = [test_size_parsing, test_security_imports]
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
        print()
    
    print("=" * 50)
    print(f"[STATS] Fix Verification: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("[SUCCESS] All fixes verified! Issues resolved.")
        print("Now run: python test_basic.py")
    else:
        print("[WARN]  Some fixes failed verification.")

if __name__ == "__main__":
    main()
