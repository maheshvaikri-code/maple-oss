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


# maple/adapters/mcp_adapter.py

import asyncio
import json
import time
from typing import Any, Dict, List, Optional, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from maple.core.types import Priority

from ..core.message import Message
from ..core.result import Result


class MCPAdapter:
    """
    MAPLE adapter for Anthropic MCP (Model Context Protocol).
    Extends MCP with MAPLE's advanced agent communication capabilities.
    """

    def __init__(self, maple_agent, mcp_config: Dict[str, Any]):
        self.maple_agent = maple_agent
        self.mcp_config = mcp_config
        self.mcp_tools = {}
        self.mcp_resources = {}

    def register_maple_as_mcp_server(self) -> Dict[str, Any]:
        """
        Register MAPLE agent as an MCP server with enhanced capabilities.
        """
        mcp_server_config = {
            "name": f"maple-{self.maple_agent.agent_id}",
            "version": "1.1.3",
            "description": "MAPLE-powered MCP server with advanced agent capabilities",
            "tools": [
                {
                    "name": "maple_agent_communicate",
                    "description": (
                        "Communicate with MAPLE agents using advanced protocol features"
                    ),
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "target_agent": {"type": "string"},
                            "message_type": {"type": "string"},
                            "payload": {"type": "object"},
                            "priority": {
                                "type": "string",
                                "enum": ["HIGH", "MEDIUM", "LOW"],
                            },
                            "resources": {"type": "object"},
                            "link_security": {"type": "boolean"},
                        },
                        "required": ["target_agent", "message_type", "payload"],
                    },
                },
                {
                    "name": "maple_resource_management",
                    "description": (
                        "Manage resources using MAPLE's advanced resource system"
                    ),
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["allocate", "release", "negotiate"],
                            },
                            "resources": {"type": "object"},
                            "priority": {"type": "string"},
                        },
                    },
                },
            ],
            "resources": [
                {
                    "uri": f"maple://{self.maple_agent.agent_id}/capabilities",
                    "name": "MAPLE Agent Capabilities",
                    "description": "Advanced capabilities provided by MAPLE protocol",
                    "mimeType": "application/json",
                }
            ],
            # MAPLE-specific enhancements
            "maple_extensions": {
                "performance": "333,384 msg/sec",
                "type_safety": "Complete Result<T,E> system",
                "resource_awareness": "Integrated resource management",
                "security": "Link Identification Mechanism (LIM)",
                "error_handling": "Advanced recovery strategies",
            },
        }
        return mcp_server_config

    async def handle_mcp_tool_call(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> Result[Any, Dict[str, Any]]:
        """
        Handle MCP tool calls with MAPLE enhancements.
        """
        if tool_name == "maple_agent_communicate":
            return await self._handle_agent_communication(arguments)
        elif tool_name == "maple_resource_management":
            return await self._handle_resource_management(arguments)
        else:
            return Result.err(
                {
                    "errorType": "UNKNOWN_TOOL",
                    "message": f"Tool {tool_name} not supported",
                }
            )

    async def _handle_agent_communication(
        self, args: Dict[str, Any]
    ) -> Result[Any, Dict[str, Any]]:
        """
        Handle inter-agent communication via MCP with MAPLE enhancements.
        """
        try:
            # Create MAPLE message
            message = Message(
                message_type=args["message_type"],
                receiver=args["target_agent"],
                priority=Priority(args.get("priority", "MEDIUM")),
                payload=args["payload"],
            )

            # Add resource requirements if specified
            if "resources" in args:
                message.payload["resources"] = args["resources"]

            # Establish secure link if requested
            if args.get("link_security", False):
                link_result = await self.maple_agent.establish_link(
                    args["target_agent"]
                )
                if link_result.is_ok():
                    message.metadata["linkId"] = link_result.unwrap()

            # Send via MAPLE protocol
            result = await self.maple_agent.send(message)

            if result.is_ok():
                return Result.ok(
                    {
                        "status": "success",
                        "message_id": result.unwrap(),
                        "maple_enhancements": {
                            "type_safety": "Result<T,E> used",
                            "performance": "High-speed MAPLE protocol",
                            "security": "Optional link security applied",
                        },
                    }
                )
            else:
                return result

        except Exception as e:
            return Result.err(
                {"errorType": "MCP_COMMUNICATION_ERROR", "message": str(e)}
            )

    def create_mcp_client_for_external_tools(self, mcp_server_url: str) -> "MCPClient":
        """
        Create MCP client to access external tools with MAPLE enhancements.
        """
        return MCPClient(
            self.maple_agent,
            mcp_server_url,
            transport=StreamableHTTPTransport(mcp_server_url),
        )


class MCPTransport(Protocol):
    """Async JSON-RPC transport contract used by :class:`MCPClient`."""

    async def request(
        self, payload: Dict[str, Any]
    ) -> Result[Optional[Dict[str, Any]], Dict[str, Any]]:
        """Send one JSON-RPC payload and return its response or transport error."""


class StreamableHTTPTransport:
    """Small dependency-free MCP Streamable HTTP transport.

    The transport bounds request and response bodies, performs the MCP
    initialize/initialized handshake lazily, and accepts either a JSON
    response or an SSE response containing the matching JSON-RPC response.
    Long-lived server notifications and resumable streams are intentionally
    outside this request/response transport's contract.
    """

    DEFAULT_PROTOCOL_VERSION = "2025-11-25"
    SUPPORTED_PROTOCOL_VERSIONS = {
        "2025-11-25",
        "2025-06-18",
        "2025-03-26",
        "2024-11-05",
    }

    def __init__(
        self,
        server_url: str,
        *,
        timeout: float = 15.0,
        max_response_bytes: int = 1_048_576,
        max_request_bytes: int = 262_144,
        client_name: str = "maple-oss",
        client_version: str = "1.1.3",
    ):
        parts = urlsplit(server_url)
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            raise ValueError("MCP server URL must be an absolute http(s) URL")
        if parts.username or parts.password or parts.fragment:
            raise ValueError("MCP server URL cannot contain credentials or a fragment")
        if timeout <= 0 or timeout > 120:
            raise ValueError("MCP transport timeout must be between 0 and 120 seconds")
        if max_response_bytes <= 0 or max_request_bytes <= 0:
            raise ValueError("MCP transport body bounds must be positive")
        self.server_url = server_url
        self.timeout = timeout
        self.max_response_bytes = max_response_bytes
        self.max_request_bytes = max_request_bytes
        self.client_name = client_name[:128]
        self.client_version = client_version[:64]
        self._protocol_version: Optional[str] = None
        self._session_id: Optional[str] = None
        self._request_id = 0
        # Create the lock on the first request so a client constructed in sync
        # code can be used by any later asyncio event loop.
        self._initialize_lock = None

    async def request(
        self, payload: Dict[str, Any]
    ) -> Result[Optional[Dict[str, Any]], Dict[str, Any]]:
        """Send an MCP request, initializing the HTTP session on first use."""
        if not isinstance(payload, dict) or not isinstance(payload.get("method"), str):
            return Result.err(
                {
                    "errorType": "MCP_REQUEST_INVALID",
                    "message": "MCP payload must be a JSON-RPC object with a method",
                }
            )

        if self._protocol_version is None and payload.get("method") != "initialize":
            if self._initialize_lock is None:
                self._initialize_lock = asyncio.Lock()
            async with self._initialize_lock:
                if self._protocol_version is None:
                    initialized = await self._initialize()
                    if initialized.is_err():
                        return initialized
        return await self._request_once(payload)

    async def _initialize(self) -> Result[None, Dict[str, Any]]:
        request_id = self._next_request_id()
        initialize = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "initialize",
            "params": {
                "protocolVersion": self.DEFAULT_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {
                    "name": self.client_name,
                    "version": self.client_version,
                },
            },
        }
        response = await self._request_once(initialize)
        if response.is_err():
            return Result.err(response.unwrap_err())
        payload = response.unwrap()
        if not isinstance(payload, dict):
            return Result.err(
                {
                    "errorType": "MCP_INITIALIZE_INVALID",
                    "message": "MCP initialize returned no JSON-RPC response",
                }
            )
        result = payload.get("result")
        if not isinstance(result, dict):
            return Result.err(
                {
                    "errorType": "MCP_INITIALIZE_INVALID",
                    "message": "MCP initialize result must be an object",
                }
            )
        protocol_version = result.get("protocolVersion")
        if protocol_version not in self.SUPPORTED_PROTOCOL_VERSIONS:
            return Result.err(
                {
                    "errorType": "MCP_PROTOCOL_UNSUPPORTED",
                    "message": "MCP server returned an unsupported protocol version",
                    "details": {"protocolVersion": protocol_version},
                }
            )
        self._protocol_version = protocol_version
        notification = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        notified = await self._request_once(notification)
        if notified.is_err():
            return Result.err(notified.unwrap_err())
        return Result.ok(None)

    async def _request_once(
        self, payload: Dict[str, Any]
    ) -> Result[Optional[Dict[str, Any]], Dict[str, Any]]:
        try:
            encoded = json.dumps(
                payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            return Result.err({"errorType": "MCP_REQUEST_INVALID", "message": str(exc)})
        if len(encoded) > self.max_request_bytes:
            return Result.err(
                {
                    "errorType": "MCP_REQUEST_TOO_LARGE",
                    "message": "MCP request exceeds the configured body limit",
                }
            )

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "User-Agent": f"{self.client_name}/{self.client_version}",
        }
        if self._protocol_version is not None:
            headers["MCP-Protocol-Version"] = self._protocol_version
        if self._session_id is not None:
            headers["Mcp-Session-Id"] = self._session_id
        request = Request(self.server_url, data=encoded, headers=headers, method="POST")
        loop = asyncio.get_running_loop()
        try:
            status, content_type, response_headers, body = await loop.run_in_executor(
                None, self._send, request
            )
        except HTTPError as exc:
            return Result.err(
                {
                    "errorType": "MCP_HTTP_ERROR",
                    "message": f"MCP server returned HTTP {exc.code}",
                    "details": {"status": exc.code},
                }
            )
        except (OSError, URLError, TimeoutError, ValueError) as exc:
            return Result.err({"errorType": "MCP_TRANSPORT_ERROR", "message": str(exc)})

        session_id = response_headers.get("Mcp-Session-Id")
        if session_id:
            self._session_id = session_id[:256]
        if status == 202 and not body:
            return Result.ok(None)
        if status < 200 or status >= 300:
            return Result.err(
                {
                    "errorType": "MCP_HTTP_ERROR",
                    "message": f"MCP server returned HTTP {status}",
                    "details": {"status": status},
                }
            )
        if not body:
            return Result.err(
                {
                    "errorType": "MCP_EMPTY_RESPONSE",
                    "message": "MCP server returned an empty response",
                }
            )
        try:
            if "text/event-stream" in content_type.lower():
                response = self._parse_sse(body, payload.get("id"))
            elif "application/json" in content_type.lower() or not content_type:
                response = json.loads(body.decode("utf-8"))
            else:
                return Result.err(
                    {
                        "errorType": "MCP_CONTENT_TYPE_UNSUPPORTED",
                        "message": (
                            "Unsupported MCP response content type: " f"{content_type}"
                        ),
                    }
                )
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            return Result.err(
                {"errorType": "MCP_RESPONSE_INVALID", "message": str(exc)}
            )
        if not isinstance(response, dict):
            return Result.err(
                {
                    "errorType": "MCP_RESPONSE_INVALID",
                    "message": "MCP response must be a JSON object",
                }
            )
        return Result.ok(response)

    def _send(self, request: Request):
        with urlopen(request, timeout=self.timeout) as response:
            body = response.read(self.max_response_bytes + 1)
            if len(body) > self.max_response_bytes:
                raise ValueError("MCP response exceeds the configured body limit")
            return (
                response.status,
                response.headers.get_content_type(),
                response.headers,
                body,
            )

    @staticmethod
    def _parse_sse(body: bytes, expected_id: Any) -> Dict[str, Any]:
        messages = []
        data_lines = []
        for line in body.decode("utf-8").splitlines() + [""]:
            if not line:
                if data_lines:
                    messages.append(json.loads("\n".join(data_lines)))
                    data_lines = []
                continue
            if line.startswith("data:"):
                data_lines.append(line[5:].lstrip())
        for message in messages:
            if isinstance(message, dict) and message.get("id") == expected_id:
                return message
        raise ValueError("MCP SSE response did not contain the matching request id")

    def _next_request_id(self) -> int:
        self._request_id += 1
        return self._request_id


