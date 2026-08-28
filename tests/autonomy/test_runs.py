"""Tests for bounded durable autonomous agent-run checkpoints."""

import asyncio
import json
from dataclasses import replace

import pytest

from maple.agent.config import Config
from maple.autonomy.agent import AutonomousAgent, AutonomousConfig
from maple.autonomy.approval import InMemoryApprovalStore
from maple.autonomy.events import EventStream
from maple.autonomy.execution import CancellationToken
from maple.autonomy.interactions import InMemoryHumanInputStore
from maple.autonomy.observability import DecisionLogger, SpanRecorder
from maple.autonomy.replay import InMemoryExecutionJournal
from maple.autonomy.runs import (
    AgentRunCheckpoint,
    FileAgentRunStore,
    InMemoryAgentRunStore,
)
from maple.autonomy.sessions import SessionMessage
from maple.autonomy.tools import (
    TOOL_REPLAY_REUSE_SUCCESS,
    Tool,
    create_agent_tool,
)
from maple.core.result import Result
from maple.llm.provider import LLMProvider
from maple.llm.registry import LLMProviderRegistry
from maple.llm.types import LLMConfig, LLMResponse, ToolCall


def make_checkpoint(
    run_id="run-1",
    *,
    status="running",
    result=None,
    pending_approval_id=None,
    pending_input_id=None,
):
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
        pending_approval_id=pending_approval_id,
        pending_input_id=pending_input_id,
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

    changed = make_checkpoint(status="paused", pending_approval_id="approval-1")
    conflict = store.save(changed, expected_version=0)
    assert conflict.is_err()
    assert conflict.unwrap_err()["errorType"] == "RUN_CHECKPOINT_CONFLICT"

    updated = store.save(changed, expected_version=1)
    assert updated.is_ok()
    assert updated.unwrap().version == 2
    assert store.load("run-1").unwrap().status == "paused"


def test_in_memory_run_store_retains_bounded_immutable_history():
    store = InMemoryAgentRunStore(max_history=2)

    first = store.save(make_checkpoint(result={"state": {"version": 1}}))
    second = store.save(
        make_checkpoint(result={"state": {"version": 2}}),
        expected_version=1,
    )
    failed = store.save(make_checkpoint(result={"state": {"version": 3}}))
    third = store.save(
        make_checkpoint(result={"state": {"version": 3}}),
        expected_version=2,
    )

    assert first.is_ok()
    assert second.is_ok()
    assert failed.is_err()
    assert failed.unwrap_err()["errorType"] == "RUN_CHECKPOINT_CONFLICT"
    assert third.is_ok()

    history = store.history("run-1")

    assert history.is_ok()
    assert [item.version for item in history.unwrap()] == [2, 3]
    assert [item.result for item in history.unwrap()] == [
        {"state": {"version": 2}},
        {"state": {"version": 3}},
    ]
    history.unwrap()[0].result["state"]["version"] = 99
    assert store.history("run-1").unwrap()[0].result == {"state": {"version": 2}}


def test_run_history_validates_limits_and_missing_runs():
    store = InMemoryAgentRunStore(max_history=2)

    assert store.history("missing-run").unwrap() == []
    invalid = store.history("missing-run", limit=3)
    assert invalid.is_err()
    assert invalid.unwrap_err()["errorType"] == "RUN_HISTORY_LIMIT_INVALID"
    invalid_bool = store.history("missing-run", limit=True)
    assert invalid_bool.is_err()
    with pytest.raises(ValueError, match="max_history"):
        InMemoryAgentRunStore(max_history=0)


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


def test_file_run_store_history_survives_recreation_and_is_bounded(tmp_path):
    store = FileAgentRunStore(tmp_path, max_history=2)
    assert store.save(make_checkpoint(result={"version": 1})).is_ok()
    assert store.save(
        make_checkpoint(result={"version": 2}), expected_version=1
    ).is_ok()
    assert store.save(
        make_checkpoint(result={"version": 3}), expected_version=2
    ).is_ok()

    history = store.history("run-1")
    restarted = FileAgentRunStore(tmp_path, max_history=2)
    restarted_history = restarted.history("run-1")

    assert history.is_ok()
    assert restarted_history.is_ok()
    assert [item.version for item in history.unwrap()] == [2, 3]
    assert [item.result for item in restarted_history.unwrap()] == [
        {"version": 2},
        {"version": 3},
    ]
    restarted_history.unwrap()[0].result["version"] = 99
    assert restarted.history("run-1").unwrap()[0].result == {"version": 2}
    assert (tmp_path / ".history" / "run-1.json").exists()


