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
"""Tests for tools/doctrine_state.py — run: python -m unittest discover tests

Includes regression tests for every G4/G5 verifier finding (see
docs/reviews/state-tooling.md and docs/qa/state-tooling*.md).
"""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import doctrine_state as ds  # noqa: E402

SCHEMAS = REPO / ".Doctrine" / "state-plane" / "schemas"
EXAMPLES = REPO / ".Doctrine" / "state-plane" / "examples"


def proposal(dead_ends=None, learned=None, active_intents=None):
    return {
        "session_id": "s-test-1",
        "control": {"role": "backend-engineer", "phase": "g3",
                    "ponytail_mode": "off",
                    "active_intents": active_intents or [],
                    "gates_passed": []},
        "distillate": {
            "task_refs": ["t-1"],
            "learned": learned if learned is not None else [
                {"claim": "canonical writer is stable", "kind": "fact",
                 "evidence": "tests/test_doctrine_state.py:1",
                 "confidence": "verified"}],
            "dead_ends": dead_ends or [], "open_threads": [],
            "next_actions": []},
    }


class TempRepo(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.email", "t@t"],
                       cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "t"],
                       cwd=self.root, check=True)
        (self.root / "seed.txt").write_text("seed\n")
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-qm", "seed"], cwd=self.root,
                       check=True)
        dest = self.root / ".Doctrine" / "state-plane" / "schemas"
        dest.mkdir(parents=True)
        for f in SCHEMAS.glob("*.json"):
            shutil.copy(f, dest / f.name)
        self.plane = ds.Plane(self.root)
        ds.cmd_init(self.plane)

    def tearDown(self):
        self._tmp.cleanup()

    def checkpoint(self, prop=None, keep=5, steal=False):
        p = self.root / "proposal.json"
        p.write_text(json.dumps(prop or proposal()), encoding="utf-8")
        return ds.cmd_checkpoint(self.plane, p, keep=keep, steal=steal)


class TestCanonical(unittest.TestCase):
    def test_sorted_lf_single_newline_no_trailing_ws(self):
        raw = ds.canonical_bytes({"b": 1, "a": {"z": [1, 2], "y": None}})
        text = raw.decode("utf-8")
        self.assertTrue(text.endswith("\n"))
        self.assertFalse(text.endswith("\n\n"))
        self.assertNotIn("\r", text)
        self.assertLess(text.index('"a"'), text.index('"b"'))
        for line in text.splitlines():
            self.assertEqual(line, line.rstrip(), "trailing whitespace")

    def test_stable(self):
        obj = json.loads((EXAMPLES / "checkpoint.example.json")
                         .read_text("utf-8"))
        self.assertEqual(ds.canonical_bytes(obj), ds.canonical_bytes(obj))


class TestValidator(unittest.TestCase):
    def setUp(self):
        self.cp_schema = json.loads(
            (SCHEMAS / "checkpoint.schema.json").read_text("utf-8"))
        self.di_schema = json.loads(
            (SCHEMAS / "distillate.schema.json").read_text("utf-8"))
        self.cp = json.loads(
            (EXAMPLES / "checkpoint.example.json").read_text("utf-8"))
        self.di = json.loads(
            (EXAMPLES / "distillate.example.json").read_text("utf-8"))

    def test_examples_validate(self):
        ds.validate(self.cp, self.cp_schema)
        ds.validate(self.di, self.di_schema)

    def test_missing_required(self):
        bad = dict(self.cp)
        del bad["seq"]
        with self.assertRaises(ds.SchemaError):
            ds.validate(bad, self.cp_schema)

    def test_unknown_field_rejected(self):
        bad = dict(self.cp, extra_field=1)
        with self.assertRaises(ds.SchemaError):
            ds.validate(bad, self.cp_schema)

    def test_max_items(self):
        bad = dict(self.di)
        bad["dead_ends"] = [{"approach": "a", "why_failed": "b"}] * 9
        with self.assertRaises(ds.SchemaError):
            ds.validate(bad, self.di_schema)

    def test_bad_pattern(self):
        bad = dict(self.cp, at_commit="NOTHEX")
        with self.assertRaises(ds.SchemaError):
            ds.validate(bad, self.cp_schema)

    def test_enum(self):
        bad = json.loads(json.dumps(self.cp))
        bad["worktree"] = "messy"
        with self.assertRaises(ds.SchemaError):
            ds.validate(bad, self.cp_schema)

    def test_property_names_traversal_rejected(self):
        """Regression: security P-1 — schema-level intent-id constraint."""
        bad = json.loads(json.dumps(self.cp))
        bad["state_index"]["intents"] = {"../evil": "a" * 64}
        with self.assertRaises(ds.SchemaError):
            ds.validate(bad, self.cp_schema)
        bad2 = json.loads(json.dumps(self.cp))
        bad2["control"]["active_intents"] = ["../evil"]
        with self.assertRaises(ds.SchemaError):
            ds.validate(bad2, self.cp_schema)


