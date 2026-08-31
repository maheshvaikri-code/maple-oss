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
"""Tests for tools/doctrine_gold.py — run: python -m unittest discover tests"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import doctrine_gold as dg  # noqa: E402
import doctrine_state as ds  # noqa: E402


class GoldRepo(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.email", "t@t"],
                       cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "t"],
                       cwd=self.root, check=True)
        # schema in place
        dest = self.root / ".Doctrine" / "schemas"
        dest.mkdir(parents=True)
        shutil.copy(REPO / ".Doctrine" / "schemas" /
                    "gold-build.schema.json", dest)
        # verdict, sign-offs, artifact
        for rel in ("docs/merges/task.md", "docs/reviews/task.md",
                    "docs/qa/task-security.md", "docs/qa/task.md",
                    "docs/reviews/task-scope.md"):
            p = self.root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(f"# {rel}\nUNANIMOUS/SIGN-OFF\n", encoding="utf-8")
        (self.root / "dist").mkdir()
        (self.root / "dist" / "app.whl").write_bytes(b"artifact-bytes-v1")
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-qm", "seed"], cwd=self.root,
                       check=True)
        subprocess.run(["git", "tag", "-a", "v1.0.0", "-m", "v1"],
                       cwd=self.root, check=True)

    def tearDown(self):
        self._tmp.cleanup()

    def proposal(self, tag="v1.0.0", **overrides):
        base = {
            "tag": tag,
            "merge_verdict": "docs/merges/task.md",
            "signoffs": {
                "code_review": "docs/reviews/task.md",
                "security": "docs/qa/task-security.md",
                "qa": "docs/qa/task.md",
                "project_review": "docs/reviews/task-scope.md",
            },
            "artifacts": [{"path": "dist/app.whl", "sha256": "0" * 64}],
            "soak": {"environment": "staging", "result": "pass",
                     "evidence": "make smoke on staging - exit 0"},
            "human_approval": {"approved_by": "Mahesh Vaikri",
                               "date": "2026-07-12",
                               "statement": "go for v1.0.0"},
        }
        base.update(overrides)
        return base

    def record(self, proposal=None):
        p = self.root / "gold-proposal.json"
        p.write_text(json.dumps(proposal or self.proposal()),
                     encoding="utf-8")
        return dg.cmd_record(self.root, p)


class TestRecordAndCheck(GoldRepo):
    def test_happy_path(self):
        self.assertEqual(self.record(), 0)
        out = self.root / "docs" / "releases" / "gold" / "v1.0.0.json"
        self.assertTrue(out.exists())
        record = json.loads(out.read_text("utf-8"))
        self.assertIsNone(record["prev_gold_sha256"])
        self.assertEqual(record["artifacts"][0]["sha256"],
                         ds.sha256_file(self.root / "dist" / "app.whl"))
        self.assertEqual(dg.cmd_check(self.root, "v1.0.0"), 0)

    def test_artifact_tamper_fails_check(self):
        self.record()
        (self.root / "dist" / "app.whl").write_bytes(b"tampered")
        self.assertEqual(dg.cmd_check(self.root, "v1.0.0"), 1)

    def test_record_tamper_fails_check(self):
        self.record()
        out = self.root / "docs" / "releases" / "gold" / "v1.0.0.json"
        record = json.loads(out.read_text("utf-8"))
        record["soak"]["environment"] = "forged"
        out.write_bytes(ds.canonical_bytes(record))
        # canonical rewrite passes schema; chain check on the NEXT record
        # catches it — verify via a second record whose prev hash was
        # computed pre-tamper.
        subprocess.run(["git", "tag", "-a", "v1.0.1", "-m", "v"],
                       cwd=self.root, check=True)
        pre_tamper_ok = self.record(self.proposal(tag="v1.0.1"))
        self.assertEqual(pre_tamper_ok, 0)
        record["soak"]["environment"] = "forged-again"
        out.write_bytes(ds.canonical_bytes(record))
        self.assertEqual(dg.cmd_check(self.root, "v1.0.1"), 1)

    def test_chain_links_records(self):
        self.record()
        first = self.root / "docs" / "releases" / "gold" / "v1.0.0.json"
        subprocess.run(["git", "tag", "-a", "v1.1.0", "-m", "v"],
                       cwd=self.root, check=True)
        self.assertEqual(self.record(self.proposal(tag="v1.1.0")), 0)
        second = json.loads(
            (self.root / "docs" / "releases" / "gold" / "v1.1.0.json")
            .read_text("utf-8"))
        self.assertEqual(second["prev_gold_sha256"], ds.sha256_file(first))
        self.assertEqual(dg.cmd_check(self.root, "v1.1.0"), 0)

    def test_missing_signoff_refused(self):
        (self.root / "docs" / "qa" / "task-security.md").unlink()
        with self.assertRaises(dg.StateError):
            self.record()
        self.assertFalse((self.root / "docs" / "releases").exists(),
                         "nothing written on refusal")

    def test_missing_verdict_refused(self):
        (self.root / "docs" / "merges" / "task.md").unlink()
        with self.assertRaises(dg.StateError):
            self.record()

    def test_empty_human_approval_refused(self):
        prop = self.proposal()
        prop["human_approval"]["statement"] = ""
        with self.assertRaises(dg.SchemaError):
            self.record(prop)

    def test_path_escape_refused(self):
        prop = self.proposal()
        prop["signoffs"]["security"] = "../outside.md"
        with self.assertRaises(dg.StateError):
            self.record(prop)

    def test_immutable_records(self):
        self.record()
        with self.assertRaises(dg.StateError):
            self.record()

    def test_unknown_tag_refused(self):
        prop = self.proposal(tag="v9.9.9")
        with self.assertRaises(
                (dg.StateError, subprocess.CalledProcessError)):
            self.record(prop)

    def test_moved_tag_fails_check(self):
        self.record()
        (self.root / "new.txt").write_text("x\n")
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-qm", "advance"], cwd=self.root,
                       check=True)
        subprocess.run(["git", "tag", "-fa", "v1.0.0", "-m", "moved"],
                       cwd=self.root, check=True)
        self.assertEqual(dg.cmd_check(self.root, "v1.0.0"), 1)

    def test_check_without_record_fails(self):
        self.assertEqual(dg.cmd_check(self.root, "v1.0.0"), 1)

    def test_chain_order_survives_clone(self):
        """Regression: G-1/GD-1 — order comes from prev-hash links, never
        mtimes (clones reset them; attackers forge them)."""
        import os
        self.record()
        for i, tag in enumerate(["v1.1.0", "v1.2.0"]):
            subprocess.run(["git", "tag", "-a", tag, "-m", "v"],
                           cwd=self.root, check=True)
            self.assertEqual(self.record(self.proposal(tag=tag)), 0)
        gold = self.root / "docs" / "releases" / "gold"
        # simulate clone: equalize, then REVERSE mtimes
        for i, p in enumerate(sorted(gold.glob("*.json"), reverse=True)):
            os.utime(p, (1000000 + i, 1000000 + i))
        chain = dg.load_chain(self.root)
        self.assertEqual([p.name for p in chain],
                         ["v1.0.0.json", "v1.1.0.json", "v1.2.0.json"])
        subprocess.run(["git", "tag", "-a", "v1.3.0", "-m", "v"],
                       cwd=self.root, check=True)
        self.assertEqual(self.record(self.proposal(tag="v1.3.0")), 0)
        fourth = json.loads((gold / "v1.3.0.json").read_text("utf-8"))
        self.assertEqual(fourth["prev_gold_sha256"],
                         ds.sha256_file(gold / "v1.2.0.json"),
                         "must chain to the true head, not the mtime head")
        self.assertEqual(dg.cmd_check(self.root, "v1.3.0"), 0)

    def test_forged_second_genesis_detected(self):
        """Regression: G-1 — a forged genesis breaks topology loudly."""
        self.record()
        gold = self.root / "docs" / "releases" / "gold"
        forged = json.loads((gold / "v1.0.0.json").read_text("utf-8"))
        forged["tag"] = "v9.9.9"
        (gold / "v9.9.9.json").write_bytes(ds.canonical_bytes(forged))
        self.assertEqual(dg.cmd_check(self.root, "v1.0.0"), 1)

    def test_chain_fork_detected(self):
        """Regression: G-1 — two records claiming one predecessor."""
        self.record()
        subprocess.run(["git", "tag", "-a", "v1.1.0", "-m", "v"],
                       cwd=self.root, check=True)
        self.record(self.proposal(tag="v1.1.0"))
        gold = self.root / "docs" / "releases" / "gold"
        fork = json.loads((gold / "v1.1.0.json").read_text("utf-8"))
        fork["tag"] = "v1.1.1"
        (gold / "v1.1.1.json").write_bytes(ds.canonical_bytes(fork))
        self.assertEqual(dg.cmd_check(self.root, "v1.1.0"), 1)

    def test_empty_signoff_refused(self):
        """Regression: G-2 — existence is not evidence."""
        (self.root / "docs" / "qa" / "task-security.md").write_bytes(b"")
        with self.assertRaises(dg.StateError):
            self.record()
        self.assertFalse((self.root / "docs" / "releases").exists())

    def test_signoff_edited_after_promotion_fails_check(self):
        """Regression: G-2 — sign-offs are content-pinned."""
        self.record()
        p = self.root / "docs" / "qa" / "task-security.md"
        p.write_text(p.read_text("utf-8") + "\nretracted!\n",
                     encoding="utf-8")
        self.assertEqual(dg.cmd_check(self.root, "v1.0.0"), 1)

    def test_lightweight_tag_refused(self):
        """Regression: GD-3 — annotated tags only."""
        subprocess.run(["git", "tag", "v2.0.0"], cwd=self.root, check=True)
        with self.assertRaises(dg.StateError):
            self.record(self.proposal(tag="v2.0.0"))

    def test_bad_tag_rejected_before_git_or_paths(self):
        """Regression: GD-4 — tag validated before argv/path use."""
        for bad in ("--all", "../secret", "v1.0.0; rm -rf", "HEAD"):
            with self.assertRaises(dg.StateError, msg=bad):
                dg.cmd_check(self.root, bad)
            with self.assertRaises(dg.StateError, msg=bad):
                self.record(self.proposal(tag=bad))

    def test_duplicate_artifact_paths_refused(self):
        """Regression: GD-6."""
        prop = self.proposal()
        prop["artifacts"] = [{"path": "dist/app.whl", "sha256": "0" * 64},
                             "dist/app.whl"]
        with self.assertRaises(dg.StateError):
            self.record(prop)

    def test_shape_tampered_record_fails_cleanly(self):
        """Regression: GD-2 — schema failure exits 1, no traceback."""
        self.record()
        out = self.root / "docs" / "releases" / "gold" / "v1.0.0.json"
        record = json.loads(out.read_text("utf-8"))
        record["artifacts"] = "not-a-list"
        out.write_bytes(ds.canonical_bytes(record))
        self.assertEqual(dg.cmd_check(self.root, "v1.0.0"), 1)


if __name__ == "__main__":
    unittest.main()
