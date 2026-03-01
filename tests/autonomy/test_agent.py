"""Tests for the AutonomousAgent with ReAct loop."""

import json
import pytest
from unittest.mock import MagicMock, patch
from maple.autonomy.agent import (
    AutonomousAgent, AutonomousConfig, Goal, ReasoningStep,
)
from maple.agent.config import Config
from maple.llm.types import (
    ChatMessage, ChatRole, LLMConfig, LLMResponse, TokenUsage, ToolCall,
)
from maple.llm.provider import LLMProvider
from maple.llm.registry import LLMProviderRegistry
from maple.core.result import Result


class MockLLMProvider(LLMProvider):
    """Mock LLM provider that returns scripted responses."""

    def __init__(self, config, responses=None):
        super().__init__(config)
        self._responses = responses or []
        self._call_index = 0

    def complete(self, messages, tools=None, temperature=None, max_tokens=None, stop=None):
        if self._call_index < len(self._responses):
            resp = self._responses[self._call_index]
            self._call_index += 1
            self._track_usage(resp)
            return Result.ok(resp)
        # Default: stop
        default = LLMResponse(
            content="Done.",
            finish_reason="stop",
            usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )
        self._track_usage(default)
        return Result.ok(default)


def make_config():
    return Config(agent_id="auto-test-agent", broker_url="memory://test")


def make_llm_config():
    return LLMConfig(provider="mock", model="mock-v1")


def make_auto_config(**kwargs):
    defaults = {
        "llm": make_llm_config(),
        "max_reasoning_steps": 5,
        "reflection_frequency": 10,  # high so we don't trigger reflection in tests
    }
    defaults.update(kwargs)
    return AutonomousConfig(**defaults)


@pytest.fixture(autouse=True)
def register_mock_provider():
    """Register mock provider before each test."""
    original = dict(LLMProviderRegistry._providers)
    LLMProviderRegistry.register("mock", MockLLMProvider)
    yield
    LLMProviderRegistry._providers = original


class TestGoal:
    def test_goal_creation(self):
        goal = Goal(goal_id="g1", description="Solve the problem")
        assert goal.goal_id == "g1"
        assert goal.status == "pending"
        assert goal.sub_goals == []
        assert goal.reasoning_trace == []

    def test_goal_with_sub_goals(self):
        sub = Goal(goal_id="s1", description="Sub-task")
        goal = Goal(goal_id="g1", description="Main", sub_goals=[sub])
        assert len(goal.sub_goals) == 1


class TestReasoningStep:
    def test_creation(self):
        step = ReasoningStep(step_number=0, phase="think", content="I should search.")
        assert step.step_number == 0
        assert step.phase == "think"
        assert step.tool_calls == []
        assert step.timestamp > 0