def test_file_run_store_allows_a_smaller_history_bound_after_restart(tmp_path):
    original = FileAgentRunStore(tmp_path, max_history=3)
    base = dict(run_id="resized-run", agent_id="agent-1", description="history")
    assert original.save(AgentRunCheckpoint(**base, result={"version": 1})).is_ok()
    assert original.save(
        AgentRunCheckpoint(**base, result={"version": 2}), expected_version=1
    ).is_ok()
    assert original.save(
        AgentRunCheckpoint(**base, result={"version": 3}), expected_version=2
    ).is_ok()

    resized = FileAgentRunStore(tmp_path, max_history=2)
    history = resized.history("resized-run")
    updated = resized.save(
        AgentRunCheckpoint(**base, result={"version": 4}), expected_version=3
    )

    assert history.is_ok()
    assert [item.version for item in history.unwrap()] == [2, 3]
    assert updated.is_ok()
    assert [item.version for item in resized.history("resized-run").unwrap()] == [
        3,
        4,
    ]


def test_file_run_store_fails_closed_on_corrupt_history_before_save(tmp_path):
    store = FileAgentRunStore(tmp_path)
    assert store.save(make_checkpoint(result={"version": 1})).is_ok()
    history_path = tmp_path / ".history" / "run-1.json"
    history_path.write_text("{not-json", encoding="utf-8")

    inspected = store.history("run-1")
    blocked = store.save(make_checkpoint(result={"version": 2}), expected_version=1)

    assert inspected.is_err()
    assert inspected.unwrap_err()["errorType"] == "RUN_HISTORY_LOAD_ERROR"
    assert blocked.is_err()
    assert blocked.unwrap_err()["errorType"] == "RUN_HISTORY_LOAD_ERROR"
    assert store.load("run-1").unwrap().result == {"version": 1}


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


@pytest.mark.parametrize(
    ("status", "pending_approval_id", "pending_input_id"),
    [
        ("paused", None, None),
        ("running", "approval-1", None),
        ("completed", None, "interaction-1"),
        ("failed", "approval-1", None),
        ("paused", "approval-1", "interaction-1"),
    ],
)
def test_checkpoint_parser_rejects_inconsistent_pending_request_state(
    status, pending_approval_id, pending_input_id
):
    payload = make_checkpoint(status="running").to_dict()
    payload.update(
        {
            "status": status,
            "pending_approval_id": pending_approval_id,
            "pending_input_id": pending_input_id,
        }
    )

    with pytest.raises(ValueError, match="pending"):
        AgentRunCheckpoint.from_dict(payload)


@pytest.mark.parametrize(
    "pending_field",
    ["pending_approval_id", "pending_input_id"],
)
def test_checkpoint_parser_accepts_one_pending_request_for_paused_run(
    pending_field,
):
    payload = make_checkpoint(status="paused").to_dict()
    payload[pending_field] = (
        "approval-1" if pending_field == "pending_approval_id" else "interaction-1"
    )

    parsed = AgentRunCheckpoint.from_dict(payload)

    assert parsed.status == "paused"
    assert getattr(parsed, pending_field) == payload[pending_field]


def test_run_store_rejects_inconsistent_pending_request_before_mutation():
    store = InMemoryAgentRunStore()
    assert store.save(make_checkpoint()).is_ok()
    invalid = make_checkpoint(status="running", pending_input_id="interaction-1")

    saved = store.save(invalid, expected_version=1)

    assert saved.is_err()
    assert saved.unwrap_err()["errorType"] == "RUN_CHECKPOINT_INVALID"
    loaded = store.load("run-1").unwrap()
    assert loaded is not None
    assert loaded.status == "running"
    assert loaded.pending_input_id is None


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


class CancellingProvider(LLMProvider):
    """Provider double that requests cancellation after one completed call."""

    def __init__(self, config, token):
        super().__init__(config)
        self.token = token
        self.calls = 0

    def complete(
        self, messages, tools=None, temperature=None, max_tokens=None, stop=None
    ):
        self.calls += 1
        response = LLMResponse(content="provider returned", finish_reason="stop")
        self._track_usage(response)
        self.token.cancel()
        return Result.ok(response)


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


