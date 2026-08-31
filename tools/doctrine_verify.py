# Copyright (C) 2025 Mahesh Vaijainthymala Krishnamoorthy
# (Mahesh Vaikri)
#
# This file is part of MAPLE - Multi Agent Protocol Language Engine.
#
# MAPLE - Multi Agent Protocol Language Engine is free software: you can
# redistribute it and/or modify it under the terms of the GNU Affero General
# Public License as published by the Free Software Foundation, either version 3
# of the License, or (at your option) any later version.
# MAPLE - Multi Agent Protocol Language Engine is distributed in the hope that
# it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty
# of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero
# General Public License for more details. You should have received a copy of
# the GNU Affero General Public License along with MAPLE - Multi Agent Protocol
# Language Engine. If not, see <https://www.gnu.org/licenses/>.
#!/usr/bin/env python3
"""doctrine_verify — the one-command gate suite, cross-platform.

`make verify` requires GNU Make, which stock Windows lacks; this runner
is the same sequence with no dependency beyond Python:

    python tools/doctrine_verify.py

Runs, in order: corpus lint -> ruff (skipped with a note when not
installed - it is a dev dependency, not a runtime one) -> the unittest
suite -> state-plane chain verify (skipped when no state plane exists
yet). Exit 0 only when every executed gate passes; each gate's REAL
output streams through untouched.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run_gate(name: str, cmd: list[str], cwd: Path) -> bool:
    print(f"=== {name}: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd)
    print(f"=== {name}: {'PASS' if result.returncode == 0 else 'FAIL'}\n")
    return result.returncode == 0


def main(argv: list[str] | None = None) -> int:
    root = Path(argv[0]).resolve() if argv else Path.cwd()
    py = sys.executable
    results: list[tuple[str, bool]] = []

    results.append(("lint", run_gate(
        "lint", [py, "tools/doctrine_lint.py"], root)))

    try:
        import ruff  # noqa: F401
        has_ruff = True
    except ImportError:
        has_ruff = subprocess.run(
            [py, "-m", "ruff", "--version"], cwd=root,
            capture_output=True).returncode == 0
    if has_ruff:
        results.append(("ruff", run_gate(
            "ruff", [py, "-m", "ruff", "check", "tools", "tests"], root)))
    else:
        print("=== ruff: not installed - skipped "
              "(pip install ruff to enable)\n")

    results.append(("tests", run_gate(
        "tests", [py, "-m", "unittest", "discover", "-s", "tests"], root)))

    if (root / ".doctrine-state" / "checkpoint.json").exists():
        results.append(("state", run_gate(
            "state", [py, "tools/doctrine_state.py", "verify"], root)))
    else:
        print("=== state: no state plane yet - skipped "
              "(python tools/doctrine_state.py init)\n")

    failed = [name for name, ok in results if not ok]
    if failed:
        print(f"VERIFY FAILED: {', '.join(failed)}")
        return 1
    print(f"VERIFY OK: {len(results)} gate(s) green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