class TestAutonomousAgent:
    def test_creation(self):
        config = make_config()
        auto_config = make_auto_config()
        agent = AutonomousAgent(config, auto_config)
        assert agent.agent_id == "auto-test-agent"
        assert agent.llm is not None
        assert agent.memory is not None
        assert agent.tool_registry is not None

    def test_pursue_goal_simple(self):
        """Test that pursuing a simple goal works when LLM responds with stop."""
        config = make_config()
        auto_config = make_auto_config()
        agent = AutonomousAgent(config, auto_config)

        # Override LLM with scripted responses
        agent.llm = MockLLMProvider(auto_config.llm, responses=[
            LLMResponse(
                content="The answer is 42.",
                finish_reason="stop",
                usage=TokenUsage(prompt_tokens=20, completion_tokens=10, total_tokens=30),
            ),
        ])

        result = agent.pursue_goal("What is the answer to everything?")
        assert result.is_ok()
        goal = result.unwrap()
        assert goal.status == "completed"
        assert goal.result == "The answer is 42."
        assert len(goal.reasoning_trace) == 1

    def test_pursue_goal_with_tool_call(self):
        """Test that the agent executes tool calls from LLM."""
        config = make_config()
        auto_config = make_auto_config()
        agent = AutonomousAgent(config, auto_config)

        # Register a custom tool
        from maple.autonomy.tools import Tool
        tool = Tool(
            name="calculator",
            description="Add two numbers",
            parameters={"type": "object", "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}}},
            handler=lambda a=0, b=0: Result.ok({"sum": a + b}),
        )
        agent.register_tool(tool)

        # Scripted: first response has tool call, second is final answer
        agent.llm = MockLLMProvider(auto_config.llm, responses=[
            LLMResponse(
                content="Let me calculate.",
                tool_calls=[ToolCall(id="tc_1", name="calculator", arguments={"a": 3, "b": 4})],
                finish_reason="tool_calls",
                usage=TokenUsage(prompt_tokens=20, completion_tokens=10, total_tokens=30),
            ),
            LLMResponse(
                content="The sum is 7.",
                finish_reason="stop",
                usage=TokenUsage(prompt_tokens=30, completion_tokens=5, total_tokens=35),
            ),
        ])

        result = agent.pursue_goal("What is 3 + 4?")
        assert result.is_ok()
        goal = result.unwrap()
        assert goal.status == "completed"
        assert "7" in goal.result
        assert len(goal.reasoning_trace) == 2

    def test_pursue_goal_tool_not_found(self):
        """Test graceful handling when LLM calls a nonexistent tool."""
        config = make_config()
        auto_config = make_auto_config()
        agent = AutonomousAgent(config, auto_config)

        agent.llm = MockLLMProvider(auto_config.llm, responses=[
            LLMResponse(
                content="Let me use a tool.",
                tool_calls=[ToolCall(id="tc_1", name="nonexistent_tool", arguments={})],
                finish_reason="tool_calls",
                usage=TokenUsage(prompt_tokens=20, completion_tokens=10, total_tokens=30),
            ),
            LLMResponse(
                content="The tool didn't work, but I'll answer anyway.",
                finish_reason="stop",
                usage=TokenUsage(prompt_tokens=30, completion_tokens=10, total_tokens=40),
            ),
        ])

        result = agent.pursue_goal("Do something")
        assert result.is_ok()
        goal = result.unwrap()
        # Should still complete - the tool error is reported back to LLM
        assert goal.status == "completed"
        # The tool result should be an error
        assert len(goal.reasoning_trace[0].tool_results) == 1
        assert goal.reasoning_trace[0].tool_results[0].is_error

    def test_max_steps_reached(self):
        """Test that hitting max steps returns an error."""
        config = make_config()
        auto_config = make_auto_config(max_reasoning_steps=2)
        agent = AutonomousAgent(config, auto_config)

        # LLM always responds with content but no stop signal
        agent.llm = MockLLMProvider(auto_config.llm, responses=[
            LLMResponse(
                content="Thinking step 1...",
                tool_calls=[ToolCall(id="tc_1", name="query_agents", arguments={})],
                finish_reason="tool_calls",
                usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            ),
            LLMResponse(
                content="Thinking step 2...",
                tool_calls=[ToolCall(id="tc_2", name="query_agents", arguments={})],
                finish_reason="tool_calls",
                usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            ),
        ])

        result = agent.pursue_goal("An impossible task")
        assert result.is_ok()
        goal = result.unwrap()
        assert goal.status == "failed"

    def test_approval_callback(self):
        """Test human-in-the-loop approval."""
        config = make_config()
        auto_config = make_auto_config(require_approval_for=["write_state"])
        agent = AutonomousAgent(config, auto_config)

        approved_calls = []

        def approval_callback(tool_name, args):
            approved_calls.append(tool_name)
            return False  # Deny

        agent.set_approval_callback(approval_callback)

        agent.llm = MockLLMProvider(auto_config.llm, responses=[
            LLMResponse(
                content="Writing state.",
                tool_calls=[ToolCall(id="tc_1", name="write_state", arguments={"key": "test", "value": "val"})],
                finish_reason="tool_calls",
                usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            ),
            LLMResponse(
                content="Action was denied.",
                finish_reason="stop",
                usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            ),
        ])

        result = agent.pursue_goal("Write some state")
        assert result.is_ok()
        assert "write_state" in approved_calls

    def test_get_active_goals(self):
        config = make_config()
        auto_config = make_auto_config()
        agent = AutonomousAgent(config, auto_config)

        # Override to make it stop immediately
        agent.llm = MockLLMProvider(auto_config.llm, responses=[
            LLMResponse(content="Done.", finish_reason="stop",
                        usage=TokenUsage(prompt_tokens=5, completion_tokens=5, total_tokens=10)),
        ])
        agent.pursue_goal("Test goal")
        goals = agent.get_active_goals()
        assert len(goals) == 1

    def test_decompose_goal(self):
        """Test goal decomposition."""
        config = make_config()
        auto_config = make_auto_config()
        agent = AutonomousAgent(config, auto_config)

        agent.llm = MockLLMProvider(auto_config.llm, responses=[
            LLMResponse(
                content='["Step 1: Research", "Step 2: Implement", "Step 3: Test"]',
                finish_reason="stop",
                usage=TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
            ),
        ])

        goal = Goal(goal_id="g1", description="Build a feature")
        result = agent.decompose_goal(goal)
        assert result.is_ok()
        sub_goals = result.unwrap()
        assert len(sub_goals) == 3
        assert "Research" in sub_goals[0].description


class TestReflection:
    def test_reflection_triggers(self):
        """Test that reflection triggers at the right frequency."""
        config = make_config()
        # reflection_frequency=2 means reflect after step 1, step 3, etc.
        auto_config = make_auto_config(
            max_reasoning_steps=4,
            reflection_frequency=2,
        )
        agent = AutonomousAgent(config, auto_config)

        agent.llm = MockLLMProvider(auto_config.llm, responses=[
            # Step 0: tool call
            LLMResponse(
                content="Step 0",
                tool_calls=[ToolCall(id="tc_1", name="query_agents", arguments={})],
                finish_reason="tool_calls",
                usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            ),
            # Step 1: tool call (triggers reflection after this)
            LLMResponse(
                content="Step 1",
                tool_calls=[ToolCall(id="tc_2", name="query_agents", arguments={})],
                finish_reason="tool_calls",
                usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            ),
            # Reflection response
            LLMResponse(
                content='{"should_stop": true, "conclusion": "All done", "reason": "task complete"}',
                finish_reason="stop",
                usage=TokenUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
            ),
        ])

        result = agent.pursue_goal("Test reflection")
        assert result.is_ok()
        goal = result.unwrap()
        assert goal.status == "completed"
