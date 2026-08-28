"""Regression coverage for opt-in remote handoff idempotency binding."""

import asyncio

from maple.autonomy import (
    AgentRegistry,
    AgentRun,
    InMemoryAgentInvocationDeduplicationStore,
    RemoteHandoffTarget,
    RunClient,
    RunServer,
    WorkflowRegistry,
)
from maple.core.result import Result


def _remote_result(agent_id, run_id, result=None):
    return Result.ok(
        {
            "run": {
                "agent_id": agent_id,
                "run_id": run_id,
                "status": "completed",
                "result": result or {"ok": True},
                "error": None,
            }
        }
    )


def test_default_remote_handoff_does_not_add_idempotency_keyword():
    client = RunClient("http://127.0.0.1:1")
    calls = []

    def run_agent(agent_id, task, context=None, *, session_id=None, run_id=None):
        calls.append(
            {
                "agent_id": agent_id,
                "task": task,
                "context": context,
                "session_id": session_id,
                "run_id": run_id,
            }
        )
        return _remote_result(agent_id, run_id or "generated")

    client.run_agent = run_agent
    target = RemoteHandoffTarget("specialist", client)

    result = target.pursue_goal("task", handoff_id="handoff-1")

    assert result.is_ok()
    assert calls == [
        {
            "agent_id": "specialist",
            "task": "task",
            "context": {},
            "session_id": None,
            "run_id": "handoff-1",
        }
    ]


def test_opt_in_remote_handoff_binds_handoff_id_to_idempotency_key():
    client = RunClient("http://127.0.0.1:1")
    calls = []

    def run_agent(
        agent_id,
        task,
        context=None,
        *,
        session_id=None,
        run_id=None,
        idempotency_key=None,
    ):
        calls.append((run_id, idempotency_key))
        return _remote_result(agent_id, run_id or "generated")

    client.run_agent = run_agent
    target = RemoteHandoffTarget(
        "specialist",
        client,
        use_handoff_id_as_idempotency_key=True,
    )

    result = target.pursue_goal("task", handoff_id="handoff-1")

    assert result.is_ok()
    assert calls == [("handoff-1", "handoff-1")]


def test_opt_in_remote_handoff_requires_id_before_http_call():
    client = RunClient("http://127.0.0.1:1")
    calls = []

    def run_agent(*args, **kwargs):
        calls.append((args, kwargs))
        return _remote_result("specialist", "unexpected")

    client.run_agent = run_agent
    target = RemoteHandoffTarget(
        "specialist",
        client,
        use_handoff_id_as_idempotency_key=True,
    )

    result = target.pursue_goal("task")

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "REMOTE_HANDOFF_INPUT_INVALID"
    assert calls == []


def test_opt_in_remote_handoff_replays_at_receiver_and_async_path_matches():
    calls = []

    def handler(task, context, *, session_id, run_id):
        calls.append((task, dict(context), session_id, run_id))
        return Result.ok(
            AgentRun("specialist", run_id, "completed", {"calls": len(calls)})
        )

    agents = AgentRegistry()
    assert agents.register("specialist", handler).is_ok()
    server = RunServer(
        WorkflowRegistry(),
        agent_registry=agents,
        agent_invocation_store=InMemoryAgentInvocationDeduplicationStore(),
        auth_token="agent-token",
    )
    base_url = server.start()
    try:
        client = RunClient(base_url, auth_token="agent-token")
        target = RemoteHandoffTarget(
            "specialist",
            client,
            use_handoff_id_as_idempotency_key=True,
        )
        first = target.pursue_goal("task", handoff_id="handoff-1")
        replay = asyncio.run(target.pursue_goal_async("task", handoff_id="handoff-1"))
    finally:
        server.close()

    assert first.is_ok()
    assert replay.is_ok()
    assert first.unwrap().goal_id == "handoff-1"
    assert replay.unwrap().goal_id == "handoff-1"
    assert first.unwrap().result == {"calls": 1}
    assert replay.unwrap().result == {"calls": 1}
    assert len(calls) == 1
