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
"""doctrine_install — install the Doctrine System into any target repo.

Copies the committed law (.Doctrine.md + .Doctrine/), the enforcement
tools, the Claude Code wiring, and the adapter overlays for the tools you
name. Idempotent: unchanged files are skipped; files that exist with
DIFFERENT content are never silently clobbered (skipped with a warning
unless --force). An existing CLAUDE.md gets the import lines APPENDED,
never replaced; an existing AGENTS.md is left alone (use
`doctrine_state.py hydrate --emit-agents` for the state block).

Usage:
  python tools/doctrine_install.py --target ../my-repo --tool claude
  python tools/doctrine_install.py --target . --tool claude,cursor,codex
  python tools/doctrine_install.py --target ../svc --tool all --enterprise
  python tools/doctrine_install.py --target . --verify   # turnkey: one command

--verify makes it turnkey: after copying, it initializes the state plane
and runs the gate suite in the target, so a single command ends in a
proven-green install. --maple opts into the MAPLE runtime by seeding the
brief.

Publishing/registry distribution stays human-gated (.Doctrine.md section 5).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# tool -> [(source under .Doctrine/adapters/, dest under target root)]
ADAPTERS: dict[str, list[tuple[str, str]]] = {
    "claude": [],  # native wiring copied separately (.claude/, CLAUDE.md)
    "codex": [],   # AGENTS.md is native; MCP registration is documented
    "cursor": [("cursor-doctrine.mdc", ".cursor/rules/doctrine.mdc")],
    "windsurf": [("windsurf-doctrine.md", ".windsurf/rules/doctrine.md")],
    "copilot": [("copilot-instructions.md",
                 ".github/copilot-instructions.md")],
    "gemini": [("GEMINI.md", "GEMINI.md")],
    "cline": [("cline-doctrine.md", ".clinerules/doctrine.md")],
    "roo": [("roo-doctrine.md", ".roo/rules/doctrine.md")],
    "amazonq": [("amazonq-doctrine.md", ".amazonq/rules/doctrine.md")],
    "continue": [("continue-doctrine.md", ".continue/rules/doctrine.md")],
    "junie": [("junie-doctrine.md", ".junie/guidelines.md")],
}
CLAUDE_IMPORTS = ["@.Doctrine.md",
                  "@.doctrine-state/local/hydration.bundle.md"]
TOOL_FILES = ["doctrine_state.py", "doctrine_lint.py", "doctrine_gold.py",
              "doctrine_mcp.py", "doctrine_install.py",
              "doctrine_metrics.py", "doctrine_verify.py"]
GITIGNORE_LINES = [".doctrine-state/local/", "__pycache__/"]


class Report:
    def __init__(self) -> None:
        self.copied: list[str] = []
        self.skipped_same: int = 0
        self.skipped_diff: list[str] = []

    def show(self) -> None:
        print(f"installed: {len(self.copied)} file(s), "
              f"unchanged: {self.skipped_same}")
        if self.skipped_diff:
            print(f"SKIPPED {len(self.skipped_diff)} file(s) that exist "
                  "with different content (rerun with --force to "
                  "overwrite):")
            for rel in self.skipped_diff:
                print(f"  - {rel}")


def copy_file(src: Path, dest: Path, target: Path, report: Report,
              force: bool) -> None:
    data = src.read_bytes()
    if dest.is_symlink():
        # never write through a link we didn't create
        if not force:
            report.skipped_diff.append(dest.relative_to(target).as_posix()
                                       + " (symlink)")
            return
        dest.unlink()
    if dest.exists():
        if dest.read_bytes() == data:
            report.skipped_same += 1
            return
        if not force:
            report.skipped_diff.append(dest.relative_to(target).as_posix())
            return
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    report.copied.append(dest.relative_to(target).as_posix())


def copy_tree(src_dir: Path, dest_dir: Path, target: Path, report: Report,
              force: bool) -> None:
    for src in sorted(src_dir.rglob("*")):
        if src.is_dir() or "__pycache__" in src.parts:
            continue
        copy_file(src, dest_dir / src.relative_to(src_dir), target,
                  report, force)


def append_lines(path: Path, lines: list[str], header: str | None,
                 report: Report, target: Path) -> None:
    """Append only the missing lines; existing content is preserved
    byte-exactly, including its newline style (CRLF files stay CRLF)."""
    existing = path.read_bytes().decode("utf-8") if path.exists() else ""
    nl = "\r\n" if "\r\n" in existing else "\n"
    present = {ln.strip("\r") for ln in existing.splitlines()}
    missing = [ln for ln in lines if ln not in present]
    if not missing:
        report.skipped_same += 1
        return
    text = existing
    if text and not text.endswith(("\n",)):
        text += nl
    if text:
        text += nl  # one blank line before the appended block
    if header and header not in existing:
        text += header + nl
    text += nl.join(missing) + nl
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    report.copied.append(path.relative_to(target).as_posix())


def run_post_install(target: Path) -> int:
    """Turnkey --verify: initialize the state plane, then run the gate
    suite in the freshly installed target. Argv list only, no shell,
    sys.executable — cross-platform. Returns the worst exit code."""
    py = sys.executable
    print("=== turnkey: initializing state plane ===")
    init = subprocess.run([py, "tools/doctrine_state.py", "init"], cwd=target)
    print("=== turnkey: running the gate suite (doctrine_verify) ===")
    verify = subprocess.run([py, "tools/doctrine_verify.py"], cwd=target)
    return init.returncode or verify.returncode


def install(source: Path, target: Path, tools: list[str],
            enterprise: bool, ci: bool, force: bool,
            startup: bool = False, verify: bool = False,
            maple: bool = False) -> int:
    if not (source / ".Doctrine.md").exists():
        print(f"error: {source} is not a doctrine source tree "
              "(.Doctrine.md missing)", file=sys.stderr)
        return 2
    src_res, tgt_res = source.resolve(), target.resolve()
    if src_res == tgt_res:
        print("error: target is the source tree itself", file=sys.stderr)
        return 2
    if src_res in tgt_res.parents or tgt_res in src_res.parents:
        print("error: source and target must not nest (installing into a "
              "subdirectory of the source re-ingests itself on rerun)",
              file=sys.stderr)
        return 2
    unknown = [t for t in tools if t not in ADAPTERS and t != "all"]
    if unknown:
        print(f"error: unknown tool(s) {unknown}; choose from "
              f"{sorted(ADAPTERS)} or 'all'", file=sys.stderr)
        return 2
    if "all" in tools:
        tools = sorted(ADAPTERS)
    target.mkdir(parents=True, exist_ok=True)
    report = Report()

    # the law
    copy_file(source / ".Doctrine.md", target / ".Doctrine.md", target,
              report, force)
    copy_tree(source / ".Doctrine", target / ".Doctrine", target, report,
              force)
    # the enforcement suite + its tests
    for name in TOOL_FILES:
        copy_file(source / "tools" / name, target / "tools" / name,
                  target, report, force)
    for test in sorted((source / "tests").glob("test_doctrine_*.py")):
        copy_file(test, target / "tests" / test.name, target, report, force)
    if not (target / "Makefile").exists():
        copy_file(source / "Makefile", target / "Makefile", target,
                  report, force)
    if ci:
        copy_file(source / ".github" / "workflows" / "doctrine.yml",
                  target / ".github" / "workflows" / "doctrine.yml",
                  target, report, force)

    # AGENTS.md universal boot (never overwrite an existing one)
    agents = target / "AGENTS.md"
    if not agents.exists():
        copy_file(source / ".Doctrine" / "adapters" / "AGENTS.md", agents,
                  target, report, force)

    if "claude" in tools:
        copy_tree(source / ".claude", target / ".claude", target, report,
                  force)
        append_lines(target / "CLAUDE.md", CLAUDE_IMPORTS, None, report,
                     target)
    for tool in tools:
        for src_name, dest_rel in ADAPTERS[tool]:
            copy_file(source / ".Doctrine" / "adapters" / src_name,
                      target / dest_rel, target, report, force)

    append_lines(target / ".gitignore", GITIGNORE_LINES,
                 "# doctrine state plane (machine-local only)", report,
                 target)
    brief_lines = []
    if enterprise:
        brief_lines.append("Merge profile: enterprise")
    if startup:
        brief_lines.append("Company profile: startup")
    if maple:
        brief_lines.append("Workforce runtime: maple")
    if brief_lines:
        append_lines(target / "docs" / "brief.md", brief_lines,
                     "<!-- G0 artifact - complete via "
                     ".Doctrine/templates/project-brief.md -->", report,
                     target)

    report.show()
    rc = 1 if report.skipped_diff else 0
    if verify:
        # SECURITY (G5 MAJOR-1): run_post_install executes the target's
        # tool files. copy_file SKIPS (does not overwrite) a tool that
        # already exists with different content unless --force, so running
        # --verify then would execute code this installer did not write and
        # could print a false "gates green". Refuse instead.
        conflicted = [r for r in report.skipped_diff
                      if any(tf in r for tf in TOOL_FILES)]
        if conflicted:
            print("refusing --verify: the target has different-content "
                  "enforcement tools that were not overwritten "
                  f"({', '.join(conflicted)}); running them would execute "
                  "code this installer did not write. Resolve the conflict "
                  "or rerun with --force.", file=sys.stderr)
            return 2
        vc = run_post_install(target)
        if vc == 0:
            print("turnkey: installed and verified - gates green. "
                  "Engage with: doctrine: <task>")
        else:
            print("turnkey: install done, but the gate suite did NOT pass "
                  "- see the gate output above (nothing was weakened to "
                  "go green; fix and rerun verify).")
        rc = vc or rc
    else:
        print("next steps: python tools/doctrine_state.py init, then "
              "python tools/doctrine_verify.py (= make verify, no Make "
              "needed); MCP + per-tool wiring: .Doctrine/05-packaging.md")
    return rc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="doctrine_install",
                                     description=__doc__.splitlines()[0])
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--source", type=Path,
                        default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--tool", default="claude",
                        help="comma-separated: "
                             f"{','.join(sorted(ADAPTERS))} or 'all'")
    parser.add_argument("--enterprise", action="store_true",
                        help="seed 'Merge profile: enterprise' in the brief")
    parser.add_argument("--startup", action="store_true",
                        help="seed 'Company profile: startup' in the brief "
                             "(activates the founder-ops roles)")
    parser.add_argument("--ci", action="store_true",
                        help="also install the GitHub Actions workflow")
    parser.add_argument("--maple", action="store_true",
                        help="seed 'Workforce runtime: maple' in the brief "
                             "(opt-in MAPLE runtime; see "
                             ".Doctrine/integrations/maple.md)")
    parser.add_argument("--verify", action="store_true",
                        help="turnkey: after install, initialize state and "
                             "run the gate suite in the target so one "
                             "command ends verified")
    parser.add_argument("--force", action="store_true",
                        help="overwrite files that exist with different "
                             "content")
    args = parser.parse_args(argv)
    tools = [t.strip() for t in args.tool.split(",") if t.strip()]
    return install(args.source.resolve(), args.target.resolve(), tools,
                   args.enterprise, args.ci, args.force, args.startup,
                   verify=args.verify, maple=args.maple)


if __name__ == "__main__":
    raise SystemExit(main())