def test_sync_cancellation_persists_terminal_checkpoint_and_emits_event():
    token = CancellationToken()
    store = InMemoryAgentRunStore()
    events = EventStream(max_events=20)
    agent = make_agent([])
    agent.llm = CancellingProvider(agent.autonomy_config.llm, token)
    agent.set_run_store(store)
    agent.set_event_stream(events)

    result = agent.pursue_goal(
        "Cancel after the provider boundary",
        run_id="run-cancel-sync",
        cancellation=token,
    )

    assert result.is_ok()
    goal = result.unwrap()
    assert goal.status == "cancelled"
    assert goal.result["errorType"] == "AGENT_RUN_CANCELLED"
    checkpoint = store.load("run-cancel-sync").unwrap()
    assert checkpoint is not None
    assert checkpoint.status == "cancelled"
    assert checkpoint.pending_approval_id is None
    assert checkpoint.pending_input_id is None
    assert checkpoint.error["errorType"] == "AGENT_RUN_CANCELLED"
    retained = events.snapshot().unwrap()
    assert [event.event_type for event in retained] == [
        "run.started",
        "run.cancelled",
    ]
    assert set(retained[-1].payload) == {
        "agent_id",
        "status",
        "step_count",
        "usage",
    }
    assert agent.llm.calls == 1

    resumed = agent.resume_run("run-cancel-sync")
    assert resumed.is_err()
    assert resumed.unwrap_err()["errorType"] == "RUN_NOT_RESUMABLE"


async def test_async_cancellation_persists_terminal_checkpoint():
    token = CancellationToken()
    store = InMemoryAgentRunStore()
    agent = make_agent([])
    agent.llm = CancellingProvider(agent.autonomy_config.llm, token)
    agent.set_run_store(store)

    result = await agent.pursue_goal_async(
        "Cancel asynchronously after the provider boundary",
        run_id="run-cancel-async",
        cancellation=token,
    )

    assert result.is_ok()
    assert result.unwrap().status == "cancelled"
    checkpoint = store.load("run-cancel-async").unwrap()
    assert checkpoint is not None
    assert checkpoint.status == "cancelled"
    assert checkpoint.error["errorType"] == "AGENT_RUN_CANCELLED"
    assert agent.llm.calls == 1


@pytest.mark.parametrize("resume", ["sync", "async"])
async def test_cancelled_resume_preserves_paused_pending_interaction(resume):
    store = InMemoryAgentRunStore()
    stored = store.save(
        make_checkpoint(status="paused", pending_approval_id="approval-1")
    )
    assert stored.is_ok()
    before = store.load("run-1").unwrap()
    token = CancellationToken()
    token.cancel()
    agent = make_agent([])
    agent.set_run_store(store)

    if resume == "sync":
        result = agent.resume_run("run-1", cancellation=token)
    else:
        result = await agent.resume_run_async("run-1", cancellation=token)

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "AGENT_RUN_CANCELLED"
    after = store.load("run-1").unwrap()
    assert before is not None and after is not None
    assert after.to_dict() == before.to_dict()


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
    events = EventStream(max_events=20)
    spans = SpanRecorder(max_spans=10)
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
    first.set_event_stream(events)
    first.set_span_recorder(spans)
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
    tool_event = next(
        event
        for event in events.snapshot().unwrap()
        if event.event_type == "tool.completed"
    )
    model_span = spans.snapshot().unwrap()[0]
    assert tool_event.payload["approval_id"] == approval_id
    assert tool_event.payload["trace_id"] == model_span.trace_id
    assert tool_event.payload["span_id"] == model_span.span_id
    stored = approval_store.get(approval_id).unwrap()
    assert stored.trace_id == model_span.trace_id
    assert stored.span_id == model_span.span_id
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


