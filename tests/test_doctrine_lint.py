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
"""Tests for tools/doctrine_lint.py — run: python -m unittest discover tests"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import doctrine_lint as dl  # noqa: E402


class TestCorpusClean(unittest.TestCase):
    def test_current_corpus_passes(self):
        self.assertEqual(dl.main([str(REPO)]), 0)


class TestBrokenRefCaught(unittest.TestCase):
    def test_broken_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".Doctrine").mkdir()
            (root / ".claude" / "agents").mkdir(parents=True)
            (root / ".Doctrine.md").write_text(
                "see `skills/does-not-exist.md`\n", encoding="utf-8")
            findings: list[str] = []
            dl.check_references(root, findings)
            self.assertEqual(len(findings), 1)
            self.assertIn("does-not-exist", findings[0])

    def test_allowlisted_external_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".Doctrine").mkdir()
            (root / ".claude" / "agents").mkdir(parents=True)
            (root / ".Doctrine.md").write_text(
                "upstream `skills/ponytail/SKILL.md`\n", encoding="utf-8")
            findings: list[str] = []
            dl.check_references(root, findings)
            self.assertEqual(findings, [])


class TestVersionSync(unittest.TestCase):
    def test_desync_caught(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".Doctrine.md").write_text(
                "# Doctrine v9.9.9\n", encoding="utf-8")
            (root / "CHANGELOG.md").write_text(
                "# Changelog\n\n## [0.1.0] - 2026-01-01\n",
                encoding="utf-8")
            findings: list[str] = []
            dl.check_version(root, findings)
            self.assertEqual(len(findings), 1)
            self.assertIn("desync", findings[0])


if __name__ == "__main__":
    unittest.main()