class TestCheckpointVerify(TempRepo):
    def test_chain_and_verify(self):
        self.assertEqual(self.checkpoint(), 0)
        self.assertEqual(ds.cmd_verify(self.plane), 0)
        self.assertEqual(self.checkpoint(), 0)
        self.assertEqual(ds.cmd_verify(self.plane), 0)
        cp = json.loads(self.plane.checkpoint.read_text("utf-8"))
        self.assertEqual(cp["seq"], 1)
        self.assertIsNotNone(cp["prev_sha256"])

    def test_tamper_detected(self):
        self.checkpoint()
        self.checkpoint()
        victim = sorted(self.plane.checkpoints.glob("0-*.json"))[0]
        data = json.loads(victim.read_text("utf-8"))
        data["session_id"] = "forged"
        victim.write_bytes(ds.canonical_bytes(data))
        self.assertEqual(ds.cmd_verify(self.plane), 1)

    def test_decisions_written_and_indexed(self):
        prop = proposal(learned=[
            {"claim": "exit codes mirror gate semantics",
             "kind": "decision_ref", "evidence": "decisions:D-1",
             "confidence": "verified"}])
        self.checkpoint(prop)
        self.assertTrue(self.plane.decisions.exists())
        self.assertEqual(ds.cmd_verify(self.plane), 0)

    def test_rejected_proposal_leaves_no_trace(self):
        """Regression: QA #1 / review BLOCKER — a rejected proposal must
        not mutate the decisions log (or anything else)."""
        good = proposal(learned=[
            {"claim": "first decision", "kind": "decision_ref",
             "evidence": "decisions:D-1", "confidence": "verified"}])
        self.checkpoint(good)
        before = self.plane.decisions.read_bytes()
        bad = proposal(learned=[
            {"claim": "phantom decision", "kind": "decision_ref",
             "evidence": "decisions:D-2", "confidence": "verified"}])
        bad["control"]["ponytail_mode"] = "invalid-mode"
        p = self.root / "bad.json"
        p.write_text(json.dumps(bad), encoding="utf-8")
        with self.assertRaises(ds.SchemaError):
            ds.cmd_checkpoint(self.plane, p)
        self.assertEqual(self.plane.decisions.read_bytes(), before,
                         "rejected proposal polluted the decisions log")
        self.assertEqual(ds.cmd_verify(self.plane), 0)

    def test_traversal_intent_rejected_at_checkpoint(self):
        """Regression: security P-1 — runtime defense."""
        prop = proposal(active_intents=["../TOPSECRET"])
        p = self.root / "evil.json"
        p.write_text(json.dumps(prop), encoding="utf-8")
        with self.assertRaises((ds.StateError, ds.SchemaError)):
            ds.cmd_checkpoint(self.plane, p)
        self.assertFalse(self.plane.checkpoint.exists())

    def test_history_wipe_detected(self):
        """Regression: review MAJOR #2."""
        self.checkpoint()
        for f in self.plane.checkpoints.glob("*.json"):
            f.unlink()
        self.assertEqual(ds.cmd_verify(self.plane), 1)

    def test_stray_file_reported_not_crash(self):
        """Regression: security F-1 / review MINOR."""
        self.checkpoint()
        (self.plane.checkpoints / "evil.json").write_text("{}")
        self.assertEqual(ds.cmd_verify(self.plane), 1)

    def test_graph_tamper_detected(self):
        """Regression: review MAJOR #3 — graph is re-hashed."""
        gdir = self.root / "graphify-out"
        gdir.mkdir()
        (gdir / "graph.json").write_text(
            json.dumps({"built_at_commit": "f3a9c21", "nodes": []}),
            encoding="utf-8")
        self.checkpoint()
        self.assertEqual(ds.cmd_verify(self.plane), 0)
        (gdir / "graph.json").write_text(
            json.dumps({"built_at_commit": "f3a9c21", "nodes": ["x"]}),
            encoding="utf-8")
        self.assertEqual(ds.cmd_verify(self.plane), 1)

    def test_graph_freshness_not_fabricated(self):
        """Regression: review MAJOR #8 — no built_at_commit means null."""
        gdir = self.root / "graphify-out"
        gdir.mkdir()
        (gdir / "graph.json").write_text(json.dumps({"nodes": []}),
                                         encoding="utf-8")
        self.checkpoint()
        cp = json.loads(self.plane.checkpoint.read_text("utf-8"))
        self.assertIsNone(cp["state_index"]["graph"]["built_at_commit"])

    def test_secretlike_claim_rejected(self):
        """Regression: security S-1 — fail closed on secret-like state."""
        prop = proposal(learned=[
            {"claim": "set api_key = sk_live_abcdef123456 in prod",
             "kind": "fact", "evidence": "config:1",
             "confidence": "verified"}])
        p = self.root / "leak.json"
        p.write_text(json.dumps(prop), encoding="utf-8")
        with self.assertRaises(ds.StateError):
            ds.cmd_checkpoint(self.plane, p)
        self.assertFalse(self.plane.checkpoint.exists())

    def test_deep_json_bounded(self):
        """Regression: security R-1 — RecursionError becomes StateError."""
        p = self.root / "deep.json"
        p.write_text("[" * 100_000 + "]" * 100_000, encoding="utf-8")
        with self.assertRaises(ds.StateError):
            ds.cmd_checkpoint(self.plane, p)

    def test_keep_below_one_rejected(self):
        with self.assertRaises(ds.StateError):
            self.checkpoint(keep=0)
        with self.assertRaises(ds.StateError):
            ds.cmd_prune(self.plane, keep=0)

    def test_invalid_proposal_rejected_nothing_written(self):
        prop = proposal()
        prop["distillate"]["learned"][0]["confidence"] = "hopeful"
        p = self.root / "bad.json"
        p.write_text(json.dumps(prop), encoding="utf-8")
        with self.assertRaises(ds.SchemaError):
            ds.cmd_checkpoint(self.plane, p)
        self.assertFalse(self.plane.checkpoint.exists())
        self.assertFalse(self.plane.decisions.exists())

    def test_state_root_avoids_doctrine_collision(self):
        """Regression: QA #3 — state root must not be .doctrine/ (which
        merges with .Doctrine/ on case-insensitive filesystems)."""
        self.assertEqual(self.plane.state.name, ".doctrine-state")
        self.assertFalse(
            (self.root / ".Doctrine" / "state").exists(),
            "state must not land inside the doctrine corpus dir")


