"""Tests for the bounded loopback workflow server."""

import json
import urllib.error
import urllib.request

import pytest

from maple.autonomy import (
    HumanInputRequest,
    InMemoryHumanInputStore,
    InMemoryCheckpointStore,
    RunClient,
    RunServer,
    Workflow,
    WorkflowPause,
    WorkflowRegistry,
)


def _workflow(name="echo"):
    workflow = Workflow(name, checkpoint_store=InMemoryCheckpointStore())
    assert workflow.add_node(
        "echo", lambda context: {"echo": context.state["value"]}
    ).is_ok()
    assert workflow.set_entry_point("echo").is_ok()
    assert workflow.add_edge("echo").is_ok()
    return workflow


def _human_input_request(interaction_id="remote-input", max_rounds=2):
    return HumanInputRequest(
        interaction_id=interaction_id,
        run_id="remote-run",
        tool_call_id="remote-call",
        prompt="Confirm the deployment.",
        input_schema={
            "type": "object",
            "properties": {"confirmed": {"type": "boolean"}},
            "required": ["confirmed"],
            "additionalProperties": False,
        },
        max_rounds=max_rounds,
    )


def _request(url, *, method="GET", payload=None, headers=None):
    data = None
    request_headers = dict(headers or {})
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        url, data=data, headers=request_headers, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def test_run_server_health_run_and_inspect_routes():
    registry = WorkflowRegistry()
    assert registry.register(_workflow()).is_ok()
    server = RunServer(registry)
    base_url = server.start()

    try:
        health_status, health = _request(f"{base_url}/healthz")
        run_status, run_payload = _request(
            f"{base_url}/v1/workflows/echo/runs",
            method="POST",
            payload={"run_id": "server-run", "state": {"value": "MAPLE"}},
        )
        inspect_status, inspect_payload = _request(
            f"{base_url}/v1/workflows/echo/runs/server-run"
        )
    finally:
        server.close()

    assert health_status == 200
    assert health == {"status": "ok", "service": "maple-run-server"}
    assert run_status == 201
    assert run_payload["run"]["status"] == "completed"
    assert run_payload["run"]["state"]["echo"] == "MAPLE"
    assert inspect_status == 200
    assert inspect_payload["run"]["run_id"] == "server-run"


def test_run_server_resumes_interrupted_workflow():
    workflow = Workflow("approval", checkpoint_store=InMemoryCheckpointStore())

    def approval(context):
        if context.resume_value is None:
            raise WorkflowPause({"question": "approve?"})
        return {"approved": context.resume_value}

    assert workflow.add_node("approval", approval).is_ok()
    assert workflow.set_entry_point("approval").is_ok()
    assert workflow.add_edge("approval").is_ok()
    registry = WorkflowRegistry()
    assert registry.register(workflow).is_ok()
    server = RunServer(registry)
    base_url = server.start()

    try:
        first_status, first = _request(
            f"{base_url}/v1/workflows/approval/runs",
            method="POST",
            payload={"run_id": "approval-run", "state": {}},
        )
        resumed_status, resumed = _request(
            f"{base_url}/v1/workflows/approval/runs/approval-run/resume",
            method="POST",
            payload={"value": True},
        )
    finally:
        server.close()

    assert first_status == 201
    assert first["run"]["status"] == "interrupted"
    assert resumed_status == 200
    assert resumed["run"]["status"] == "completed"
    assert resumed["run"]["state"]["approved"] is True


def test_run_server_rejects_unknown_routes_workflows_and_oversized_bodies():
    registry = WorkflowRegistry()
    assert registry.register(_workflow()).is_ok()
    server = RunServer(registry, max_body_bytes=128)
    base_url = server.start()

    try:
        missing_status, missing = _request(
            f"{base_url}/v1/workflows/missing/runs",
            method="POST",
            payload={"state": {}},
        )
        oversized_status, oversized = _request(
            f"{base_url}/v1/workflows/echo/runs",
            method="POST",
            payload={"state": {"value": "x" * 1_000}},
        )
    finally:
        server.close()

    assert missing_status == 404
    assert missing["error"]["errorType"] == "WORKFLOW_NOT_FOUND"
    assert oversized_status == 413
    assert oversized["error"]["errorType"] == "REQUEST_TOO_LARGE"


def test_run_server_rejects_non_loopback_host_and_malformed_json():
    with pytest.raises(ValueError):
        RunServer(WorkflowRegistry(), host="0.0.0.0")

    registry = WorkflowRegistry()
    assert registry.register(_workflow()).is_ok()
    server = RunServer(registry)
    base_url = server.start()
    request = urllib.request.Request(
        f"{base_url}/v1/workflows/echo/runs",
        data=b"not-json",
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request, timeout=2)
        payload = json.loads(error.value.read().decode("utf-8"))
    finally:
        server.close()

    assert error.value.code == 400
    assert payload["error"]["errorType"] == "REQUEST_BODY_INVALID"


def test_authenticated_run_client_round_trips_workflow_operations():
    registry = WorkflowRegistry()
    assert registry.register(_workflow()).is_ok()
    server = RunServer(registry, auth_token="test-token")
    base_url = server.start()

    try:
        client = RunClient(base_url, auth_token="test-token")
        health = client.healthz()
        run = client.run("echo", {"value": "remote"}, run_id="client-run")
        inspected = client.inspect("echo", "client-run")
        unauthorized = _request(f"{base_url}/healthz")
        wrong_token = RunClient(base_url, auth_token="wrong-token").healthz()
    finally:
        server.close()

    assert health.is_ok()
    assert health.unwrap() == {"status": "ok", "service": "maple-run-server"}
    assert run.is_ok()
    assert run.unwrap()["run"]["state"]["echo"] == "remote"
    assert inspected.is_ok()
    assert inspected.unwrap()["run"]["run_id"] == "client-run"
    assert unauthorized[0] == 401
    assert unauthorized[1]["error"]["errorType"] == "UNAUTHORIZED"
    assert wrong_token.is_err()
    assert wrong_token.unwrap_err()["errorType"] == "UNAUTHORIZED"


