"""Tests for the autonomy tool framework."""

import pytest

from maple.autonomy.agent import Goal
from maple.autonomy.tools import (
    Tool,
    ToolRegistry,
    create_builtin_tools,
    create_handoff_tool,
)
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

    async def test_execute_async_preserves_executor_boundary(self):
        from maple.autonomy.execution import ExecutionPolicy, TrustedLocalExecutor

        calls = []

        async def async_handler():
            raise AssertionError("async handler must not bypass executor policy")

        tool = Tool(
            name="bounded_async",
            description="Uses the trusted execution boundary",
            parameters={"type": "object"},
            handler=lambda: calls.append("sync") or Result.ok({"ok": True}),
            async_handler=async_handler,
            executor=TrustedLocalExecutor(ExecutionPolicy(timeout_seconds=1)),
        )

        result = await tool.execute_async()

        assert result.is_ok()
        assert calls == ["sync"]

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

    async def test_execute_async_uses_declared_handler(self):
        async def async_handler(x):
            return Result.ok({"doubled": x * 2})

        reg = ToolRegistry()
        reg.register(
            Tool(
                name="async_doubler",
                description="Double asynchronously",
                parameters={
                    "type": "object",
                    "properties": {"x": {"type": "integer"}},
                    "required": ["x"],
                },
                handler=lambda x: Result.ok({"doubled": x * 2}),
                async_handler=async_handler,
            )
        )

        result = await reg.execute_async("async_doubler", {"x": 6})

        assert result.is_ok()
        assert result.unwrap() == {"doubled": 12}


class HandoffAgent:
    """Minimal synchronous target for handoff-tool tests."""

    def __init__(self, agent_id="specialist"):
        self.agent_id = agent_id
        self.tasks = []

    def pursue_goal(self, description):
        self.tasks.append(description)
        return Result.ok(
            Goal(
                goal_id="goal-specialist",
                description=description,
                status="completed",
                result={"answer": description.upper()},
            )
        )


class ContextHandoffAgent(HandoffAgent):
    """Target that explicitly accepts filtered handoff context."""

    def __init__(self, agent_id="specialist"):
        super().__init__(agent_id=agent_id)
        self.contexts = []

    def pursue_goal_with_context(self, description, context):
        self.contexts.append(context)
        return self.pursue_goal(description)


class AsyncHandoffAgent(ContextHandoffAgent):
    """Target that explicitly accepts async handoff execution."""

    async def pursue_goal_async(self, description):
        return self.pursue_goal(description)

    async def pursue_goal_with_context_async(self, description, context):
        self.contexts.append(context)
        return self.pursue_goal(description)


class TestHandoffTool:
    def test_handoff_success_is_structured_and_approval_required(self):
        target = HandoffAgent()
        tool = create_handoff_tool(target)

        result = tool.execute(task="Research the release notes")

        assert result.is_ok()
        assert result.unwrap() == {
            "agent_id": "specialist",
            "goal_id": "goal-specialist",
            "status": "completed",
            "result": {"answer": "RESEARCH THE RELEASE NOTES"},
        }
        assert target.tasks == ["Research the release notes"]
        assert tool.requires_approval is True
        assert tool.to_llm_definition().parameters["required"] == ["task"]

    def test_handoff_target_failure_does_not_expose_raw_error(self):
        class FailingAgent(HandoffAgent):
            def pursue_goal(self, description):
                return Result.err(
                    {
                        "errorType": "TARGET_FAILURE",
                        "message": "secret provider response",
                    }
                )

        result = create_handoff_tool(FailingAgent()).execute(task="Try this")

        assert result.is_err()
        error = result.unwrap_err()
        assert error["errorType"] == "HANDOFF_TARGET_FAILED"
        assert error["details"]["target_error_type"] == "TARGET_FAILURE"
        assert "secret" not in str(error)

    def test_handoff_target_exception_is_normalized(self):
        class RaisingAgent(HandoffAgent):
            def pursue_goal(self, description):
                raise RuntimeError("private failure")

        result = create_handoff_tool(RaisingAgent()).execute(task="Try this")

        assert result.is_err()
        assert result.unwrap_err()["errorType"] == "HANDOFF_TARGET_ERROR"
        assert result.unwrap_err()["details"]["exception"] == "RuntimeError"
        assert "private failure" not in str(result.unwrap_err())

    def test_handoff_rejects_empty_and_oversized_tasks_before_target(self):
        target = HandoffAgent()
        tool = create_handoff_tool(target, requires_approval=False)

        empty = tool.execute(task="")
        oversized = tool.execute(task="x" * 8193)

        assert empty.is_err()
        assert oversized.is_err()
        assert empty.unwrap_err()["errorType"] == "TOOL_INPUT_INVALID"
        assert oversized.unwrap_err()["errorType"] == "TOOL_INPUT_INVALID"
        assert target.tasks == []

    def test_handoff_rejects_invalid_target(self):
        with pytest.raises(ValueError, match="target_agent"):
            create_handoff_tool(object())

    def test_handoff_filters_context_and_requires_explicit_target_support(self):
        target = ContextHandoffAgent()
        tool = create_handoff_tool(target, allowed_context_keys=["project"])

        result = tool.execute(
            task="Use the release notes",
            context={"project": {"name": "MAPLE"}},
        )

        assert result.is_ok()
        assert target.contexts == [{"project": {"name": "MAPLE"}}]
        assert tool.to_llm_definition().parameters["required"] == ["task"]

    def test_handoff_rejects_context_keys_outside_allowlist_before_target(self):
        target = ContextHandoffAgent()
        tool = create_handoff_tool(target, allowed_context_keys=["project"])

        result = tool.execute(task="Use the release notes", context={"secret": "x"})

        assert result.is_err()
        assert result.unwrap_err()["errorType"] == "HANDOFF_CONTEXT_KEY_DENIED"
        assert target.tasks == []

    def test_handoff_rejects_context_for_legacy_target(self):
        target = HandoffAgent()
        tool = create_handoff_tool(target, allowed_context_keys=["project"])

        result = tool.execute(
            task="Use the release notes", context={"project": "MAPLE"}
        )

        assert result.is_err()
        assert result.unwrap_err()["errorType"] == "HANDOFF_CONTEXT_UNSUPPORTED"
        assert target.tasks == []

    async def test_async_handoff_uses_async_target_contract(self):
        target = AsyncHandoffAgent()
        tool = create_handoff_tool(target, allowed_context_keys=["project"])

        result = await tool.execute_async(
            task="Use the release notes",
            context={"project": "MAPLE"},
        )

        assert result.is_ok()
        assert target.contexts == [{"project": "MAPLE"}]


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
        assert "request_human_input" in names

    def test_write_state_requires_approval(self):
        class FakeAgent:
            agent_id = "test-agent"
            registry = None

            def send(self, msg):
                return Result.ok(None)

        tools = create_builtin_tools(FakeAgent())
        write_tool = next(t for t in tools if t.name == "write_state")
        assert write_tool.requires_approval is True
