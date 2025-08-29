#!/usr/bin/env python3
"""
Quick formatting fix script for MAPLE
This script will apply black and isort formatting to all Python files in the maple/ directory.
"""

import os
import subprocess
import sys
from pathlib import Path

def run_command(cmd, description):
    """Run a command and return True if successful."""
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"✅ {description} - SUCCESS")
        if result.stdout:
            print(f"Output: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - FAILED")
        print(f"Error: {e.stderr}")
        if e.stdout:
            print(f"Output: {e.stdout}")
        return False
    except FileNotFoundError:
        print(f"❌ {description} - COMMAND NOT FOUND")
        print(f"Please install the required tool: pip install {cmd[0]}")
        return False

def main():
    """Fix all formatting issues in the maple/ directory."""
    print("🍁 MAPLE Code Formatting Fix Script")
    print("="*50)
    
    # Change to the project directory
    project_root = Path(__file__).parent
    os.chdir(project_root)
    
    maple_dir = "maple"
    if not os.path.exists(maple_dir):
        print(f"❌ Error: {maple_dir} directory not found!")
        sys.exit(1)
    
    print(f"Working in: {os.getcwd()}")
    print(f"Formatting directory: {maple_dir}/")
    print()
    
    # Install dependencies if needed
    print("Installing formatting tools...")
    install_cmd = [sys.executable, "-m", "pip", "install", "black", "isort", "flake8"]
    run_command(install_cmd, "Installing formatting tools")
    print()
    
    # Step 1: Apply black formatting
    print("Step 1: Applying Black formatting")
    black_cmd = ["black", "--line-length", "88", "--target-version", "py38", maple_dir]
    black_success = run_command(black_cmd, "Black code formatting")
    print()
    
    # Step 2: Apply isort for import sorting  
    print("Step 2: Applying isort for import sorting")
    isort_cmd = ["isort", "--profile", "black", "--multi-line", "3", maple_dir]
    isort_success = run_command(isort_cmd, "Import sorting with isort")
    print()
    
    # Step 3: Check formatting
    print("Step 3: Verifying formatting")
    black_check_cmd = ["black", "--check", "--diff", maple_dir]
    black_check_success = run_command(black_check_cmd, "Black formatting verification")
    
    isort_check_cmd = ["isort", "--check-only", "--diff", maple_dir]
    isort_check_success = run_command(isort_check_cmd, "Import sorting verification")
    print()
    
    # Step 4: Run flake8 for basic linting
    print("Step 4: Running flake8 linting")
    flake8_cmd = ["flake8", maple_dir, "--max-line-length=88", "--extend-ignore=E203,W503"]
    flake8_success = run_command(flake8_cmd, "Flake8 linting check")
    print()
    
    # Summary
    print("="*50)
    print("📊 FORMATTING SUMMARY")
    print("="*50)
    
    results = {
        "Black formatting": black_success,
        "Import sorting": isort_success,  
        "Black verification": black_check_success,
        "Import verification": isort_check_success,
        "Flake8 linting": flake8_success
    }
    
    all_success = all(results.values())
    
    for task, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{task:<20} {status}")
    
    print()
    if all_success:
        print("🎉 ALL FORMATTING CHECKS PASSED!")
        print("Your code is now ready for the GitHub Actions quality check.")
    else:
        print("⚠️  Some formatting issues remain. Check the output above.")
        print("You may need to manually fix remaining issues.")
    
    print()
    print("Next steps:")
    print("1. Commit the formatted code: git add . && git commit -m 'Fix: Code formatting with black and isort'")
    print("2. Push to trigger GitHub Actions: git push")
    
    return 0 if all_success else 1

if __name__ == "__main__":
    sys.exit(main())