def test_sync_resume_rejects_mismatched_approval_before_execution():
    run_store = InMemoryAgentRunStore()
    approval_store = InMemoryApprovalStore()
    calls = []
    agent = make_agent(
        [
            LLMResponse(
                content="request write",
                tool_calls=[ToolCall("approval-target", "write_value", {})],
                finish_reason="tool_calls",
            )
        ]
    )
    agent.set_run_store(run_store)
    agent.set_approval_store(approval_store)
    assert agent.register_tool(approval_tool(calls)).is_ok()

    started = agent.pursue_goal("Write once", run_id="run-approval-target")
    assert started.is_ok()
    approval_id = started.unwrap().result["details"]["approval_id"]
    checkpoint = run_store.load("run-approval-target").unwrap()
    assert checkpoint is not None
    tampered_messages = tuple(
        (
            replace(message, tool_call_id="wrong-target")
            if message.tool_call_id == "approval-target"
            else message
        )
        for message in checkpoint.messages
    )
    assert run_store.save(
        replace(checkpoint, messages=tampered_messages),
        expected_version=checkpoint.version,
    ).is_ok()
    assert agent.decide_approval(approval_id, approved=True).is_ok()

    resumed = agent.resume_run("run-approval-target")

    assert resumed.is_err()
    assert resumed.unwrap_err()["errorType"] == "RUN_PENDING_TOOL_MISSING"
    assert calls == []
    assert approval_store.get(approval_id).unwrap().status == "approved"
    assert run_store.load("run-approval-target").unwrap().pending_approval_id == (
        approval_id
    )


def test_sync_approval_outcome_replays_after_checkpoint_save_failure():
    class FailThirdSaveStore(InMemoryAgentRunStore):
        def __init__(self):
            super().__init__()
            self.save_count = 0

        def save(self, checkpoint, expected_version=None):
            self.save_count += 1
            if self.save_count == 3:
                return Result.err(
                    {
                        "errorType": "TEST_CHECKPOINT_FAILURE",
                        "message": "checkpoint failed after approval execution",
                    }
                )
            return super().save(checkpoint, expected_version=expected_version)

    run_store = FailThirdSaveStore()
    approval_store = InMemoryApprovalStore()
    calls = []
    first = make_agent(
        [
            LLMResponse(
                content="request write",
                tool_calls=[ToolCall("approval-replay-call", "write_value", {})],
                finish_reason="tool_calls",
            )
        ]
    )
    first.set_run_store(run_store)
    first.set_approval_store(approval_store)
    assert first.register_tool(approval_tool(calls)).is_ok()

    started = first.pursue_goal("Write once", run_id="run-approval-replay")
    assert started.is_ok()
    assert started.unwrap().status == "paused"
    approval_id = started.unwrap().result["details"]["approval_id"]
    assert first.decide_approval(approval_id, approved=True).is_ok()

    failed = first.resume_run("run-approval-replay")
    assert failed.is_err()
    assert failed.unwrap_err()["errorType"] == "RUN_STORE_ERROR"
    assert calls == [{}]
    consumed = approval_store.get(approval_id).unwrap()
    assert consumed is not None
    assert consumed.status == "consumed"
    assert consumed.execution_result == {
        "content": '{"written": true}',
        "is_error": False,
    }

    restarted = make_agent([LLMResponse(content="done", finish_reason="stop")])
    restarted.set_run_store(run_store)
    restarted.set_approval_store(approval_store)
    assert restarted.register_tool(approval_tool(calls)).is_ok()

    resumed = restarted.resume_run("run-approval-replay")

    assert resumed.is_ok()
    assert resumed.unwrap().status == "completed"
    assert calls == [{}]


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


def test_sync_tool_replay_journal_reuses_success_after_checkpoint_failure():
    class FailSecondSaveStore(InMemoryAgentRunStore):
        def __init__(self):
            super().__init__()
            self.save_count = 0

        def save(self, checkpoint, expected_version=None):
            self.save_count += 1
            if self.save_count == 2:
                return Result.err(
                    {
                        "errorType": "TEST_CHECKPOINT_FAILURE",
                        "message": "checkpoint failed after tool execution",
                    }
                )
            return super().save(checkpoint, expected_version=expected_version)

    run_store = FailSecondSaveStore()
    journal = InMemoryExecutionJournal()
    calls = []
    tool_call = ToolCall(
        id="replay-call",
        name="write_value",
        arguments={"value": "once"},
    )
    tool = Tool(
        name="write_value",
        description="Write one value",
        parameters={"type": "object", "additionalProperties": True},
        replay_policy=TOOL_REPLAY_REUSE_SUCCESS,
        handler=lambda **kwargs: (calls.append(kwargs) or Result.ok({"written": True})),
    )
    first = make_agent(
        [
            LLMResponse(
                content="write", tool_calls=[tool_call], finish_reason="tool_calls"
            )
        ]
    )
    first.set_run_store(run_store)
    first.set_execution_journal(journal)
    assert first.register_tool(tool).is_ok()

    interrupted = first.pursue_goal(
        "Perform one durable write", run_id="run-tool-replay"
    )

    assert interrupted.is_ok()
    assert interrupted.unwrap().status == "failed"
    assert calls == [{"value": "once"}]
    checkpoint = run_store.load("run-tool-replay").unwrap()
    assert checkpoint is not None
    assert checkpoint.step_count == 0

    restarted = make_agent(
        [
            LLMResponse(
                content="retry write",
                tool_calls=[tool_call],
                finish_reason="tool_calls",
            ),
            LLMResponse(content="done", finish_reason="stop"),
        ]
    )
    restarted.set_run_store(run_store)
    restarted.set_execution_journal(journal)
    assert restarted.register_tool(tool).is_ok()

    resumed = restarted.resume_run("run-tool-replay")

    assert resumed.is_ok()
    assert resumed.unwrap().status == "completed"
    assert calls == [{"value": "once"}]


