"""
Copyright (C) 2025 Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

This file is part of MAPLE - Multi Agent Protocol Language Engine.

MAPLE - Multi Agent Protocol Language Engine is free software: you can
redistribute it and/or modify it under the terms of the GNU Affero General
Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later version.
MAPLE - Multi Agent Protocol Language Engine is distributed in the hope that
it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty
of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero
General Public License for more details. You should have received a copy of the
GNU Affero General Public License along with MAPLE - Multi Agent Protocol
Language Engine. If not, see <https://www.gnu.org/licenses/>.
"""

# maple/cli.py
# Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

import argparse
import json
import sys


def doctor_report():
    """Return a local-only readiness report for the published runtime surface."""
    from maple import (
        EvalCase,
        EventStream,
        InMemoryLexicalRetriever,
        InMemorySessionStore,
        InteropEnvelope,
        TrustedLocalExecutor,
        __version__,
    )

    checks = {
        "core": True,
        "execution": isinstance(TrustedLocalExecutor(), TrustedLocalExecutor),
        "retrieval": isinstance(InMemoryLexicalRetriever(), InMemoryLexicalRetriever),
        "sessions": isinstance(InMemorySessionStore(), InMemorySessionStore),
        "events": isinstance(EventStream(), EventStream),
        "evaluation": isinstance(
            EvalCase("doctor", True, expected_output=True), EvalCase
        ),
        "interop": InteropEnvelope(
            protocol="doctor",
            message_type="READY",
            payload={"ok": True},
            metadata={},
        )
        .to_json()
        .is_ok(),
    }
    return {
        "status": "SUCCESS" if all(checks.values()) else "ERROR",
        "version": __version__,
        "ready": all(checks.values()),
        "checks": checks,
        "network": False,
    }


def main():
    """MAPLE CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="maple",
        description="MAPLE - Multi Agent Protocol Language Engine",
    )
    parser.add_argument("--version", action="store_true", help="Show MAPLE version")
    parser.add_argument(
        "command",
        nargs="?",
        choices=["validate", "info", "doctor"],
        help="Command to run",
    )
    parser.add_argument(
        "--json", action="store_true", help="Print machine-readable output"
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

    if args.command == "doctor":
        report = doctor_report()
        if args.json:
            print(json.dumps(report, sort_keys=True))
        else:
            print(f"MAPLE v{report['version']} doctor: {report['status']}")
            for name, passed in report["checks"].items():
                print(f"  {name}: {'PASS' if passed else 'FAIL'}")
        return 0 if report["ready"] else 1

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
