#!/usr/bin/env python3
"""
Format all Python files in the maple directory with black-like formatting.
This script manually applies common formatting fixes.
"""

import os
import re
from pathlib import Path
from typing import List, Dict


def format_imports(content: str) -> str:
    """Apply basic import formatting - group standard library, third-party, and local imports."""
    lines = content.split('\n')
    
    # Find the end of license/docstring headers
    in_docstring = False
    docstring_char = None
    header_end = 0
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        
        # Track docstrings
        if stripped.startswith('"""') or stripped.startswith("'''"):
            if not in_docstring:
                in_docstring = True
                docstring_char = stripped[:3]
            elif stripped.endswith(docstring_char):
                in_docstring = False
                header_end = i + 1
                continue
        elif in_docstring and stripped.endswith(docstring_char):
            in_docstring = False
            header_end = i + 1
            continue
        
        # Skip empty lines and comments after header
        if not in_docstring and stripped and not stripped.startswith('#'):
            if not stripped.startswith('import') and not stripped.startswith('from'):
                header_end = i
            break
    
    # Extract header, imports, and rest
    header = lines[:header_end]
    rest_lines = lines[header_end:]
    
    # Find import section
    import_lines = []
    post_import_start = 0
    
    for i, line in enumerate(rest_lines):
        stripped = line.strip()
        if stripped and (stripped.startswith('import ') or stripped.startswith('from ')):
            import_lines.append(line)
        elif import_lines and stripped:  # Non-import after imports
            post_import_start = i
            break
        elif not stripped and import_lines:  # Empty line after imports
            post_import_start = i + 1
            break
    
    # Sort imports (basic grouping)
    std_imports = []
    local_imports = []
    
    for imp in import_lines:
        stripped = imp.strip()
        if stripped.startswith('from .') or stripped.startswith('from ..'):
            local_imports.append(imp)
        else:
            std_imports.append(imp)
    
    # Combine all parts
    result_lines = header
    
    # Add blank line after header if needed
    if header and header[-1].strip():
        result_lines.append('')
    
    # Add imports
    if std_imports:
        result_lines.extend(sorted(std_imports))
    
    if std_imports and local_imports:
        result_lines.append('')
    
    if local_imports:
        result_lines.extend(sorted(local_imports))
    
    if import_lines:
        result_lines.append('')
    
    # Add rest of the content
    result_lines.extend(rest_lines[post_import_start:])
    
    return '\n'.join(result_lines)


def format_quotes(content: str) -> str:
    """Convert single quotes to double quotes (basic implementation)."""
    # This is a simplified approach - in practice, black is much more sophisticated
    
    # Don't change quotes inside strings or comments
    lines = content.split('\n')
    formatted_lines = []
    
    for line in lines:
        # Skip comments and docstrings
        if line.strip().startswith('#'):
            formatted_lines.append(line)
            continue
        
        if '"""' in line or "'''" in line:
            formatted_lines.append(line)
            continue
        
        # Simple quote replacement (this is very basic and not 100% accurate)
        new_line = line
        
        # Replace single quotes with double quotes, but be careful of apostrophes
        # This is a very simplified version - black's implementation is much more complex
        if "'" in line and '"' not in line:
            # Basic replacement for simple cases
            new_line = re.sub(r"'([^']*)'", r'"\1"', line)
        
        formatted_lines.append(new_line)
    
    return '\n'.join(formatted_lines)


def format_spacing(content: str) -> str:
    """Apply basic spacing rules."""
    lines = content.split('\n')
    formatted_lines = []
    
    for line in lines:
        # Remove trailing whitespace
        formatted_line = line.rstrip()
        
        # Basic spacing around operators (very simplified)
        # This is just a basic example - black does much more
        
        formatted_lines.append(formatted_line)
    
    return '\n'.join(formatted_lines)


def format_python_file(filepath: Path) -> bool:
    """Format a single Python file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            original_content = f.read()
        
        # Apply formatting
        formatted_content = original_content
        formatted_content = format_imports(formatted_content)
        formatted_content = format_quotes(formatted_content)
        formatted_content = format_spacing(formatted_content)
        
        # Only write if changed
        if formatted_content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(formatted_content)
            return True
        
        return False
    
    except Exception as e:
        print(f"Error formatting {filepath}: {e}")
        return False


def find_python_files(directory: Path) -> List[Path]:
    """Find all Python files in directory."""
    python_files = []
    
    for root, dirs, files in os.walk(directory):
        # Skip __pycache__ directories
        dirs[:] = [d for d in dirs if d != '__pycache__']
        
        for file in files:
            if file.endswith('.py'):
                python_files.append(Path(root) / file)
    
    return python_files


def main():
    """Format all Python files in maple directory."""
    project_root = Path(__file__).parent
    maple_dir = project_root / 'maple'
    
    if not maple_dir.exists():
        print(f"Error: {maple_dir} directory not found!")
        return 1
    
    print(f"🍁 MAPLE Python File Formatter")
    print(f"Working directory: {project_root}")
    print(f"Formatting files in: {maple_dir}")
    print("=" * 50)
    
    # Find all Python files
    python_files = find_python_files(maple_dir)
    
    print(f"Found {len(python_files)} Python files to check:")
    for file in python_files:
        print(f"  - {file.relative_to(project_root)}")
    print()
    
    # Format each file
    modified_files = []
    
    for file in python_files:
        print(f"Checking {file.relative_to(project_root)}...", end=' ')
        
        if format_python_file(file):
            print("✅ FORMATTED")
            modified_files.append(file)
        else:
            print("✅ NO CHANGES")
    
    print()
    print("=" * 50)
    print("📊 FORMATTING SUMMARY")
    print("=" * 50)
    
    print(f"Files checked: {len(python_files)}")
    print(f"Files modified: {len(modified_files)}")
    
    if modified_files:
        print("\nModified files:")
        for file in modified_files:
            print(f"  - {file.relative_to(project_root)}")
    
    print()
    if len(modified_files) > 0:
        print("🎉 Files have been formatted!")
        print("Next steps:")
        print("1. Review the changes: git diff")
        print("2. Commit the formatted code: git add . && git commit -m 'Fix: Apply code formatting'")
        print("3. Push to trigger GitHub Actions: git push")
    else:
        print("✨ All files are already properly formatted!")
    
    return 0


if __name__ == "__main__":
    exit(main())