class TestPrune(TempRepo):
    def test_dead_ends_merge_forward(self):
        for i in range(3):
            self.checkpoint(proposal(dead_ends=[
                {"approach": f"approach-{i}", "why_failed": f"reason-{i}"}]),
                keep=2)
        dists = ds._distillate_files(self.plane)
        self.assertLessEqual(len(dists), 2)
        latest = json.loads(dists[-1].read_text("utf-8"))
        approaches = {e["approach"] for e in latest["dead_ends"]}
        self.assertIn("approach-0", approaches,
                      "pruned negatives must outlive the prune")
        self.assertIn("approach-2", approaches)

    def test_no_negative_lost_across_retained_set(self):
        """Regression: review MINOR — negatives survive pruning. The union
        of dead_ends across ALL retained distillates loses nothing, and the
        hydration bundle merges across the retained set (HYDRATION.md
        'dead_ends merged from last K')."""
        for i in range(12):
            self.checkpoint(proposal(dead_ends=[
                {"approach": f"a-{i:02d}", "why_failed": "r"}]), keep=2)
        union = set()
        for f in ds._distillate_files(self.plane):
            d = json.loads(f.read_text("utf-8"))
            union |= {e["approach"] for e in d["dead_ends"]}
        self.assertEqual(union, {f"a-{i:02d}" for i in range(12)},
                         "a pruned negative was lost")
        body, _, _ = ds.build_bundle_body(self.plane)
        self.assertIn("a-10", body)
        self.assertIn("a-11", body)

    def test_keep_one(self):
        self.checkpoint(keep=1)
        self.checkpoint(keep=1)
        self.assertEqual(len(ds._distillate_files(self.plane)), 1)

    def test_manual_prune_stages_pending(self):
        for i in range(3):
            self.checkpoint(proposal(dead_ends=[
                {"approach": f"a-{i}", "why_failed": "r"}]))
        self.assertEqual(ds.cmd_prune(self.plane, keep=1), 0)
        pending = self.plane.distillates / "pending-dead-ends.json"
        self.assertTrue(pending.exists())
        self.checkpoint()
        self.assertFalse(pending.exists(), "pending consumed by checkpoint")
        latest = json.loads(
            ds._distillate_files(self.plane)[-1].read_text("utf-8"))
        self.assertIn("a-0", {e["approach"] for e in latest["dead_ends"]})

    def test_ascii_only_terminal_output(self):
        """Regression: QA #2 — cp1252-safe prints."""
        self.checkpoint()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ds.cmd_prune(self.plane, keep=5)
            ds.cmd_status(self.plane)
            ds.cmd_verify(self.plane)
        for ch in buf.getvalue():
            self.assertLess(ord(ch), 128,
                            f"non-ASCII {ch!r} in terminal output")