class MCPClient:
    """
    Enhanced MCP client with MAPLE capabilities.
    """

    def __init__(
        self,
        maple_agent,
        server_url: str,
        *,
        transport: Optional[MCPTransport] = None,
        max_tools: int = 64,
    ):
        self.maple_agent = maple_agent
        self.server_url = server_url
        self.transport = transport
        if max_tools <= 0:
            raise ValueError("max_tools must be positive")
        self.max_tools = max_tools
        self._request_counter = 0

    async def list_mcp_tools(self) -> Result[List[Dict[str, Any]], Dict[str, Any]]:
        """Return the bounded, paginated tool descriptors from the MCP server."""
        if self.transport is None:
            return Result.err(
                {
                    "errorType": "MCP_TRANSPORT_NOT_CONFIGURED",
                    "message": "Configure an MCP transport before live discovery",
                }
            )
        tools = []
        cursor = None
        seen_cursors = set()
        for _ in range(16):
            params = {"cursor": cursor} if cursor is not None else None
            page = await self._request("tools/list", params)
            if page.is_err():
                return Result.err(page.unwrap_err())
            result = page.unwrap()
            if not isinstance(result, dict) or not isinstance(
                result.get("tools"), list
            ):
                return Result.err(
                    {
                        "errorType": "MCP_LIST_INVALID",
                        "message": "MCP tools/list result must contain a tools array",
                    }
                )
            tools.extend(result["tools"])
            if len(tools) > self.max_tools:
                return Result.err(
                    {
                        "errorType": "MCP_TOOL_LIMIT_EXCEEDED",
                        "message": "MCP server returned more tools than allowed",
                        "details": {"maxTools": self.max_tools},
                    }
                )
            cursor = result.get("nextCursor")
            if cursor is None:
                return Result.ok(tools)
            if not isinstance(cursor, str) or not cursor or cursor in seen_cursors:
                return Result.err(
                    {
                        "errorType": "MCP_PAGINATION_INVALID",
                        "message": (
                            "MCP tools/list returned an invalid pagination cursor"
                        ),
                    }
                )
            seen_cursors.add(cursor)
        return Result.err(
            {
                "errorType": "MCP_PAGINATION_LIMIT_EXCEEDED",
                "message": "MCP tools/list exceeded the pagination limit",
            }
        )

    async def call_mcp_tool(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> Result[Any, Dict[str, Any]]:
        """
        Call MCP tool with MAPLE error handling and performance tracking.
        """
        if not isinstance(tool_name, str) or not tool_name:
            return Result.err(
                {"errorType": "MCP_TOOL_INVALID", "message": "Tool name is required"}
            )
        if not isinstance(arguments, dict):
            return Result.err(
                {
                    "errorType": "MCP_TOOL_INVALID",
                    "message": "Tool arguments must be an object",
                }
            )
        start_time = time.monotonic()
        result = await self._request(
            "tools/call", {"name": tool_name, "arguments": arguments}
        )
        if result.is_err():
            return Result.err(result.unwrap_err())
        value = result.unwrap()
        if not isinstance(value, dict):
            return Result.err(
                {
                    "errorType": "MCP_TOOL_RESULT_INVALID",
                    "message": "MCP tools/call result must be an object",
                }
            )
        response = dict(value)
        response["maple_metrics"] = {
            "duration_ms": (time.monotonic() - start_time) * 1000,
            "protocol": "MCP via MAPLE",
        }
        return Result.ok(response)

    async def _request(
        self, method: str, params: Optional[Dict[str, Any]]
    ) -> Result[Dict[str, Any], Dict[str, Any]]:
        if self.transport is None:
            return Result.err(
                {
                    "errorType": "MCP_TRANSPORT_NOT_CONFIGURED",
                    "message": "Configure an MCP transport before sending requests",
                }
            )
        self._request_counter += 1
        request_id = self._request_counter
        payload: Dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            payload["params"] = params
        try:
            response = self.transport.request(payload)
            if hasattr(response, "__await__"):
                response = await response
        except Exception as exc:
            return Result.err({"errorType": "MCP_TRANSPORT_ERROR", "message": str(exc)})
        if not isinstance(response, Result):
            response = Result.ok(response)
        if response.is_err():
            return Result.err(response.unwrap_err())
        envelope = response.unwrap()
        if not isinstance(envelope, dict):
            return Result.err(
                {
                    "errorType": "MCP_RESPONSE_INVALID",
                    "message": "MCP transport returned no JSON-RPC response",
                }
            )
        if envelope.get("jsonrpc") != "2.0" or envelope.get("id") != request_id:
            return Result.err(
                {
                    "errorType": "MCP_RESPONSE_INVALID",
                    "message": "MCP JSON-RPC response did not match the request",
                }
            )
        if "error" in envelope:
            error = envelope["error"]
            if not isinstance(error, dict):
                error = {"message": str(error)}
            return Result.err(
                {
                    "errorType": "MCP_RPC_ERROR",
                    "message": str(error.get("message", "MCP request failed")),
                    "details": {
                        "code": error.get("code"),
                        "data": error.get("data"),
                    },
                }
            )
        result = envelope.get("result")
        if not isinstance(result, dict):
            return Result.err(
                {
                    "errorType": "MCP_RESPONSE_INVALID",
                    "message": "MCP JSON-RPC result must be an object",
                }
            )
        return Result.ok(result)
