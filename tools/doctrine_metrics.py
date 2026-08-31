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
"""doctrine_metrics — bridge the doctrine's review artifacts to CodeMonk.

Git history alone reads HITL as zero. This tool scans the doctrine's
review/QA/merge artifacts (docs/reviews/, docs/qa/, docs/merges/) for
commit references, verifies each against the repository, and emits a
CodeMonk enrichment overlay marking those commits as reviewed:

  python tools/doctrine_metrics.py enrich
  python -m codemonk analyze --repo . --enrich docs/metrics/enrichment.json

Fidelity note (stated in the output too): in a doctrine repo the review
loop is the fresh-context VERIFIER fan-out (adversarial agent review,
human-arbitrated) — the enrichment flags coverage by that loop via
CodeMonk's review field. Quote the resulting HITL with that label.

Only hex tokens that resolve to real commits reachable from HEAD are
emitted; tokens are regex-validated before ever reaching git argv.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from doctrine_state import StateError, git  # noqa: E402

ARTIFACT_DIRS = ["docs/reviews", "docs/qa", "docs/merges"]
DEFAULT_OUT = Path("docs") / "metrics" / "enrichment.json"
# word-bounded 7-40 hex; a 64-hex sha256 is one word and cannot match
HEX_RE = re.compile(r"\b[0-9a-f]{7,40}\b")

# --- gate instrumentation -------------------------------------------------
# A verdict event is an ADDED artifact line that carries the word
# "verdict" plus a verdict token. Requiring "verdict" on the line keeps
# prose ("holds the ship veto") and pasted tool output ("CHECK FAILED")
# from inflating the counts. Order matters: longest token first.
VERDICT_LINE_RE = re.compile(r"(?i)verdict")
VERDICT_TOKENS = ["APPROVE-WITH-NITS", "REQUEST-CHANGES", "SIGN-OFF",
                  "APPROVE", "VETO", "PASS", "FAIL"]
ADVERSE = {"REQUEST-CHANGES", "VETO", "FAIL"}
TAG_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


def resolve_commit(repo: Path, token: str) -> str | None:
    """Full sha if the token names a commit reachable from HEAD."""
    try:
        full = git(repo, "rev-parse", "--verify", "--quiet",
                   f"{token}^{{commit}}")
    except subprocess.CalledProcessError:
        return None
    try:
        git(repo, "merge-base", "--is-ancestor", full, "HEAD")
    except subprocess.CalledProcessError:
        return None
    return full


def collect(repo: Path, dirs: list[str]) -> tuple[dict[str, list[str]], int]:
    """commit -> artifact paths that reference it, plus files scanned."""
    referenced: dict[str, set[str]] = {}
    scanned = 0
    cache: dict[str, str | None] = {}
    for rel in dirs:
        base = repo / rel
        if not base.exists():
            continue
        for f in sorted(base.rglob("*.md")):
            scanned += 1
            text = f.read_text("utf-8", errors="replace")
            for token in set(HEX_RE.findall(text)):
                if token not in cache:
                    cache[token] = resolve_commit(repo, token)
                full = cache[token]
                if full:
                    referenced.setdefault(full, set()).add(
                        f.relative_to(repo).as_posix())
    return {sha: sorted(files) for sha, files in referenced.items()}, scanned


def cmd_enrich(repo: Path, dirs: list[str], out_rel: Path,
               mark_authorship: str | None = None) -> int:
    if not (repo / ".git").exists():
        raise StateError(f"{repo} is not a git repository")
    referenced, scanned = collect(repo, dirs)
    if not scanned:
        print("no review artifacts found under "
              f"{', '.join(dirs)} - nothing to enrich", file=sys.stderr)
        return 1
    entries: list[dict] = [{"id": sha, "human_reviewed": True}
                           for sha in sorted(referenced)]
    if mark_authorship:
        # operator-asserted provenance for repos whose commits carry no
        # trailer (e.g. after a history rewrite): EVERY HEAD-reachable
        # commit is marked with the given authorship. Only assert what
        # is true for the whole history - this is a blanket claim.
        allowed = {"agent_autonomous", "agent_assisted", "human"}
        if mark_authorship not in allowed:
            raise StateError(f"--mark-authorship must be one of "
                             f"{sorted(allowed)}")
        by_id = {e["id"]: e for e in entries}
        for sha in git(repo, "rev-list", "HEAD").splitlines():
            entry = by_id.setdefault(sha, {"id": sha})
            entry["authorship"] = mark_authorship
            if mark_authorship.startswith("agent"):
                entry["agent_name"] = "claude"
        entries = [by_id[k] for k in sorted(by_id)]
        print(f"authorship '{mark_authorship}' asserted for "
              f"{len(entries)} commit(s) (blanket operator claim)")
    out = repo / out_rel
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes((json.dumps(entries, indent=2, sort_keys=True) + "\n")
                    .encode("utf-8"))
    reviewed = sum(1 for e in entries if e.get("human_reviewed"))
    print(f"enrichment written: {out_rel.as_posix()} - {len(entries)} "
          f"entr{'ies' if len(entries) != 1 else 'y'}, {reviewed} "
          f"reviewed, from {scanned} artifact file(s)")
    print("fidelity: 'reviewed' = referenced by the doctrine's verifier "
          "fan-out artifacts (adversarial agent review, human-arbitrated) "
          "- label HITL accordingly when quoting")
    for sha, files in sorted(referenced.items()):
        print(f"  {sha[:12]} <- {', '.join(files)}")
    print("consume: python -m codemonk analyze --repo . "
          f"--enrich {out_rel.as_posix()}")
    return 0


def classify_verdict_line(line: str) -> str | None:
    """First verdict token on a line that names a verdict, else None."""
    if not VERDICT_LINE_RE.search(line):
        return None
    upper = line.upper()
    for token in VERDICT_TOKENS:
        if token in upper:
            return token
    return None


def _release_tags(repo: Path) -> list[str]:
    tags = [t for t in git(repo, "tag", "--list", "v*").splitlines()
            if TAG_RE.match(t)]
    return sorted(tags, key=lambda t: tuple(
        int(x) for x in TAG_RE.match(t).groups()))


def _verdicts_in_range(repo: Path, spec: str) -> dict[str, int]:
    """Verdict events ADDED to review artifacts within a git range."""
    diff = git(repo, "diff", spec, "--", *ARTIFACT_DIRS)
    counts: dict[str, int] = {}
    for line in diff.splitlines():
        if not line.startswith("+") or line.startswith("+++"):
            continue
        token = classify_verdict_line(line[1:])
        if token:
            counts[token] = counts.get(token, 0) + 1
    return counts


def _parse_git_timestamp(value: str) -> _dt.datetime:
    """Parse Git's ISO timestamp on every supported Python version."""
    normalized = value.strip()
    if normalized.endswith("Z"):
        # Python 3.10 and earlier do not accept the ISO-8601 UTC suffix.
        normalized = normalized[:-1] + "+00:00"
    return _dt.datetime.fromisoformat(normalized)