def test_sync_agent_tool_replay_journal_reuses_successful_child_result():
    class ReplayableTarget:
        agent_id = "replayable-specialist"

        def __init__(self):
            self.calls = 0

        def pursue_goal(self, description):
            self.calls += 1
            return Result.ok(
                type(
                    "Goal",
                    (),
                    {
                        "goal_id": "child-run-1",
                        "status": "completed",
                        "result": {"answer": description.upper()},
                    },
                )()
            )

    target = ReplayableTarget()
    agent = make_agent([])
    agent.set_execution_journal(InMemoryExecutionJournal())
    tool = create_agent_tool(
        target,
        requires_approval=False,
        replay_policy=TOOL_REPLAY_REUSE_SUCCESS,
    )
    assert agent.register_tool(tool).is_ok()

    first = agent._execute_tool_call(
        ToolCall("child-call-1", tool.name, {"task": "recover this"}),
        run_id="parent-replay-run",
        step_num=0,
        tool_call_index=0,
    )
    second = agent._execute_tool_call(
        ToolCall("child-call-2", tool.name, {"task": "recover this"}),
        run_id="parent-replay-run",
        step_num=0,
        tool_call_index=0,
    )

    assert not first.is_error
    assert not second.is_error
    assert first.content == second.content
    assert second.tool_call_id == "child-call-2"
    assert target.calls == 1


@pytest.mark.asyncio
async def test_async_agent_tool_replay_journal_reuses_successful_child_result():
    class AsyncReplayableTarget:
        agent_id = "async-replayable-specialist"

        def __init__(self):
            self.calls = 0

        def pursue_goal(self, description):
            raise AssertionError("sync child path must not be selected")

        async def pursue_goal_async(self, description):
            self.calls += 1
            return Result.ok(
                type(
                    "Goal",
                    (),
                    {
                        "goal_id": "async-child-run-1",
                        "status": "completed",
                        "result": {"answer": description.upper()},
                    },
                )()
            )

    target = AsyncReplayableTarget()
    agent = make_agent([])
    agent.set_execution_journal(InMemoryExecutionJournal())
    tool = create_agent_tool(
        target,
        requires_approval=False,
        replay_policy=TOOL_REPLAY_REUSE_SUCCESS,
    )
    assert agent.register_tool(tool).is_ok()

    first = await agent._execute_tool_call_async(
        ToolCall("async-child-call-1", tool.name, {"task": "recover this"}),
        run_id="async-parent-replay-run",
        step_num=0,
        tool_call_index=0,
    )
    second = await agent._execute_tool_call_async(
        ToolCall("async-child-call-2", tool.name, {"task": "recover this"}),
        run_id="async-parent-replay-run",
        step_num=0,
        tool_call_index=0,
    )

    assert not first.is_error
    assert not second.is_error
    assert first.content == second.content
    assert second.tool_call_id == "async-child-call-2"
    assert target.calls == 1


def test_async_tool_replay_journal_reuses_successful_result():
    journal = InMemoryExecutionJournal()
    calls = []
    agent = make_agent([])
    agent.set_execution_journal(journal)

    async def handler(**kwargs):
        calls.append(kwargs)
        return Result.ok({"written": True})

    tool = Tool(
        name="async_write",
        description="Write one value asynchronously",
        parameters={"type": "object", "additionalProperties": True},
        async_handler=handler,
        handler=lambda **kwargs: Result.ok({"written": True}),
        replay_policy=TOOL_REPLAY_REUSE_SUCCESS,
    )
    assert agent.register_tool(tool).is_ok()
    first_call = ToolCall("async-replay-1", "async_write", {"value": "once"})
    second_call = ToolCall("async-replay-2", "async_write", {"value": "once"})

    first = asyncio.run(
        agent._execute_tool_call_async(
            first_call, run_id="async-replay-run", step_num=0, tool_call_index=0
        )
    )
    second = asyncio.run(
        agent._execute_tool_call_async(
            second_call, run_id="async-replay-run", step_num=0, tool_call_index=0
        )
    )

    assert not first.is_error
    assert not second.is_error
    assert second.tool_call_id == "async-replay-2"
    assert calls == [{"value": "once"}]


