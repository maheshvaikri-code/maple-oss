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

# maple/cli.py
# Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

import argparse
import sys


def main():
    """MAPLE CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="maple",
        description="MAPLE - Multi Agent Protocol Language Engine",
    )
    parser.add_argument(
        "--version", action="store_true", help="Show MAPLE version"
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=["validate", "info"],
        help="Command to run",
    )

    args = parser.parse_args()

    if args.version:
        from maple import __version__
        print(f"MAPLE v{__version__}")
        return 0

    if args.command == "validate":
        from maple import validate_installation
        result = validate_installation()
        if result["status"] == "SUCCESS":
            print(f"MAPLE v{result['version']} is properly installed.")
            return 0
        else:
            print(f"Validation failed: {result.get('error', 'Unknown error')}")
            return 1

    if args.command == "info":
        from maple import __version__, __author__, __license__
        print(f"MAPLE v{__version__}")
        print(f"Author: {__author__}")
        print(f"License: {__license__}")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
