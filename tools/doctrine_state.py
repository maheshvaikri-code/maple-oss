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
"""doctrine_state — stdlib-only reference implementation of the Doctrine
state plane (.Doctrine/state-plane/STATE.md + hydration/HYDRATION.md).

Commands:
  init                    create .doctrine-state/ layout (local/ gitignored)
  checkpoint --proposal F model proposes, this validator disposes: BOTH
                          schema instances validate before ANY write; then
                          checkpoint + history copy + distillate written,
                          decision_ref claims appended to DECISIONS.ndjson,
                          old distillates pruned (dead_ends merge forward)
  verify                  walk the checkpoint chain (prev_sha256 links,
                          monotonic seq, canonical bytes) and re-hash every
                          state_index target, including the graph
  hydrate [--check]       verify first, then compile the bounded bundle
                          (markdown) with per-section degrade-to forms;
                          --check compiles twice and asserts identical
                          bundle_sha256
  prune [--keep N]        prune distillates beyond N (N >= 1, default 5)
  status                  one-screen summary (warns if chain verify fails)

Design decisions (per docs/plans/state-tooling.md and the G4/G5 review):
- State root is `.doctrine-state/` (NOT `.doctrine/state/`): on
  case-insensitive filesystems `.doctrine/` merges into `.Doctrine/`,
  landing runtime state inside the doctrine corpus. Spec amended.
- dead_ends of pruned distillates merge into the NEW distillate, newest
  negatives kept preferentially, oldest dropped at the schema cap of 8.
- STATE.md checkpoint step 4 (git commit) is left to the operator or a
  hook; the CLI prints the exact command instead of committing itself.
- `hydrate --check` double-compiles in-process: the body is a pure
  function of canonical (sorted-key) serialization, so it carries no
  hash-seed or environment dependence.

Terminal output is ASCII-only (Windows cp1252 pipes). Canonicalization
(pack-wide): UTF-8, LF, sorted keys, no trailing whitespace, single
trailing newline.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_KEEP = 5
LEASE_TTL_SECONDS = 3600
TOKEN_CHARS = 4  # 1 token ~ 4 chars, per HYDRATION.md budget accounting
MAX_STATE_FILE_BYTES = 5_000_000  # bound on any parsed state artifact
GIT_TIMEOUT = 30
STATE_DIRNAME = ".doctrine-state"
CHECKPOINT_FILE_RE = re.compile(r"^(\d+)-[0-9a-f]{12}\.json$")
DISTILLATE_FILE_RE = re.compile(r"^(\d+)-[0-9a-f]{12}\.json$")
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
SECRET_RES = [
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"(?i)\b(password|passwd|secret|token|api[_-]?key)\b"
               r"\s*[:=]\s*['\"]?[^\s'\"]{6,}"),
]
# HTML-comment tokens / marker sentinels in state text could break out of
# the AGENTS.md managed block (self-propagating instruction injection into
# a committed, auto-read file) — rejected fail-closed at checkpoint AND
# at emit (defense in depth; intents are written by other tools).
MARKER_RES = [
    re.compile(r"<!--"),
    re.compile(r"-->"),
    re.compile(r"doctrine:state:(begin|end)"),
]
BUDGETS = {  # section -> tokens (HYDRATION.md); invariants+control never trim
    "invariants": 800, "control": 200, "intents": 1200,
    "distillate": 1600, "decisions": 800, "graph": 1000, "effects": 400,
}


class StateError(ValueError):
    """Operational error: bad input, unreadable artifact, unsafe id."""


# ---------------------------------------------------------------- canonical

def canonical_bytes(obj: object) -> bytes:
    text = json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2,
                      separators=(",", ": "))
    return (text + "\n").encode("utf-8")


def canonical_line(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json(path: Path, what: str = "state file"):
    """Bounded, exception-hardened parse of an untrusted state artifact."""
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise StateError(f"{what} {path}: {exc}") from exc
    if size > MAX_STATE_FILE_BYTES:
        raise StateError(f"{what} {path}: {size} bytes exceeds the "
                         f"{MAX_STATE_FILE_BYTES}-byte state-file bound")
    try:
        return json.loads(path.read_text("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, RecursionError) as exc:
        raise StateError(f"{what} {path}: unparseable ({exc})") from exc


def read_ndjson_text(path: Path, what: str) -> str:
    """Bounded, decode-hardened read of an NDJSON state log."""
    try:
        if path.stat().st_size > MAX_STATE_FILE_BYTES:
            raise StateError(f"{what} {path}: exceeds the "
                             f"{MAX_STATE_FILE_BYTES}-byte state-file bound")
        return path.read_text("utf-8")
    except UnicodeDecodeError as exc:
        raise StateError(f"{what} {path}: not valid UTF-8 ({exc})") from exc
    except OSError as exc:
        raise StateError(f"{what} {path}: {exc}") from exc


# ------------------------------------------------------- minimal validator

class SchemaError(ValueError):
    pass


def validate(instance: object, schema: dict, root: dict | None = None,
             path: str = "$") -> None:
    """Minimal JSON-Schema validator covering the constructs used by the
    state-plane schemas (incl. propertyNames). Raises SchemaError with a
    JSON-path on first failure."""
    if root is None:
        root = schema
    if "$ref" in schema:
        ref = schema["$ref"]
        if not ref.startswith("#/$defs/"):
            raise SchemaError(f"{path}: unsupported $ref {ref}")
        schema = root["$defs"][ref.split("/")[-1]]

    if "anyOf" in schema:
        errors = []
        for sub in schema["anyOf"]:
            try:
                validate(instance, sub, root, path)
                break
            except SchemaError as exc:
                errors.append(str(exc))
        else:
            raise SchemaError(f"{path}: matched no anyOf branch "
                              f"({'; '.join(errors)})")
        return

    if "const" in schema and instance != schema["const"]:
        raise SchemaError(f"{path}: expected const {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        raise SchemaError(f"{path}: {instance!r} not in {schema['enum']}")

    stype = schema.get("type")
    if stype == "object":
        if not isinstance(instance, dict):
            raise SchemaError(f"{path}: expected object")
        for req in schema.get("required", []):
            if req not in instance:
                raise SchemaError(f"{path}: missing required '{req}'")
        if "propertyNames" in schema:
            for key in instance:
                validate(key, schema["propertyNames"], root,
                         f"{path}(key {key!r})")
        props = schema.get("properties", {})
        addl = schema.get("additionalProperties", True)
        for key, value in instance.items():
            if key in props:
                validate(value, props[key], root, f"{path}.{key}")
            elif isinstance(addl, dict):
                validate(value, addl, root, f"{path}.{key}")
            elif addl is False:
                raise SchemaError(f"{path}: unknown field '{key}' rejected "
                                  "(additionalProperties: false)")
    elif stype == "array":
        if not isinstance(instance, list):
            raise SchemaError(f"{path}: expected array")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            raise SchemaError(f"{path}: {len(instance)} items exceeds "
                              f"maxItems {schema['maxItems']}")
        for i, item in enumerate(instance):
            if "items" in schema:
                validate(item, schema["items"], root, f"{path}[{i}]")
    elif stype == "string":
        if not isinstance(instance, str):
            raise SchemaError(f"{path}: expected string")
        if "minLength" in schema and len(instance) < schema["minLength"]:
            raise SchemaError(f"{path}: shorter than {schema['minLength']}")
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            raise SchemaError(f"{path}: longer than {schema['maxLength']}")
        if "pattern" in schema and not re.fullmatch(schema["pattern"],
                                                    instance):
            raise SchemaError(f"{path}: does not match {schema['pattern']}")
        if schema.get("format") == "date-time" and not re.fullmatch(
                r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?"
                r"(Z|[+-]\d{2}:\d{2})", instance):
            raise SchemaError(f"{path}: not an RFC3339 date-time")
    elif stype == "integer":
        if not isinstance(instance, int) or isinstance(instance, bool):
            raise SchemaError(f"{path}: expected integer")
        if "minimum" in schema and instance < schema["minimum"]:
            raise SchemaError(f"{path}: below minimum {schema['minimum']}")
    elif stype == "null":
        if instance is not None:
            raise SchemaError(f"{path}: expected null")


# ------------------------------------------------------------------ layout

class Plane:
    """Paths of one repo's state plane."""

    def __init__(self, repo_root: Path):
        self.repo = repo_root
        self.state = repo_root / STATE_DIRNAME
        self.checkpoint = self.state / "checkpoint.json"
        self.checkpoints = self.state / "checkpoints"
        self.intents = self.state / "intent"
        self.decisions = self.state / "decisions" / "DECISIONS.ndjson"
        self.effects = self.state / "effects"
        self.distillates = self.state / "distillates"
        self.local = self.state / "local"

    def load_schema(self, name: str) -> dict:
        path = (self.repo / ".Doctrine" / "state-plane" / "schemas"
                / f"{name}.schema.json")
        if not path.exists():
            raise StateError(f"schema not found: {path} (is .Doctrine/ "
                             "installed at the repo root?)")
        return load_json(path, "schema")