def test_run_client_bounds_inputs_and_normalizes_transport_errors():
    with pytest.raises(ValueError):
        RunClient("file:///tmp/maple")
    with pytest.raises(ValueError):
        RunClient("http://user:password@example.test")
    with pytest.raises(ValueError):
        RunClient("http://example.test", auth_token=" ")
    with pytest.raises(ValueError):
        RunClient("http://example.test", auth_token="safe-token")
    with pytest.raises(ValueError):
        RunClient("http://example.test", auth_token="safe\r\nInjected: value")
    with pytest.raises(ValueError):
        RunClient("http://example.test/unsafe\npath")

    client = RunClient("http://127.0.0.1:1", timeout_seconds=0.1)
    invalid_state = client.run("echo", [])
    unreachable = client.healthz()
    oversized_request = RunClient("http://127.0.0.1:1", max_body_bytes=32).run(
        "echo", {"value": "x" * 100}
    )

    assert invalid_state.is_err()
    assert invalid_state.unwrap_err()["errorType"] == "INVALID_STATE"
    assert unreachable.is_err()
    assert unreachable.unwrap_err()["errorType"] == "TRANSPORT_ERROR"
    assert oversized_request.is_err()
    assert oversized_request.unwrap_err()["errorType"] == "REQUEST_TOO_LARGE"


def test_run_client_rejects_responses_over_its_configured_limit():
    registry = WorkflowRegistry()
    assert registry.register(_workflow()).is_ok()
    server = RunServer(registry, auth_token="test-token")
    base_url = server.start()

    try:
        client = RunClient(base_url, auth_token="test-token", max_response_bytes=1)
        result = client.healthz()
    finally:
        server.close()

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "RESPONSE_TOO_LARGE"


def test_authenticated_run_client_round_trips_human_input_operations():
    registry = WorkflowRegistry()
    assert registry.register(_workflow()).is_ok()
    store = InMemoryHumanInputStore()
    assert store.create(_human_input_request()).is_ok()
    server = RunServer(
        registry,
        auth_token="interaction-token",
        human_input_store=store,
    )
    base_url = server.start()

    try:
        client = RunClient(base_url, auth_token="interaction-token")
        pending = client.list_pending_human_input(limit=10)
        inspected = client.get_human_input("remote-input")
        responded = client.respond_human_input(
            "remote-input", {"confirmed": True}, actor_id="operator-1"
        )
        continued = client.continue_human_input(
            "remote-input",
            "Confirm the second step.",
            {
                "type": "object",
                "properties": {"confirmed": {"type": "boolean"}},
                "required": ["confirmed"],
            },
            actor_id="operator-1",
        )
        responded_again = client.respond_human_input(
            "remote-input", {"confirmed": False}, actor_id="operator-1"
        )
        consumed = client.consume_human_input("remote-input")
        unauthorized = RunClient(base_url).list_pending_human_input()
    finally:
        server.close()

    assert pending.is_ok()
    assert pending.unwrap()["interactions"][0]["interaction_id"] == "remote-input"
    assert inspected.is_ok()
    assert inspected.unwrap()["interaction"]["status"] == "pending"
    assert responded.is_ok()
    assert responded.unwrap()["interaction"]["status"] == "responded"
    assert continued.is_ok()
    assert continued.unwrap()["interaction"]["round_index"] == 1
    assert responded_again.is_ok()
    assert responded_again.unwrap()["interaction"]["decision"]["response"] == {
        "confirmed": False
    }
    assert consumed.is_ok()
    assert consumed.unwrap()["interaction"]["status"] == "consumed"
    assert unauthorized.is_err()
    assert unauthorized.unwrap_err()["errorType"] == "UNAUTHORIZED"


def test_run_server_human_input_transport_fails_closed_without_a_store():
    registry = WorkflowRegistry()
    assert registry.register(_workflow()).is_ok()
    server = RunServer(registry)
    base_url = server.start()

    try:
        result = RunClient(base_url).list_pending_human_input()
    finally:
        server.close()

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "HUMAN_INPUT_STORE_UNAVAILABLE"


def test_run_server_requires_authentication_for_human_input_transport():
    registry = WorkflowRegistry()
    assert registry.register(_workflow()).is_ok()

    with pytest.raises(ValueError):
        RunServer(registry, human_input_store=InMemoryHumanInputStore())


def test_run_client_rejects_out_of_bounds_human_input_list_limits():
    client = RunClient("http://127.0.0.1:1", timeout_seconds=0.1)

    zero = client.list_pending_human_input(0)
    too_large = client.list_pending_human_input(1_001)
    invalid_schema = client.continue_human_input("input-1", "next", [])  # type: ignore[arg-type]

    assert zero.is_err()
    assert zero.unwrap_err()["errorType"] == "HUMAN_INPUT_LIMIT_INVALID"
    assert too_large.is_err()
    assert too_large.unwrap_err()["errorType"] == "HUMAN_INPUT_LIMIT_INVALID"
    assert invalid_schema.is_err()
    assert invalid_schema.unwrap_err()["errorType"] == "REQUEST_BODY_INVALID"
