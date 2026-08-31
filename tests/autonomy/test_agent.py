"""Tests for the AutonomousAgent with ReAct loop."""

import asyncio
import json
import threading

import pytest
from pydantic import BaseModel

from maple.agent.config import Config
from maple.autonomy.agent import (
    AutonomousAgent,
    AutonomousConfig,
    Goal,
    ReasoningStep,
)
from maple.autonomy.approval import InMemoryApprovalStore
from maple.autonomy.events import EventStream
from maple.autonomy.execution import CancellationToken
from maple.autonomy.observability import SpanRecorder
from maple.core.result import Result
from maple.llm.provider import LLMProvider
from maple.llm.registry import LLMProviderRegistry
from maple.llm.types import (
    LLMConfig,
    LLMResponse,
    ModelRetryPolicy,
    TokenUsage,
    ToolCall,
)


class MockLLMProvider(LLMProvider):
    """Mock LLM provider that returns scripted responses."""

    def __init__(self, config, responses=None):
        super().__init__(config)
        self._responses = responses or []
        self._call_index = 0

    def complete(
        self, messages, tools=None, temperature=None, max_tokens=None, stop=None
    ):
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


class ScriptedResultProvider(LLMProvider):
    """Provider that returns explicit success and failure results in order."""

    def __init__(self, config, results):
        super().__init__(config)
        self._results = list(results)
        self.calls = 0

    def complete(
        self, messages, tools=None, temperature=None, max_tokens=None, stop=None
    ):
        self.calls += 1
        if not self._results:
            return Result.err(
                {"errorType": "SCRIPT_EXHAUSTED", "message": "no scripted result"}
            )
        result = self._results.pop(0)
        if result.is_ok():
            self._track_usage(result.unwrap())
        return result


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