def safe_intent_path(plane: Plane, intent: str) -> Path:
    """Resolve an intent id to a file, refusing unsafe ids and any path
    escaping the intents directory (path-traversal defense)."""
    if not SAFE_ID_RE.fullmatch(intent):
        raise StateError(f"unsafe intent id {intent!r} (must match "
                         f"{SAFE_ID_RE.pattern})")
    candidate = (plane.intents / f"{intent}.intent.json").resolve()
    base = plane.intents.resolve()
    if base not in candidate.parents:
        raise StateError(f"intent id {intent!r} escapes the intents dir")
    return candidate


_GIT = shutil.which("git")


def git(repo: Path, *args: str) -> str:
    if not _GIT:
        raise StateError("git executable not found on PATH")
    out = subprocess.run([_GIT, *args], cwd=repo, capture_output=True,
                         text=True, check=True, timeout=GIT_TIMEOUT)
    return out.stdout.strip()


def head_commit(repo: Path) -> str:
    return git(repo, "rev-parse", "HEAD")


def worktree_state(repo: Path) -> str:
    return "dirty" if git(repo, "status", "--porcelain") else "clean"


def now_utc() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------------- lease
# Same-worktree write coordination. The lease lives in local/ (gitignored),
# so it never travels between clones — cross-clone concurrency surfaces as
# a chain FORK at pull time and is handled by verify + merge instead.

def check_lease(plane: Plane, session_id: str | None,
                steal: bool = False) -> None:
    """Refuse writes while another session's unexpired lease holds."""
    path = plane.local / "lease.json"
    if not path.exists():
        return
    try:
        lease = load_json(path, "lease")  # bounded, decode-hardened
    except StateError:
        print("warning: corrupt lease file - overwriting", file=sys.stderr)
        return
    if not isinstance(lease, dict):
        print("warning: malformed lease file - overwriting",
              file=sys.stderr)
        return
    holder = lease.get("session_id")
    expires = lease.get("expires_at", 0)
    if holder == session_id or expires <= time.time():
        return
    if steal:
        print(f"warning: lease STOLEN from session '{holder}' "
              f"(held until {lease.get('expires_human', '?')})",
              file=sys.stderr)
        return
    raise StateError(
        f"state plane is leased by session '{holder}' until "
        f"{lease.get('expires_human', '?')} - concurrent writers fork "
        "the chain; wait, or pass --steal to take over deliberately")


