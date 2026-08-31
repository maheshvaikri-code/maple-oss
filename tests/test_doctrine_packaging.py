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
"""Tests for tools/doctrine_install.py and tools/doctrine_mcp.py."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import doctrine_install as di  # noqa: E402
import doctrine_lint as dl  # noqa: E402


class TestInstaller(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.target = Path(self._tmp.name) / "consumer"

    def tearDown(self):
        self._tmp.cleanup()

    def install(self, tools="claude", **kw):
        return di.install(REPO, self.target,
                          [t for t in tools.split(",")],
                          kw.get("enterprise", False), kw.get("ci", False),
                          kw.get("force", False))

    def test_claude_install_round_trip(self):
        self.assertEqual(self.install("claude,cursor"), 0)
        for rel in (".Doctrine.md", ".Doctrine/00-charter.md",
                    ".Doctrine/skills/backend.md",
                    "tools/doctrine_state.py", "tools/doctrine_mcp.py",
                    ".claude/agents/code-reviewer.md",
                    ".claude/commands/checkpoint.md",
                    ".claude/settings.json", "CLAUDE.md", "AGENTS.md",
                    ".cursor/rules/doctrine.mdc", "Makefile",
                    "tests/test_doctrine_state.py"):
            self.assertTrue((self.target / rel).exists(), rel)
        claude_md = (self.target / "CLAUDE.md").read_text("utf-8")
        self.assertIn("@.Doctrine.md", claude_md)
        gitignore = (self.target / ".gitignore").read_text("utf-8")
        self.assertIn(".doctrine-state/local/", gitignore)

    def test_maple_flag_seeds_brief(self):
        # v0.1 turnkey: --maple records the runtime opt-in in the brief
        self.assertEqual(
            di.install(REPO, self.target, ["claude"], False, False, False,
                       maple=True), 0)
        brief = (self.target / "docs" / "brief.md").read_text("utf-8")
        self.assertIn("Workforce runtime: maple", brief)

    def test_maple_absent_by_default(self):
        di.install(REPO, self.target, ["claude"], False, False, False)
        brief = self.target / "docs" / "brief.md"
        # brief is only seeded when a profile/runtime line is requested
        if brief.exists():
            self.assertNotIn("Workforce runtime: maple",
                             brief.read_text("utf-8"))

    def test_verify_flag_runs_init_then_gates(self):
        # --verify must init state THEN run the gate suite, both in the
        # target; assert the plumbing (not the 9-min suite itself, which
        # has its own tests and would recurse through the copied tests).
        calls = []

        def fake_run(cmd, cwd=None, **kw):
            calls.append((list(cmd), Path(cwd)))
            return type("R", (), {"returncode": 0})()

        with mock.patch.object(di.subprocess, "run", fake_run):
            rc = di.install(REPO, self.target, ["claude"], False, False,
                            False, verify=True)
        self.assertEqual(rc, 0)
        self.assertEqual(len(calls), 2, calls)
        (init_cmd, init_cwd), (verify_cmd, verify_cwd) = calls
        self.assertIn("tools/doctrine_state.py", init_cmd)
        self.assertIn("init", init_cmd)
        self.assertEqual(init_cwd, self.target)
        self.assertIn("tools/doctrine_verify.py", verify_cmd)
        self.assertEqual(verify_cwd, self.target)

    def test_verify_propagates_gate_failure(self):
        # a failing gate suite must surface as a non-zero install exit
        def fake_run(cmd, cwd=None, **kw):
            hit = any("doctrine_verify.py" in str(c) for c in cmd)
            return type("R", (), {"returncode": 1 if hit else 0})()

        with mock.patch.object(di.subprocess, "run", fake_run):
            rc = di.install(REPO, self.target, ["claude"], False, False,
                            False, verify=True)
        self.assertNotEqual(rc, 0)

    def test_verify_refuses_on_tool_conflict(self):
        # G5 MAJOR-1 regression: a target carrying a different-content
        # enforcement tool must NOT be executed by --verify. copy_file
        # skips it (no --force), so --verify must refuse, not run it.
        (self.target / "tools").mkdir(parents=True)
        (self.target / "tools" / "doctrine_verify.py").write_text(
            "raise SystemExit('should never run')\n", encoding="utf-8")
        calls = []

        def fake_run(cmd, cwd=None, **kw):
            calls.append(cmd)
            return type("R", (), {"returncode": 0})()

        with mock.patch.object(di.subprocess, "run", fake_run):
            rc = di.install(REPO, self.target, ["claude"], False, False,
                            False, verify=True)
        self.assertEqual(rc, 2)
        self.assertEqual(calls, [])  # never executed the target's tools

    def test_no_verify_runs_no_subprocess(self):
        calls = []

        def fake_run(cmd, cwd=None, **kw):
            calls.append(cmd)
            return type("R", (), {"returncode": 0})()

        with mock.patch.object(di.subprocess, "run", fake_run):
            di.install(REPO, self.target, ["claude"], False, False, False)
        self.assertEqual(calls, [])

    def test_idempotent(self):
        self.install()
        first = sorted(p.relative_to(self.target).as_posix()
                       for p in self.target.rglob("*") if p.is_file())
        self.assertEqual(self.install(), 0)
        second = sorted(p.relative_to(self.target).as_posix()
                        for p in self.target.rglob("*") if p.is_file())
        self.assertEqual(first, second)

    def test_existing_claude_md_appended_not_replaced(self):
        self.target.mkdir(parents=True)
        (self.target / "CLAUDE.md").write_text(
            "# My project rules\nkeep me\n", encoding="utf-8")
        self.install()
        text = (self.target / "CLAUDE.md").read_text("utf-8")
        self.assertIn("keep me", text)
        self.assertIn("@.Doctrine.md", text)

    def test_differing_file_skipped_without_force(self):
        self.install()
        marker = self.target / ".Doctrine" / "00-charter.md"
        marker.write_text("locally edited\n", encoding="utf-8")
        self.assertEqual(self.install(), 1)  # nonzero: skipped diffs
        self.assertEqual(marker.read_text("utf-8"), "locally edited\n")
        self.assertEqual(self.install(force=True), 0)
        self.assertNotEqual(marker.read_text("utf-8"), "locally edited\n")

    def test_existing_agents_md_untouched(self):
        self.target.mkdir(parents=True)
        (self.target / "AGENTS.md").write_text("mine\n", encoding="utf-8")
        self.install()
        self.assertEqual((self.target / "AGENTS.md").read_text("utf-8"),
                         "mine\n")

    def test_enterprise_seeds_brief(self):
        self.install(enterprise=True)
        brief = (self.target / "docs" / "brief.md").read_text("utf-8")
        self.assertIn("Merge profile: enterprise", brief)

    def test_startup_seeds_brief(self):
        di.install(REPO, self.target, ["claude"], False, False, False,
                   startup=True)
        brief = (self.target / "docs" / "brief.md").read_text("utf-8")
        self.assertIn("Company profile: startup", brief)

    def test_unknown_tool_refused(self):
        self.assertEqual(self.install("notatool"), 2)

    def test_source_equals_target_refused(self):
        self.assertEqual(di.install(REPO, REPO, ["claude"], False, False,
                                    False), 2)

    def test_nested_source_target_refused(self):
        """Regression: PD-4/IN-2 — self-ingestion on rerun."""
        self.assertEqual(di.install(REPO, REPO / "consumer", ["claude"],
                                    False, False, False), 2)
        self.assertFalse((REPO / "consumer").exists())

    def test_installer_ships_every_tool(self):
        """Regression: doctrine_metrics.py was added in v0.6.1 but never
        joined TOOL_FILES — consumer installs lacked it while their
        copied hooks referenced it. Any tools/doctrine_*.py not shipped
        by the installer is a packaging defect."""
        on_disk = {p.name for p in (REPO / "tools").glob("doctrine_*.py")}
        self.assertEqual(on_disk, set(di.TOOL_FILES),
                         "installer TOOL_FILES out of sync with tools/")

    def test_installed_target_lints_clean(self):
        """Regression: PD-1 — a consumer repo must verify out of the box
        (no CHANGELOG, no plugin/ — source-repo-only checks skip)."""
        self.assertEqual(self.install(), 0)
        self.assertEqual(dl.main([str(self.target)]), 0)

    def test_append_preserves_crlf(self):
        """Regression: PD-5 — same class as v0.3.0's D-2."""
        self.target.mkdir(parents=True)
        (self.target / "CLAUDE.md").write_bytes(
            b"# Mine\r\n\r\nkeep-crlf\r\n")
        self.install()
        raw = (self.target / "CLAUDE.md").read_bytes()
        self.assertIn(b"keep-crlf\r\n", raw)
        self.assertIn(b"@.Doctrine.md\r\n", raw)


