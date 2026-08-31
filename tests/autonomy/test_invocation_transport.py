"""Regression coverage for keyed agent invocation transport."""

import threading

from maple.autonomy import (
    AgentInvocationResponse,
    AgentRegistry,
    AgentRun,
    FileAgentInvocationDeduplicationStore,
    InMemoryAgentInvocationDeduplicationStore,
    RunClient,
    RunServer,
    WorkflowRegistry,
)
from maple.core.result import Result


def _assert_error(result, error_type):
    assert result.is_err()
    assert result.unwrap_err()["errorType"] == error_type


def _server(agents, store=None):
    return RunServer(
        WorkflowRegistry(),
        agent_registry=agents,
        agent_invocation_store=store,
        auth_token="agent-token",
    )


def test_keyed_named_agent_replays_completed_response_without_second_handler_call():
    calls = []

    def handler(task, context, *, session_id, run_id):
        calls.append((task, dict(context), session_id, run_id))
        return Result.ok(
            AgentRun("alpha", run_id, "completed", result={"calls": len(calls)})
        )

    agents = AgentRegistry()
    assert agents.register("alpha", handler).is_ok()
    server = _server(agents, InMemoryAgentInvocationDeduplicationStore())
    base_url = server.start()
    try:
        client = RunClient(base_url, auth_token="agent-token")
        first = client.run_agent_typed(
            "alpha",
            "task",
            {"value": 1},
            session_id="session-1",
            idempotency_key="request-1",
        )
        replay = client.run_agent_typed(
            "alpha",
            "task",
            {"value": 1},
            session_id="session-1",
            idempotency_key="request-1",
        )
    finally:
        server.close()

    assert first.is_ok()
    assert replay.is_ok()
    assert first.unwrap().run_id == replay.unwrap().run_id
    assert first.unwrap().result == {"calls": 1}
    assert replay.unwrap().result == {"calls": 1}
    assert len(calls) == 1


def test_keyed_capability_route_replays_selected_agent_identity():
    calls = {"alpha": 0, "zeta": 0}

    def handler_for(agent_id):
        def handler(task, context, *, session_id, run_id):
            calls[agent_id] += 1
            return Result.ok(
                AgentRun(agent_id, run_id, "completed", result={"agent": agent_id})
            )

        return handler

    agents = AgentRegistry()
    assert agents.register(
        "zeta", handler_for("zeta"), capabilities=["research"]
    ).is_ok()
    assert agents.register(
        "alpha", handler_for("alpha"), capabilities=["research"]
    ).is_ok()
    server = _server(agents, InMemoryAgentInvocationDeduplicationStore())
    base_url = server.start()
    try:
        client = RunClient(base_url, auth_token="agent-token")
        first = client.route_agent_typed(
            "research", "task", idempotency_key="route-request"
        )
        replay = client.route_agent_typed(
            "research", "task", idempotency_key="route-request"
        )
    finally:
        server.close()

    assert first.is_ok()
    assert replay.is_ok()
    assert first.unwrap().agent_id == "alpha"
    assert replay.unwrap().agent_id == "alpha"
    assert first.unwrap().run_id == replay.unwrap().run_id
    assert calls == {"alpha": 1, "zeta": 0}


def test_keyed_concurrent_duplicate_returns_in_progress_without_second_handler_call():
    started = threading.Event()
    release = threading.Event()
    calls = []

    def handler(task, context, *, session_id, run_id):
        calls.append(run_id)
        started.set()
        assert release.wait(timeout=5)
        return Result.ok(AgentRun("alpha", run_id, "completed", result={}))

    agents = AgentRegistry()
    assert agents.register("alpha", handler).is_ok()
    server = _server(agents, InMemoryAgentInvocationDeduplicationStore())
    base_url = server.start()
    first_result = []

    def first_call():
        first_result.append(
            RunClient(base_url, auth_token="agent-token").run_agent(
                "alpha", "task", idempotency_key="concurrent-request"
            )
        )

    first_thread = threading.Thread(target=first_call)
    first_thread.start()
    try:
        assert started.wait(timeout=5)
        duplicate = RunClient(base_url, auth_token="agent-token").run_agent(
            "alpha", "task", idempotency_key="concurrent-request"
        )
        release.set()
        first_thread.join(timeout=5)
    finally:
        release.set()
        first_thread.join(timeout=5)
        server.close()

    assert len(first_result) == 1
    assert first_result[0].is_ok()
    _assert_error(duplicate, "AGENT_INVOCATION_IN_PROGRESS")
    assert len(calls) == 1