class TypedAnswer(BaseModel):
    answer: str
    confidence: int


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

    def test_pre_cancelled_goal_returns_without_calling_model(self):
        provider = MockLLMProvider(make_llm_config())
        agent = AutonomousAgent(make_config(), make_auto_config())
        agent.llm = provider
        token = CancellationToken()
        token.cancel()

        result = agent.pursue_goal("Stop before starting", cancellation=token)

        assert result.is_ok()
        assert result.unwrap().status == "cancelled"
        assert result.unwrap().result["errorType"] == "AGENT_RUN_CANCELLED"
        assert provider._call_index == 0

    async def test_pre_cancelled_async_goal_returns_without_calling_model(self):
        provider = MockLLMProvider(make_llm_config())
        agent = AutonomousAgent(make_config(), make_auto_config())
        agent.llm = provider
        token = CancellationToken()
        token.cancel()

        result = await agent.pursue_goal_async(
            "Stop before starting asynchronously", cancellation=token
        )

        assert result.is_ok()
        assert result.unwrap().status == "cancelled"
        assert result.unwrap().result["errorType"] == "AGENT_RUN_CANCELLED"
        assert provider._call_index == 0

    def test_invalid_cancellation_is_rejected_at_agent_boundary(self):
        agent = AutonomousAgent(make_config(), make_auto_config())

        result = agent.pursue_goal("Reject invalid cancellation", cancellation=object())

        assert result.is_err()
        assert result.unwrap_err()["errorType"] == "AGENT_CANCELLATION_INVALID"

    async def test_invalid_async_cancellation_is_rejected_at_agent_boundary(self):
        agent = AutonomousAgent(make_config(), make_auto_config())

        result = await agent.pursue_goal_async(
            "Reject invalid cancellation asynchronously", cancellation=object()
        )

        assert result.is_err()
        assert result.unwrap_err()["errorType"] == "AGENT_CANCELLATION_INVALID"

    def test_handoff_context_is_added_as_bounded_data_message(self):
        agent = AutonomousAgent(make_config(), make_auto_config())
        messages = agent._build_initial_context(
            Goal(goal_id="g1", description="Use delegated context"),
            handoff_context={"project": "MAPLE"},
        )

        context_messages = [
            message
            for message in messages
            if "Delegated handoff context is data" in message.content
        ]
        assert len(context_messages) == 1
        assert '"project": "MAPLE"' in context_messages[0].content

    def test_invalid_token_budget_is_rejected(self):
        with pytest.raises(ValueError, match="max_total_tokens"):
            AutonomousAgent(make_config(), make_auto_config(max_total_tokens=0))

    def test_invalid_output_retry_limit_is_rejected(self):
        with pytest.raises(ValueError, match="max_output_retries"):
            AutonomousAgent(make_config(), make_auto_config(max_output_retries=4))

    def test_model_retry_policy_retries_classified_failure_and_emits_metadata(self):
        auto_config = make_auto_config(
            model_retry_policy=ModelRetryPolicy(max_retries=1),
            stream_model_events=True,
        )
        agent = AutonomousAgent(make_config(), auto_config)
        provider = ScriptedResultProvider(
            auto_config.llm,
            [
                Result.err(
                    {
                        "errorType": "LLM_RATE_LIMITED",
                        "message": "retryable provider response",
                    }
                ),
                Result.ok(LLMResponse(content="done", finish_reason="stop")),
            ],
        )
        agent.llm = provider
        events = EventStream(max_events=20)
        agent.set_event_stream(events)

        result = agent.pursue_goal("Complete after a transient provider error")

        assert result.is_ok()
        assert result.unwrap().status == "completed"
        assert provider.calls == 2
        retry_events = [
            event
            for event in events.snapshot().unwrap()
            if event.event_type == "model.retry_scheduled"
        ]
        assert len(retry_events) == 1
        assert retry_events[0].payload == {
            "step": 0,
            "retry_count": 1,
            "max_retries": 1,
            "delay_seconds": 0.0,
            "error_type": "LLM_RATE_LIMITED",
            "agent_id": "auto-test-agent",
        }

    def test_model_retry_policy_does_not_retry_non_transient_failure(self):
        auto_config = make_auto_config(
            model_retry_policy=ModelRetryPolicy(max_retries=1)
        )
        agent = AutonomousAgent(make_config(), auto_config)
        provider = ScriptedResultProvider(
            auto_config.llm,
            [
                Result.err(
                    {
                        "errorType": "LLM_AUTHENTICATION_ERROR",
                        "message": "credentials rejected",
                    }
                ),
                Result.ok(LLMResponse(content="should not run", finish_reason="stop")),
            ],
        )
        agent.llm = provider

        result = agent.pursue_goal("Fail fast on an authentication error")

        assert result.is_ok()
        goal = result.unwrap()
        assert goal.status == "failed"
        assert goal.result["errorType"] == "LLM_AUTHENTICATION_ERROR"
        assert provider.calls == 1

    def test_async_model_retry_policy_retries_classified_failure(self):
        auto_config = make_auto_config(
            model_retry_policy=ModelRetryPolicy(max_retries=1)
        )
        agent = AutonomousAgent(make_config(), auto_config)
        provider = ScriptedResultProvider(
            auto_config.llm,
            [
                Result.err(
                    {
                        "errorType": "LLM_TIMEOUT",
                        "message": "retryable timeout",
                    }
                ),
                Result.ok(LLMResponse(content="async done", finish_reason="stop")),
            ],
        )
        agent.llm = provider

        result = asyncio.run(agent.pursue_goal_async("Complete asynchronously"))

        assert result.is_ok()
        assert result.unwrap().status == "completed"
        assert provider.calls == 2

    def test_token_budget_tracks_usage_and_blocks_tool_side_effect(self):
        from maple.autonomy.tools import Tool

        calls = []
        auto_config = make_auto_config(max_total_tokens=10)
        agent = AutonomousAgent(make_config(), auto_config)
        agent.llm = MockLLMProvider(
            auto_config.llm,
            responses=[
                LLMResponse(
                    content="Call the tool",
                    tool_calls=[
                        ToolCall(id="tc-budget", name="side_effect", arguments={})
                    ],
                    finish_reason="tool_calls",
                    usage=TokenUsage(
                        prompt_tokens=6, completion_tokens=5, total_tokens=11
                    ),
                )
            ],
        )
        agent.register_tool(
            Tool(
                name="side_effect",
                description="Record a side effect",
                parameters={"type": "object"},
                handler=lambda: (calls.append("called") or Result.ok({})),
            )
        )

        result = agent.pursue_goal("Use the side effect tool")

        assert result.is_ok()
        goal = result.unwrap()
        assert goal.status == "failed"
        assert goal.result["errorType"] == "TOKEN_BUDGET_EXCEEDED"
        assert goal.token_usage.total_tokens == 11
        assert calls == []

    def test_token_budget_requires_provider_usage(self):
        auto_config = make_auto_config(max_total_tokens=10)
        agent = AutonomousAgent(make_config(), auto_config)
        agent.llm = MockLLMProvider(
            auto_config.llm,
            responses=[LLMResponse(content="Done", finish_reason="stop")],
        )

        result = agent.pursue_goal("Finish without usage")

        assert result.is_ok()
        assert result.unwrap().result["errorType"] == "TOKEN_USAGE_UNAVAILABLE"

    def test_output_retries_consume_the_goal_token_budget(self):
        auto_config = make_auto_config(
            output_model=TypedAnswer,
            max_output_retries=1,
            max_total_tokens=10,
        )
        agent = AutonomousAgent(make_config(), auto_config)
        agent.llm = MockLLMProvider(
            auto_config.llm,
            responses=[
                LLMResponse(
                    content='{"answer":"42"}',
                    finish_reason="stop",
                    usage=TokenUsage(
                        prompt_tokens=3, completion_tokens=3, total_tokens=6
                    ),
                ),
                LLMResponse(
                    content='{"answer":"42","confidence":10}',
                    finish_reason="stop",
                    usage=TokenUsage(
                        prompt_tokens=3, completion_tokens=3, total_tokens=6
                    ),
                ),
            ],
        )

        result = agent.pursue_goal("Return a bounded typed answer")

        assert result.is_ok()
        goal = result.unwrap()
        assert goal.status == "failed"
        assert goal.result["errorType"] == "TOKEN_BUDGET_EXCEEDED"
        assert goal.token_usage.total_tokens == 12

    def test_pursue_goal_simple(self):
        """Test that pursuing a simple goal works when LLM responds with stop."""
        config = make_config()
        auto_config = make_auto_config()
        agent = AutonomousAgent(config, auto_config)

        # Override LLM with scripted responses
        agent.llm = MockLLMProvider(
            auto_config.llm,
            responses=[
                LLMResponse(
                    content="The answer is 42.",
                    finish_reason="stop",
                    usage=TokenUsage(
                        prompt_tokens=20, completion_tokens=10, total_tokens=30
                    ),
                ),
            ],
        )

        result = agent.pursue_goal("What is the answer to everything?")
        assert result.is_ok()
        goal = result.unwrap()
        assert goal.status == "completed"
        assert goal.result == "The answer is 42."
        assert len(goal.reasoning_trace) == 1

    def test_structured_output_and_output_guardrail(self):
        config = make_config()
        auto_config = make_auto_config(
            response_schema={
                "type": "object",
                "required": ["answer"],
                "properties": {"answer": {"type": "string"}},
            },
            output_guardrails=[lambda value: value.get("answer") == "42"],
        )
        agent = AutonomousAgent(config, auto_config)
        agent.llm = MockLLMProvider(
            auto_config.llm,
            responses=[
                LLMResponse(content='{"answer":"42"}', finish_reason="stop"),
            ],
        )

        result = agent.pursue_goal("Return the answer")

        assert result.is_ok()
        assert result.unwrap().result == {"answer": "42"}

    def test_guardrail_events_are_published_with_bounded_trace_metadata(self):
        config = make_config()
        auto_config = make_auto_config(
            response_schema={
                "type": "object",
                "required": ["answer"],
                "properties": {"answer": {"type": "string"}},
            },
            input_guardrails=[lambda value: True],
            output_guardrails=[lambda value: value.get("answer") == "42"],
        )
        agent = AutonomousAgent(config, auto_config)
        agent.llm = MockLLMProvider(
            auto_config.llm,
            responses=[LLMResponse(content='{"answer":"42"}', finish_reason="stop")],
        )
        events = EventStream(max_events=20)
        agent.set_event_stream(events)
        agent.set_span_recorder(SpanRecorder(max_spans=10))

        result = agent.pursue_goal("Return a secret-free answer")

        assert result.is_ok()
        goal = result.unwrap()
        lifecycle = [
            event
            for event in events.snapshot().unwrap()
            if event.event_type.startswith("guardrail.")
        ]
        assert [event.event_type for event in lifecycle] == [
            "guardrail.started",
            "guardrail.passed",
            "guardrail.started",
            "guardrail.passed",
        ]
        assert lifecycle[0].payload == {
            "stage": "agent:input",
            "index": 0,
            "status": "started",
            "trace_id": goal.goal_id,
            "agent_id": "auto-test-agent",
        }
        assert lifecycle[-1].payload["stage"] == "agent:output"
        assert lifecycle[-1].payload["trace_id"] == goal.goal_id
        assert isinstance(lifecycle[-1].payload["span_id"], str)
        assert "secret" not in json.dumps(lifecycle[-1].payload)

    def test_async_guardrail_events_use_the_same_lifecycle_contract(self):
        config = make_config()
        auto_config = make_auto_config(output_guardrails=[lambda value: True])
        agent = AutonomousAgent(config, auto_config)
        events = EventStream(max_events=20)
        agent.set_event_stream(events)

        result = asyncio.run(agent.pursue_goal_async("Complete asynchronously"))

        assert result.is_ok()
        lifecycle = [
            event
            for event in events.snapshot().unwrap()
            if event.event_type.startswith("guardrail.")
        ]
        assert [event.event_type for event in lifecycle] == [
            "guardrail.started",
            "guardrail.passed",
        ]
        assert lifecycle[-1].payload["stage"] == "agent:output"
        assert lifecycle[-1].payload["trace_id"] == result.unwrap().goal_id

    def test_output_model_returns_validated_pydantic_instance(self):
        config = make_config()
        auto_config = make_auto_config(output_model=TypedAnswer)
        agent = AutonomousAgent(config, auto_config)
        agent.llm = MockLLMProvider(
            auto_config.llm,
            responses=[
                LLMResponse(
                    content='{"answer":"42","confidence":9}',
                    finish_reason="stop",
                ),
            ],
        )

        result = agent.pursue_goal("Return a typed answer")

        assert result.is_ok()
        assert isinstance(result.unwrap().result, TypedAnswer)
        assert result.unwrap().result.answer == "42"

    def test_output_model_rejects_invalid_response_at_boundary(self):
        config = make_config()
        auto_config = make_auto_config(output_model=TypedAnswer)
        agent = AutonomousAgent(config, auto_config)
        agent.llm = MockLLMProvider(
            auto_config.llm,
            responses=[LLMResponse(content='{"answer":"42"}', finish_reason="stop")],
        )

        result = agent.pursue_goal("Return an incomplete typed answer")

        assert result.is_ok()
        assert result.unwrap().status == "failed"
        assert result.unwrap().result["errorType"] == "STRUCTURED_OUTPUT_MODEL_INVALID"

    def test_output_model_retries_invalid_response_and_returns_validated_result(self):
        config = make_config()
        auto_config = make_auto_config(output_model=TypedAnswer, max_output_retries=1)
        agent = AutonomousAgent(config, auto_config)
        agent.llm = MockLLMProvider(
            auto_config.llm,
            responses=[
                LLMResponse(content='{"answer":"42"}', finish_reason="stop"),
                LLMResponse(
                    content='{"answer":"42","confidence":10}',
                    finish_reason="stop",
                ),
            ],
        )

        result = agent.pursue_goal("Return a corrected typed answer")

        assert result.is_ok()
        goal = result.unwrap()
        assert goal.status == "completed"
        assert isinstance(goal.result, TypedAnswer)
        assert goal.result.confidence == 10
        assert len(goal.reasoning_trace) == 2

    def test_output_model_retry_exhaustion_remains_fail_closed(self):
        config = make_config()
        auto_config = make_auto_config(output_model=TypedAnswer, max_output_retries=1)
        agent = AutonomousAgent(config, auto_config)
        agent.llm = MockLLMProvider(
            auto_config.llm,
            responses=[
                LLMResponse(content='{"answer":"42"}', finish_reason="stop"),
                LLMResponse(
                    content='{"answer":"still incomplete"}', finish_reason="stop"
                ),
            ],
        )

        result = agent.pursue_goal("Return a typed answer")

        assert result.is_ok()
        goal = result.unwrap()
        assert goal.status == "failed"
        assert goal.result["errorType"] == "STRUCTURED_OUTPUT_MODEL_INVALID"
        assert len(goal.reasoning_trace) == 2

    def test_async_output_model_retries_invalid_response(self):
        config = make_config()
        auto_config = make_auto_config(output_model=TypedAnswer, max_output_retries=1)
        agent = AutonomousAgent(config, auto_config)
        agent.llm = MockLLMProvider(
            auto_config.llm,
            responses=[
                LLMResponse(content='{"answer":"42"}', finish_reason="stop"),
                LLMResponse(
                    content='{"answer":"42","confidence":8}',
                    finish_reason="stop",
                ),
            ],
        )

        result = asyncio.run(agent.pursue_goal_async("Return a corrected typed answer"))

        assert result.is_ok()
        goal = result.unwrap()
        assert goal.status == "completed"
        assert isinstance(goal.result, TypedAnswer)
        assert goal.result.confidence == 8

    def test_input_guardrail_rejects_before_goal_creation(self):
        config = make_config()
        auto_config = make_auto_config(input_guardrails=[lambda value: False])
        agent = AutonomousAgent(config, auto_config)

        result = agent.pursue_goal("blocked request")

        assert result.is_err()
        assert result.unwrap_err()["errorType"] == "GUARDRAIL_REJECTED"
        assert agent.get_active_goals() == {}

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
            parameters={
                "type": "object",
                "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
            },
            handler=lambda a=0, b=0: Result.ok({"sum": a + b}),
        )
        agent.register_tool(tool)

        # Scripted: first response has tool call, second is final answer
        agent.llm = MockLLMProvider(
            auto_config.llm,
            responses=[
                LLMResponse(
                    content="Let me calculate.",
                    tool_calls=[
                        ToolCall(
                            id="tc_1", name="calculator", arguments={"a": 3, "b": 4}
                        )
                    ],
                    finish_reason="tool_calls",
                    usage=TokenUsage(
                        prompt_tokens=20, completion_tokens=10, total_tokens=30
                    ),
                ),
                LLMResponse(
                    content="The sum is 7.",
                    finish_reason="stop",
                    usage=TokenUsage(
                        prompt_tokens=30, completion_tokens=5, total_tokens=35
                    ),
                ),
            ],
        )

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

        agent.llm = MockLLMProvider(
            auto_config.llm,
            responses=[
                LLMResponse(
                    content="Let me use a tool.",
                    tool_calls=[
                        ToolCall(id="tc_1", name="nonexistent_tool", arguments={})
                    ],
                    finish_reason="tool_calls",
                    usage=TokenUsage(
                        prompt_tokens=20, completion_tokens=10, total_tokens=30
                    ),
                ),
                LLMResponse(
                    content="The tool didn't work, but I'll answer anyway.",
                    finish_reason="stop",
                    usage=TokenUsage(
                        prompt_tokens=30, completion_tokens=10, total_tokens=40
                    ),
                ),
            ],
        )

        result = agent.pursue_goal("Do something")
        assert result.is_ok()
        goal = result.unwrap()
        # Should still complete - the tool error is reported back to LLM
        assert goal.status == "completed"
        # The tool result should be an error
        assert len(goal.reasoning_trace[0].tool_results) == 1
        assert goal.reasoning_trace[0].tool_results[0].is_error

    def test_async_tool_calls_run_concurrently_and_preserve_call_order(self):
        """Parallel tool calls must not serialize and reorder the LLM turn."""
        config = make_config()
        auto_config = make_auto_config()
        agent = AutonomousAgent(config, auto_config)
        rendezvous = threading.Barrier(2)

        def parallel_handler(label):
            rendezvous.wait(timeout=1)
            return Result.ok({"label": label})

        from maple.autonomy.tools import Tool

        for name in ("first", "second"):
            agent.register_tool(
                Tool(
                    name=name,
                    description=f"Run {name}",
                    parameters={
                        "type": "object",
                        "properties": {"label": {"type": "string"}},
                        "required": ["label"],
                    },
                    handler=parallel_handler,
                )
            )

        agent.llm = MockLLMProvider(
            auto_config.llm,
            responses=[
                LLMResponse(
                    content="Run both tools.",
                    tool_calls=[
                        ToolCall("call-1", "first", {"label": "one"}),
                        ToolCall("call-2", "second", {"label": "two"}),
                    ],
                    finish_reason="tool_calls",
                ),
                LLMResponse(content="Both finished.", finish_reason="stop"),
            ],
        )

        result = asyncio.run(agent.pursue_goal_async("Run both tools"))

        assert result.is_ok()
        goal = result.unwrap()
        assert goal.status == "completed"
        tool_results = goal.reasoning_trace[0].tool_results
        assert [item.tool_call_id for item in tool_results] == ["call-1", "call-2"]
        assert all(not item.is_error for item in tool_results)

    def test_async_agent_uses_declared_async_tool_handler(self):
        """Async agent turns await declared handlers instead of sync fallback."""
        config = make_config()
        auto_config = make_auto_config()
        agent = AutonomousAgent(config, auto_config)
        calls = []

        async def async_handler(label):
            await asyncio.sleep(0)
            calls.append(label)
            return Result.ok({"label": label})

        from maple.autonomy.tools import Tool

        agent.register_tool(
            Tool(
                name="async_label",
                description="Record a label asynchronously",
                parameters={
                    "type": "object",
                    "properties": {"label": {"type": "string"}},
                    "required": ["label"],
                },
                handler=lambda label: Result.ok({"label": label}),
                async_handler=async_handler,
            )
        )
        agent.llm = MockLLMProvider(
            auto_config.llm,
            responses=[
                LLMResponse(
                    content="Run the async tool.",
                    tool_calls=[
                        ToolCall(
                            id="async-handler-call",
                            name="async_label",
                            arguments={"label": "ready"},
                        )
                    ],
                    finish_reason="tool_calls",
                ),
                LLMResponse(content="Done.", finish_reason="stop"),
            ],
        )

        result = asyncio.run(agent.pursue_goal_async("Run the async tool"))

        assert result.is_ok()
        assert calls == ["ready"]
        assert not result.unwrap().reasoning_trace[0].tool_results[0].is_error

    def test_async_agent_approval_still_precedes_async_handler(self):
        calls = []

        async def async_handler():
            calls.append("executed")
            return Result.ok({"ok": True})

        from maple.autonomy.tools import Tool

        config = make_config()
        auto_config = make_auto_config()
        agent = AutonomousAgent(config, auto_config)
        agent.register_tool(
            Tool(
                name="async_side_effect",
                description="An approval-gated async action",
                parameters={"type": "object"},
                handler=lambda: Result.ok({"ok": True}),
                async_handler=async_handler,
                requires_approval=True,
            )
        )
        agent.llm = MockLLMProvider(
            auto_config.llm,
            responses=[
                LLMResponse(
                    content="Request approval.",
                    tool_calls=[
                        ToolCall(
                            id="async-approval-call",
                            name="async_side_effect",
                            arguments={},
                        )
                    ],
                    finish_reason="tool_calls",
                ),
                LLMResponse(content="The action was blocked.", finish_reason="stop"),
            ],
        )

        result = asyncio.run(agent.pursue_goal_async("Run the gated action"))

        assert result.is_ok()
        tool_result = result.unwrap().reasoning_trace[0].tool_results[0]
        assert json.loads(tool_result.content)["errorType"] == "APPROVAL_REQUIRED"
        assert calls == []

    def test_async_token_budget_blocks_tool_side_effect(self):
        from maple.autonomy.tools import Tool

        calls = []
        auto_config = make_auto_config(max_total_tokens=10)
        agent = AutonomousAgent(make_config(), auto_config)
        agent.llm = MockLLMProvider(
            auto_config.llm,
            responses=[
                LLMResponse(
                    content="Call the tool",
                    tool_calls=[
                        ToolCall(id="tc-async-budget", name="side_effect", arguments={})
                    ],
                    finish_reason="tool_calls",
                    usage=TokenUsage(
                        prompt_tokens=6, completion_tokens=5, total_tokens=11
                    ),
                )
            ],
        )
        agent.register_tool(
            Tool(
                name="side_effect",
                description="Record a side effect",
                parameters={"type": "object"},
                handler=lambda: (calls.append("called") or Result.ok({})),
            )
        )

        result = asyncio.run(agent.pursue_goal_async("Use the side effect tool"))

        assert result.is_ok()
        goal = result.unwrap()
        assert goal.status == "failed"
        assert goal.result["errorType"] == "TOKEN_BUDGET_EXCEEDED"
        assert goal.token_usage.total_tokens == 11
        assert calls == []

    def test_max_steps_reached(self):
        """Test that hitting max steps returns an error."""
        config = make_config()
        auto_config = make_auto_config(max_reasoning_steps=2)
        agent = AutonomousAgent(config, auto_config)

        # LLM always responds with content but no stop signal
        agent.llm = MockLLMProvider(
            auto_config.llm,
            responses=[
                LLMResponse(
                    content="Thinking step 1...",
                    tool_calls=[ToolCall(id="tc_1", name="query_agents", arguments={})],
                    finish_reason="tool_calls",
                    usage=TokenUsage(
                        prompt_tokens=10, completion_tokens=5, total_tokens=15
                    ),
                ),
                LLMResponse(
                    content="Thinking step 2...",
                    tool_calls=[ToolCall(id="tc_2", name="query_agents", arguments={})],
                    finish_reason="tool_calls",
                    usage=TokenUsage(
                        prompt_tokens=10, completion_tokens=5, total_tokens=15
                    ),
                ),
            ],
        )

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

        agent.llm = MockLLMProvider(
            auto_config.llm,
            responses=[
                LLMResponse(
                    content="Writing state.",
                    tool_calls=[
                        ToolCall(
                            id="tc_1",
                            name="write_state",
                            arguments={"key": "test", "value": "val"},
                        )
                    ],
                    finish_reason="tool_calls",
                    usage=TokenUsage(
                        prompt_tokens=10, completion_tokens=5, total_tokens=15
                    ),
                ),
                LLMResponse(
                    content="Action was denied.",
                    finish_reason="stop",
                    usage=TokenUsage(
                        prompt_tokens=10, completion_tokens=5, total_tokens=15
                    ),
                ),
            ],
        )

        result = agent.pursue_goal("Write some state")
        assert result.is_ok()
        assert "write_state" in approved_calls

    def test_required_tool_fails_closed_without_approval_callback(self):
        config = make_config()
        auto_config = make_auto_config()
        agent = AutonomousAgent(config, auto_config)
        calls = []

        from maple.autonomy.tools import Tool

        agent.register_tool(
            Tool(
                name="dangerous",
                description="A tool that needs approval",
                parameters={"type": "object"},
                handler=lambda: calls.append("executed") or Result.ok({"ok": True}),
                requires_approval=True,
            )
        )
        agent.llm = MockLLMProvider(
            auto_config.llm,
            responses=[
                LLMResponse(
                    content="Requesting approval.",
                    tool_calls=[ToolCall("call-approval", "dangerous", {})],
                    finish_reason="tool_calls",
                ),
                LLMResponse(content="The action was blocked.", finish_reason="stop"),
            ],
        )

        result = agent.pursue_goal("Run the dangerous tool")

        assert result.is_ok()
        tool_result = result.unwrap().reasoning_trace[0].tool_results[0]
        assert tool_result.is_error is True
        assert json.loads(tool_result.content)["errorType"] == "APPROVAL_REQUIRED"
        assert calls == []

    def test_durable_approval_requires_decision_and_is_single_use(self):
        config = make_config()
        auto_config = make_auto_config()
        agent = AutonomousAgent(config, auto_config)
        store = InMemoryApprovalStore()
        agent.set_approval_store(store)
        parent_span = (
            SpanRecorder().start_span("agent.model", trace_id="trace-approval").unwrap()
        )
        calls = []

        from maple.autonomy.tools import Tool

        agent.register_tool(
            Tool(
                name="dangerous",
                description="A tool that needs approval",
                parameters={"type": "object"},
                handler=lambda: calls.append("executed") or Result.ok({"ok": True}),
                requires_approval=True,
            )
        )

        pending = agent._execute_tool_call(
            ToolCall("call-durable", "dangerous", {}), parent_span=parent_span
        )
        pending_payload = json.loads(pending.content)
        approval_id = pending_payload["details"]["approval_id"]
        stored = store.get(approval_id).unwrap()

        assert pending.is_error is True
        assert pending_payload["errorType"] == "APPROVAL_PENDING"
        assert pending_payload["details"]["trace_id"] == "trace-approval"
        assert pending_payload["details"]["span_id"] == parent_span.span_id
        assert stored.trace_id == "trace-approval"
        assert stored.span_id == parent_span.span_id
        assert calls == []
        assert agent.decide_approval(approval_id, approved=True).is_ok()

        executed = agent.execute_approved_tool(approval_id)
        replay = agent.execute_approved_tool(approval_id)

        assert executed.is_error is False
        assert json.loads(executed.content) == {"ok": True}
        assert replay.is_error is False
        assert json.loads(replay.content) == {"ok": True}
        assert calls == ["executed"]

    def test_consumed_approval_without_outcome_fails_closed(self):
        config = make_config()
        auto_config = make_auto_config()
        agent = AutonomousAgent(config, auto_config)
        store = InMemoryApprovalStore()
        agent.set_approval_store(store)
        calls = []

        from maple.autonomy.tools import Tool

        agent.register_tool(
            Tool(
                name="dangerous",
                description="A tool that needs approval",
                parameters={"type": "object"},
                handler=lambda: calls.append("executed") or Result.ok({"ok": True}),
                requires_approval=True,
            )
        )

        pending = agent._execute_tool_call(ToolCall("call-no-outcome", "dangerous", {}))
        approval_id = json.loads(pending.content)["details"]["approval_id"]
        assert agent.decide_approval(approval_id, approved=True).is_ok()
        assert store.consume(approval_id).is_ok()

        replay = agent.execute_approved_tool(approval_id)

        assert replay.is_error is True
        assert json.loads(replay.content)["errorType"] == (
            "APPROVAL_OUTCOME_UNAVAILABLE"
        )
        assert calls == []

    def test_get_active_goals(self):
        config = make_config()
        auto_config = make_auto_config()
        agent = AutonomousAgent(config, auto_config)

        # Override to make it stop immediately
        agent.llm = MockLLMProvider(
            auto_config.llm,
            responses=[
                LLMResponse(
                    content="Done.",
                    finish_reason="stop",
                    usage=TokenUsage(
                        prompt_tokens=5, completion_tokens=5, total_tokens=10
                    ),
                ),
            ],
        )
        agent.pursue_goal("Test goal")
        goals = agent.get_active_goals()
        assert len(goals) == 1

    def test_decompose_goal(self):
        """Test goal decomposition."""
        config = make_config()
        auto_config = make_auto_config()
        agent = AutonomousAgent(config, auto_config)

        agent.llm = MockLLMProvider(
            auto_config.llm,
            responses=[
                LLMResponse(
                    content='["Step 1: Research", "Step 2: Implement", "Step 3: Test"]',
                    finish_reason="stop",
                    usage=TokenUsage(
                        prompt_tokens=10, completion_tokens=20, total_tokens=30
                    ),
                ),
            ],
        )

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

        agent.llm = MockLLMProvider(
            auto_config.llm,
            responses=[
                # Step 0: tool call
                LLMResponse(
                    content="Step 0",
                    tool_calls=[ToolCall(id="tc_1", name="query_agents", arguments={})],
                    finish_reason="tool_calls",
                    usage=TokenUsage(
                        prompt_tokens=10, completion_tokens=5, total_tokens=15
                    ),
                ),
                # Step 1: tool call (triggers reflection after this)
                LLMResponse(
                    content="Step 1",
                    tool_calls=[ToolCall(id="tc_2", name="query_agents", arguments={})],
                    finish_reason="tool_calls",
                    usage=TokenUsage(
                        prompt_tokens=10, completion_tokens=5, total_tokens=15
                    ),
                ),
                # Reflection response
                LLMResponse(
                    content=(
                        '{"should_stop": true, "conclusion": "All done", '
                        '"reason": "task complete"}'
                    ),
                    finish_reason="stop",
                    usage=TokenUsage(
                        prompt_tokens=10, completion_tokens=10, total_tokens=20
                    ),
                ),
            ],
        )

        result = agent.pursue_goal("Test reflection")
        assert result.is_ok()
        goal = result.unwrap()
        assert goal.status == "completed"
        assert goal.token_usage.total_tokens == 50
