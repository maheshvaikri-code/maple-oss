#!/usr/bin/env python3
"""
Run Fixed Tests - Quick validation
Creator: Mahesh Vaikri
"""
import sys
import os
import time
import subprocess

# Add the project root to Python path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

def main():
    """Run the comprehensive test suite from the parent directory."""
    print("🚀 RUNNING MAPLE FIXED TESTS")
    print("Creator: Mahesh Vaikri") 
    print("=" * 50)
    
    # Change to parent directory and run tests
    original_dir = os.getcwd()
    try:
        os.chdir(parent_dir)
        result = subprocess.run([
            sys.executable, 
            "tests/comprehensive_test_suite.py"
        ], capture_output=True, text=True)
        
        print("STDOUT:")
        print(result.stdout)
        
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
            
        return result.returncode
        
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return 1
    finally:
        os.chdir(original_dir)

if __name__ == "__main__":
    sys.exit(main())