def test_tool_replay_rejects_malformed_journal_record_without_running_handler():
    class MalformedJournal:
        def load(self, execution_key, input_digest):
            return Result.ok({"not": "an execution record"})

        def save(self, record):
            return Result.ok(record)

    calls = []
    agent = make_agent([])
    agent.set_execution_journal(MalformedJournal())
    assert agent.register_tool(
        Tool(
            name="replay_guard",
            description="Guarded replay tool",
            parameters={"type": "object"},
            replay_policy=TOOL_REPLAY_REUSE_SUCCESS,
            handler=lambda **kwargs: (calls.append(True) or Result.ok({"ok": True})),
        )
    ).is_ok()

    result = agent._execute_tool_call(
        ToolCall("malformed-replay", "replay_guard", {}),
        run_id="malformed-replay-run",
        step_num=0,
        tool_call_index=0,
    )

    assert result.is_error
    assert json.loads(result.content)["errorType"] == "TOOL_REPLAY_RECORD_INVALID"
    assert calls == []


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
    spans = SpanRecorder(max_spans=10)
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
    first.set_span_recorder(spans)
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
    tool_event = next(
        event
        for event in events.snapshot().unwrap()
        if event.event_type == "tool.completed"
    )
    model_span = spans.snapshot().unwrap()[0]
    assert tool_event.payload["approval_id"] == approval_id
    assert tool_event.payload["trace_id"] == model_span.trace_id
    assert tool_event.payload["span_id"] == model_span.span_id
    stored = approval_store.get(approval_id).unwrap()
    assert stored.trace_id == model_span.trace_id
    assert stored.span_id == model_span.span_id
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


def test_async_resume_rejects_mismatched_approval_before_execution():
    run_store = InMemoryAgentRunStore()
    approval_store = InMemoryApprovalStore()
    calls = []
    agent = make_agent(
        [
            LLMResponse(
                content="request write",
                tool_calls=[ToolCall("async-approval-target", "write_value", {})],
                finish_reason="tool_calls",
            )
        ]
    )
    agent.set_run_store(run_store)
    agent.set_approval_store(approval_store)
    assert agent.register_tool(approval_tool(calls)).is_ok()

    started = asyncio.run(
        agent.pursue_goal_async("Write once", run_id="async-approval-target")
    )
    assert started.is_ok()
    approval_id = started.unwrap().result["details"]["approval_id"]
    checkpoint = run_store.load("async-approval-target").unwrap()
    assert checkpoint is not None
    tampered_messages = tuple(
        (
            replace(message, tool_call_id="wrong-target")
            if message.tool_call_id == "async-approval-target"
            else message
        )
        for message in checkpoint.messages
    )
    assert run_store.save(
        replace(checkpoint, messages=tampered_messages),
        expected_version=checkpoint.version,
    ).is_ok()
    assert agent.decide_approval(approval_id, approved=True).is_ok()

    resumed = asyncio.run(agent.resume_run_async("async-approval-target"))

    assert resumed.is_err()
    assert resumed.unwrap_err()["errorType"] == "RUN_PENDING_TOOL_MISSING"
    assert calls == []
    assert approval_store.get(approval_id).unwrap().status == "approved"