class TestConcurrency(TempRepo):
    def other_session(self, dead_ends=None):
        prop = proposal(dead_ends=dead_ends)
        prop["session_id"] = "s-test-2"
        return prop

    def test_lease_blocks_other_session(self):
        """Audit gap #1: two same-machine sessions must not fork."""
        self.checkpoint()
        prop = self.other_session()
        p = self.root / "p2.json"
        p.write_text(json.dumps(prop), encoding="utf-8")
        with self.assertRaises(ds.StateError) as ctx:
            ds.cmd_checkpoint(self.plane, p)
        self.assertIn("leased", str(ctx.exception))

    def test_lease_steal_and_same_session_ok(self):
        self.checkpoint()
        self.checkpoint()  # same session: lease is ours, proceeds
        prop = self.other_session()
        p = self.root / "p2.json"
        p.write_text(json.dumps(prop), encoding="utf-8")
        self.assertEqual(ds.cmd_checkpoint(self.plane, p, steal=True), 0)

    def test_expired_lease_allows(self):
        self.checkpoint()
        lease_path = self.plane.local / "lease.json"
        lease = json.loads(lease_path.read_text("utf-8"))
        lease["expires_at"] = 1.0
        lease_path.write_bytes(ds.canonical_bytes(lease))
        prop = self.other_session()
        p = self.root / "p2.json"
        p.write_text(json.dumps(prop), encoding="utf-8")
        self.assertEqual(ds.cmd_checkpoint(self.plane, p), 0)

    def make_fork(self):
        """Simulate two clones checkpointing from the same head, then
        reuniting via git: both seq-1 files land in checkpoints/."""
        self.checkpoint()  # seq 0, shared head
        head0 = self.plane.checkpoint.read_bytes()
        self.checkpoint(proposal(dead_ends=[
            {"approach": "clone-A-path", "why_failed": "a"}]))  # 1-aaa
        # clone B never saw 1-aaa: rewind the head pointer and write B's
        self.plane.checkpoint.write_bytes(head0)
        prop = self.other_session(dead_ends=[
            {"approach": "clone-B-path", "why_failed": "b"}])
        p = self.root / "pb.json"
        p.write_text(json.dumps(prop), encoding="utf-8")
        ds.cmd_checkpoint(self.plane, p, steal=True)  # 1-bbb
        ones = sorted(f.name for f in self.plane.checkpoints.glob("1-*"))
        self.assertEqual(len(ones), 2, "fork precondition")
        return ones

    def test_fork_detected_hydrate_refuses_merge_heals(self):
        """Audit gap #1 end-to-end: fork -> loud stop -> merge -> the
        loser's negatives survive into the next checkpoint."""
        ones = self.make_fork()
        self.assertEqual(ds.cmd_verify(self.plane), 1)
        self.assertEqual(ds.cmd_hydrate(self.plane), 1)
        # current head is clone B's; archive it as the loser
        current_sha = ds.sha256_bytes(self.plane.checkpoint.read_bytes())
        loser_name = next(
            n for n in ones
            if ds.sha256_file(self.plane.checkpoints / n) == current_sha)
        self.assertEqual(ds.cmd_merge(self.plane, loser_name), 0)
        self.assertEqual(ds.cmd_verify(self.plane), 0)
        self.assertTrue(
            (self.plane.checkpoints / "forks" / loser_name).exists(),
            "history archived, never deleted")
        pending = json.loads(
            (self.plane.distillates / "pending-dead-ends.json")
            .read_text("utf-8"))
        self.assertIn("clone-B-path",
                      {e["approach"] for e in pending["dead_ends"]})
        # post-merge, session A takes the lease back deliberately
        self.checkpoint(steal=True)  # salvage consumed
        latest = json.loads(
            ds._distillate_files(self.plane)[-1].read_text("utf-8"))
        self.assertIn("clone-B-path",
                      {e["approach"] for e in latest["dead_ends"]},
                      "the losing session's negatives must survive")

    def test_merge_refuses_malformed_loser(self):
        """Regression: SC-1 — merge is run on damaged chains; it must
        StateError, never raw-KeyError."""
        ones = self.make_fork()
        victim = self.plane.checkpoints / ones[0]
        victim.write_bytes(ds.canonical_bytes({"not": "a checkpoint"}))
        with self.assertRaises(ds.StateError):
            ds.cmd_merge(self.plane, ones[0])

    def test_deep_lease_warns_and_proceeds(self):
        """Regression: LE-1 — a crafted lease must not crash the
        (advisory) check path."""
        self.checkpoint()
        (self.plane.local / "lease.json").write_text(
            "[" * 3000 + "]" * 3000, encoding="utf-8")
        self.assertEqual(self.checkpoint(), 0)

    def test_poisoned_pending_fails_closed(self):
        """Regression: SV-1 context — a poisoned pending file blocks the
        consuming checkpoint loudly (and merge now filters at source)."""
        self.checkpoint()
        pending = self.plane.distillates / "pending-dead-ends.json"
        pending.write_bytes(ds.canonical_bytes({"dead_ends": [
            {"approach": "leak AKIAIOSFODNN7EXAMPLE key",
             "why_failed": "x"}]}))
        with self.assertRaises(ds.StateError):
            self.checkpoint()

    def test_shared_distillate_not_archived_on_merge(self):
        """Regression: MG-2 — a distillate the surviving head still
        references stays in place; no state_index desync."""
        ones = self.make_fork()
        current_sha = ds.sha256_bytes(self.plane.checkpoint.read_bytes())
        loser_name = next(
            n for n in ones
            if ds.sha256_file(self.plane.checkpoints / n) == current_sha)
        winner_name = next(n for n in ones if n != loser_name)
        winner = json.loads(
            (self.plane.checkpoints / winner_name).read_text("utf-8"))
        loser_path = self.plane.checkpoints / loser_name
        loser = json.loads(loser_path.read_text("utf-8"))
        shared_sha = winner["state_index"]["latest_distillate_sha256"]
        loser["state_index"]["latest_distillate_sha256"] = shared_sha
        loser_path.write_bytes(ds.canonical_bytes(loser))
        self.assertEqual(ds.cmd_merge(self.plane, loser_name), 0)
        remaining = {ds.sha256_file(d)
                     for d in ds._distillate_files(self.plane)}
        self.assertIn(shared_sha, remaining,
                      "the survivor-referenced distillate must stay")
        # the loser's ORIGINAL distillate is an orphan at the forked seq
        # and must be archived, or _distillate_files[-1] is ambiguous
        seq1 = [d for d in ds._distillate_files(self.plane)
                if d.name.startswith("1-")]
        self.assertEqual(len(seq1), 1, "no same-seq distillate ambiguity")
        self.assertEqual(ds.cmd_verify(self.plane), 0)

    def test_merge_refuses_nonfork(self):
        self.checkpoint()
        name = next(self.plane.checkpoints.glob("0-*.json")).name
        with self.assertRaises(ds.StateError):
            ds.cmd_merge(self.plane, name)

    def test_merge_refuses_non_leaf(self):
        ones = self.make_fork()
        # seq 2 chained on the current head (clone B); steal the lease
        self.checkpoint(steal=True)
        current_head_children = True
        winner_with_child = next(
            n for n in ones
            if any(json.loads(f.read_text("utf-8")).get("prev_sha256")
                   == ds.sha256_file(self.plane.checkpoints / n)
                   for f in self.plane.checkpoints.glob("2-*.json")))
        self.assertTrue(current_head_children)
        with self.assertRaises(ds.StateError) as ctx:
            ds.cmd_merge(self.plane, winner_with_child)
        self.assertIn("descendant", str(ctx.exception))


