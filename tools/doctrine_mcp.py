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
"""doctrine_mcp — stdlib-only MCP server (stdio) for the Doctrine tooling.

Exposes the enforcement suite as MCP tools so ANY MCP-capable agent
(Claude Code, Codex, Cursor, Windsurf, Copilot, Gemini CLI, ...) can run
them natively: corpus lint, state-plane operations, gold-build gates.

Transport: newline-delimited JSON-RPC 2.0 over stdio (the MCP stdio
transport). Handles initialize, notifications/initialized, ping,
tools/list, tools/call. Logs to stderr only; stdout carries protocol
messages exclusively. A tool failure returns isError content - the
server itself never crashes on a bad call.

Register (examples - see .Doctrine/05-packaging.md for the full matrix):
  Claude Code:  claude mcp add doctrineos -- python tools/doctrine_mcp.py
  Codex:        [mcp_servers.doctrineos] in config.toml
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import doctrine_gold  # noqa: E402
import doctrine_lint  # noqa: E402
import doctrine_state  # noqa: E402

PROTOCOL_VERSION = "2025-06-18"
KNOWN_PROTOCOLS = {"2024-11-05", "2025-03-26", "2025-06-18"}
SERVER_INFO = {"name": "doctrineos", "version": "0.6.12"}
MAX_LINE_BYTES = 5_000_000
NO_ARGS = {"type": "object", "properties": {}, "additionalProperties": False}
REQUIRED_ARGS = {"state_checkpoint": ["proposal_json"],
                 "gold_record": ["proposal_json"], "gold_check": ["tag"]}

TOOLS = [
    {"name": "doctrine_lint",
     "description": "Run the doctrine corpus self-consistency gate "
                    "(references, formats, counts, version sync, canonical "
                    "examples). Exit text lists findings; clean = ok.",
     "inputSchema": NO_ARGS},
    {"name": "state_status",
     "description": "One-screen state-plane summary (checkpoint seq, "
                    "commit, intents, unresolved effects).",
     "inputSchema": NO_ARGS},
    {"name": "state_verify",
     "description": "Verify the checkpoint hash chain and every "
                    "state_index target. Run before trusting state.",
     "inputSchema": NO_ARGS},
    {"name": "state_hydrate",
     "description": "Compile the deterministic hydration bundle (verifies "
                    "the chain first). check=true only asserts "
                    "determinism; emit_agents=true also maintains the "
                    "marker-managed AGENTS.md block.",
     "inputSchema": {"type": "object", "properties": {
         "check": {"type": "boolean"},
         "emit_agents": {"type": "boolean"}},
         "additionalProperties": False}},
    {"name": "state_checkpoint",
     "description": "Write a state-plane checkpoint from a proposal "
                    "(propose->dispose; see state-plane/STATE.md caps). "
                    "proposal_json is the JSON text of {session_id, "
                    "control, distillate}.",
     "inputSchema": {"type": "object",
                     "properties": {"proposal_json": {"type": "string"}},
                     "required": ["proposal_json"],
                     "additionalProperties": False}},
    {"name": "gold_check",
     "description": "The deploy gate: verify a Gold Build record (schema, "
                    "artifact/verdict/sign-off re-hash, chain topology, "
                    "tag->commit). Deploy only on 'check OK'.",
     "inputSchema": {"type": "object",
                     "properties": {"tag": {"type": "string"}},
                     "required": ["tag"], "additionalProperties": False}},
    {"name": "gold_record",
     "description": "Promote a candidate to GOLD (enterprise profile). "
                    "proposal_json is the JSON text of the gold proposal; "
                    "refused without council verdict + sign-offs + human "
                    "approval on disk.",
     "inputSchema": {"type": "object",
                     "properties": {"proposal_json": {"type": "string"}},
                     "required": ["proposal_json"],
                     "additionalProperties": False}},
]


def _run(func, *args) -> tuple[int, str]:
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = func(*args)
    except (doctrine_state.SchemaError, doctrine_state.StateError) as exc:
        return 2, out.getvalue() + f"error: {exc}"
    except Exception as exc:  # server must survive any tool failure
        return 2, out.getvalue() + f"unexpected error: {exc!r}"
    return code, out.getvalue()


def _with_proposal(text: str, func, root: Path) -> tuple[int, str]:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                     encoding="utf-8") as fh:
        fh.write(text)
        tmp = Path(fh.name)
    try:
        return _run(func, root, tmp)
    finally:
        tmp.unlink(missing_ok=True)


def call_tool(root: Path, name: str, args: dict) -> tuple[int, str]:
    plane = doctrine_state.Plane(root)
    if name == "doctrine_lint":
        return _run(doctrine_lint.main, [str(root)])
    if name == "state_status":
        return _run(doctrine_state.cmd_status, plane)
    if name == "state_verify":
        return _run(doctrine_state.cmd_verify, plane)
    if name == "state_hydrate":
        return _run(doctrine_state.cmd_hydrate, plane,
                    bool(args.get("check")), False,
                    bool(args.get("emit_agents")))
    if name == "state_checkpoint":
        return _with_proposal(
            args["proposal_json"],
            lambda r, p: doctrine_state.cmd_checkpoint(
                doctrine_state.Plane(r), p), root)
    if name == "gold_check":
        return _run(doctrine_gold.cmd_check, root, str(args["tag"]))
    if name == "gold_record":
        return _with_proposal(args["proposal_json"],
                              doctrine_gold.cmd_record, root)
    raise KeyError(name)


def handle(root: Path, message: dict) -> dict | None:
    method = message.get("method")
    msg_id = message.get("id")
    if method == "initialize":
        params = message.get("params")
        client_proto = params.get("protocolVersion") \
            if isinstance(params, dict) else None
        return {"jsonrpc": "2.0", "id": msg_id, "result": {
            "protocolVersion": client_proto
            if client_proto in KNOWN_PROTOCOLS else PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO}}
    if method in ("notifications/initialized", "notifications/cancelled"):
        return None
    if method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = message.get("params")
        if not isinstance(params, dict):
            return {"jsonrpc": "2.0", "id": msg_id, "error": {
                "code": -32602, "message": "params must be an object"}}
        name = params.get("name", "")
        args = params.get("arguments") or {}
        if not isinstance(args, dict):
            return {"jsonrpc": "2.0", "id": msg_id, "error": {
                "code": -32602, "message": "arguments must be an object"}}
        if name not in {t["name"] for t in TOOLS}:
            return {"jsonrpc": "2.0", "id": msg_id, "error": {
                "code": -32602, "message": f"unknown tool: {name}"}}
        missing = [a for a in REQUIRED_ARGS.get(name, [])
                   if not isinstance(args.get(a), str)]
        if missing:
            return {"jsonrpc": "2.0", "id": msg_id, "error": {
                "code": -32602,
                "message": f"{name}: missing/invalid argument(s): "
                           f"{', '.join(missing)}"}}
        code, text = call_tool(root, name, args)
        return {"jsonrpc": "2.0", "id": msg_id, "result": {
            "content": [{"type": "text",
                         "text": text.strip() or f"(exit {code})"}],
            "isError": code != 0}}
    if msg_id is not None:
        return {"jsonrpc": "2.0", "id": msg_id, "error": {
            "code": -32601, "message": f"method not found: {method}"}}
    return None


def serve(root: Path) -> int:
    print(f"doctrineos MCP server on {root}", file=sys.stderr)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        if len(line.encode("utf-8", "replace")) > MAX_LINE_BYTES:
            print(json.dumps({"jsonrpc": "2.0", "id": None, "error": {
                "code": -32700,
                "message": f"line exceeds {MAX_LINE_BYTES} bytes"}}),
                flush=True)
            continue
        try:
            message = json.loads(line)
        except (json.JSONDecodeError, RecursionError):
            print(json.dumps({"jsonrpc": "2.0", "id": None, "error": {
                "code": -32700, "message": "parse error"}}), flush=True)
            continue
        if not isinstance(message, dict):
            # includes JSON-RPC batch arrays, which MCP stdio does not use
            print(json.dumps({"jsonrpc": "2.0", "id": None, "error": {
                "code": -32600,
                "message": "request must be a single JSON object"}}),
                flush=True)
            continue
        try:
            reply = handle(root, message)
        except Exception as exc:  # the serve loop itself never dies
            reply = {"jsonrpc": "2.0", "id": message.get("id"), "error": {
                "code": -32603, "message": f"internal error: {exc!r}"}}
        if reply is not None:
            print(json.dumps(reply), flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(prog="doctrine_mcp")
    parser.add_argument("--root", type=Path, default=Path.cwd(),
                        help="repo root the tools operate on")
    args = parser.parse_args(argv)
    return serve(args.root.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
