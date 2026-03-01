"""Tests for the autonomy tool framework."""

import pytest
from maple.autonomy.tools import Tool, ToolRegistry, create_builtin_tools
from maple.core.result import Result


def make_tool(name="test_tool", requires_approval=False, tags=None):
    """Helper to create a simple test tool."""
    def handler(x: int = 0) -> Result:
        return Result.ok({"doubled": x * 2})

    return Tool(
        name=name,
        description=f"Test tool: {name}",
        parameters={
            "type": "object",
            "properties": {"x": {"type": "integer"}},
        },
        handler=handler,
        requires_approval=requires_approval,
        tags=tags or [],
    )


class TestTool:
    def test_create_tool(self):
        tool = make_tool("my_tool")
        assert tool.name == "my_tool"
        assert not tool.requires_approval

    def test_execute_success(self):
        tool = make_tool()
        result = tool.execute(x=5)
        assert result.is_ok()
        assert result.unwrap()["doubled"] == 10

    def test_execute_handler_error(self):
        def bad_handler(**kwargs):
            raise ValueError("boom")

        tool = Tool(
            name="bad",
            description="fails",
            parameters={"type": "object"},
            handler=bad_handler,
        )
        result = tool.execute()
        assert result.is_err()
        assert "boom" in result.unwrap_err()["message"]

    def test_to_llm_definition(self):
        tool = make_tool("calc")
        defn = tool.to_llm_definition()
        assert defn.name == "calc"
        assert defn.description.startswith("Test tool")
        assert "properties" in defn.parameters

    def test_tags(self):
        tool = make_tool("tagged", tags=["math", "utility"])
        assert "math" in tool.tags
        assert "utility" in tool.tags


class TestToolRegistry:
    def test_register_and_get(self):
        reg = ToolRegistry()
        tool = make_tool("calc")
        result = reg.register(tool)
        assert result.is_ok()

        get_result = reg.get("calc")
        assert get_result.is_ok()
        assert get_result.unwrap().name == "calc"

    def test_get_not_found(self):
        reg = ToolRegistry()
        result = reg.get("nonexistent")
        assert result.is_err()
        assert result.unwrap_err()["errorType"] == "TOOL_NOT_FOUND"

    def test_list_tools(self):
        reg = ToolRegistry()
        reg.register(make_tool("a", tags=["math"]))
        reg.register(make_tool("b", tags=["io"]))
        reg.register(make_tool("c", tags=["math", "io"]))

        all_tools = reg.list_tools()
        assert len(all_tools) == 3

        math_tools = reg.list_tools(tags=["math"])
        assert len(math_tools) == 2

        io_tools = reg.list_tools(tags=["io"])
        assert len(io_tools) == 2

    def test_get_llm_definitions(self):
        reg = ToolRegistry()
        reg.register(make_tool("a"))
        reg.register(make_tool("b"))
        defs = reg.get_llm_definitions()
        assert len(defs) == 2
        assert all(d.name in ("a", "b") for d in defs)

    def test_execute(self):
        reg = ToolRegistry()
        reg.register(make_tool("doubler"))
        result = reg.execute("doubler", {"x": 7})
        assert result.is_ok()
        assert result.unwrap()["doubled"] == 14

    def test_execute_not_found(self):
        reg = ToolRegistry()
        result = reg.execute("missing", {})
        assert result.is_err()


class TestBuiltinTools:
    def test_create_builtin_tools(self):
        class FakeAgent:
            agent_id = "test-agent"
            registry = None

            def send(self, msg):
                return Result.ok(None)

        agent = FakeAgent()
        tools = create_builtin_tools(agent)
        assert len(tools) >= 3
        names = [t.name for t in tools]
        assert "send_message" in names
        assert "query_agents" in names
        assert "read_state" in names
        assert "write_state" in names

    def test_write_state_requires_approval(self):
        class FakeAgent:
            agent_id = "test-agent"
            registry = None

            def send(self, msg):
                return Result.ok(None)

        tools = create_builtin_tools(FakeAgent())
        write_tool = next(t for t in tools if t.name == "write_state")
        assert write_tool.requires_approval is True
