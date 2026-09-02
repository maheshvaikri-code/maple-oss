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
    @staticmethod
    def _repo(tmp: str, *, source_repo: bool) -> Path:
        """A minimal repo root with a doctrine header and a CHANGELOG.

        ``source_repo`` marks it as the doctrine's OWN repo the same way
        check_plugin_parity detects it: the plugin ships from there only.
        """
        root = Path(tmp)
        (root / ".Doctrine.md").write_text(
            "# Doctrine v9.9.9\n", encoding="utf-8")
        (root / "CHANGELOG.md").write_text(
            "# Changelog\n\n## [0.1.0] - 2026-01-01\n", encoding="utf-8")
        if source_repo:
            (root / "plugin").mkdir()
        return root

    def test_desync_caught_in_the_doctrine_source_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._repo(tmp, source_repo=True)
            findings: list[str] = []
            dl.check_version(root, findings)
            self.assertEqual(len(findings), 1)
            self.assertIn("desync", findings[0])

    def test_consumer_repo_product_carriers_are_not_compared(self):
        """A consumer's CHANGELOG describes the consumer, not the doctrine.

        Regression guard: this check was dormant in consumer repos only
        because their CHANGELOG headings happened not to match Keep a
        Changelog's ``## [x.y.z]``. Normalizing the headings woke it, and it
        reported MAPLE 2.0.0 as desynced from Engineering Doctrine v0.6.12 --
        two unrelated artifacts that will never share a version.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = self._repo(tmp, source_repo=False)
            findings: list[str] = []
            dl.check_version(root, findings)
            self.assertEqual(findings, [])

    def test_doctrine_owned_carrier_compared_even_in_a_consumer_repo(self):
        """doctrine_mcp.py ships WITH the doctrine, so it tracks it anywhere."""
        with tempfile.TemporaryDirectory() as tmp:
            root = self._repo(tmp, source_repo=False)
            (root / "tools").mkdir()
            (root / "tools" / "doctrine_mcp.py").write_text(
                '"version": "1.2.3"\n', encoding="utf-8")
            findings: list[str] = []
            dl.check_version(root, findings)
            self.assertEqual(len(findings), 1)
            self.assertIn("doctrine_mcp.py", findings[0])


if __name__ == "__main__":
    unittest.main()
