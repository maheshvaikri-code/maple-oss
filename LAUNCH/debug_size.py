#!/usr/bin/env python3
"""
Debug Size Parsing Issue
Creator: Mahesh Vaikri
"""
import sys
import os

# Add the project root to Python path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

def test_size_parsing():
    print("🔍 DEBUGGING SIZE PARSING")
    print("=" * 30)
    
    try:
        from maple.core.types import Size
        print("✅ Size class imported successfully")
        
        # Test the parsing
        test_cases = ["4GB", "1KB", "32GB", "8MB"]
        
        for test_case in test_cases:
            try:
                result = Size.parse(test_case)
                print(f"✅ {test_case} -> {result} bytes")
            except Exception as e:
                print(f"❌ {test_case} failed: {e}")
                import traceback
                traceback.print_exc()
                
    except Exception as e:
        print(f"❌ Import failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_size_parsing()
