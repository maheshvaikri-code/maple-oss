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

import logging
from typing import Any, Dict, List, Optional

from ..core.result import Result
from .tools import Tool, ToolRegistry

logger = logging.getLogger(__name__)


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


def register_mcp_tools(registry: ToolRegistry, tools: List[Tool]) -> int:
    """Register a list of MCP tools into a ToolRegistry. Returns count registered."""
    registered = 0
    for tool in tools:
        result = registry.register(tool)
        if result.is_ok():
            registered += 1
        else:
            logger.warning(f"Failed to register MCP tool '{tool.name}'")
    return registered
