#!/usr/bin/env python3
"""Verify the README still documents the sections a reader needs to start.

Extracted from an inline ``python -c`` block in the old `quality.yml` workflow
(ADR-158) so it can be linted, typechecked, and run locally the same way CI
runs it:

    python tools/check_readme_sections.py

This is a shallow guard against the public entry point losing its orientation
material during a refactor. It checks presence, not quality.
"""

from __future__ import annotations

import sys
from pathlib import Path

README = Path(__file__).resolve().parent.parent / "README.md"
REQUIRED_SECTIONS = (
    "MAPLE",
    "Installation",
    "Quick Start",
    "Mahesh Vaikri",
    "AutonomousAgent",
)


def main() -> int:
    if not README.is_file():
        print(f"error: README not found: {README}", file=sys.stderr)
        return 2

    content = README.read_text(encoding="utf-8")
    missing = [section for section in REQUIRED_SECTIONS if section not in content]

    if missing:
        print(f"README is missing required sections: {missing}")
        return 1

    print(f"README has all {len(REQUIRED_SECTIONS)} required sections")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