class TestMcpServer(unittest.TestCase):
    """Protocol-level test over a real stdio subprocess against this repo
    (read-only tools only)."""

    def test_handshake_list_and_calls(self):
        proc = subprocess.Popen(
            [sys.executable, str(REPO / "tools" / "doctrine_mcp.py"),
             "--root", str(REPO)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8")
        try:
            def rpc(payload):
                proc.stdin.write(json.dumps(payload) + "\n")
                proc.stdin.flush()
                return json.loads(proc.stdout.readline())

            init = rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                        "params": {"protocolVersion": "2025-06-18",
                                   "capabilities": {},
                                   "clientInfo": {"name": "t"}}})
            self.assertEqual(init["result"]["serverInfo"]["name"],
                             "doctrineos")
            proc.stdin.write(json.dumps(
                {"jsonrpc": "2.0",
                 "method": "notifications/initialized"}) + "\n")
            proc.stdin.flush()

            tools = rpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
            names = {t["name"] for t in tools["result"]["tools"]}
            self.assertLessEqual(
                {"doctrine_lint", "state_verify", "gold_check"}, names)

            status = rpc({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                          "params": {"name": "state_status",
                                     "arguments": {}}})
            self.assertFalse(status["result"]["isError"])
            text = status["result"]["content"][0]["text"]
            self.assertTrue("checkpoint seq" in text
                            or "no state plane" in text, text)

            gold = rpc({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                        "params": {"name": "gold_check",
                                   "arguments": {"tag": "v0.4.0"}}})
            self.assertTrue(gold["result"]["isError"])
            self.assertIn("no gold record",
                          gold["result"]["content"][0]["text"])

            unknown = rpc({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                           "params": {"name": "nope", "arguments": {}}})
            self.assertIn("error", unknown)

            bad = rpc({"jsonrpc": "2.0", "id": 6, "method": "no/such"})
            self.assertEqual(bad["error"]["code"], -32601)

            # Regression: PD-2/MCP-1 — malformed input never kills the loop
            for raw in ("[]", '"just a string"', "42", "null",
                        "[" * 3000 + "]" * 3000):
                proc.stdin.write(raw + "\n")
                proc.stdin.flush()
                reply = json.loads(proc.stdout.readline())
                self.assertIn("error", reply, raw[:20])
            string_params = rpc({"jsonrpc": "2.0", "id": 7,
                                 "method": "tools/call",
                                 "params": "state_status"})
            self.assertEqual(string_params["error"]["code"], -32602)
            missing_arg = rpc({"jsonrpc": "2.0", "id": 8,
                               "method": "tools/call",
                               "params": {"name": "gold_check",
                                          "arguments": {}}})
            self.assertEqual(missing_arg["error"]["code"], -32602)
            self.assertIn("tag", missing_arg["error"]["message"])
            alive = rpc({"jsonrpc": "2.0", "id": 9, "method": "ping"})
            self.assertEqual(alive.get("result"), {},
                             "server must survive all of the above")
        finally:
            proc.stdin.close()
            proc.wait(timeout=15)


if __name__ == "__main__":
    unittest.main()
