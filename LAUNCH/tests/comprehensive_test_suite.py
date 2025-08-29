#!/usr/bin/env python3
"""
Comprehensive MAPLE Test Suite - Launch Directory Version
Creator: Mahesh Vaikri

Run all tests from the Launch directory
"""

import sys
import os
import subprocess

# Add the parent directory to Python path so we can import MAPLE
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

def main():
    """Run the comprehensive test suite from the parent directory."""
    print("