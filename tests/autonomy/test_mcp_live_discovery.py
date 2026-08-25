"""Regression tests for live MCP discovery and JSON-RPC calls."""

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from maple.adapters.mcp_adapter import MCPClient, StreamableHTTPTransport
from maple.autonomy.mcp_tools import discover_mcp_tools
from maple.core.result import Result


class FakeAgent:
    agent_id = "test-agent"


@pytest.mark.parametrize(
    "server_url",
    [
        "file:///tmp/maple-mcp",
        "ftp://example.test/mcp",
        "http://user:password@example.test/mcp",
        "http://example.test/mcp#fragment",
    ],
)
def test_streamable_http_transport_rejects_non_http_or_ambiguous_urls(server_url):
    with pytest.raises(ValueError):
        StreamableHTTPTransport(server_url)


class RecordingTransport:
    def __init__(self, pages=None):
        self.calls = []
        self.pages = pages or [
            [
                {
                    "name": "search",
                    "description": "Find things",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                }
            ]
        ]
        self.call_result = {"content": [{"type": "text", "text": "found"}]}

    async def request(self, payload):
        self.calls.append(payload)
        if payload["method"] == "tools/list":
            index = 0 if "cursor" not in payload.get("params", {}) else 1
            result = {"tools": self.pages[index]}
            if index == 0 and len(self.pages) > 1:
                result["nextCursor"] = "page-2"
            return Result.ok({"jsonrpc": "2.0", "id": payload["id"], "result": result})
        if payload["method"] == "tools/call":
            return Result.ok(
                {
                    "jsonrpc": "2.0",
                    "id": payload["id"],
                    "result": self.call_result,
                }
            )
        return Result.err(
            {"errorType": "MCP_TEST_ERROR", "message": "unexpected method"}
        )


def test_live_discovery_uses_server_descriptors_and_calls_real_tool():
    transport = RecordingTransport()
    client = MCPClient(FakeAgent(), "http://example.test/mcp", transport=transport)

    result = discover_mcp_tools("http://example.test/mcp", FakeAgent(), client=client)

    assert result.is_ok()
    tool = result.unwrap()[0]
    assert tool.name == "search"
    assert tool.requires_approval is True
    assert tool.execute(query="MAPLE").unwrap()["content"][0]["text"] == "found"
    assert [call["method"] for call in transport.calls] == ["tools/list", "tools/call"]
    assert transport.calls[-1]["params"] == {
        "name": "search",
        "arguments": {"query": "MAPLE"},
    }


def test_live_discovery_rejects_malformed_descriptor_without_partial_tools():
    transport = RecordingTransport(
        pages=[
            [
                {"name": "good", "inputSchema": {"type": "object"}},
                {"name": "bad name", "inputSchema": {"type": "object"}},
            ]
        ]
    )
    client = MCPClient(FakeAgent(), "http://example.test/mcp", transport=transport)

    result = discover_mcp_tools("http://example.test/mcp", FakeAgent(), client=client)

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "MCP_DESCRIPTOR_INVALID"


def test_live_discovery_supports_bounded_pagination():
    transport = RecordingTransport(
        pages=[
            [{"name": "first", "inputSchema": {"type": "object"}}],
            [{"name": "second", "inputSchema": {"type": "object"}}],
        ]
    )
    client = MCPClient(FakeAgent(), "http://example.test/mcp", transport=transport)

    result = discover_mcp_tools("http://example.test/mcp", FakeAgent(), client=client)

    assert result.is_ok()
    assert [tool.name for tool in result.unwrap()] == ["first", "second"]
    assert transport.calls[1]["params"] == {"cursor": "page-2"}


def test_live_discovery_rejects_schema_features_not_supported_by_maple_validator():
    transport = RecordingTransport(
        pages=[
            [
                {
                    "name": "search",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"query": {"type": "string", "pattern": ".*"}},
                    },
                }
            ]
        ]
    )
    client = MCPClient(FakeAgent(), "http://example.test/mcp", transport=transport)

    result = discover_mcp_tools("http://example.test/mcp", FakeAgent(), client=client)

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "MCP_SCHEMA_UNSUPPORTED"


def test_live_discovery_maps_rpc_errors_as_data():
    class ErrorTransport:
        async def request(self, payload):
            return Result.ok(
                {
                    "jsonrpc": "2.0",
                    "id": payload["id"],
                    "error": {"code": -32601, "message": "Method not found"},
                }
            )

    client = MCPClient(
        FakeAgent(), "http://example.test/mcp", transport=ErrorTransport()
    )
    result = discover_mcp_tools("http://example.test/mcp", FakeAgent(), client=client)

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "MCP_RPC_ERROR"
    assert result.unwrap_err()["details"]["code"] == -32601


def test_streamable_http_transport_initializes_and_sends_protocol_headers():
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802 - stdlib handler API
            length = int(self.headers["Content-Length"])
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            calls.append((payload, dict(self.headers)))
            if payload["method"] == "initialize":
                body = {
                    "jsonrpc": "2.0",
                    "id": payload["id"],
                    "result": {"protocolVersion": "2025-11-25"},
                }
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Mcp-Session-Id", "session-1")
            elif payload["method"] == "notifications/initialized":
                self.send_response(202)
                self.end_headers()
                return
            else:
                body = {"jsonrpc": "2.0", "id": payload["id"], "result": {"tools": []}}
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            encoded = json.dumps(body).encode("utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        transport = StreamableHTTPTransport(
            f"http://127.0.0.1:{server.server_port}/mcp"
        )
        client = MCPClient(FakeAgent(), transport.server_url, transport=transport)
        result = asyncio.run(client.list_mcp_tools())
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()

    assert result.is_ok()
    assert [call[0]["method"] for call in calls] == [
        "initialize",
        "notifications/initialized",
        "tools/list",
    ]
    assert calls[2][1]["Mcp-Protocol-Version"] == "2025-11-25"
    assert calls[2][1]["Mcp-Session-Id"] == "session-1"
