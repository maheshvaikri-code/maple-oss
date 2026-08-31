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
"""doctrine_gold — Gold Build promotion for the enterprise merge profile
(.Doctrine/standards/merge-and-promotion.md).

Commands:
  record --input F   promote a candidate: validate the proposal, stamp
                     at_commit from the ANNOTATED tag, hash the artifacts
                     AND the council verdict AND every sign-off into the
                     record (empty files refused - "no verdict, no gold"
                     means content, not filenames), chain to the head of
                     the gold chain. Nothing is written until everything
                     validates.
  check --tag vX.Y.Z the deploy gate: schema, artifact/verdict/sign-off
                     re-hash, chain topology (single genesis, no forks,
                     record reachable), tag -> commit match. Deploy
                     pipelines run this and refuse on exit 1.

Chain order is derived ONLY by walking prev_gold_sha256 links - file
mtimes are never an authority signal (clones reset them; attackers forge
them). Gold records are immutable canonical JSON at
docs/releases/gold/<tag>.json; the chain is the rollback ladder.

Terminal output is ASCII-only. Exit codes: 0 ok / 1 verification failed /
2 usage or validation error.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from doctrine_state import (  # noqa: E402
    SchemaError,
    StateError,
    canonical_bytes,
    git,
    head_commit,
    load_json,
    now_utc,
    sha256_bytes,
    sha256_file,
    validate,
    worktree_state,
)

GOLD_DIR = Path("docs") / "releases" / "gold"
TAG_RE = re.compile(r"^v[0-9]+\.[0-9]+\.[0-9]+$")


def load_gold_schema(repo: Path) -> dict:
    path = repo / ".Doctrine" / "schemas" / "gold-build.schema.json"
    if not path.exists():
        raise StateError(f"schema not found: {path}")
    return load_json(path, "schema")


def require_tag_format(tag: str) -> None:
    """Validate BEFORE the tag string reaches git argv or any path."""
    if not TAG_RE.fullmatch(tag):
        raise StateError(f"tag {tag!r} is not vX.Y.Z - refusing before "
                         "it reaches git or the filesystem")


def safe_repo_path(repo: Path, rel: str, what: str) -> Path:
    """Resolve a record-referenced path, refusing escapes from the repo."""
    candidate = (repo / rel).resolve()
    root = repo.resolve()
    if root != candidate and root not in candidate.parents:
        raise StateError(f"{what} '{rel}' escapes the repo root")
    return candidate


def hashed_ref(repo: Path, rel: str, what: str) -> dict:
    """{path, sha256} for a referenced file; empty/whitespace-only files
    are refused - existence is not evidence."""
    p = safe_repo_path(repo, rel, what)
    if not p.exists():
        raise StateError(f"{what} not on disk: {rel}")
    data = p.read_bytes()
    if not data.strip():
        raise StateError(f"{what} is empty: {rel} - an empty file is not "
                         "a sign-off")
    return {"path": rel, "sha256": sha256_bytes(data)}


def tag_commit(repo: Path, tag: str) -> str:
    """Full commit sha of an ANNOTATED tag (lightweight tags refused -
    'annotated tags only' per standards/git-conventions.md)."""
    kind = git(repo, "cat-file", "-t", tag)
    if kind != "tag":
        raise StateError(f"tag {tag} is {kind}, not an annotated tag - "
                         "releases use annotated tags only")
    return git(repo, "rev-list", "-n", "1", tag)


def load_chain(repo: Path) -> list[Path]:
    """Order gold records by walking prev_gold_sha256 links. Exactly one
    genesis, every prev resolves to exactly one record, no forks, all
    records reachable - anything else is a broken ladder (StateError)."""
    gold = repo / GOLD_DIR
    if not gold.exists():
        return []
    entries: list[tuple[Path, str, str | None]] = []
    for p in sorted(gold.glob("*.json")):
        rec = load_json(p, "gold record")
        prev = rec.get("prev_gold_sha256") if isinstance(rec, dict) else ""
        entries.append((p, sha256_file(p), prev))
    if not entries:
        return []
    shas = {sha for _, sha, _ in entries}
    genesis = [e for e in entries if e[2] is None]
    if len(genesis) != 1:
        raise StateError(f"gold chain topology: {len(genesis)} genesis "
                         "record(s), expected exactly 1")
    child_of: dict[str, tuple[Path, str]] = {}
    for p, sha, prev in entries:
        if prev is None:
            continue
        if prev not in shas:
            raise StateError(f"{p.name}: prev_gold_sha256 matches no gold "
                             "record on disk - broken rollback chain")
        if prev in child_of:
            raise StateError(f"gold chain fork: {p.name} and "
                             f"{child_of[prev][0].name} both claim the "
                             f"same predecessor {prev[:12]}")
        child_of[prev] = (p, sha)
    ordered = [genesis[0][0]]
    cursor = genesis[0][1]
    while cursor in child_of:
        p, sha = child_of[cursor]
        ordered.append(p)
        cursor = sha
    if len(ordered) != len(entries):
        raise StateError(f"gold chain topology: {len(entries) - len(ordered)}"
                         " record(s) unreachable from genesis")
    return ordered


def cmd_record(repo: Path, input_path: Path) -> int:
    proposal = load_json(input_path, "gold proposal")
    if not isinstance(proposal, dict):
        raise StateError("gold proposal must be a JSON object")
    for field in ("tag", "merge_verdict", "signoffs", "artifacts", "soak",
                  "human_approval"):
        if field not in proposal:
            raise StateError(f"gold proposal missing '{field}'")
    if not isinstance(proposal["signoffs"], dict) or \
            not isinstance(proposal["artifacts"], list):
        raise StateError("gold proposal: 'signoffs' must be an object and "
                         "'artifacts' a list")
    tag = str(proposal["tag"])
    require_tag_format(tag)

    # ---- dispose: every claim verified before anything is written ----
    at_commit = tag_commit(repo, tag)
    if head_commit(repo) != at_commit:
        print(f"warning: HEAD is not {tag}'s commit - artifacts are "
              "hashed from THIS worktree; make sure they were built from "
              f"{at_commit[:12]}", file=sys.stderr)
    if worktree_state(repo) == "dirty":
        print("warning: worktree is dirty while promoting - artifact "
              "hashes may not be reproducible from the tag",
              file=sys.stderr)

    verdict = hashed_ref(repo, str(proposal["merge_verdict"]),
                         "council verdict")
    signoffs = {name: hashed_ref(repo, str(rel), f"sign-off '{name}'")
                for name, rel in proposal["signoffs"].items()}

    artifacts, seen_paths = [], set()
    for entry in proposal["artifacts"]:
        rel = entry["path"] if isinstance(entry, dict) else str(entry)
        if rel in seen_paths:
            raise StateError(f"duplicate artifact path: {rel}")
        seen_paths.add(rel)
        p = safe_repo_path(repo, rel, "artifact")
        if not p.exists():
            raise StateError(f"artifact not on disk: {rel}")
        artifacts.append({"path": rel, "sha256": sha256_file(p)})

    chain = load_chain(repo)
    prev = chain[-1] if chain else None
    record = {
        "gold_version": "1", "tag": tag, "at_commit": at_commit,
        "created_at": now_utc(),
        "merge_verdict": verdict,
        "signoffs": signoffs,
        "artifacts": artifacts,
        "soak": proposal["soak"],
        "human_approval": proposal["human_approval"],
        "prev_gold_sha256": sha256_file(prev) if prev else None,
    }
    validate(record, load_gold_schema(repo))

    out = repo / GOLD_DIR / f"{tag}.json"
    if out.exists():
        raise StateError(f"gold record already exists for {tag} - records "
                         "are immutable; a correction is a NEW tag")

    # ---- write phase ----
    out.parent.mkdir(parents=True, exist_ok=True)
    data = canonical_bytes(record)
    out.write_bytes(data)
    print(f"GOLD: {tag} at {at_commit[:12]} "
          f"({sha256_bytes(data)[:12]}); {len(artifacts)} artifact(s)"
          + (f"; chained to {prev.name}" if prev else "; genesis record"))
    print(f"remember: git add {out.relative_to(repo).as_posix()} && "
          f"git commit -m \"release: gold {tag}\"")
    return 0


def cmd_check(repo: Path, tag: str) -> int:
    require_tag_format(tag)
    path = repo / GOLD_DIR / f"{tag}.json"
    if not path.exists():
        print(f"CHECK FAILED: no gold record for {tag} - do not deploy")
        return 1
    record = load_json(path, "gold record")
    try:
        validate(record, load_gold_schema(repo))
    except SchemaError as exc:
        # shape is untrusted beyond this point - report and stop
        print(f"CHECK FAILED (1) - do not deploy {tag}:")
        print(f"  - schema: {exc}")
        return 1

    findings: list[str] = []
    if record["tag"] != tag:
        findings.append(f"record tag {record['tag']!r} != {tag!r}")
    try:
        actual = tag_commit(repo, tag)
        if record["at_commit"] != actual:
            findings.append(f"tag now points at {actual[:12]}, record "
                            f"says {record['at_commit'][:12]} - the tag "
                            "moved")
    except (subprocess.CalledProcessError, StateError) as exc:
        findings.append(f"tag verification: {exc}")

    refs = [("council verdict", record["merge_verdict"])]
    refs += [(f"sign-off '{k}'", v) for k, v in record["signoffs"].items()]
    refs += [("artifact", a) for a in record["artifacts"]]
    for what, entry in refs:
        try:
            p = safe_repo_path(repo, entry["path"], what)
        except StateError as exc:
            findings.append(str(exc))
            continue
        if not p.exists():
            findings.append(f"{what} missing: {entry['path']}")
        elif sha256_file(p) != entry["sha256"]:
            findings.append(f"{what} hash mismatch: {entry['path']} - "
                            "content changed after promotion")

    try:
        chain = load_chain(repo)
        if path.resolve() not in [p.resolve() for p in chain]:
            findings.append("record not reachable in the gold chain")
    except StateError as exc:
        findings.append(str(exc))

    if findings:
        print(f"CHECK FAILED ({len(findings)}) - do not deploy {tag}:")
        for msg in findings:
            print(f"  - {msg}")
        return 1
    print(f"check OK: {tag} is GOLD - schema valid, artifacts/verdict/"
          "sign-offs match their recorded hashes, chain intact")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="doctrine_gold",
                                     description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="command", required=True)
    p_rec = sub.add_parser("record")
    p_rec.add_argument("--input", type=Path, required=True)
    p_chk = sub.add_parser("check")
    p_chk.add_argument("--tag", required=True)
    args = parser.parse_args(argv)

    repo = args.root.resolve()
    try:
        if args.command == "record":
            return cmd_record(repo, args.input)
        if args.command == "check":
            return cmd_check(repo, args.tag)
    except (SchemaError, StateError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as exc:
        print(f"git failed: {exc.stderr.strip()}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