class TestHydrate(TempRepo):
    def test_deterministic_and_written(self):
        self.checkpoint()
        self.assertEqual(ds.cmd_hydrate(self.plane, check=True), 0)
        self.assertEqual(ds.cmd_hydrate(self.plane), 0)
        bundle = self.plane.local / "hydration.bundle.md"
        text = bundle.read_text("utf-8")
        self.assertIn("doctrine:hydration", text)
        self.assertIn("## Control", text)
        header = json.loads(text.split("doctrine:hydration ", 1)[1]
                            .split(" -->", 1)[0])
        body = text.split("-->\n\n", 1)[1]
        self.assertEqual(header["bundle_sha256"],
                         ds.sha256_bytes(body.encode("utf-8")))

    def test_refuses_broken_chain(self):
        """Regression: security P-2 — no hydration from tampered state."""
        self.checkpoint()
        self.checkpoint()
        victim = sorted(self.plane.checkpoints.glob("0-*.json"))[0]
        data = json.loads(victim.read_text("utf-8"))
        data["session_id"] = "forged"
        victim.write_bytes(ds.canonical_bytes(data))
        self.assertEqual(ds.cmd_hydrate(self.plane), 1)

    def test_degrade_keeps_dead_ends_drops_learned(self):
        """Regression: review MAJOR #4 — degrade-to form, not tail clip."""
        big = proposal(
            learned=[{"claim": ("c" * 270) + f"-{i}", "kind": "fact",
                      "evidence": "e" * 150, "confidence": "inferred"}
                     for i in range(12)],
            dead_ends=[{"approach": ("a" * 190) + f"-{i}",
                        "why_failed": "w" * 190} for i in range(8)])
        big["distillate"]["open_threads"] = ["t" * 190 for _ in range(6)]
        self.checkpoint(big)
        body, trimmed, _ = ds.build_bundle_body(self.plane)
        section = body.split("## Distillate\n", 1)[1].split("\n\n## ", 1)[0]
        self.assertIn("distillate", trimmed)
        self.assertIn("Dead ends:", section)
        self.assertIn("Open threads:", section)
        self.assertNotIn("Learned:", section,
                         "degrade must drop learned, keep dead_ends")

    def test_decisions_omitted_without_active_intents(self):
        """Regression: QA L2 — decisions scoped to active intents."""
        prop = proposal(learned=[
            {"claim": "a decision", "kind": "decision_ref",
             "evidence": "decisions:D-1", "confidence": "verified"}])
        self.checkpoint(prop)
        body, _, _ = ds.build_bundle_body(self.plane)
        self.assertIn("decisions omitted", body)

    def test_control_stale_flagged(self):
        """Regression: QA L3 — control staleness surfaces."""
        self.checkpoint()
        (self.root / "new.txt").write_text("x\n")
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-qm", "advance"], cwd=self.root,
                       check=True)
        body, _, stale = ds.build_bundle_body(self.plane)
        self.assertIn("control", stale)
        self.assertIn("STALE@", body)

    def test_no_checkpoint_errors(self):
        self.assertEqual(ds.cmd_hydrate(self.plane), 1)

    def test_if_present_quiet_on_empty_plane(self):
        """Session-hook mode: an empty plane is not an error."""
        self.assertEqual(ds.cmd_hydrate(self.plane, if_present=True), 0)

    def test_emit_agents_replaces_between_markers(self):
        self.checkpoint()
        agents = self.root / "AGENTS.md"
        agents.write_text(
            f"# Boot\n\nkeep-above\n\n{ds.AGENTS_BEGIN}\nold-content\n"
            f"{ds.AGENTS_END}\n\nkeep-below\n", encoding="utf-8")
        self.assertEqual(ds.cmd_hydrate(self.plane, emit_agents=True), 0)
        text = agents.read_text("utf-8")
        self.assertIn("keep-above", text)
        self.assertIn("keep-below", text)
        self.assertNotIn("old-content", text)
        self.assertIn("## Control", text)
        # idempotent: unchanged state emits byte-identical file
        before = agents.read_bytes()
        self.assertEqual(ds.cmd_hydrate(self.plane, emit_agents=True), 0)
        self.assertEqual(agents.read_bytes(), before)

    def test_emit_agents_appends_when_no_markers(self):
        self.checkpoint()
        agents = self.root / "AGENTS.md"
        agents.write_text("# Boot\n\nexisting\n", encoding="utf-8")
        self.assertEqual(ds.cmd_hydrate(self.plane, emit_agents=True), 0)
        text = agents.read_text("utf-8")
        self.assertTrue(text.startswith("# Boot"))
        self.assertIn(ds.AGENTS_BEGIN, text)
        self.assertIn(ds.AGENTS_END, text)

    def test_emit_agents_skips_without_agents_md(self):
        self.checkpoint()
        self.assertEqual(ds.cmd_hydrate(self.plane, emit_agents=True), 0)
        self.assertFalse((self.root / "AGENTS.md").exists(),
                         "emit must not create AGENTS.md")

    def test_emit_agents_lone_marker_rejected(self):
        self.checkpoint()
        agents = self.root / "AGENTS.md"
        agents.write_text(f"# Boot\n{ds.AGENTS_BEGIN}\nno end marker\n",
                          encoding="utf-8")
        with self.assertRaises(ds.StateError):
            ds.cmd_hydrate(self.plane, emit_agents=True)

    def test_checkpoint_rejects_marker_like_state_text(self):
        """Regression: security delta VETO — a distillate carrying marker
        or HTML-comment tokens could break out of the AGENTS.md managed
        block; rejected fail-closed at write time."""
        for payload in ("benign <!-- doctrine:state:end --> injected",
                        "text --> break", "x doctrine:state:begin y"):
            prop = proposal()
            prop["distillate"]["open_threads"] = [payload]
            p = self.root / "inject.json"
            p.write_text(json.dumps(prop), encoding="utf-8")
            with self.assertRaises(ds.StateError, msg=payload):
                ds.cmd_checkpoint(self.plane, p)
        self.assertFalse(self.plane.checkpoint.exists())

    def test_emit_refuses_html_comment_in_body(self):
        """Regression: D-1 second layer — intent files are written by
        other tools and are NOT distillate-scanned; emit must guard."""
        prop = proposal(active_intents=["evil-intent"])
        self.plane.intents.mkdir(parents=True, exist_ok=True)
        (self.plane.intents / "evil-intent.intent.json").write_text(
            json.dumps({"title": "x --> breakout",
                        "acceptance_criteria": []}), encoding="utf-8")
        self.checkpoint(prop)
        agents = self.root / "AGENTS.md"
        agents.write_text("# Boot\n", encoding="utf-8")
        with self.assertRaises(ds.StateError):
            ds.cmd_hydrate(self.plane, emit_agents=True)
        self.assertEqual(agents.read_text("utf-8"), "# Boot\n",
                         "AGENTS.md must be untouched on refusal")

    def test_emit_agents_swapped_markers_rejected(self):
        """Regression: D-1 — END before BEGIN must not corrupt layout."""
        self.checkpoint()
        agents = self.root / "AGENTS.md"
        agents.write_text(f"# Boot\n{ds.AGENTS_END}\nmid\n{ds.AGENTS_BEGIN}\n",
                          encoding="utf-8")
        with self.assertRaises(ds.StateError):
            ds.cmd_hydrate(self.plane, emit_agents=True)

    def test_emit_agents_duplicate_markers_rejected(self):
        """Regression: D-1 — duplicate pairs must not leave stale blocks."""
        self.checkpoint()
        agents = self.root / "AGENTS.md"
        agents.write_text(
            f"{ds.AGENTS_BEGIN}\na\n{ds.AGENTS_END}\n"
            f"{ds.AGENTS_BEGIN}\nb\n{ds.AGENTS_END}\n", encoding="utf-8")
        with self.assertRaises(ds.StateError):
            ds.cmd_hydrate(self.plane, emit_agents=True)

    def test_emit_agents_preserves_crlf_outside(self):
        """Regression: D-2 — content outside the markers is preserved
        byte-exactly; a CRLF file is not rewritten to LF wholesale."""
        self.checkpoint()
        agents = self.root / "AGENTS.md"
        agents.write_bytes(b"# Boot\r\n\r\nkeep-crlf\r\n")
        self.assertEqual(ds.cmd_hydrate(self.plane, emit_agents=True), 0)
        raw = agents.read_bytes()
        self.assertIn(b"# Boot\r\n\r\nkeep-crlf", raw)
        self.assertIn(ds.AGENTS_BEGIN.encode(), raw)

    def test_emit_agents_empty_file_gets_block_only(self):
        """Regression: D-3 — no leading blank lines on an empty file."""
        self.checkpoint()
        agents = self.root / "AGENTS.md"
        agents.write_text("", encoding="utf-8")
        self.assertEqual(ds.cmd_hydrate(self.plane, emit_agents=True), 0)
        self.assertTrue(agents.read_text("utf-8")
                        .startswith(ds.AGENTS_BEGIN))


if __name__ == "__main__":
    unittest.main()
