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
"""Two clocks, chosen by purpose (ADR-163).

Durations are measured on a clock that cannot step; records keep the wall
clock. Both halves need guarding: a new wall-clock duration reintroduces the
NTP bug, and a blanket replacement would break JWT interop and turn audit
timestamps into seconds since boot.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "maple"

#: Modules whose timing decisions must not ride on the wall clock.
DURATION_MODULES = [
    "broker/queue.py",
    "broker/routing.py",
    "broker/broker.py",
    "agent/agent.py",
    "error/circuit_breaker.py",
    "security/link.py",
    "task_management/fault_tolerance.py",
    "broker/file_broker.py",
]

#: Wall-clock arithmetic that is correct, with the reason it is correct.
#: Anything not listed here fails, so the omission surfaces in CI rather than
#: as a clock-skew bug six months later.
ALLOWED_WALL_CLOCK_ARITHMETIC = {
    (
        "broker/queue.py",
        "else time.time() - queued_msg.timestamp",
    ): "Fallback for a QueuedMessage built without a monotonic reading.",
}

#: Known blind spot: the pattern above only sees `time.time()` adjacent to a
#: subtraction. A hoisted reading - `now = time.time()` used later as
#: `now - other` - is not flagged. `file_broker.py` does exactly that, and
#: correctly: it compares against file mtimes, which are wall clock and must
#: mean the same thing in another process (ADR-167). Tightening the pattern
#: would flag that legitimate case and every other hoisted timestamp, so the
#: gap is recorded rather than papered over.

_DURATION = re.compile(r"time\.time\(\)\s*-|-\s*time\.time\(\)")


def _code_lines(path: Path):
    """Source lines with comments and docstring prose filtered out."""
    for number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("#:"):
            continue
        yield number, line


class TestDurationsDoNotUseTheWallClock:
    @pytest.mark.parametrize("relative", DURATION_MODULES)
    def test_no_undeclared_wall_clock_duration(self, relative):
        path = ROOT / relative
        assert path.exists(), f"{relative} moved; update DURATION_MODULES"

        offenders = []
        for number, line in _code_lines(path):
            if not _DURATION.search(line):
                continue
            key = (relative, line.strip())
            if key in ALLOWED_WALL_CLOCK_ARITHMETIC:
                continue
            offenders.append(f"{relative}:{number}: {line.strip()}")

        assert not offenders, (
            "Wall-clock duration arithmetic. time.time() steps under NTP: "
            "measured, a +1h step skipped a 30s circuit-breaker window and a "
            "-1h step held it open for 3599.8s. Use time.perf_counter() for "
            "durations, or add the line to ALLOWED_WALL_CLOCK_ARITHMETIC with "
            "the reason it is correct.\n  " + "\n  ".join(offenders)
        )

    def test_the_allowlist_entries_still_exist(self):
        """An allowlist that outlives its code silently permits new sins."""
        for (relative, snippet), reason in ALLOWED_WALL_CLOCK_ARITHMETIC.items():
            source = (ROOT / relative).read_text(encoding="utf-8")
            assert snippet in source, (
                f"Allowlisted line is gone from {relative}; remove the entry. "
                f"({reason})"
            )

    @pytest.mark.parametrize("relative", DURATION_MODULES)
    def test_duration_modules_measure_with_perf_counter(self, relative):
        """perf_counter, not monotonic: both are unadjustable, but monotonic
        resolves to 15.6ms on Windows against perf_counter's 100ns."""
        source = (ROOT / relative).read_text(encoding="utf-8")
        if "time.monotonic()" in source:
            pytest.fail(
                f"{relative} uses time.monotonic(). On Windows its resolution "
                "is 15.6ms, which loses sub-frame intervals; use "
                "time.perf_counter()."
            )


class TestRecordsKeepTheWallClock:
    """The other half of the rule. A blanket replacement is the failure mode
    on this side, and it is a quiet one."""

    def test_jwt_claims_are_epoch_seconds(self):
        """RFC 7519 NumericDate is seconds since epoch, verified by other
        parties. A monotonic reading here produces tokens nothing accepts."""
        source = (ROOT / "security/authentication.py").read_text(encoding="utf-8")
        assert "time.time()" in source
        assert "perf_counter" not in source, (
            "authentication.py must not measure token lifetimes on a "
            "process-local clock"
        )

    def test_audit_timestamps_are_wall_clock(self):
        source = (ROOT / "security/audit.py").read_text(encoding="utf-8")
        assert "timestamp=time.time()" in source

    def test_audit_cutoffs_match_the_records_they_filter(self):
        """The one-hour cutoff is compared against wall-clock record
        timestamps, so it must be wall clock too. Mixing the two would filter
        against an unrelated origin."""
        source = (ROOT / "security/audit.py").read_text(encoding="utf-8")
        assert "one_hour_ago = time.time() - 3600" in source

    def test_the_circuit_breaker_record_is_still_an_epoch(self):
        """last_failure_time is a public property on two wrapper classes and
        appears in a get_statistics() dict that reaches the metrics exporter."""
        source = (ROOT / "error/circuit_breaker.py").read_text(encoding="utf-8")
        assert "self.last_failure_time = time.time()" in source

    def test_link_established_at_is_still_an_epoch(self):
        source = (ROOT / "security/link.py").read_text(encoding="utf-8")
        assert "self.established_at = time.time()" in source
