# Copyright (C) 2025 Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)
#
# This file is part of MAPLE - Multi Agent Protocol Language Engine.
#
# MAPLE - Multi Agent Protocol Language Engine is free software: you can
# redistribute it and/or modify it under the terms of the GNU Affero General
# Public License as published by the Free Software Foundation, either version
# 3 of the License, or (at your option) any later version.
# MAPLE - Multi Agent Protocol Language Engine is distributed in the hope that
# it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty
# of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero
# General Public License for more details. You should have received a copy of
# the GNU Affero General Public License along with MAPLE - Multi Agent Protocol
# Language Engine. If not, see <https://www.gnu.org/licenses/>.

"""MCP tool discovery and integration for MAPLE autonomous agents."""

import asyncio
import dataclasses
import inspect
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Mapping, Optional

from ..core.result import Result
from .tools import Tool, ToolRegistry

logger = logging.getLogger(__name__)

# A discovered MCP tool name is UNTRUSTED (an external server names it).
# Reduce it to a safe
# identifier before it becomes a registry key or lands in a rendered tool list.
_UNSAFE_TOOL = re.compile(r"[^A-Za-z0-9_.\-]")

# A host authorization callback: given a discovered tool (and its server id)
# return True to allow registration, False to REJECT it. Lets a host apply a
# default-deny / classification
# policy at the trust boundary instead of registering an untrusted server's tools as-is.
ToolPolicy = Callable[[Tool, Optional[str]], bool]

MAX_DISCOVERED_TOOLS = 64
MAX_TOOL_DESCRIPTION = 4096
MAX_TOOL_SCHEMA_BYTES = 65_536
MAX_SCHEMA_DEPTH = 16
MAX_SCHEMA_ITEMS = 256


def sanitize_tool_name(name: str, max_len: int = 64) -> str:
    """Reduce an untrusted MCP tool name to a safe identifier.

    The identifier uses alphanumeric characters plus ``_ . -`` and is length
    bounded. This prevents control-byte/newline injection into a registry key
    or rendered tool list, and limits hostile server names.
    """
    return _UNSAFE_TOOL.sub("", str(name or ""))[:max_len]


def _run_async(value):
    """Resolve an awaitable from sync discovery without nesting an event loop."""
    if not inspect.isawaitable(value):
        return value
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(value)
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, value).result(timeout=60)


def _bounded_json(
    value: Any, *, max_bytes: int, label: str
) -> Result[None, Dict[str, Any]]:
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        return Result.err(
            {"errorType": "MCP_DESCRIPTOR_INVALID", "message": f"{label}: {exc}"}
        )
    if len(encoded) > max_bytes:
        return Result.err(
            {
                "errorType": "MCP_DESCRIPTOR_TOO_LARGE",
                "message": f"{label} exceeds the configured size limit",
            }
        )
    return Result.ok(None)


def _bounded_schema(
    value: Any, *, depth: int = 0, items: int = 0
) -> Result[None, Dict[str, Any]]:
    """Bound untrusted schema shape before it reaches a MAPLE Tool."""
    if depth > MAX_SCHEMA_DEPTH:
        return Result.err(
            {
                "errorType": "MCP_SCHEMA_TOO_DEEP",
                "message": "MCP schema nesting is too deep",
            }
        )
    if isinstance(value, dict):
        if len(value) > MAX_SCHEMA_ITEMS or items + len(value) > MAX_SCHEMA_ITEMS:
            return Result.err(
                {
                    "errorType": "MCP_SCHEMA_TOO_LARGE",
                    "message": "MCP schema has too many items",
                }
            )
        for key, child in value.items():
            if not isinstance(key, str) or len(key) > 256:
                return Result.err(
                    {
                        "errorType": "MCP_SCHEMA_INVALID",
                        "message": "MCP schema keys are invalid",
                    }
                )
            if key == "pattern":
                return Result.err(
                    {
                        "errorType": "MCP_SCHEMA_UNSUPPORTED",
                        "message": "MCP schemas with pattern are not supported",
                    }
                )
            child_result = _bounded_schema(
                child, depth=depth + 1, items=items + len(value)
            )
            if child_result.is_err():
                return child_result
    elif isinstance(value, list):
        if len(value) > MAX_SCHEMA_ITEMS or items + len(value) > MAX_SCHEMA_ITEMS:
            return Result.err(
                {
                    "errorType": "MCP_SCHEMA_TOO_LARGE",
                    "message": "MCP schema has too many items",
                }
            )
        for child in value:
            child_result = _bounded_schema(
                child, depth=depth + 1, items=items + len(value)
            )
            if child_result.is_err():
                return child_result
    return Result.ok(None)