def write_lease(plane: Plane, session_id: str | None) -> None:
    plane.local.mkdir(parents=True, exist_ok=True)
    expires = time.time() + LEASE_TTL_SECONDS
    (plane.local / "lease.json").write_bytes(canonical_bytes({
        "session_id": session_id or "(anonymous)",
        "host": socket.gethostname(),
        "acquired_at": now_utc(),
        "expires_at": expires,
        "expires_human": _dt.datetime.fromtimestamp(
            expires, _dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }))


# ---------------------------------------------------------------- commands

def _warn_legacy_layout(plane: Plane) -> None:
    """Planes created by pre-0.2.0 builds lived at .doctrine/state/ (which
    case-insensitive filesystems merge into .Doctrine/state/)."""
    for legacy in (plane.repo / ".doctrine" / "state",
                   plane.repo / ".Doctrine" / "state"):
        if (legacy / "checkpoint.json").exists():
            print(f"warning: legacy state plane found at {legacy} - "
                  f"move it to {plane.state} (spec 0.2.0 renamed the "
                  "state root)", file=sys.stderr)
            return


def cmd_init(plane: Plane) -> int:
    _warn_legacy_layout(plane)
    for d in (plane.checkpoints, plane.intents, plane.decisions.parent,
              plane.effects, plane.distillates, plane.local):
        d.mkdir(parents=True, exist_ok=True)
    ignore = plane.local / ".gitignore"
    if not ignore.exists():
        ignore.write_bytes(b"*\n!.gitignore\n")
    print(f"state plane initialized at {plane.state}")
    return 0


def _distillate_files(plane: Plane) -> list[Path]:
    if not plane.distillates.exists():
        return []
    files = [p for p in plane.distillates.iterdir()
             if DISTILLATE_FILE_RE.match(p.name)]
    return sorted(files, key=lambda p: int(p.name.split("-", 1)[0]))


def _unresolved_effect_entries(plane: Plane) -> list[dict]:
    entries: list[dict] = []
    if plane.effects.exists():
        for f in sorted(plane.effects.glob("*.effects.ndjson")):
            for line in read_ndjson_text(f, "effects log").splitlines():
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    entry = {"status": "malformed", "raw": line[:80]}
                if entry.get("status") not in ("confirmed", "compensated"):
                    entries.append(entry)
    return entries


def _graph_index(plane: Plane) -> dict:
    """Index graphify-out/graph.json. Never fabricates freshness: if the
    graph does not carry built_at_commit, it stays null (stale-as-fresh is
    the failure mode STATE.md defends against)."""
    graph = plane.repo / "graphify-out" / "graph.json"
    if not graph.exists():
        return {"built_at_commit": None}
    entry: dict = {"sha256": sha256_file(graph)}
    try:
        built = load_json(graph, "graph").get("built_at_commit")
    except StateError as exc:
        print(f"warning: graph.json unreadable, freshness unknown ({exc})",
              file=sys.stderr)
        built = None
    entry["built_at_commit"] = built if isinstance(built, str) else None
    return entry


def _merge_dead_ends(new_ends: list, pruned_files: list[Path],
                     cap: int = 8) -> tuple[list, int]:
    """Dedupe (approach, why_failed). Priority: the new distillate's own
    ends, then pruned negatives NEWEST first — the oldest are dropped at
    the cap. Corrupt pruned files are reported, not silently skipped."""
    seen, merged = set(), []
    pruned_ends: list = []
    for f in reversed(pruned_files):  # newest pruned first
        try:
            pruned_ends.extend(load_json(f, "distillate")
                               .get("dead_ends", []))
        except StateError as exc:
            print(f"warning: dead_ends lost from corrupt {f.name}: {exc}",
                  file=sys.stderr)
    for end in list(new_ends) + pruned_ends:
        key = (end.get("approach"), end.get("why_failed"))
        if key in seen:
            continue
        seen.add(key)
        merged.append(end)
    return merged[:cap], max(0, len(merged) - cap)


def _scan_secrets(distillate: dict) -> None:
    """Refuse secret-like content in committed state (fail closed)."""
    texts: list[str] = []
    for item in distillate.get("learned", []):
        texts += [item.get("claim", ""), item.get("evidence", "")]
    for end in distillate.get("dead_ends", []):
        texts += [end.get("approach", ""), end.get("why_failed", "")]
    texts += distillate.get("open_threads", [])
    texts += distillate.get("next_actions", [])
    for text in texts:
        for pattern in SECRET_RES:
            if pattern.search(text):
                raise StateError(
                    "distillate text matches a secret pattern "
                    f"({pattern.pattern[:40]}...); state files are "
                    "committed forever - rephrase without the secret")
        for pattern in MARKER_RES:
            if pattern.search(text):
                raise StateError(
                    "distillate text contains an HTML-comment/marker token "
                    f"({pattern.pattern}); it could break out of the "
                    "AGENTS.md managed state block - rephrase without it")


def cmd_checkpoint(plane: Plane, proposal_path: Path,
                   keep: int = DEFAULT_KEEP, steal: bool = False) -> int:
    if keep < 1:
        raise StateError("--keep must be >= 1")
    proposal = load_json(proposal_path, "proposal")
    for field in ("session_id", "control", "distillate"):
        if field not in proposal:
            raise StateError(f"proposal missing '{field}'")
    check_lease(plane, proposal["session_id"], steal)

    at_commit = head_commit(plane.repo)
    created = now_utc()
    session = proposal["session_id"]

    prev_sha, seq = None, 0
    if plane.checkpoint.exists():
        prev_sha = sha256_file(plane.checkpoint)
        seq = load_json(plane.checkpoint, "checkpoint")["seq"] + 1

    # ---- propose/dispose: EVERYTHING validates before ANY write ----
    existing = _distillate_files(plane)
    cut = len(existing) - (keep - 1)
    pruned = existing[:cut] if cut > 0 else []
    pending = plane.distillates / "pending-dead-ends.json"

    dist_body = dict(proposal["distillate"])
    pending_ends = load_json(pending, "pending dead-ends").get(
        "dead_ends", []) if pending.exists() else []
    merged, dropped = _merge_dead_ends(
        list(dist_body.get("dead_ends", [])) + pending_ends, pruned)
    dist_body["dead_ends"] = merged

    distillate = {
        "distillate_version": "1", "seq": seq, "session_id": session,
        "created_at": created, "at_commit": at_commit, **dist_body,
    }
    validate(distillate, plane.load_schema("distillate"))
    _scan_secrets(distillate)
    dist_bytes = canonical_bytes(distillate)
    dist_sha = sha256_bytes(dist_bytes)

    # prospective decisions content, hashed BEFORE writing anything
    decision_lines = [
        canonical_line({
            "at_commit": at_commit, "claim": c["claim"],
            "created_at": created, "evidence": c["evidence"],
            "intents": distillate.get("task_refs", []),
            "seq": seq, "session_id": session,
        }) + "\n"
        for c in distillate.get("learned", [])
        if c.get("kind") == "decision_ref"
    ]
    existing_decisions = plane.decisions.read_bytes() \
        if plane.decisions.exists() else b""
    prospective_decisions = existing_decisions + \
        "".join(decision_lines).encode("utf-8")

    intents_index = {}
    if plane.intents.exists():
        for p in sorted(plane.intents.glob("*.intent.json")):
            stem = p.name.removesuffix(".intent.json")
            if not SAFE_ID_RE.fullmatch(stem):
                raise StateError(f"unsafe intent filename: {p.name}")
            intents_index[stem] = sha256_file(p)
    for intent in proposal["control"].get("active_intents", []):
        if not SAFE_ID_RE.fullmatch(str(intent)):
            raise StateError(f"unsafe intent id in control: {intent!r}")

    checkpoint = {
        "checkpoint_version": "1", "seq": seq, "prev_sha256": prev_sha,
        "created_at": created, "at_commit": at_commit,
        "session_id": session, "worktree": worktree_state(plane.repo),
        "control": proposal["control"],
        "state_index": {
            "intents": intents_index,
            "decisions_sha256": sha256_bytes(prospective_decisions),
            "latest_distillate_sha256": dist_sha,
            "graph": _graph_index(plane),
            "unresolved_effects": len(_unresolved_effect_entries(plane)),
        },
    }
    validate(checkpoint, plane.load_schema("checkpoint"))
    cp_bytes = canonical_bytes(checkpoint)
    cp_sha = sha256_bytes(cp_bytes)

    # ---- write phase: both instances valid, nothing written until now ----
    if dropped:
        print(f"note: {dropped} merged dead_end(s) dropped at the schema "
              "cap of 8 (oldest first)", file=sys.stderr)
    plane.distillates.mkdir(parents=True, exist_ok=True)
    (plane.distillates / f"{seq}-{dist_sha[:12]}.json").write_bytes(
        dist_bytes)
    for f in pruned:
        f.unlink()
    if pending.exists():
        pending.unlink()
    if decision_lines:
        plane.decisions.parent.mkdir(parents=True, exist_ok=True)
        plane.decisions.write_bytes(prospective_decisions)
    plane.checkpoints.mkdir(parents=True, exist_ok=True)
    plane.checkpoint.write_bytes(cp_bytes)
    (plane.checkpoints / f"{seq}-{cp_sha[:12]}.json").write_bytes(cp_bytes)
    write_lease(plane, session)

    print(f"checkpoint {seq} written at {at_commit[:12]} "
          f"({cp_sha[:12]}); distillate {dist_sha[:12]}"
          + (f"; pruned {len(pruned)} distillate(s)" if pruned else ""))
    print(f"remember (STATE.md step 4): git add {STATE_DIRNAME} && "
          f"git commit -m \"state: checkpoint {seq}\"")
    return 0


def verify_findings(plane: Plane) -> list[str]:
    """Full chain + state_index verification; returns findings ([] = OK)."""
    findings: list[str] = []
    files: list[Path] = []
    if plane.checkpoints.exists():
        for p in sorted(plane.checkpoints.iterdir()):
            if p.is_dir() and p.name == "forks":
                continue  # merge-archived fork heads, out of the chain
            if CHECKPOINT_FILE_RE.match(p.name):
                files.append(p)
            elif p.name != ".gitignore":
                kind = "directory" if p.is_dir() else "file"
                findings.append(f"stray {kind} in checkpoints/: {p.name}")
    files.sort(key=lambda p: int(p.name.split("-", 1)[0]))

    # fork detection: concurrent writers (usually two clones reunited by
    # git) produce duplicate seq numbers and/or duplicate predecessors
    by_seq: dict[int, list[str]] = {}
    for f in files:
        by_seq.setdefault(int(f.name.split("-", 1)[0]), []).append(f.name)
    forked = {seq: names for seq, names in by_seq.items()
              if len(names) > 1}
    if forked:
        for seq, names in sorted(forked.items()):
            findings.append(
                f"CHAIN FORKED at seq {seq}: {', '.join(sorted(names))} - "
                "resolve with: doctrine_state merge --loser <file>")
        return findings  # a linear walk is meaningless on a fork

    if plane.checkpoint.exists() and not files:
        findings.append("checkpoint.json exists but checkpoints/ history "
                        "is empty - history wiped or never copied")
        return findings
    if not files:
        return findings  # genuinely empty plane

    schema = plane.load_schema("checkpoint")
    prev_file: Path | None = None
    for f in files:
        try:
            data = load_json(f, "checkpoint")
        except StateError as exc:
            findings.append(str(exc))
            prev_file = f
            continue
        try:
            validate(data, schema)
        except SchemaError as exc:
            findings.append(f"{f.name}: schema: {exc}")
        expected_seq = 0 if prev_file is None else \
            int(prev_file.name.split("-", 1)[0]) + 1
        if data.get("seq") != expected_seq:
            findings.append(f"{f.name}: seq {data.get('seq')} != expected "
                            f"{expected_seq}")
        expected_prev = None if prev_file is None else sha256_file(prev_file)
        if data.get("prev_sha256") != expected_prev:
            findings.append(f"{f.name}: broken chain - prev_sha256 does "
                            "not match predecessor's canonical bytes")
        if f.read_bytes() != canonical_bytes(data):
            findings.append(f"{f.name}: not canonical bytes")
        prev_file = f

    if not plane.checkpoint.exists():
        findings.append("checkpoint.json missing while history exists")
        return findings
    if plane.checkpoint.read_bytes() != prev_file.read_bytes():
        findings.append("checkpoint.json != latest history copy")
        return findings

    current = load_json(plane.checkpoint, "checkpoint")
    idx = current["state_index"]
    actual_decisions = sha256_file(plane.decisions) \
        if plane.decisions.exists() else sha256_bytes(b"")
    if idx["decisions_sha256"] != actual_decisions:
        findings.append("state_index.decisions_sha256 desync")
    dists = _distillate_files(plane)
    have = sha256_file(dists[-1]) if dists else None
    if idx["latest_distillate_sha256"] != have:
        findings.append("state_index.latest_distillate_sha256 desync")
    for intent, sha in (idx.get("intents") or {}).items():
        try:
            p = safe_intent_path(plane, intent)
        except StateError as exc:
            findings.append(str(exc))
            continue
        if not p.exists():
            findings.append(f"intent '{intent}' indexed but missing")
        elif sha256_file(p) != sha:
            findings.append(f"intent '{intent}' hash desync")
    graph_idx = idx.get("graph", {})
    if "sha256" in graph_idx:
        graph = plane.repo / "graphify-out" / "graph.json"
        if not graph.exists():
            findings.append("state_index.graph.sha256 set but graph.json "
                            "missing")
        elif sha256_file(graph) != graph_idx["sha256"]:
            findings.append("state_index.graph hash desync (graph.json "
                            "changed since checkpoint)")
    return findings


def cmd_verify(plane: Plane) -> int:
    findings = verify_findings(plane)
    if findings:
        print(f"VERIFY FAILED ({len(findings)}):")
        for msg in findings:
            print(f"  - {msg}")
        return 1
    n = len([p for p in plane.checkpoints.glob("*.json")
             if CHECKPOINT_FILE_RE.match(p.name)]) \
        if plane.checkpoints.exists() else 0
    if n == 0:
        print("nothing to verify: no checkpoints")
    else:
        print(f"verify OK: {n} checkpoint(s), chain intact, "
              "state_index hashes match")
    return 0


# ---------------------------------------------------------------- hydrate

def _fit(section: str, full: str, degraded: str | None,
         trimmed: list[str]) -> str:
    """Budget a section: full form if it fits; else the spec's degrade-to
    form; else a hard clip of the degraded form. Records the trim."""
    limit = BUDGETS[section] * TOKEN_CHARS
    if len(full) <= limit:
        return full
    trimmed.append(section)
    text = degraded if degraded is not None else full
    if len(text) <= limit:
        return text
    return text[:limit].rsplit("\n", 1)[0] + "\n[clipped]"


def _extract_sections(md: str, headings: list[str]) -> str:
    out: list[str] = []
    keep = False
    for line in md.splitlines():
        if line.startswith("## "):
            keep = any(h in line for h in headings)
        if keep:
            out.append(line)
    return "\n".join(out).strip()


def _stale_prefix(artifact_commit: str | None, head: str,
                  stale: list[str], label: str) -> str:
    if artifact_commit and artifact_commit != head \
            and not head.startswith(artifact_commit):
        stale.append(label)
        return f"STALE@{artifact_commit[:12]} "
    return ""


def build_bundle_body(plane: Plane) -> tuple[str, list[str], list[str]]:
    """Deterministic bundle body (no timestamps). Returns
    (body, trimmed[], stale[])."""
    cp = load_json(plane.checkpoint, "checkpoint")
    head = head_commit(plane.repo)
    trimmed: list[str] = []
    stale: list[str] = []
    parts: list[str] = []

    # 1 invariants — never trimmed (HYDRATION.md: "earlier sections are
    # never trimmed"), sourced from REPO.md/ROLE.md else the doctrine slice
    sources = [plane.repo / "REPO.md", plane.repo / "ROLE.md"]
    inv = "\n\n".join(_extract_sections(p.read_text("utf-8"), ["Invariant"])
                      for p in sources if p.exists()).strip()
    if not inv:
        doctrine = plane.repo / ".Doctrine.md"
        if doctrine.exists():
            inv = _extract_sections(doctrine.read_text("utf-8"),
                                    ["Prime Directive", "Non-Negotiables"])
    parts.append("## Invariants\n" + (inv or "(no invariant source found)"))

    # 2 control — never trimmed; staleness flagged like any artifact
    control = dict(cp["control"])
    prefix = _stale_prefix(cp["at_commit"], head, stale, "control")
    parts.append(
        "## Control\n"
        f"{prefix}seq={cp['seq']} at_commit={cp['at_commit'][:12]} "
        f"worktree={cp['worktree']} role={control['role']} "
        f"phase={control['phase']} ponytail={control['ponytail_mode']} "
        f"gates={','.join(control.get('gates_passed', [])) or '-'}")

    # 3 active intents — degrade: titles + acceptance criteria only
    full_lines, deg_lines = [], []
    for intent in control.get("active_intents", []):
        p = safe_intent_path(plane, str(intent))
        if not p.exists():
            full_lines.append(f"- {intent}: MISSING intent file")
            deg_lines.append(f"- {intent}: MISSING intent file")
            continue
        data = load_json(p, "intent")
        prefix = _stale_prefix(data.get("at_commit"), head, stale,
                               f"intent:{intent}")
        title = data.get("title", intent)
        acc = data.get("acceptance_criteria", [])
        head_line = f"- {prefix}**{intent}** - {title}"
        ac_lines = [f"  - AC: {a}" for a in acc]
        deg_lines += [head_line, *ac_lines]
        extra = [f"  - {k}: {data[k]}" for k in ("description",
                                                 "constraints") if k in data]
        full_lines += [head_line, *ac_lines, *extra]
    empty = "(no active intents)"
    parts.append("## Active intents\n" + _fit(
        "intents", "\n".join(full_lines) or empty,
        "\n".join(deg_lines) or empty, trimmed))

    # 4 distillate — latest, + dead_ends merged from the last K retained
    # (HYDRATION.md); degrade: dead_ends + open_threads ONLY (the
    # anti-thought-drift payload survives first)
    dists = _distillate_files(plane)
    if dists:
        d = load_json(dists[-1], "distillate")
        merged_ends, seen = [], set()
        for f in reversed(dists):  # newest first across ALL retained
            for e in load_json(f, "distillate").get("dead_ends", []):
                key = (e.get("approach"), e.get("why_failed"))
                if key not in seen:
                    seen.add(key)
                    merged_ends.append(e)
        prefix = _stale_prefix(d.get("at_commit"), head, stale, "distillate")
        core = [f"{prefix}(distillate seq {d['seq']})", "Dead ends:"]
        core += [f"- {e['approach']} -> {e['why_failed']}"
                 for e in merged_ends]
        core.append("Open threads:")
        core += [f"- {t}" for t in d.get("open_threads", [])]
        full = list(core)
        full.append("Learned:")
        full += [f"- [{i['kind']}/{i['confidence']}] {i['claim']} "
                 f"(evidence: {i['evidence']})"
                 for i in d.get("learned", [])]
        full.append("Next actions:")
        full += [f"- {n}" for n in d.get("next_actions", [])]
        parts.append("## Distillate\n" + _fit(
            "distillate", "\n".join(full), "\n".join(core), trimmed))
    else:
        parts.append("## Distillate\n(no distillates)")

    # 5 decisions — scoped to active intents; degrade: ids + one line
    active = set(control.get("active_intents", []))
    full_lines, deg_lines = [], []
    if plane.decisions.exists() and active:
        raw_lines = read_ndjson_text(plane.decisions,
                                     "decisions log").splitlines()
        for n, raw in enumerate(raw_lines, 1):
            if not raw.strip():
                continue
            try:
                entry = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise StateError(f"decisions log line {n} unparseable "
                                 f"({exc}) - the log is hash-verified, so "
                                 "this is committed corruption") from exc
            if active & set(entry.get("intents", [])):
                full_lines.append(f"- (seq {entry['seq']}) {entry['claim']} "
                                  f"[{entry['evidence']}]")
                deg_lines.append(f"- D{entry['seq']}: "
                                 f"{entry['claim'][:80]}")
    empty = "(no active intents - decisions omitted)" if not active \
        else "(no matching decisions)"
    parts.append("## Decisions\n" + _fit(
        "decisions", "\n".join(full_lines) or empty,
        "\n".join(deg_lines) or empty, trimmed))

    # 6 graph — degrade: god nodes + EXTRACTED lines only
    report = plane.repo / "graphify-out" / "GRAPH_REPORT.md"
    if report.exists():
        built = cp["state_index"]["graph"].get("built_at_commit")
        prefix = _stale_prefix(built, head, stale, "graph")
        text = report.read_text("utf-8")
        key_lines = [ln for ln in text.splitlines()
                     if "god" in ln.lower() or "EXTRACTED" in ln]
        parts.append("## Graph\n" + _fit(
            "graph", prefix + text,
            prefix + ("\n".join(key_lines) or text.split("\n\n")[0]),
            trimmed))
    else:
        parts.append("## Graph\n(no graph built)")

    # 7 unresolved effects — degrade: count + most recent entry
    entries = _unresolved_effect_entries(plane)
    if entries:
        full = [f"unresolved effects: {len(entries)}"]
        full += [f"- {e.get('status', '?')}: "
                 f"{e.get('action', e.get('raw', ''))[:80]}"
                 for e in entries]
        deg = (f"unresolved effects: {len(entries)}\nmost recent: "
               f"{entries[-1].get('action', entries[-1].get('raw', ''))[:80]}")
        parts.append("## Unresolved effects\n" + _fit(
            "effects", "\n".join(full), deg, trimmed))
    else:
        parts.append("## Unresolved effects\nunresolved effects: 0")

    body = "\n\n".join(parts) + "\n"
    return body, trimmed, stale


AGENTS_BEGIN = ("<!-- doctrine:state:begin "
                "(generated by doctrine_state hydrate; do not edit) -->")
AGENTS_END = "<!-- doctrine:state:end -->"


def emit_agents_block(plane: Plane, deterministic_header: str,
                      body: str) -> None:
    """Inject/replace the marker-managed state block in root AGENTS.md.
    The block is deterministic (no timestamps), so unchanged state emits
    byte-identical files. The compiler owns the content between markers;
    the adapter owns the location (HYDRATION.md adapter-emit rule).
    Fail-closed guards: the body must carry no HTML-comment tokens (block
    breakout = instruction injection into a committed, auto-read file),
    and the existing file must have exactly one begin/end pair, in order.
    Content outside the markers is preserved byte-exactly (incl. CRLF)."""
    agents = plane.repo / "AGENTS.md"
    if not agents.exists():
        print("note: no AGENTS.md at repo root - state block not emitted "
              "(create one from .Doctrine/adapters/AGENTS.md to enable)")
        return
    if re.search(r"<!--|-->", body):
        raise StateError(
            "bundle body contains an HTML-comment token ('<!--'/'-->') - "
            "emitting would break the AGENTS.md managed block; rephrase "
            "the offending state text (distillate, intent, or invariant "
            "source)")
    block = (f"{AGENTS_BEGIN}\n<!-- doctrine:hydration "
             f"{deterministic_header} -->\n\n{body}{AGENTS_END}\n")
    try:
        text = agents.read_bytes().decode("utf-8")
    except UnicodeDecodeError as exc:
        raise StateError(f"AGENTS.md is not valid UTF-8 ({exc})") from exc
    n_begin, n_end = text.count(AGENTS_BEGIN), text.count(AGENTS_END)
    if n_begin == 0 and n_end == 0:
        if not text.strip():
            new = block
        else:
            sep = "\r\n\r\n" if "\r\n" in text else "\n\n"
            new = text.rstrip("\r\n") + sep + block
    elif n_begin == 1 and n_end == 1 \
            and text.index(AGENTS_BEGIN) < text.index(AGENTS_END):
        pre = text[:text.index(AGENTS_BEGIN)]
        post = text[text.index(AGENTS_END) + len(AGENTS_END):]
        new = pre + block + post.lstrip("\r\n")
    else:
        raise StateError(
            f"AGENTS.md marker integrity: expected exactly one "
            f"begin/end pair in order, found {n_begin} begin / {n_end} "
            "end - repair the markers by hand before emitting")
    if new != text:
        agents.write_bytes(new.encode("utf-8"))
        print(f"state block emitted into {agents}")
    else:
        print("AGENTS.md state block already current")


def cmd_hydrate(plane: Plane, check: bool = False,
                if_present: bool = False, emit_agents: bool = False) -> int:
    if not plane.checkpoint.exists():
        if if_present:
            print("no state plane checkpoint - nothing to hydrate")
            return 0
        print("no checkpoint.json - run checkpoint first", file=sys.stderr)
        return 1
    findings = verify_findings(plane)  # never hydrate from a broken chain
    if findings:
        print("refusing to hydrate: chain verification failed "
              f"({len(findings)} finding(s); run verify)", file=sys.stderr)
        return 1
    body1, trimmed, stale = build_bundle_body(plane)
    sha1 = sha256_bytes(body1.encode("utf-8"))
    if check:
        body2, _, _ = build_bundle_body(plane)
        sha2 = sha256_bytes(body2.encode("utf-8"))
        if sha1 != sha2:
            print(f"DETERMINISM FAILED: {sha1[:12]} != {sha2[:12]}")
            return 1
        print(f"hydrate --check OK: bundle_sha256 {sha1[:12]} stable")
        if emit_agents:
            print("note: --emit-agents is ignored with --check "
                  "(check never writes)")
        return 0

    cp = load_json(plane.checkpoint, "checkpoint")
    header_fields = {
        "at_commit": cp["at_commit"], "bundle_sha256": sha1,
        "checkpoint_seq": cp["seq"],
        "stale": sorted(stale), "trimmed": sorted(trimmed),
    }
    header = canonical_line({**header_fields, "generated_at": now_utc()})
    plane.local.mkdir(parents=True, exist_ok=True)
    out = plane.local / "hydration.bundle.md"
    out.write_bytes((f"<!-- doctrine:hydration {header} -->\n\n" + body1)
                    .encode("utf-8"))
    print(f"bundle written: {out} ({len(body1) // TOKEN_CHARS} tokens est., "
          f"sha {sha1[:12]}"
          + (f", trimmed: {','.join(sorted(trimmed))}" if trimmed else "")
          + (f", STALE: {','.join(sorted(stale))}" if stale else "") + ")")
    if emit_agents:
        emit_agents_block(plane, canonical_line(header_fields), body1)
    return 0


def cmd_prune(plane: Plane, keep: int) -> int:
    # no lease check: prune removes retained distillates (chain-safe -
    # they are not chain links) and stages their dead_ends into the
    # pending file consumed by the next (lease-guarded) checkpoint
    if keep < 1:
        raise StateError("--keep must be >= 1")
    files = _distillate_files(plane)
    victims = files[:-keep] if len(files) > keep else []
    if not victims:
        print(f"nothing to prune ({len(files)} distillate(s) <= keep "
              f"{keep})")
        return 0
    print(f"pruning {len(victims)} distillate(s); their dead_ends will "
          "merge into the NEXT checkpoint's distillate:")
    ends, _ = _merge_dead_ends([], victims, cap=10 ** 6)
    pending = plane.distillates / "pending-dead-ends.json"
    pending.write_bytes(canonical_bytes({"dead_ends": ends}))
    for f in victims:
        print(f"  - {f.name}")
        f.unlink()
    print(f"merged negatives staged in {pending.name}")
    return 0


def cmd_merge(plane: Plane, loser_name: str) -> int:
    """Resolve a leaf fork: archive the losing head (history preserved
    under forks/, out of the chain scan), repoint checkpoint.json to the
    winning head, and salvage the loser's dead_ends into the pending
    file the next checkpoint consumes. The loser's learned/open_threads
    are PRINTED for honest re-proposal — claims are never auto-grafted.
    No lease check: a fork means the lease already failed its job."""
    if not CHECKPOINT_FILE_RE.match(loser_name):
        raise StateError(f"'{loser_name}' is not a checkpoint filename "
                         "(<seq>-<12hex>.json)")
    loser_path = plane.checkpoints / loser_name
    if not loser_path.exists():
        raise StateError(f"no such checkpoint: {loser_name}")
    loser = load_json(loser_path, "checkpoint")
    if not isinstance(loser, dict) \
            or not isinstance(loser.get("seq"), int) \
            or not isinstance(loser.get("state_index"), dict):
        raise StateError(f"{loser_name} is not a well-formed checkpoint - "
                         "merge cannot reason about it; repair or remove "
                         "it by hand")
    seq = loser["seq"]

    files = [p for p in plane.checkpoints.iterdir()
             if CHECKPOINT_FILE_RE.match(p.name)]
    siblings = [p for p in files
                if int(p.name.split("-", 1)[0]) == seq
                and p.name != loser_name]
    if not siblings:
        raise StateError(f"seq {seq} is not forked - nothing to merge")
    loser_sha = sha256_file(loser_path)

    def _prev_of(p: Path) -> str | None:
        data = load_json(p, "checkpoint")
        return data.get("prev_sha256") if isinstance(data, dict) else None

    children = [p.name for p in files if _prev_of(p) == loser_sha]
    if children:
        raise StateError(f"{loser_name} has descendant(s) "
                         f"{', '.join(sorted(children))} - forks merge "
                         "from the LEAF; merge those first")

    # archive the losing head + its distillate (never delete history)
    forks = plane.checkpoints / "forks"
    forks.mkdir(parents=True, exist_ok=True)
    loser_path.rename(forks / loser_name)
    dist_sha = loser["state_index"].get("latest_distillate_sha256")
    survivors = [p for p in plane.checkpoints.iterdir()
                 if CHECKPOINT_FILE_RE.match(p.name)]
    referenced = set()
    for p in survivors:
        data = load_json(p, "checkpoint")
        if isinstance(data, dict):
            referenced.add(data.get("state_index", {})
                           .get("latest_distillate_sha256"))
    # at the forked seq, exactly the survivor-referenced distillates may
    # remain — any other same-seq file (the loser's, or an orphan from
    # the fork) would leave _distillate_files ambiguous and desync verify
    salvage: dict = {}
    for d in list(_distillate_files(plane)):
        if int(d.name.split("-", 1)[0]) != seq:
            continue
        d_sha = sha256_file(d)
        if d_sha in referenced:
            continue
        if d_sha == dist_sha:
            salvage = load_json(d, "distillate")
        dist_forks = plane.distillates / "forks"
        dist_forks.mkdir(parents=True, exist_ok=True)
        d.rename(dist_forks / d.name)
    if dist_sha in referenced:
        print("note: loser's distillate is shared with a surviving head - "
              "left in place, nothing to salvage")
    elif not salvage:
        print("note: loser's distillate not found (already pruned?) - "
              "nothing to salvage")

    # repoint checkpoint.json to the winning head if it named the loser
    remaining = sorted(
        (p for p in plane.checkpoints.iterdir()
         if CHECKPOINT_FILE_RE.match(p.name)),
        key=lambda p: int(p.name.split("-", 1)[0]))
    head = remaining[-1] if remaining else None
    if head and (not plane.checkpoint.exists()
                 or plane.checkpoint.read_bytes() != head.read_bytes()):
        plane.checkpoint.write_bytes(head.read_bytes())

    # salvage: dead_ends survive mechanically via the pending file —
    # scanned NOW so a poisoned loser cannot soft-lock future checkpoints
    ends, rejected = [], 0
    for end in salvage.get("dead_ends", []):
        try:
            _scan_secrets({"dead_ends": [end]})
            ends.append(end)
        except StateError:
            rejected += 1
    if rejected:
        print(f"warning: {rejected} salvaged dead_end(s) REJECTED by the "
              "secret/marker scan and NOT staged", file=sys.stderr)
    if ends:
        pending = plane.distillates / "pending-dead-ends.json"
        existing = load_json(pending, "pending dead-ends").get(
            "dead_ends", []) if pending.exists() else []
        merged, _ = _merge_dead_ends(existing + ends, [], cap=10 ** 6)
        pending.write_bytes(canonical_bytes({"dead_ends": merged}))

    print(f"merged: {loser_name} archived under checkpoints/forks/; "
          f"chain head is {head.name if head else '(empty)'}"
          + (f"; {len(ends)} dead_end(s) staged for the next checkpoint"
             if ends else ""))
    for key in ("learned", "open_threads", "next_actions"):
        items = salvage.get(key, [])
        if items:
            print(f"loser's {key} (re-propose honestly in your next "
                  "checkpoint if still true):")
            for item in items:
                text = item.get("claim", item) if isinstance(item, dict) \
                    else item
                print(f"  - {text}")
    # post-merge verify is mandatory, not advisory (security MG-1)
    post = verify_findings(plane)
    if post:
        print(f"MERGE VERIFY FAILED ({len(post)}):")
        for msg in post:
            print(f"  - {msg}")
        return 1
    print("merge verify OK - chain is linear again; commit the merge")
    return 0


def cmd_status(plane: Plane) -> int:
    _warn_legacy_layout(plane)
    if not plane.checkpoint.exists():
        print("no state plane (run: init, then checkpoint)")
        return 0
    findings = verify_findings(plane)
    if findings:
        print(f"WARNING: chain verification fails ({len(findings)} "
              "finding(s)) - run verify. Status below is UNVERIFIED.")
    cp = load_json(plane.checkpoint, "checkpoint")
    dists = _distillate_files(plane)
    print(f"checkpoint seq {cp['seq']} @ {cp['at_commit'][:12]} "
          f"({cp['worktree']}) session {cp['session_id']}")
    print(f"role={cp['control']['role']} phase={cp['control']['phase']} "
          f"intents={','.join(cp['control']['active_intents']) or '-'}")
    print(f"distillates: {len(dists)} | unresolved effects: "
          f"{cp['state_index']['unresolved_effects']}")
    return 0


# -------------------------------------------------------------------- main

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="doctrine_state",
                                     description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path.cwd(),
                        help="repo root (default: cwd)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    p_cp = sub.add_parser("checkpoint")
    p_cp.add_argument("--proposal", type=Path, required=True)
    p_cp.add_argument("--keep", type=int, default=DEFAULT_KEEP)
    p_cp.add_argument("--steal", action="store_true",
                      help="take over another session's unexpired lease")
    sub.add_parser("verify")
    p_mg = sub.add_parser("merge")
    p_mg.add_argument("--loser", required=True,
                      help="forked checkpoint filename to archive "
                           "(<seq>-<12hex>.json)")
    p_hy = sub.add_parser("hydrate")
    p_hy.add_argument("--check", action="store_true")
    p_hy.add_argument("--if-present", action="store_true",
                      help="exit 0 quietly when no checkpoint exists "
                           "(for session hooks)")
    p_hy.add_argument("--emit-agents", action="store_true",
                      help="also inject the bundle into root AGENTS.md "
                           "between doctrine:state markers")
    p_pr = sub.add_parser("prune")
    p_pr.add_argument("--keep", type=int, default=DEFAULT_KEEP)
    sub.add_parser("status")
    args = parser.parse_args(argv)

    plane = Plane(args.root.resolve())
    try:
        if args.command == "init":
            return cmd_init(plane)
        if args.command == "checkpoint":
            return cmd_checkpoint(plane, args.proposal, args.keep,
                                  args.steal)
        if args.command == "verify":
            return cmd_verify(plane)
        if args.command == "merge":
            return cmd_merge(plane, args.loser)
        if args.command == "hydrate":
            return cmd_hydrate(plane, args.check, args.if_present,
                               args.emit_agents)
        if args.command == "prune":
            return cmd_prune(plane, args.keep)
        if args.command == "status":
            return cmd_status(plane)
    except (SchemaError, StateError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as exc:
        print(f"git failed: {exc.stderr.strip()}", file=sys.stderr)
        return 2
    except subprocess.TimeoutExpired:
        print(f"git timed out after {GIT_TIMEOUT}s", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
