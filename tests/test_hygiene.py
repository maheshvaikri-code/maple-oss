"""Tests for MAPLE hygiene fixes (improvement #5; revalidate with owner).

- #5a: no deprecated datetime.utcnow() -- Message timestamps stay naive-UTC (serialization
  unchanged) but no longer emit a DeprecationWarning on Python 3.12+.
- #5b: library modules no longer call logging.basicConfig (which hijacks the host's root
  logger and emits INFO noise) -- importing them does not force the root logger to INFO.
- #5c: verified separately -- every thread in maple/ already sets daemon=True (no change).
"""

import subprocess
import sys
import warnings
from datetime import datetime
from pathlib import Path

from maple.core.message import Message

# Repo root (…/maple-oss), computed portably so the subprocess below runs from a
# real directory on any OS/CI — not a hardcoded developer path.
_REPO_ROOT = Path(__file__).resolve().parent.parent


class TestTimestampNoDeprecation:
    def test_creating_a_message_emits_no_utcnow_deprecation(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)  # any DeprecationWarning -> raise
            m = Message(message_type="TEST")
        assert isinstance(m.timestamp, datetime)
        assert m.timestamp.tzinfo is None  # preserved naive-UTC (serialization unchanged)

    def test_timestamp_serializes_without_a_double_timezone(self):
        m = Message(message_type="TEST")
        iso = m.timestamp.isoformat() + "Z"
        assert iso.endswith("Z") and "+00:00" not in iso  # naive -> no offset, a single Z


class TestNoRootLoggerHijack:
    def test_fresh_import_does_not_force_the_root_logger_to_info(self):
        # In a fresh process, importing MAPLE library modules must not call basicConfig
        # (which would set root level to INFO and attach a handler). We assert the root
        # level is NOT forced to INFO and MAPLE added no root handler.
        code = (
            "import logging, maple.core.message, maple.error.recovery, "
            "maple.error.circuit_breaker, maple.resources.manager;"
            "r=logging.getLogger();"
            "print('LEVEL', r.level, 'HANDLERS', len(r.handlers))"
        )
        out = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
        )
        assert out.returncode == 0, out.stderr
        line = out.stdout.strip().splitlines()[-1]
        _, level, _, handlers = line.split()
        assert int(level) != 20  # 20 == logging.INFO -> would mean basicConfig forced it
        assert int(handlers) == 0  # MAPLE attached no root handler
