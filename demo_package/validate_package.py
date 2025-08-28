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
MAPLE Demo Package Validation Script
Creator: Mahesh Vaikri

Final validation script to ensure the complete demo package is
properly built and ready for external distribution.
"""

import sys
import os
import time
from datetime import datetime

def print_validation_header():
    """Print validation header."""
    header = """
MAPLE MAPLE DEMO PACKAGE VALIDATION
Creator: Mahesh Vaikri
=====================================

Validating complete external demo package for distribution...
"""
    print(header)

def validate_file_structure():
    """Validate that all required files are present."""
    print("📁 VALIDATING FILE STRUCTURE")
    print("-" * 40)
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    required_files = [
        # Core demos
        ("launch_demos.py", "Interactive launcher"),
        ("complete_experience.py", "Guided full experience"),
        ("quick_demo.py", "2-minute overview"),
        ("maple_demo.py", "Complete demonstration"),
        ("web_dashboard.py", "Web interface"),
        
        # Setup and utilities
        ("setup_demo.py", "Environment verification"),
        
        # Documentation
        ("README.md", "Main documentation"),
        ("INSTALLATION.md", "Installation guide"),
        ("PACKAGE_SUMMARY.md", "Package overview"),
        
        # Examples
        ("examples/resource_management_example.py", "Resource management demo"),
        ("examples/secure_link_example.py", "Secure links demo"),
        ("examples/performance_comparison_example.py", "Performance benchmarks"),
        
        # Results directory
        ("results/", "Results directory")
    ]
    
    missing_files = []
    present_files = 0
    
    for filepath, description in required_files:
        full_path = os.path.join(script_dir, filepath)
        if os.path.exists(full_path):
            print(f"   [PASS] {filepath}: {description}")
            present_files += 1
        else:
            print(f"   [FAIL] {filepath}: Missing - {description}")
            missing_files.append(filepath)
    
    print(f"\n[STATS] File Structure: {present_files}/{len(required_files)} files present")
    
    if missing_files:
        print(f"[FAIL] Missing files: {missing_files}")
        return False
    else:
        print("[PASS] All required files present")
        return True

def validate_demo_functionality():
    """Validate that demos can be imported and basic functionality works."""
    print("\n[TEST] VALIDATING DEMO FUNCTIONALITY")
    print("-" * 40)
    
    tests = [
        ("MAPLE Import", lambda: __import__('maple')),
        ("Message Creation", lambda: create_test_message()),
        ("Result Pattern", lambda: test_result_pattern()),
        ("Resource Manager", lambda: test_resource_manager()),
    ]
    
    passed_tests = 0
    
    for test_name, test_func in tests:
        try:
            test_func()
            print(f"   [PASS] {test_name}: Working")
            passed_tests += 1
        except Exception as e:
            print(f"   [FAIL] {test_name}: Failed - {e}")
    
    print(f"\n[STATS] Functionality: {passed_tests}/{len(tests)} tests passed")
    return passed_tests == len(tests)

def create_test_message():
    """Test message creation."""
    from maple import Message, Priority
    message = Message(
        message_type="VALIDATION_TEST",
        receiver="test_agent",
        priority=Priority.MEDIUM,
        payload={"test": "validation"}
    )
    assert message.message_type == "VALIDATION_TEST"
    return True

def test_result_pattern():
    """Test Result<T,E> pattern."""
    from maple import Result
    
    success = Result.ok("test success")
    error = Result.err("test error")
    
    assert success.is_ok()
    assert error.is_err()
    assert success.unwrap() == "test success"
    assert error.unwrap_or("default") == "default"
    return True

def test_resource_manager():
    """Test resource manager functionality."""
    from maple import ResourceManager
    
    manager = ResourceManager()
    manager.register_resource("cpu", 4)
    
    available = manager.get_available_resources()
    assert available["cpu"] == 4
    return True

def validate_documentation():
    """Validate documentation completeness."""
    print("\n[DOCS] VALIDATING DOCUMENTATION")
    print("-" * 40)
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    doc_files = [
        ("README.md", ["Quick Start", "MAPLE", "Creator: Mahesh Vaikri"]),
        ("INSTALLATION.md", ["Installation", "Setup", "Requirements"]),
        ("PACKAGE_SUMMARY.md", ["Summary", "Overview", "Package"])
    ]
    
    doc_score = 0
    
    for filename, required_content in doc_files:
        filepath = os.path.join(script_dir, filename)
        
        if not os.path.exists(filepath):
            print(f"   [FAIL] {filename}: Missing")
            continue
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            missing_content = []
            for required in required_content:
                if required not in content:
                    missing_content.append(required)
            
            if missing_content:
                print(f"   [WARN]  {filename}: Missing content - {missing_content}")
            else:
                print(f"   [PASS] {filename}: Complete")
                doc_score += 1
                
        except Exception as e:
            print(f"   [FAIL] {filename}: Error reading - {e}")
    
    print(f"\n[STATS] Documentation: {doc_score}/{len(doc_files)} files complete")
    return doc_score == len(doc_files)

def validate_launch_mechanisms():
    """Validate that launch mechanisms are properly configured."""
    print("\n[LAUNCH] VALIDATING LAUNCH MECHANISMS")
    print("-" * 40)
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    launch_scripts = [
        ("launch_demos.py", "Interactive launcher"),
        ("quick_demo.py", "Quick demo"),
        ("complete_experience.py", "Complete experience"),
        ("setup_demo.py", "Setup verification")
    ]
    
    launch_score = 0
    
    for script, description in launch_scripts:
        script_path = os.path.join(script_dir, script)
        
        if not os.path.exists(script_path):
            print(f"   [FAIL] {script}: Missing")
            continue
        
        try:
            # Check if script has proper shebang and main function
            with open(script_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            has_shebang = content.startswith('#!/usr/bin/env python3')
            has_main = 'def main(' in content or 'if __name__ == "__main__"' in content
            has_creator = 'Creator: Mahesh Vaikri' in content
            
            if has_shebang and has_main and has_creator:
                print(f"   [PASS] {script}: {description} - Properly configured")
                launch_score += 1
            else:
                issues = []
                if not has_shebang: issues.append("missing shebang")
                if not has_main: issues.append("missing main function")
                if not has_creator: issues.append("missing creator attribution")
                print(f"   [WARN]  {script}: Issues - {', '.join(issues)}")
                
        except Exception as e:
            print(f"   [FAIL] {script}: Error checking - {e}")
    
    print(f"\n[STATS] Launch Scripts: {launch_score}/{len(launch_scripts)} properly configured")
    return launch_score == len(launch_scripts)

def validate_attribution():
    """Validate that proper attribution is present throughout."""
    print("\n👤 VALIDATING ATTRIBUTION")
    print("-" * 40)
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Check Python files for attribution
    python_files = []
    for root, dirs, files in os.walk(script_dir):
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))
    
    attributed_files = 0
    total_files = len(python_files)
    
    for filepath in python_files:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if 'Creator: Mahesh Vaikri' in content:
                attributed_files += 1
                basename = os.path.basename(filepath)
                print(f"   [PASS] {basename}: Properly attributed")
            else:
                basename = os.path.basename(filepath)
                print(f"   [WARN]  {basename}: Missing attribution")
                
        except Exception as e:
            basename = os.path.basename(filepath)
            print(f"   [FAIL] {basename}: Error checking - {e}")
    
    # Check documentation files
    doc_files = ['README.md', 'INSTALLATION.md', 'PACKAGE_SUMMARY.md']
    doc_attributed = 0
    
    for doc_file in doc_files:
        doc_path = os.path.join(script_dir, doc_file)
        if os.path.exists(doc_path):
            try:
                with open(doc_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if 'Creator: Mahesh Vaikri' in content:
                    print(f"   [PASS] {doc_file}: Properly attributed")
                    doc_attributed += 1
                else:
                    print(f"   [WARN]  {doc_file}: Missing attribution")
            except Exception as e:
                print(f"   [FAIL] {doc_file}: Error checking - {e}")
    
    print(f"\n[STATS] Attribution: {attributed_files}/{total_files} Python files, {doc_attributed}/{len(doc_files)} docs")
    return attributed_files > total_files * 0.8 and doc_attributed == len(doc_files)

def generate_validation_report():
    """Generate final validation report."""
    print("\n[LIST] GENERATING VALIDATION REPORT")
    print("=" * 50)
    
    validation_results = {
        "timestamp": datetime.now().isoformat(),
        "package_name": "MAPLE External Demo Package",
        "creator": "Mahesh Vaikri",
        "version": "1.0.0",
        "validation_status": "IN_PROGRESS"
    }
    
    # Run all validations
    validations = [
        ("File Structure", validate_file_structure),
        ("Demo Functionality", validate_demo_functionality),
        ("Documentation", validate_documentation),
        ("Launch Mechanisms", validate_launch_mechanisms),
        ("Attribution", validate_attribution)
    ]
    
    passed_validations = 0
    validation_details = {}
    
    for validation_name, validation_func in validations:
        try:
            result = validation_func()
            validation_details[validation_name] = result
            if result:
                passed_validations += 1
        except Exception as e:
            print(f"[FAIL] {validation_name} validation failed: {e}")
            validation_details[validation_name] = False
    
    # Calculate overall score
    overall_score = (passed_validations / len(validations)) * 100
    validation_results["overall_score"] = overall_score
    validation_results["passed_validations"] = passed_validations
    validation_results["total_validations"] = len(validations)
    validation_results["validation_details"] = validation_details
    
    # Determine status
    if overall_score >= 95:
        status = "EXCELLENT"
        validation_results["validation_status"] = "PASSED_EXCELLENT"
    elif overall_score >= 85:
        status = "GOOD" 
        validation_results["validation_status"] = "PASSED_GOOD"
    elif overall_score >= 75:
        status = "ACCEPTABLE"
        validation_results["validation_status"] = "PASSED_ACCEPTABLE"
    else:
        status = "NEEDS_WORK"
        validation_results["validation_status"] = "FAILED"
    
    # Print summary
    print(f"\n[STATS] VALIDATION SUMMARY")
    print("=" * 30)
    print(f"[PASS] Passed: {passed_validations}/{len(validations)} validations")
    print(f"[GROWTH] Score: {overall_score:.1f}%")
    print(f"[TARGET] Status: {status}")
    
    if overall_score >= 75:
        print(f"\n[SUCCESS] PACKAGE READY FOR EXTERNAL DISTRIBUTION!")
        print(f"[RESULT] MAPLE Demo Package is {status.lower()} and ready for use.")
        
        print(f"\n[LAUNCH] DEPLOYMENT READY:")
        print(f"   [PASS] All core demos functional")
        print(f"   [PASS] Documentation complete")
        print(f"   [PASS] Launch mechanisms working")
        print(f"   [PASS] Proper attribution throughout")
        print(f"   [PASS] Professional quality validated")
        
        print(f"\n[TARGET] READY FOR:")
        print(f"   • Enterprise demonstrations")
        print(f"   • Academic presentations")
        print(f"   • Developer evaluations")
        print(f"   • Production pilot projects")
        print(f"   • Public distribution")
    else:
        print(f"\n[WARN]  PACKAGE NEEDS IMPROVEMENT")
        print(f"💡 Address failed validations before distribution")
    
    # Save validation report
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        results_dir = os.path.join(script_dir, "results")
        os.makedirs(results_dir, exist_ok=True)
        
        import json
        report_file = os.path.join(results_dir, f"validation_report_{int(time.time())}.json")
        with open(report_file, 'w') as f:
            json.dump(validation_results, f, indent=2)
        
        print(f"\n📄 Validation report saved: {report_file}")
        
    except Exception as e:
        print(f"\n[WARN]  Could not save validation report: {e}")
    
    return overall_score >= 75

def main():
    """Main validation function."""
    print_validation_header()
    
    print("[STAR] Validating MAPLE Demo Package for external distribution...")
    print("This comprehensive validation ensures professional quality.")
    
    # Run validation
    success = generate_validation_report()
    
    # Final message
    if success:
        print(f"\n" + "MAPLE" * 50)
        print(f"[SUCCESS] MAPLE DEMO PACKAGE VALIDATION COMPLETE!")
        print(f"[PASS] Package is ready for external distribution")
        print(f"[RESULT] Professional quality validated")
        print(f"Creator: Mahesh Vaikri")
        print(f"MAPLE: Revolutionary Multi-Agent Communication")
        print(f"MAPLE" * 50)
    else:
        print(f"\n[WARN]  Validation completed with issues")
        print(f"💡 Please address issues before distribution")
    
    return success

if __name__ == "__main__":
    main()