def _validate_descriptor(
    descriptor: Any, seen_names: set
) -> Result[Dict[str, Any], Dict[str, Any]]:
    if not isinstance(descriptor, Mapping):
        return Result.err(
            {
                "errorType": "MCP_DESCRIPTOR_INVALID",
                "message": "MCP tool descriptor must be an object",
            }
        )
    name = descriptor.get("name")
    if not isinstance(name, str) or not name or len(name) > 64:
        return Result.err(
            {
                "errorType": "MCP_DESCRIPTOR_INVALID",
                "message": "MCP tool name is invalid",
            }
        )
    safe_name = sanitize_tool_name(name)
    if safe_name != name or not safe_name:
        return Result.err(
            {
                "errorType": "MCP_DESCRIPTOR_INVALID",
                "message": "MCP tool name contains unsupported characters",
            }
        )
    if safe_name in seen_names:
        return Result.err(
            {
                "errorType": "MCP_DESCRIPTOR_DUPLICATE",
                "message": f'MCP tool name "{safe_name}" is duplicated',
            }
        )
    description = descriptor.get("description", "")
    if not isinstance(description, str) or len(description) > MAX_TOOL_DESCRIPTION:
        return Result.err(
            {
                "errorType": "MCP_DESCRIPTOR_INVALID",
                "message": f'MCP tool "{safe_name}" description is invalid',
            }
        )
    schema = descriptor.get("inputSchema")
    if not isinstance(schema, dict) or schema.get("type") != "object":
        return Result.err(
            {
                "errorType": "MCP_SCHEMA_INVALID",
                "message": (
                    f'MCP tool "{safe_name}" inputSchema must be an object schema'
                ),
            }
        )
    for label, candidate in (
        ("inputSchema", schema),
        ("outputSchema", descriptor.get("outputSchema")),
    ):
        if candidate is None:
            continue
        if not isinstance(candidate, dict):
            return Result.err(
                {
                    "errorType": "MCP_SCHEMA_INVALID",
                    "message": f"MCP tool {safe_name} {label} must be an object",
                }
            )
        size_result = _bounded_json(
            candidate, max_bytes=MAX_TOOL_SCHEMA_BYTES, label=label
        )
        if size_result.is_err():
            return Result.err(size_result.unwrap_err())
        shape_result = _bounded_schema(candidate)
        if shape_result.is_err():
            return Result.err(shape_result.unwrap_err())
    seen_names.add(safe_name)
    return Result.ok(
        {
            "name": safe_name,
            "mcp_name": name,
            "description": description or f"MCP tool {safe_name}",
            "parameters": dict(schema),
            "result_schema": descriptor.get("outputSchema"),
        }
    )


def _legacy_standard_tools(mcp_server_url: str, client) -> List[Tool]:
    """Preserve the historical offline helper until the next major API cycle."""
    def _make_mcp_handler(tool_name):
        def handler(**kwargs) -> Result:
            try:
                return _run_async(client.call_mcp_tool(tool_name, kwargs))
            except Exception as exc:
                return Result.err(
                    {
                        "errorType": "MCP_CALL_ERROR",
                        "message": f'Failed to call MCP tool "{tool_name}": {exc}',
                    }
                )

        return handler

    return [
        Tool(
            name="mcp_agent_communicate",
            description=f"Communicate with agents via MCP server at {mcp_server_url}",
            parameters={
                "type": "object",
                "properties": {
                    "target_agent": {
                        "type": "string",
                        "description": "Target agent ID",
                    },
                    "message_type": {"type": "string", "description": "Message type"},
                    "payload": {"type": "object", "description": "Message payload"},
                },
                "required": ["target_agent", "message_type", "payload"],
            },
            handler=_make_mcp_handler("maple_agent_communicate"),
            tags=["mcp", "external"],
        ),
        Tool(
            name="mcp_resource_management",
            description=f"Manage resources via MCP server at {mcp_server_url}",
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["allocate", "release", "negotiate"],
                    },
                    "resources": {"type": "object"},
                },
                "required": ["action"],
            },
            handler=_make_mcp_handler("maple_resource_management"),
            tags=["mcp", "external"],
        ),
    ]


