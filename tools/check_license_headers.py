#!/usr/bin/env python3
"""Verify every shipped Python module carries the project's license attribution.

Extracted from an inline ``python -c`` block in the old `quality.yml` workflow
(ADR-158) so it can be linted, typechecked, and run locally the same way CI
runs it:

    python tools/check_license_headers.py

Exits non-zero and names the offending files when any are missing.
"""

from __future__ import annotations

import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent / "maple"
REQUIRED_ATTRIBUTION = "Mahesh Vaijainthymala Krishnamoorthy"


def main() -> int:
    if not PACKAGE_ROOT.is_dir():
        print(f"error: package directory not found: {PACKAGE_ROOT}", file=sys.stderr)
        return 2

    checked = 0
    missing: list[Path] = []
    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        checked += 1
        if REQUIRED_ATTRIBUTION not in path.read_text(encoding="utf-8"):
            missing.append(path)

    if not checked:
        print("error: no Python files found to check", file=sys.stderr)
        return 2

    if missing:
        print(f"Files missing the license header ({len(missing)}):")
        for path in missing:
            print(f"  {path.relative_to(PACKAGE_ROOT.parent)}")
        return 1

    print(f"All {checked} files have proper license headers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