def test_async_approval_outcome_replays_after_checkpoint_save_failure():
    class FailThirdSaveStore(InMemoryAgentRunStore):
        def __init__(self):
            super().__init__()
            self.save_count = 0

        def save(self, checkpoint, expected_version=None):
            self.save_count += 1
            if self.save_count == 3:
                return Result.err(
                    {
                        "errorType": "TEST_CHECKPOINT_FAILURE",
                        "message": "checkpoint failed after approval execution",
                    }
                )
            return super().save(checkpoint, expected_version=expected_version)

    run_store = FailThirdSaveStore()
    approval_store = InMemoryApprovalStore()
    calls = []
    first = make_agent(
        [
            LLMResponse(
                content="request write",
                tool_calls=[ToolCall("async-approval-replay", "write_value", {})],
                finish_reason="tool_calls",
            )
        ]
    )
    first.set_run_store(run_store)
    first.set_approval_store(approval_store)
    assert first.register_tool(approval_tool(calls)).is_ok()

    started = asyncio.run(
        first.pursue_goal_async("Write once", run_id="async-approval-replay")
    )
    assert started.is_ok()
    assert started.unwrap().status == "paused"
    approval_id = started.unwrap().result["details"]["approval_id"]
    assert first.decide_approval(approval_id, approved=True).is_ok()

    failed = asyncio.run(first.resume_run_async("async-approval-replay"))
    assert failed.is_err()
    assert failed.unwrap_err()["errorType"] == "RUN_STORE_ERROR"
    assert calls == [{}]

    restarted = make_agent([LLMResponse(content="done", finish_reason="stop")])
    restarted.set_run_store(run_store)
    restarted.set_approval_store(approval_store)
    assert restarted.register_tool(approval_tool(calls)).is_ok()

    resumed = asyncio.run(restarted.resume_run_async("async-approval-replay"))

    assert resumed.is_ok()
    assert resumed.unwrap().status == "completed"
    assert calls == [{}]


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


def test_sync_resume_rejects_mismatched_human_input_before_consume():
    run_store = InMemoryAgentRunStore()
    input_store = InMemoryHumanInputStore()
    agent = make_agent(
        [
            LLMResponse(
                content="ask for code",
                tool_calls=[_human_input_call("input-target")],
                finish_reason="tool_calls",
            )
        ]
    )
    agent.set_run_store(run_store)
    agent.set_human_input_store(input_store)

    started = agent.pursue_goal("Deploy safely", run_id="run-input-target")
    assert started.is_ok()
    interaction_id = started.unwrap().result["details"]["interaction_id"]
    checkpoint = run_store.load("run-input-target").unwrap()
    assert checkpoint is not None
    tampered_messages = tuple(
        (
            replace(message, tool_call_id="wrong-target")
            if message.tool_call_id == "input-target"
            else message
        )
        for message in checkpoint.messages
    )
    assert run_store.save(
        replace(checkpoint, messages=tampered_messages),
        expected_version=checkpoint.version,
    ).is_ok()
    assert agent.respond_human_input(interaction_id, {"code": "green"}).is_ok()

    resumed = agent.resume_run("run-input-target")

    assert resumed.is_err()
    assert resumed.unwrap_err()["errorType"] == "RUN_PENDING_TOOL_MISSING"
    assert input_store.get(interaction_id).unwrap().status == "responded"
    assert run_store.load("run-input-target").unwrap().pending_input_id == (
        interaction_id
    )


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


def test_async_resume_rejects_mismatched_human_input_before_consume():
    run_store = InMemoryAgentRunStore()
    input_store = InMemoryHumanInputStore()
    agent = make_agent(
        [
            LLMResponse(
                content="ask for code",
                tool_calls=[_human_input_call("async-input-target")],
                finish_reason="tool_calls",
            )
        ]
    )
    agent.set_run_store(run_store)
    agent.set_human_input_store(input_store)

    started = asyncio.run(
        agent.pursue_goal_async("Deploy safely", run_id="async-input-target")
    )
    assert started.is_ok()
    interaction_id = started.unwrap().result["details"]["interaction_id"]
    checkpoint = run_store.load("async-input-target").unwrap()
    assert checkpoint is not None
    tampered_messages = tuple(
        (
            replace(message, tool_call_id="wrong-target")
            if message.tool_call_id == "async-input-target"
            else message
        )
        for message in checkpoint.messages
    )
    assert run_store.save(
        replace(checkpoint, messages=tampered_messages),
        expected_version=checkpoint.version,
    ).is_ok()
    assert agent.respond_human_input(interaction_id, {"code": "green"}).is_ok()

    resumed = asyncio.run(agent.resume_run_async("async-input-target"))

    assert resumed.is_err()
    assert resumed.unwrap_err()["errorType"] == "RUN_PENDING_TOOL_MISSING"
    assert input_store.get(interaction_id).unwrap().status == "responded"
    assert run_store.load("async-input-target").unwrap().pending_input_id == (
        interaction_id
    )


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