def test_keyed_request_conflict_does_not_reinvoke_or_replace_completed_response():
    calls = []

    def handler(task, context, *, session_id, run_id):
        calls.append(task)
        return Result.ok(AgentRun("alpha", run_id, "completed", result={"task": task}))

    agents = AgentRegistry()
    assert agents.register("alpha", handler).is_ok()
    server = _server(agents, InMemoryAgentInvocationDeduplicationStore())
    base_url = server.start()
    try:
        client = RunClient(base_url, auth_token="agent-token")
        first = client.run_agent_typed(
            "alpha", "one", idempotency_key="conflict-request"
        )
        conflict = client.run_agent("alpha", "two", idempotency_key="conflict-request")
        replay = client.run_agent_typed(
            "alpha", "one", idempotency_key="conflict-request"
        )
    finally:
        server.close()

    assert first.is_ok()
    _assert_error(conflict, "AGENT_INVOCATION_CONFLICT")
    assert replay.is_ok()
    assert replay.unwrap().result == {"task": "one"}
    assert calls == ["one"]


def test_keyed_invocation_requires_explicit_store_but_unkeyed_legacy_call_remains():
    calls = []

    def handler(task, context, *, session_id, run_id):
        calls.append(task)
        return Result.ok(AgentRun("alpha", run_id, "completed", result={}))

    agents = AgentRegistry()
    assert agents.register("alpha", handler).is_ok()
    server = _server(agents)
    base_url = server.start()
    try:
        client = RunClient(base_url, auth_token="agent-token")
        request_id = "request-1"
        keyed = client.run_agent("alpha", "keyed", idempotency_key=request_id)
        legacy = client.run_agent("alpha", "legacy")
    finally:
        server.close()

    _assert_error(keyed, "AGENT_INVOCATION_STORE_UNAVAILABLE")
    assert legacy.is_ok()
    assert calls == ["legacy"]


def test_keyed_handler_error_is_replayed_without_second_execution():
    calls = []

    def handler(task, context, *, session_id, run_id):
        calls.append(run_id)
        return Result.err(
            {
                "errorType": "AGENT_HANDLER_REJECTED",
                "message": "request was rejected",
            }
        )

    agents = AgentRegistry()
    assert agents.register("alpha", handler).is_ok()
    server = _server(agents, InMemoryAgentInvocationDeduplicationStore())
    base_url = server.start()
    try:
        client = RunClient(base_url, auth_token="agent-token")
        first = client.run_agent("alpha", "task", idempotency_key="error-request")
        replay = client.run_agent("alpha", "task", idempotency_key="error-request")
    finally:
        server.close()

    _assert_error(first, "AGENT_HANDLER_REJECTED")
    _assert_error(replay, "AGENT_HANDLER_REJECTED")
    assert len(calls) == 1


def test_file_store_replays_remote_response_after_server_restart(tmp_path):
    calls = []

    def handler(task, context, *, session_id, run_id):
        calls.append(run_id)
        return Result.ok(AgentRun("alpha", run_id, "completed", result={"ok": True}))

    agents = AgentRegistry()
    assert agents.register("alpha", handler).is_ok()
    first_server = _server(agents, FileAgentInvocationDeduplicationStore(tmp_path))
    first_url = first_server.start()
    try:
        first = RunClient(first_url, auth_token="agent-token").run_agent_typed(
            "alpha", "task", idempotency_key="restart-request"
        )
    finally:
        first_server.close()

    second_server = _server(agents, FileAgentInvocationDeduplicationStore(tmp_path))
    second_url = second_server.start()
    try:
        replay = RunClient(second_url, auth_token="agent-token").run_agent_typed(
            "alpha", "task", idempotency_key="restart-request"
        )
    finally:
        second_server.close()

    assert first.is_ok()
    assert replay.is_ok()
    assert replay.unwrap().run_id == first.unwrap().run_id
    assert len(calls) == 1


def test_client_rejects_invalid_idempotency_key_before_network_call():
    client = RunClient("http://127.0.0.1:1", timeout_seconds=0.1)
    invalid_named = client.run_agent("alpha", "task", idempotency_key="x" * 257)
    invalid_route = client.route_agent("research", "task", idempotency_key="x" * 257)
    _assert_error(invalid_named, "AGENT_INVOCATION_KEY_INVALID")
    _assert_error(invalid_route, "AGENT_INVOCATION_KEY_INVALID")


def test_public_invocation_response_is_detached_and_json_safe():
    response = AgentInvocationResponse(201, {"run": {"result": {"value": 1}}})
    copied = response.to_dict()
    copied["payload"]["run"]["result"]["value"] = 2
    assert response.payload["run"]["result"]["value"] == 1