def cmd_gates(repo: Path, out_rel: Path | None) -> int:
    """Per-release process metrics mined from what the pipeline already
    files: cycle time, commit/fix volume, and review-verdict events."""
    if not (repo / ".git").exists():
        raise StateError(f"{repo} is not a git repository")
    tags = _release_tags(repo)
    if len(tags) < 2:
        print("need at least two vX.Y.Z tags to compute release windows",
              file=sys.stderr)
        return 1
    rows = []
    totals = {"commits": 0, "fixes": 0, "adverse": 0, "clearing": 0}
    for prev, cur in zip(tags, tags[1:]):
        spec = f"{prev}..{cur}"
        t0 = _parse_git_timestamp(git(repo, "log", "-1", "--format=%cI", prev))
        t1 = _parse_git_timestamp(git(repo, "log", "-1", "--format=%cI", cur))
        hours = (t1 - t0).total_seconds() / 3600
        commits = int(git(repo, "rev-list", "--count", spec))
        fixes = int(git(repo, "rev-list", "--count",
                        "--grep=^fix", spec))
        verdicts = _verdicts_in_range(repo, spec)
        adverse = sum(n for t, n in verdicts.items() if t in ADVERSE)
        clearing = sum(n for t, n in verdicts.items() if t not in ADVERSE)
        rows.append((cur, hours, commits, fixes, adverse, clearing,
                     verdicts))
        totals["commits"] += commits
        totals["fixes"] += fixes
        totals["adverse"] += adverse
        totals["clearing"] += clearing

    lines = [
        "# Gate instrumentation - process metrics per release",
        "",
        "Mined from committed artifacts and git history. Verdict counts",
        "are token heuristics over ADDED lines naming a verdict; cycle",
        "time is tag-commit to tag-commit. Adverse = REQUEST-CHANGES/",
        "VETO/FAIL (a review round that sent work back); clearing =",
        "APPROVE*/SIGN-OFF/PASS.",
        "",
        "| Release | Cycle (h) | Commits | Fix commits | Adverse | "
        "Clearing | Verdicts |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for cur, hours, commits, fixes, adverse, clearing, verdicts in rows:
        detail = ", ".join(f"{t}:{n}" for t, n in sorted(verdicts.items()))
        lines.append(f"| {cur} | {hours:.1f} | {commits} | {fixes} | "
                     f"{adverse} | {clearing} | {detail or '-'} |")
    lines.append(f"| **total** |  | {totals['commits']} | "
                 f"{totals['fixes']} | {totals['adverse']} | "
                 f"{totals['clearing']} |  |")
    lines.append("")
    lines.append(f"Releases: {len(rows)} - adverse verdicts sent work "
                 "back to G3 and every one is documented in "
                 "docs/reviews|qa; a zero-adverse release with material "
                 "code change deserves retro scrutiny (review erosion), "
                 "exactly like the HITL/CESR gate.")
    report = "\n".join(lines) + "\n"
    if out_rel:
        out = repo / out_rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(report.encode("utf-8"))
        print(f"gate metrics written: {out_rel.as_posix()}")
    else:
        print(report, end="")
    return 0


def cmd_capture_hint(repo: Path) -> int:
    """One-line SessionStart hint when a metrics-adopted repo runs
    without token capture. Always exits 0 - it is a hint, not a gate."""
    import os
    adopted = (repo / ".Doctrine" / "integrations" / "codemonk.md").exists()
    captured = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT") \
        or os.environ.get("ANTHROPIC_BASE_URL")
    if adopted and not captured:
        print("metrics hint: this session's tokens are NOT being captured "
              "- launch via 'codemonk wrap --otel -- claude' (or see "
              ".Doctrine/integrations/codemonk.md) so TCR/cost join the "
              "ledger", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="doctrine_metrics",
                                     description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="command", required=True)
    p_en = sub.add_parser("enrich")
    p_en.add_argument("--dirs", nargs="*", default=ARTIFACT_DIRS)
    p_en.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p_en.add_argument("--mark-authorship", default=None,
                      help="assert authorship for ALL commits (blanket "
                           "claim): agent_autonomous|agent_assisted|human")
    p_ga = sub.add_parser("gates")
    p_ga.add_argument("--out", type=Path, default=None,
                      help="write the report here instead of stdout")
    sub.add_parser("capture-hint")
    args = parser.parse_args(argv)
    try:
        if args.command == "enrich":
            return cmd_enrich(args.root.resolve(), list(args.dirs),
                              args.out, args.mark_authorship)
        if args.command == "gates":
            return cmd_gates(args.root.resolve(), args.out)
        if args.command == "capture-hint":
            return cmd_capture_hint(args.root.resolve())
    except StateError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as exc:
        print(f"git failed: {exc.stderr.strip()}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
