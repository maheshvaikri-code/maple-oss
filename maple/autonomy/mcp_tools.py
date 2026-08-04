"""
Copyright (C) 2025 Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

This file is part of MAPLE - Multi Agent Protocol Language Engine.

MAPLE - Multi Agent Protocol Language Engine is free software: you can redistribute it and/or
modify it under the terms of the GNU Affero General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later version.
MAPLE - Multi Agent Protocol Language Engine is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE. See the GNU Affero General Public License for more details. You should have
received a copy of the GNU Affero General Public License along with MAPLE - Multi Agent Protocol
Language Engine. If not, see <https://www.gnu.org/licenses/>.
"""

"""MCP tool discovery and integration for MAPLE autonomous agents."""

import dataclasses
import logging
import re
from typing import Any, Callable, Dict, List, Optional

from ..core.result import Result
from .tools import Tool, ToolRegistry

logger = logging.getLogger(__name__)

# A discovered MCP tool name is UNTRUSTED (an external server names it). Reduce it to a safe
# identifier before it becomes a registry key or lands in a rendered tool list.
_UNSAFE_TOOL = re.compile(r"[^A-Za-z0-9_.\-]")

# A host authorization callback: given a discovered tool (and its server id) return True to
# allow registration, False to REJECT it. Lets a host apply a default-deny / classification
# policy at the trust boundary instead of registering an untrusted server's tools as-is.
ToolPolicy = Callable[[Tool, Optional[str]], bool]


def sanitize_tool_name(name: str, max_len: int = 64) -> str:
    """Reduce an untrusted MCP tool name to a safe identifier (alnum + ``_ . -``), length
    bounded. Prevents control-byte / newline injection into a registry key or a rendered
    tool list, and an unbounded name from a hostile server."""
    return _UNSAFE_TOOL.sub("", str(name or ""))[:max_len]


def discover_mcp_tools(mcp_server_url: str, agent) -> Result[List[Tool], Dict[str, Any]]:
    """
    Discover tools from an external MCP server and wrap them as MAPLE Tools.

    Uses the existing MCPAdapter/MCPClient infrastructure to connect to an
    MCP server, discover available tools, and convert them to MAPLE Tool
    objects that can be registered in a ToolRegistry.
    """
    try:
        from ..adapters.mcp_adapter import MCPClient

        client = MCPClient(agent, mcp_server_url)
        tools = []

        # MCP tool discovery uses the server's tool listing
        # The MCPClient wraps each call with MAPLE Result<T,E> error handling
        def _make_mcp_handler(client_ref, tool_name):
            """Create a handler closure for an MCP tool."""
            def handler(**kwargs) -> Result:
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # If we're already in an async context, create a task
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as pool:
                            result = pool.submit(
                                asyncio.run,
                                client_ref.call_mcp_tool(tool_name, kwargs)
                            ).result(timeout=60)
                        return result
                    else:
                        return loop.run_until_complete(
                            client_ref.call_mcp_tool(tool_name, kwargs)
                        )
                except Exception as e:
                    return Result.err({
                        'errorType': 'MCP_CALL_ERROR',
                        'message': f'Failed to call MCP tool "{tool_name}": {str(e)}'
                    })
            return handler

        # Create MAPLE Tool wrappers for standard MCP tools
        # These are the tools advertised by MAPLE's own MCP server
        standard_mcp_tools = [
            {
                "name": "mcp_agent_communicate",
                "description": f"Communicate with agents via MCP server at {mcp_server_url}",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target_agent": {"type": "string", "description": "Target agent ID"},
                        "message_type": {"type": "string", "description": "Message type"},
                        "payload": {"type": "object", "description": "Message payload"},
                    },
                    "required": ["target_agent", "message_type", "payload"]
                },
                "mcp_name": "maple_agent_communicate",
            },
            {
                "name": "mcp_resource_management",
                "description": f"Manage resources via MCP server at {mcp_server_url}",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["allocate", "release", "negotiate"]},
                        "resources": {"type": "object"},
                    },
                    "required": ["action"]
                },
                "mcp_name": "maple_resource_management",
            },
        ]

        for tool_def in standard_mcp_tools:
            tool = Tool(
                name=tool_def["name"],
                description=tool_def["description"],
                parameters=tool_def["parameters"],
                handler=_make_mcp_handler(client, tool_def["mcp_name"]),
                tags=["mcp", "external"],
            )
            tools.append(tool)

        logger.info(f"Discovered {len(tools)} MCP tools from {mcp_server_url}")
        return Result.ok(tools)

    except ImportError:
        return Result.err({
            'errorType': 'MCP_ADAPTER_MISSING',
            'message': 'MCPAdapter not available. Ensure maple.adapters.mcp_adapter is accessible.'
        })
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

    MCP tools come from an EXTERNAL, untrusted server. The optional governance hooks let a
    host mediate that trust boundary (recommended for any server you do not fully control):

    - ``policy(tool, server_id) -> bool`` -- a host authorization callback. A tool the policy
      rejects (or that makes the policy raise) is NOT registered. This is the default-deny
      hook: a host can classify/gate each discovered tool instead of trusting the server's
      self-reported name/description.
    - ``namespace=True`` (requires ``server_id``) -- register each tool under a sanitized,
      server-namespaced name ``mcp.<server_id>.<name>`` so an untrusted server cannot shadow
      or overwrite another server's -- or a native -- tool.
    - ``max_tools`` -- cap the number registered from one discovery (a flood bound).

    Backward-compatible: with no hooks it registers all tools as before -- safe only for a
    server you fully trust.
    """
    registered = 0
    safe_server = sanitize_tool_name(server_id, 32) if server_id else None
    for tool in tools or []:
        if max_tools is not None and registered >= max_tools:
            break
        if policy is not None:
            try:
                if not policy(tool, server_id):
                    logger.info("MCP tool '%s' rejected by host policy", getattr(tool, "name", "?"))
                    continue
            except Exception as e:  # a policy fault fails CLOSED (reject), never registers
                logger.warning(
                    "MCP policy raised for '%s' -> rejected: %s", getattr(tool, "name", "?"), e
                )
                continue
        entry = tool
        if namespace:
            bare = sanitize_tool_name(getattr(tool, "name", ""))
            if not bare or not safe_server:  # can't namespace safely -> skip (fail-closed)
                continue
            entry = dataclasses.replace(tool, name=f"mcp.{safe_server}.{bare}")
        result = registry.register(entry)
        if result.is_ok():
            registered += 1
        else:
            logger.warning("Failed to register MCP tool '%s'", getattr(entry, "name", "?"))
    return registered
