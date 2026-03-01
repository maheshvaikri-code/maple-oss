"""Tests for MCP tool discovery and integration."""

import pytest
from maple.autonomy.mcp_tools import discover_mcp_tools, register_mcp_tools
from maple.autonomy.tools import Tool, ToolRegistry
from maple.core.result import Result


class FakeAgent:
    agent_id = "test-agent"

    def _generate_request_id(self):
        return "req-123"


class TestDiscoverMCPTools:
    def test_discover_returns_tools(self):
        agent = FakeAgent()
        result = discover_mcp_tools("http://localhost:8080", agent)
        assert result.is_ok()
        tools = result.unwrap()
        assert len(tools) == 2
        names = [t.name for t in tools]
        assert "mcp_agent_communicate" in names
        assert "mcp_resource_management" in names

    def test_tools_have_correct_tags(self):
        agent = FakeAgent()
        tools = discover_mcp_tools("http://localhost:8080", agent).unwrap()
        for tool in tools:
            assert "mcp" in tool.tags
            assert "external" in tool.tags

    def test_tools_have_parameters(self):
        agent = FakeAgent()
        tools = discover_mcp_tools("http://localhost:8080", agent).unwrap()
        comm_tool = next(t for t in tools if t.name == "mcp_agent_communicate")
        assert "properties" in comm_tool.parameters
        assert "target_agent" in comm_tool.parameters["properties"]


class TestRegisterMCPTools:
    def test_register_tools(self):
        registry = ToolRegistry()
        tools = [
            Tool(name="mcp_a", description="A", parameters={},
                 handler=lambda: Result.ok(None), tags=["mcp"]),
            Tool(name="mcp_b", description="B", parameters={},
                 handler=lambda: Result.ok(None), tags=["mcp"]),
        ]
        count = register_mcp_tools(registry, tools)
        assert count == 2
        assert len(registry.list_tools()) == 2

    def test_register_empty(self):
        registry = ToolRegistry()
        count = register_mcp_tools(registry, [])
        assert count == 0