def discover_mcp_tools(
    mcp_server_url: str,
    agent,
    *,
    client=None,
    transport=None,
    max_tools: int = MAX_DISCOVERED_TOOLS,
) -> Result[List[Tool], Dict[str, Any]]:
    """
    Discover tools from an external MCP server and wrap them as MAPLE Tools.

    With ``client`` or ``transport`` supplied, this calls the server's live
    ``tools/list`` method and converts bounded descriptors into MAPLE Tools.
    With only the historical URL and agent arguments, it preserves the
    offline two-tool compatibility behavior; that path never makes a network
    request and is not live discovery.
    """
    try:
        from ..adapters.mcp_adapter import MCPClient

        if max_tools <= 0 or max_tools > MAX_DISCOVERED_TOOLS:
            return Result.err(
                {
                    "errorType": "MCP_TOOL_LIMIT_INVALID",
                    "message": (
                        f"max_tools must be between 1 and {MAX_DISCOVERED_TOOLS}"
                    ),
                }
            )
        live_requested = client is not None or transport is not None
        if client is None:
            client = MCPClient(
                agent,
                mcp_server_url,
                transport=transport,
                max_tools=max_tools,
            )
        if not live_requested:
            tools = _legacy_standard_tools(mcp_server_url, client)
            logger.info(
                "Using offline MCP compatibility descriptors for %s", mcp_server_url
            )
            return Result.ok(tools)

        descriptors = _run_async(client.list_mcp_tools())
        if not isinstance(descriptors, Result):
            return Result.err(
                {
                    "errorType": "MCP_DISCOVERY_ERROR",
                    "message": "MCP client returned an invalid result",
                }
            )
        if descriptors.is_err():
            return Result.err(descriptors.unwrap_err())
        raw_tools = descriptors.unwrap()
        if not isinstance(raw_tools, list) or len(raw_tools) > max_tools:
            return Result.err(
                {
                    "errorType": "MCP_TOOL_LIMIT_EXCEEDED",
                    "message": f"MCP server returned more than {max_tools} tools",
                }
            )
        seen_names = set()
        validated = []
        for descriptor in raw_tools:
            checked = _validate_descriptor(descriptor, seen_names)
            if checked.is_err():
                return Result.err(checked.unwrap_err())
            validated.append(checked.unwrap())

        tools = []
        for tool_def in validated:
            tool = Tool(
                name=tool_def["name"],
                description=tool_def["description"],
                parameters=tool_def["parameters"],
                handler=lambda _tool_name=tool_def["mcp_name"], **kwargs: _run_async(
                    client.call_mcp_tool(_tool_name, kwargs)
                ),
                result_schema=tool_def["result_schema"],
                requires_approval=True,
                tags=["mcp", "external"],
            )
            tools.append(tool)
        logger.info("Discovered %d live MCP tools from %s", len(tools), mcp_server_url)
        return Result.ok(tools)

    except ImportError:
        return Result.err(
            {
                "errorType": "MCP_ADAPTER_MISSING",
                "message": (
                    "MCPAdapter not available. Ensure "
                    "maple.adapters.mcp_adapter is accessible."
                ),
            }
        )
    except Exception as e:
        return Result.err({
            'errorType': 'MCP_DISCOVERY_ERROR',
            'message': f'Failed to discover MCP tools: {str(e)}'
        })


def register_mcp_tools(
    registry: ToolRegistry,
    tools: List[Tool],
    *,
    server_id: Optional[str] = None,
    policy: Optional[ToolPolicy] = None,
    namespace: bool = False,
    max_tools: Optional[int] = None,
) -> int:
    """Register a list of MCP tools into a ToolRegistry. Returns the count registered.

    MCP tools come from an EXTERNAL, untrusted server. The optional governance
    hooks let a host mediate that trust boundary (recommended for any server
    you do not fully control):

    - ``policy(tool, server_id) -> bool`` -- a host authorization callback. A
      tool the policy rejects (or that makes the policy raise) is NOT
      registered. This is the default-deny hook: a host can classify/gate each
      discovered tool instead of trusting the server's self-reported
      name/description.
    - ``namespace=True`` (requires ``server_id``) -- register each tool under
      a sanitized, server-namespaced name ``mcp.<server_id>.<name>`` so an
      untrusted server cannot shadow or overwrite another server's -- or a
      native -- tool.
    - ``max_tools`` -- cap the number registered from one discovery (a flood bound).

    Backward-compatible: with no hooks it registers all tools as before -- safe
    only for a server you fully trust.
    """
    registered = 0
    safe_server = sanitize_tool_name(server_id, 32) if server_id else None
    for tool in tools or []:
        if max_tools is not None and registered >= max_tools:
            break
        if policy is not None:
            try:
                if not policy(tool, server_id):
                    logger.info(
                        "MCP tool '%s' rejected by host policy",
                        getattr(tool, "name", "?"),
                    )
                    continue
            except Exception as e:  # policy faults fail closed; never register
                logger.warning(
                    "MCP policy raised for '%s' -> rejected: %s",
                    getattr(tool, "name", "?"),
                    e,
                )
                continue
        entry = tool
        if namespace:
            bare = sanitize_tool_name(getattr(tool, "name", ""))
            if not bare or not safe_server:  # can't namespace safely -> skip
                continue
            entry = dataclasses.replace(tool, name=f"mcp.{safe_server}.{bare}")
        result = registry.register(entry)
        if result.is_ok():
            registered += 1
        else:
            logger.warning(
                "Failed to register MCP tool '%s'", getattr(entry, "name", "?")
            )
    return registered
