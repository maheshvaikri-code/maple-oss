#!/usr/bin/env python3
"""
Script to help commit the formatting fixes.
"""

import subprocess
import sys
import os
from pathlib import Path

def run_command(cmd, description):
    """Run a command and return success status."""
    print(f"📝 {description}")
    print(f"   Running: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"   ✅ Success")
        if result.stdout:
            print(f"   Output: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"   ❌ Failed: {e}")
        if e.stderr:
            print(f"   Error: {e.stderr.strip()}")
        return False

def main():
    """Commit the formatting changes."""
    print("🍁 MAPLE Code Formatting - Commit Helper")
    print("="*50)
    
    # Change to project directory
    project_root = Path(__file__).parent
    os.chdir(project_root)
    
    print(f"Working directory: {project_root}")
    print()
    
    # Check git status
    print("1️⃣ Checking Git Status")
    success = run_command(["git", "status", "--porcelain"], "Check git status")
    
    if not success:
        print("❌ Git not available or not in a git repository")
        return 1
    
    print()
    
    # Add all changes
    print("2️⃣ Adding Changes")
    success = run_command(["git", "add", "."], "Add all changes")
    
    if not success:
        print("❌ Failed to add changes")
        return 1
    
    print()
    
    # Create commit
    print("3️⃣ Creating Commit")
    commit_message = "Fix: Apply code formatting with black and isort standards\n\n" + \
                    "- Fix import ordering (standard library first, then local)\n" + \
                    "- Convert single quotes to double quotes\n" + \
                    "- Apply consistent spacing and indentation\n" + \
                    "- Remove trailing whitespace\n" + \
                    "- Fix line length issues for GitHub Actions quality check"
    
    success = run_command(["git", "commit", "-m", commit_message], "Create commit")
    
    if not success:
        print("❌ Failed to create commit")
        return 1
    
    print()
    
    # Show final status
    print("4️⃣ Final Status")
    run_command(["git", "log", "--oneline", "-1"], "Show latest commit")
    
    print()
    print("🎉 FORMATTING COMMIT CREATED SUCCESSFULLY!")
    print()
    print("Next steps:")
    print("1. Push to GitHub: git push")
    print("2. Watch the GitHub Actions quality check pass! ✅")
    print()
    print("The code formatting issues have been resolved and committed.")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
