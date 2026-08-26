"""Tests for bounded durable autonomous agent-run checkpoints."""

import asyncio
import json

import pytest

from maple.agent.config import Config
from maple.autonomy.agent import AutonomousAgent, AutonomousConfig
from maple.autonomy.approval import InMemoryApprovalStore
from maple.autonomy.events import EventStream
from maple.autonomy.interactions import InMemoryHumanInputStore
from maple.autonomy.observability import DecisionLogger, SpanRecorder
from maple.autonomy.runs import (
    AgentRunCheckpoint,
    FileAgentRunStore,
    InMemoryAgentRunStore,
)
from maple.autonomy.sessions import SessionMessage
from maple.autonomy.tools import Tool
from maple.core.result import Result
from maple.llm.provider import LLMProvider
from maple.llm.registry import LLMProviderRegistry
from maple.llm.types import LLMConfig, LLMResponse, ToolCall


def make_checkpoint(run_id="run-1", *, status="running", result=None):
    return AgentRunCheckpoint(
        run_id=run_id,
        agent_id="agent-1",
        description="Persist this run",
        status=status,
        messages=(SessionMessage(role="user", content="hello"),),
        reasoning_steps=(
            {
                "step_number": 0,
                "phase": "think",
                "content": "plan",
                "tool_calls": [],
                "tool_results": [],
                "timestamp": 1.0,
            },
        ),
        step_count=1,
        token_usage={"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5},
        result=result,
    )


def test_in_memory_run_store_round_trips_and_uses_compare_and_set():
    store = InMemoryAgentRunStore()

    saved = store.save(make_checkpoint())

    assert saved.is_ok()
    assert saved.unwrap().version == 1
    loaded = store.load("run-1")
    assert loaded.is_ok()
    assert loaded.unwrap().to_dict() == saved.unwrap().to_dict()

    changed = make_checkpoint(status="paused")
    conflict = store.save(changed, expected_version=0)
    assert conflict.is_err()
    assert conflict.unwrap_err()["errorType"] == "RUN_CHECKPOINT_CONFLICT"

    updated = store.save(changed, expected_version=1)
    assert updated.is_ok()
    assert updated.unwrap().version == 2
    assert store.load("run-1").unwrap().status == "paused"


def test_file_run_store_survives_recreation_and_rejects_oversized_state(tmp_path):
    store = FileAgentRunStore(tmp_path)
    assert store.save(make_checkpoint(result={"answer": "ok"})).is_ok()

    restarted = FileAgentRunStore(tmp_path)
    loaded = restarted.load("run-1")
    assert loaded.is_ok()
    assert loaded.unwrap().result == {"answer": "ok"}

    tiny = FileAgentRunStore(tmp_path / "tiny", max_checkpoint_bytes=32)
    oversized = tiny.save(make_checkpoint())
    assert oversized.is_err()
    assert oversized.unwrap_err()["errorType"] == "RUN_CHECKPOINT_SIZE_EXCEEDED"


def test_checkpoint_rejects_non_json_values_before_store_mutation():
    store = InMemoryAgentRunStore()
    invalid = make_checkpoint(result=object())

    saved = store.save(invalid)

    assert saved.is_err()
    assert saved.unwrap_err()["errorType"] == "RUN_CHECKPOINT_INVALID"
    assert store.load("run-1").unwrap() is None


def test_checkpoint_parser_does_not_execute_embedded_values():
    payload = make_checkpoint().to_dict()
    payload["result"] = {"__class__": "os.system", "args": ["not executed"]}

    parsed = AgentRunCheckpoint.from_dict(payload)

    assert parsed.result == payload["result"]
    assert json.dumps(parsed.to_dict(), allow_nan=False)


class ScriptedProvider(LLMProvider):
    """Small provider double for restart and approval boundaries."""

    def __init__(self, config, responses=None):
        super().__init__(config)
        self.responses = list(responses or [])

    def complete(
        self, messages, tools=None, temperature=None, max_tokens=None, stop=None
    ):
        response = self.responses.pop(0)
        return response if isinstance(response, Result) else Result.ok(response)


@pytest.fixture(autouse=True)
def register_run_provider():
    original = dict(LLMProviderRegistry._providers)
    LLMProviderRegistry.register("run-test", ScriptedProvider)
    yield
    LLMProviderRegistry._providers = original


def make_agent(responses, *, stream_model_events=False):
    config = Config(agent_id="run-agent", broker_url="memory://test")
    autonomy_config = AutonomousConfig(
        llm=LLMConfig(provider="run-test", model="run-v1"),
        max_reasoning_steps=4,
        reflection_frequency=10,
        stream_model_events=stream_model_events,
    )
    agent = AutonomousAgent(config, autonomy_config)
    agent.llm = ScriptedProvider(autonomy_config.llm, responses)
    return agent


def approval_tool(calls):
    return Tool(
        name="write_value",
        description="Write one value",
        parameters={"type": "object", "additionalProperties": True},
        requires_approval=True,
        handler=lambda **kwargs: (calls.append(kwargs) or Result.ok({"written": True})),
    )


def test_sync_run_pauses_for_approval_and_resumes_after_restart():
    run_store = InMemoryAgentRunStore()
    approval_store = InMemoryApprovalStore()
    calls = []
    first = make_agent(
        [
            LLMResponse(
                content="request write",
                tool_calls=[
                    ToolCall(
                        id="call-write",
                        name="write_value",
                        arguments={"value": "ready"},
                    )
                ],
                finish_reason="tool_calls",
            )
        ]
    )
    first.set_run_store(run_store)
    first.set_approval_store(approval_store)
    assert first.register_tool(approval_tool(calls)).is_ok()

    started = first.pursue_goal("Write the value", run_id="run-approval")

    assert started.is_ok()
    assert started.unwrap().status == "paused"
    approval_id = started.unwrap().result["details"]["approval_id"]
    checkpoint = run_store.load("run-approval").unwrap()
    assert checkpoint is not None
    assert checkpoint.status == "paused"
    assert checkpoint.pending_approval_id == approval_id
    assert calls == []
    assert first.resume_run("run-approval").unwrap_err()["errorType"] == (
        "RUN_WAITING_APPROVAL"
    )

    assert first.decide_approval(
        approval_id, approved=True, edited_arguments={"value": "edited"}
    ).is_ok()
    restarted = make_agent(
        [LLMResponse(content="write complete", finish_reason="stop")]
    )
    restarted.set_run_store(run_store)
    restarted.set_approval_store(approval_store)
    assert restarted.register_tool(approval_tool(calls)).is_ok()

    resumed = restarted.resume_run("run-approval")

    assert resumed.is_ok()
    assert resumed.unwrap().status == "completed"
    assert calls == [{"value": "edited"}]
    final_checkpoint = run_store.load("run-approval").unwrap()
    assert final_checkpoint is not None
    assert final_checkpoint.status == "completed"
    assert final_checkpoint.pending_approval_id is None


def test_sync_resume_does_not_repeat_completed_tool_after_model_interruption():
    run_store = InMemoryAgentRunStore()
    calls = []
    first = make_agent(
        [
            LLMResponse(
                content="call tool",
                tool_calls=[ToolCall(id="call-once", name="write_value", arguments={})],
                finish_reason="tool_calls",
            ),
            Result.err({"errorType": "MODEL_INTERRUPTED", "message": "retry"}),
        ]
    )
    first.set_run_store(run_store)
    tool = Tool(
        name="write_value",
        description="Write one value",
        parameters={"type": "object"},
        handler=lambda **kwargs: (calls.append("called") or Result.ok({"ok": True})),
    )
    assert first.register_tool(tool).is_ok()

    interrupted = first.pursue_goal("Perform one write", run_id="run-recover")

    assert interrupted.is_ok()
    assert interrupted.unwrap().status == "failed"
    assert calls == ["called"]
    checkpoint = run_store.load("run-recover").unwrap()
    assert checkpoint is not None
    assert checkpoint.status == "running"
    assert checkpoint.step_count == 1

    restarted = make_agent([LLMResponse(content="recovered", finish_reason="stop")])
    restarted.set_run_store(run_store)
    assert restarted.register_tool(tool).is_ok()

    resumed = restarted.resume_run("run-recover")

    assert resumed.is_ok()
    assert resumed.unwrap().status == "completed"
    assert calls == ["called"]


def test_agent_publishes_bounded_lifecycle_events_with_usage_trailer():
    events = EventStream(max_events=20)
    run_store = InMemoryAgentRunStore()
    agent = make_agent(
        [
            LLMResponse(
                content="call tool",
                tool_calls=[
                    ToolCall(id="event-call", name="write_value", arguments={})
                ],
                finish_reason="tool_calls",
                request_id="provider-run-1",
            ),
            LLMResponse(
                content="complete",
                finish_reason="stop",
                request_id="provider-run-2",
            ),
        ]
    )
    agent.set_run_store(run_store)
    agent.set_event_stream(events)
    assert agent.register_tool(
        Tool(
            name="write_value",
            description="Write one value",
            parameters={"type": "object"},
            handler=lambda **kwargs: Result.ok({"ok": True}),
        )
    ).is_ok()

    result = agent.pursue_goal("Emit lifecycle events", run_id="event-run")

    assert result.is_ok()
    assert result.unwrap().status == "completed"
    retained = events.snapshot().unwrap()
    assert [event.event_type for event in retained] == [
        "run.started",
        "model.response",
        "tool.completed",
        "model.response",
        "run.completed",
    ]
    assert all(event.run_id == "event-run" for event in retained)
    assert retained[-1].payload["usage"]["total_tokens"] == 0
    model_events = [event for event in retained if event.event_type == "model.response"]
    assert [event.payload["provider_request_id"] for event in model_events] == [
        "provider-run-1",
        "provider-run-2",
    ]


def test_agent_can_publish_metadata_only_model_chunk_events():
    events = EventStream(max_events=20)
    agent = make_agent(
        [LLMResponse(content="streamed", finish_reason="stop")],
        stream_model_events=True,
    )
    agent.set_event_stream(events)

    result = agent.pursue_goal("Emit model chunks")

    assert result.is_ok()
    assert result.unwrap().status == "completed"
    retained = events.snapshot().unwrap()
    assert [event.event_type for event in retained] == [
        "run.started",
        "model.chunk",
        "model.chunk",
        "model.response",
        "run.completed",
    ]
    chunk_events = [event for event in retained if event.event_type == "model.chunk"]
    assert chunk_events[0].payload["content_bytes"] == len("streamed".encode("utf-8"))
    assert chunk_events[1].payload["content_bytes"] == 0
    assert all("content" not in event.payload for event in chunk_events)


def test_async_agent_can_publish_metadata_only_model_chunk_events():
    events = EventStream(max_events=20)
    agent = make_agent(
        [LLMResponse(content="async-streamed", finish_reason="stop")],
        stream_model_events=True,
    )
    agent.set_event_stream(events)

    result = asyncio.run(agent.pursue_goal_async("Emit async model chunks"))

    assert result.is_ok()
    assert result.unwrap().status == "completed"
    retained = events.snapshot().unwrap()
    assert [event.event_type for event in retained] == [
        "run.started",
        "model.chunk",
        "model.chunk",
        "model.response",
        "run.completed",
    ]
    chunk_events = [event for event in retained if event.event_type == "model.chunk"]
    assert chunk_events[0].payload["content_bytes"] == len(
        "async-streamed".encode("utf-8")
    )
    assert chunk_events[1].payload["content_bytes"] == 0


def test_agent_links_model_events_to_a_finished_span():
    events = EventStream(max_events=20)
    spans = SpanRecorder(max_spans=10)
    agent = make_agent(
        [
            LLMResponse(
                content="traced",
                finish_reason="stop",
                request_id="provider-trace-1",
            )
        ],
        stream_model_events=True,
    )
    agent.set_event_stream(events)
    agent.set_span_recorder(spans)
    decision_logger = DecisionLogger()
    agent._decision_logger = decision_logger

    result = agent.pursue_goal("Trace one model step")

    assert result.is_ok()
    retained = events.snapshot().unwrap()
    model_events = [
        event
        for event in retained
        if event.event_type in {"model.chunk", "model.response"}
    ]
    span = spans.snapshot().unwrap()[0]
    assert span.status == "ok"
    assert all(event.payload["trace_id"] == span.trace_id for event in model_events)
    assert all(event.payload["span_id"] == span.span_id for event in model_events)
    assert span.attributes["provider_request_id"] == "provider-trace-1"
    decision = decision_logger.get_traces()[0]
    assert decision.trace_id == span.trace_id
    assert decision.span_id == span.span_id


def test_async_agent_links_model_events_to_a_finished_span():
    events = EventStream(max_events=20)
    spans = SpanRecorder(max_spans=10)
    agent = make_agent(
        [LLMResponse(content="async-traced", finish_reason="stop")],
        stream_model_events=True,
    )
    agent.set_event_stream(events)
    agent.set_span_recorder(spans)

    result = asyncio.run(agent.pursue_goal_async("Trace async model step"))

    assert result.is_ok()
    assert len(spans.snapshot().unwrap()) == 1
    assert spans.snapshot().unwrap()[0].status == "ok"


def test_sync_tool_span_is_a_child_of_the_model_span():
    spans = SpanRecorder(max_spans=10)
    agent = make_agent(
        [
            LLMResponse(
                content="use tool",
                tool_calls=[
                    ToolCall(
                        id="trace-tool-call",
                        name="write_value",
                        arguments={"value": "secret-input"},
                    )
                ],
                finish_reason="tool_calls",
            ),
            LLMResponse(content="done", finish_reason="stop"),
        ]
    )
    agent.set_span_recorder(spans)
    assert agent.register_tool(
        Tool(
            name="write_value",
            description="Write one value",
            parameters={"type": "object"},
            handler=lambda **kwargs: Result.ok({"written": True}),
        )
    ).is_ok()

    result = agent.pursue_goal("Trace a tool step")

    assert result.is_ok()
    retained = spans.snapshot().unwrap()
    assert [span.name for span in retained] == [
        "agent.model",
        "agent.tool",
        "agent.model",
    ]
    model_span, tool_span, _ = retained
    assert model_span.status == "ok"
    assert tool_span.status == "ok"
    assert tool_span.parent_span_id == model_span.span_id
    assert tool_span.trace_id == model_span.trace_id
    assert tool_span.attributes["tool"] == "write_value"
    assert tool_span.attributes["is_error"] is False
    assert "secret-input" not in tool_span.to_dict()


def test_async_tool_span_is_a_child_of_the_model_span():
    spans = SpanRecorder(max_spans=10)
    agent = make_agent(
        [
            LLMResponse(
                content="use async tool",
                tool_calls=[
                    ToolCall(
                        id="async-trace-tool-call",
                        name="write_value",
                        arguments={"value": "secret-input"},
                    )
                ],
                finish_reason="tool_calls",
            ),
            LLMResponse(content="done", finish_reason="stop"),
        ]
    )
    agent.set_span_recorder(spans)
    assert agent.register_tool(
        Tool(
            name="write_value",
            description="Write one value",
            parameters={"type": "object"},
            handler=lambda **kwargs: Result.ok({"written": True}),
        )
    ).is_ok()

    result = asyncio.run(agent.pursue_goal_async("Trace an async tool step"))

    assert result.is_ok()
    retained = spans.snapshot().unwrap()
    assert [span.name for span in retained] == [
        "agent.model",
        "agent.tool",
        "agent.model",
    ]
    model_span, tool_span, _ = retained
    assert model_span.status == "ok"
    assert tool_span.status == "ok"
    assert tool_span.parent_span_id == model_span.span_id
    assert tool_span.trace_id == model_span.trace_id
    assert tool_span.attributes["tool"] == "write_value"
    assert tool_span.attributes["is_error"] is False
    assert "secret-input" not in tool_span.to_dict()


def test_async_run_pauses_for_approval_and_resumes_after_restart():
    run_store = InMemoryAgentRunStore()
    approval_store = InMemoryApprovalStore()
    events = EventStream(max_events=20)
    calls = []
    first = make_agent(
        [
            LLMResponse(
                content="request write",
                tool_calls=[
                    ToolCall(
                        id="async-call-write",
                        name="write_value",
                        arguments={"value": "ready"},
                    )
                ],
                finish_reason="tool_calls",
            )
        ]
    )
    first.set_run_store(run_store)
    first.set_approval_store(approval_store)
    first.set_event_stream(events)
    assert first.register_tool(approval_tool(calls)).is_ok()

    started = asyncio.run(
        first.pursue_goal_async("Write the value", run_id="async-run-approval")
    )

    assert started.is_ok()
    assert started.unwrap().status == "paused"
    approval_id = started.unwrap().result["details"]["approval_id"]
    checkpoint = run_store.load("async-run-approval").unwrap()
    assert checkpoint is not None
    assert checkpoint.status == "paused"
    assert checkpoint.pending_approval_id == approval_id
    assert calls == []
    assert [event.event_type for event in events.snapshot().unwrap()] == [
        "run.started",
        "model.response",
        "tool.completed",
        "run.paused",
    ]
    waiting = asyncio.run(first.resume_run_async("async-run-approval"))
    assert waiting.is_err()
    assert waiting.unwrap_err()["errorType"] == "RUN_WAITING_APPROVAL"

    assert first.decide_approval(
        approval_id, approved=True, edited_arguments={"value": "async-edited"}
    ).is_ok()
    restarted = make_agent(
        [LLMResponse(content="write complete", finish_reason="stop")]
    )
    restarted.set_run_store(run_store)
    restarted.set_approval_store(approval_store)
    restarted.set_event_stream(events)
    assert restarted.register_tool(approval_tool(calls)).is_ok()

    resumed = asyncio.run(restarted.resume_run_async("async-run-approval"))

    assert resumed.is_ok()
    assert resumed.unwrap().status == "completed"
    assert calls == [{"value": "async-edited"}]
    final_checkpoint = run_store.load("async-run-approval").unwrap()
    assert final_checkpoint is not None
    assert final_checkpoint.status == "completed"
    assert final_checkpoint.pending_approval_id is None
    assert [event.event_type for event in events.snapshot().unwrap()][-3:] == [
        "run.resumed",
        "model.response",
        "run.completed",
    ]


def test_async_durable_approval_pauses_before_later_tool_side_effects():
    run_store = InMemoryAgentRunStore()
    approval_store = InMemoryApprovalStore()
    calls = []
    agent = make_agent(
        [
            LLMResponse(
                content="prepare and write",
                tool_calls=[
                    ToolCall(id="async-safe", name="safe_value", arguments={}),
                    ToolCall(
                        id="async-gated",
                        name="write_value",
                        arguments={"value": "ready"},
                    ),
                ],
                finish_reason="tool_calls",
            )
        ]
    )
    agent.set_run_store(run_store)
    agent.set_approval_store(approval_store)
    assert agent.register_tool(
        Tool(
            name="safe_value",
            description="Perform a safe side effect",
            parameters={"type": "object"},
            handler=lambda **kwargs: (calls.append("safe") or Result.ok({"ok": True})),
        )
    ).is_ok()
    assert agent.register_tool(approval_tool(calls)).is_ok()

    started = asyncio.run(
        agent.pursue_goal_async("Prepare and write", run_id="async-run-order")
    )

    assert started.is_ok()
    assert started.unwrap().status == "paused"
    assert calls == ["safe"]
    checkpoint = run_store.load("async-run-order").unwrap()
    assert checkpoint is not None
    assert checkpoint.status == "paused"
    assert checkpoint.pending_approval_id is not None


def test_async_resume_does_not_repeat_completed_tool_after_model_interruption():
    run_store = InMemoryAgentRunStore()
    calls = []
    first = make_agent(
        [
            LLMResponse(
                content="call tool",
                tool_calls=[
                    ToolCall(id="async-call-once", name="write_value", arguments={})
                ],
                finish_reason="tool_calls",
            ),
            Result.err({"errorType": "MODEL_INTERRUPTED", "message": "retry"}),
        ]
    )
    first.set_run_store(run_store)
    tool = Tool(
        name="write_value",
        description="Write one value",
        parameters={"type": "object"},
        handler=lambda **kwargs: (calls.append("called") or Result.ok({"ok": True})),
    )
    assert first.register_tool(tool).is_ok()

    interrupted = asyncio.run(
        first.pursue_goal_async("Perform one write", run_id="async-run-recover")
    )

    assert interrupted.is_ok()
    assert interrupted.unwrap().status == "failed"
    assert calls == ["called"]
    checkpoint = run_store.load("async-run-recover").unwrap()
    assert checkpoint is not None
    assert checkpoint.status == "running"
    assert checkpoint.step_count == 1

    restarted = make_agent([LLMResponse(content="recovered", finish_reason="stop")])
    restarted.set_run_store(run_store)
    assert restarted.register_tool(tool).is_ok()

    resumed = asyncio.run(restarted.resume_run_async("async-run-recover"))

    assert resumed.is_ok()
    assert resumed.unwrap().status == "completed"
    assert calls == ["called"]


def _human_input_call(call_id="ask-input", max_rounds=1):
    return ToolCall(
        id=call_id,
        name="request_human_input",
        arguments={
            "prompt": "Provide the deployment code.",
            "input_schema": {
                "type": "object",
                "properties": {"code": {"type": "string", "minLength": 1}},
                "required": ["code"],
                "additionalProperties": False,
            },
            "max_rounds": max_rounds,
        },
    )


def test_sync_durable_human_input_pauses_and_resumes_after_restart():
    run_store = InMemoryAgentRunStore()
    input_store = InMemoryHumanInputStore()
    first = make_agent(
        [
            LLMResponse(
                content="ask for code",
                tool_calls=[_human_input_call()],
                finish_reason="tool_calls",
            )
        ]
    )
    first.set_run_store(run_store)
    first.set_human_input_store(input_store)

    started = first.pursue_goal("Deploy safely", run_id="run-human-input")

    assert started.is_ok()
    assert started.unwrap().status == "paused"
    interaction_id = started.unwrap().result["details"]["interaction_id"]
    checkpoint = run_store.load("run-human-input").unwrap()
    assert checkpoint is not None
    assert checkpoint.pending_input_id == interaction_id
    waiting = first.resume_run("run-human-input")
    assert waiting.is_err()
    assert waiting.unwrap_err()["errorType"] == "RUN_WAITING_INPUT"

    assert first.respond_human_input(interaction_id, {"code": "green"}).is_ok()
    restarted = make_agent(
        [LLMResponse(content="deployment approved", finish_reason="stop")]
    )
    restarted.set_run_store(run_store)
    restarted.set_human_input_store(input_store)

    resumed = restarted.resume_run("run-human-input")

    assert resumed.is_ok()
    assert resumed.unwrap().status == "completed"
    assert resumed.unwrap().result == "deployment approved"
    final_checkpoint = run_store.load("run-human-input").unwrap()
    assert final_checkpoint is not None
    assert final_checkpoint.pending_input_id is None
    assert input_store.get(interaction_id).unwrap().status == "consumed"


def test_async_durable_human_input_rejection_resumes_as_typed_tool_error():
    run_store = InMemoryAgentRunStore()
    input_store = InMemoryHumanInputStore()
    first = make_agent(
        [
            LLMResponse(
                content="ask for code",
                tool_calls=[_human_input_call("async-ask-input")],
                finish_reason="tool_calls",
            )
        ]
    )
    first.set_run_store(run_store)
    first.set_human_input_store(input_store)

    started = asyncio.run(
        first.pursue_goal_async("Deploy safely", run_id="async-human-input")
    )

    assert started.is_ok()
    assert started.unwrap().status == "paused"
    interaction_id = started.unwrap().result["details"]["interaction_id"]
    assert first.reject_human_input(interaction_id, "No change window.").is_ok()
    restarted = make_agent([LLMResponse(content="do not deploy", finish_reason="stop")])
    restarted.set_run_store(run_store)
    restarted.set_human_input_store(input_store)

    resumed = asyncio.run(restarted.resume_run_async("async-human-input"))

    assert resumed.is_ok()
    assert resumed.unwrap().status == "completed"
    assert resumed.unwrap().result == "do not deploy"
    assert input_store.get(interaction_id).unwrap().status == "consumed"


def test_sync_durable_human_input_supports_bounded_follow_up_before_resume():
    run_store = InMemoryAgentRunStore()
    input_store = InMemoryHumanInputStore()
    first = make_agent(
        [
            LLMResponse(
                content="ask for code",
                tool_calls=[_human_input_call("multi-round-input", max_rounds=2)],
                finish_reason="tool_calls",
            )
        ]
    )
    first.set_run_store(run_store)
    first.set_human_input_store(input_store)

    started = first.pursue_goal("Deploy safely", run_id="run-multi-round")

    assert started.is_ok()
    assert started.unwrap().status == "paused"
    interaction_id = started.unwrap().result["details"]["interaction_id"]
    assert first.respond_human_input(interaction_id, {"code": "green"}).is_ok()
    continued = first.continue_human_input(
        interaction_id,
        "Confirm the replacement code.",
        {"type": "object", "required": ["code"]},
    )
    assert continued.is_ok()
    assert continued.unwrap().status == "pending"
    assert continued.unwrap().round_index == 1
    assert first.resume_run("run-multi-round").unwrap_err()["errorType"] == (
        "RUN_WAITING_INPUT"
    )

    assert first.respond_human_input(interaction_id, {"code": "blue"}).is_ok()
    restarted = make_agent(
        [LLMResponse(content="deployment approved", finish_reason="stop")]
    )
    restarted.set_run_store(run_store)
    restarted.set_human_input_store(input_store)

    resumed = restarted.resume_run("run-multi-round")

    assert resumed.is_ok()
    assert resumed.unwrap().status == "completed"
    final_request = input_store.get(interaction_id).unwrap()
    assert final_request is not None
    assert final_request.status == "consumed"
    assert final_request.round_index == 1
    assert final_request.history[0].decision.response == {"code": "green"}
    assert final_request.decision is not None
    assert final_request.decision.response == {"code": "blue"}
