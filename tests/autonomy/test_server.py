"""Tests for the bounded loopback workflow server."""

import json
import urllib.error
import urllib.request

import pytest

from maple.autonomy import (
    AgentDescriptor,
    AgentRegistry,
    AgentRun,
    AgentRunCheckpoint,
    ApprovalRequest,
    EventCursor,
    EventStream,
    HandoffRecord,
    HttpEventExporter,
    HumanInputRequest,
    InMemoryAgentRunStore,
    InMemoryApprovalStore,
    InMemoryCheckpointStore,
    InMemoryEventDeduplicationStore,
    InMemoryHandoffStore,
    InMemoryHumanInputStore,
    Principal,
    RemoteHandoffTarget,
    RunClient,
    RunServer,
    Workflow,
    WorkflowPause,
    WorkflowRegistry,
)
from maple.core.result import Result
from maple.task_management import TaskQueue
from maple.task_management.task_queue import TaskPriority, TaskStatus


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


def _approval_request(approval_id="remote-approval"):
    return ApprovalRequest(
        approval_id=approval_id,
        tool_call_id="remote-tool-call",
        tool_name="write_value",
        arguments={"value": "original"},
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


def test_authenticated_remote_task_queue_round_trip_and_ownership():
    queue = TaskQueue(max_queue_size=4)
    server = RunServer(
        WorkflowRegistry(),
        auth_token="task-token",
        task_queue=queue,
    )
    base_url = server.start()

    try:
        client = RunClient(base_url, auth_token="task-token")
        submitted = client.submit_task(
            "research",
            {"query": "MAPLE"},
            priority=TaskPriority.HIGH,
            requirements=["search"],
            metadata={"source": "test"},
        )
        assert submitted.is_ok()
        task_id = submitted.unwrap()["task_id"]
        listed = client.list_tasks(status=TaskStatus.QUEUED, task_type="research")
        inspected = client.inspect_task(task_id)
        claimed = client.claim_task(task_id, "worker-a")
        wrong_owner = client.complete_task(task_id, "worker-b", {"answer": "no"})
        completed = client.complete_task(task_id, "worker-a", {"answer": "yes"})
        final = client.inspect_task(task_id)
    finally:
        server.close()

    assert listed.is_ok()
    assert [item["task_id"] for item in listed.unwrap()["tasks"]] == [task_id]
    assert inspected.is_ok()
    assert inspected.unwrap()["task"]["status"] == "queued"
    assert claimed.is_ok()
    assert claimed.unwrap()["task"]["assigned_agent"] == "worker-a"
    assert wrong_owner.is_err()
    assert wrong_owner.unwrap_err()["errorType"] == "TASK_CONFLICT"
    assert completed.is_ok()
    assert completed.unwrap()["task"]["status"] == "completed"
    assert final.is_ok()
    assert final.unwrap()["task"]["result"] == {"answer": "yes"}


def test_remote_task_queue_requires_auth_and_scopes_agent_targets():
    queue = TaskQueue()
    with pytest.raises(ValueError):
        RunServer(WorkflowRegistry(), task_queue=queue)

    principal = Principal(
        "worker-principal",
        (
            "task:submit",
            "task:read",
            "task:claim",
            "task:complete",
        ),
        allowed_agent_ids=("worker-a",),
        allowed_capabilities=("search",),
    )
    server = RunServer(
        WorkflowRegistry(),
        auth_token="scoped-task-token",
        auth_principal=principal,
        task_queue=queue,
    )
    base_url = server.start()

    try:
        client = RunClient(base_url, auth_token="scoped-task-token")
        denied_capability = client.submit_task("research", {}, requirements=["write"])
        submitted = client.submit_task("research", {}, requirements=["search"])
        task_id = submitted.unwrap()["task_id"]
        denied_agent = client.claim_task(task_id, "worker-b")
        denied_next = client.claim_next_task("worker-a", capabilities=["write"])
        claimed = client.claim_task(task_id, "worker-a")
        denied_failure = client.fail_task(task_id, "worker-a", "not now")
        denied_listing = RunClient(base_url).list_tasks()
    finally:
        server.close()

    assert denied_capability.is_err()
    assert denied_capability.unwrap_err()["errorType"] == "FORBIDDEN"
    assert submitted.is_ok()
    assert denied_agent.is_err()
    assert denied_agent.unwrap_err()["errorType"] == "FORBIDDEN"
    assert denied_next.is_err()
    assert denied_next.unwrap_err()["errorType"] == "FORBIDDEN"
    assert claimed.is_ok()
    assert denied_failure.is_err()
    assert denied_failure.unwrap_err()["errorType"] == "FORBIDDEN"
    assert denied_listing.is_err()
    assert denied_listing.unwrap_err()["errorType"] == "UNAUTHORIZED"


def test_remote_task_claim_next_matches_capabilities_and_priority():
    server = RunServer(
        WorkflowRegistry(),
        auth_token="task-token",
        task_queue=TaskQueue(max_queue_size=4),
    )
    base_url = server.start()

    try:
        client = RunClient(base_url, auth_token="task-token")
        low = client.submit_task(
            "low-search",
            {},
            priority=TaskPriority.LOW,
            requirements=["search"],
        )
        blocked = client.submit_task(
            "write",
            {},
            priority=TaskPriority.HIGH,
            requirements=["write"],
        )
        critical = client.submit_task(
            "critical-search",
            {},
            priority=TaskPriority.CRITICAL,
            requirements=["search"],
        )
        first = client.claim_next_task("worker-a", capabilities=["search"])
        second = client.claim_next_task("worker-a", capabilities=["search"])
        none = client.claim_next_task("worker-a", capabilities=["search"])
        remaining = client.list_tasks(status=TaskStatus.QUEUED)
    finally:
        server.close()

    assert low.is_ok() and blocked.is_ok() and critical.is_ok()
    assert first.is_ok()
    assert first.unwrap()["task"]["task_type"] == "critical-search"
    assert second.is_ok()
    assert second.unwrap()["task"]["task_type"] == "low-search"
    assert none.is_ok()
    assert none.unwrap()["task"] is None
    assert remaining.is_ok()
    assert [task["task_type"] for task in remaining.unwrap()["tasks"]] == ["write"]


def test_remote_task_queue_rejects_malformed_queries_and_payloads():
    server = RunServer(
        WorkflowRegistry(),
        auth_token="task-token",
        task_queue=TaskQueue(),
    )
    base_url = server.start()

    try:
        unknown_field_status, unknown_field = _request(
            f"{base_url}/v1/tasks",
            method="POST",
            payload={"task_type": "research", "unexpected": True},
            headers={"Authorization": "Bearer task-token"},
        )
        duplicate_query_status, duplicate_query = _request(
            f"{base_url}/v1/tasks?limit=1&limit=2",
            headers={"Authorization": "Bearer task-token"},
        )
        invalid_result = RunClient(base_url, auth_token="task-token").complete_task(
            "task", "worker", {"bad": object()}
        )
    finally:
        server.close()

    assert unknown_field_status == 400
    assert unknown_field["error"]["errorType"] == "TASK_INPUT_INVALID"
    assert duplicate_query_status == 400
    assert duplicate_query["error"]["errorType"] == "TASK_QUERY_INVALID"
    assert invalid_result.is_err()
    assert invalid_result.unwrap_err()["errorType"] == "TASK_RESULT_INVALID"


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


def test_run_server_enforces_host_configured_principal_scopes():
    registry = WorkflowRegistry()
    assert registry.register(_workflow()).is_ok()
    server = RunServer(
        registry,
        auth_token="scoped-token",
        auth_principal=Principal(
            "operator",
            ("health:read", "workflow:read"),
        ),
    )
    base_url = server.start()

    try:
        client = RunClient(base_url, auth_token="scoped-token")
        health = client.healthz()
        inspect_missing = client.inspect("echo", "not-created")
        invoke = client.run("echo", {"value": "blocked"})
    finally:
        server.close()

    assert health.is_ok()
    assert inspect_missing.is_err()
    assert inspect_missing.unwrap_err()["errorType"] == "RUN_NOT_FOUND"
    assert invoke.is_err()
    assert invoke.unwrap_err()["errorType"] == "FORBIDDEN"


def test_principal_scope_families_and_configuration_fail_closed():
    principal = Principal("operator", ("workflow:*",))

    assert principal.allows("workflow:invoke")
    assert not principal.allows("approval:read")
    with pytest.raises(ValueError):
        Principal("operator", ("Workflow:read",))
    with pytest.raises(ValueError):
        Principal("operator", ())
    with pytest.raises(ValueError):
        RunServer(WorkflowRegistry(), auth_principal=principal)


def test_principal_target_allowlists_are_bounded_and_exact():
    principal = Principal(
        "operator",
        ("agent:read", "agent:invoke"),
        allowed_agent_ids=("alpha",),
        allowed_capabilities=("research",),
    )

    assert principal.allows_agent("alpha")
    assert not principal.allows_agent("beta")
    assert principal.allows_capability("research")
    assert not principal.allows_capability("billing")
    assert Principal("operator", ("agent:invoke",)).allows_agent("any-agent")
    with pytest.raises(ValueError):
        Principal("operator", ("agent:invoke",), allowed_agent_ids=["alpha"])
    with pytest.raises(ValueError):
        Principal(
            "operator",
            ("agent:invoke",),
            allowed_agent_ids=("alpha", "alpha"),
        )
    with pytest.raises(ValueError):
        Principal(
            "operator",
            ("agent:invoke",),
            allowed_capabilities=("research", "research"),
        )


def test_agent_target_policy_filters_discovery_and_blocks_denied_routes():
    calls = []

    def make_handler(agent_id):
        def handler(task, context, *, session_id, run_id):
            calls.append((agent_id, task, dict(context), session_id, run_id))
            return Result.ok(
                AgentRun(agent_id, run_id, "completed", {"agent": agent_id})
            )

        return handler

    agents = AgentRegistry()
    assert agents.register(
        "alpha", make_handler("alpha"), capabilities=["research"]
    ).is_ok()
    assert agents.register(
        "beta", make_handler("beta"), capabilities=["billing"]
    ).is_ok()
    server = RunServer(
        WorkflowRegistry(),
        agent_registry=agents,
        auth_token="policy-token",
        max_body_bytes=128,
        auth_principal=Principal(
            "operator",
            ("agent:read", "agent:invoke"),
            allowed_agent_ids=("alpha",),
            allowed_capabilities=("research",),
        ),
    )
    base_url = server.start()

    try:
        client = RunClient(base_url, auth_token="policy-token")
        listing = client.list_agents()
        allowed_named = client.run_agent("alpha", "research", run_id="allowed-run")
        denied_named_status, denied_named = _request(
            f"{base_url}/v1/agents/beta/runs",
            method="POST",
            payload={"task": "secret " + "x" * 500},
            headers={"Authorization": "Bearer policy-token"},
        )
        allowed_route = client.route_agent("research", "find")
        denied_route = client.route_agent("billing", "charge")
    finally:
        server.close()

    assert listing.is_ok()
    assert listing.unwrap() == {
        "agents": [{"agent_id": "alpha", "capabilities": ["research"]}]
    }
    assert allowed_named.is_ok()
    assert allowed_named.unwrap()["run"]["agent_id"] == "alpha"
    assert denied_named_status == 403
    assert denied_named["error"]["errorType"] == "FORBIDDEN"
    assert denied_named["error"]["details"]["policy"] == "allowed_agent_ids"
    assert "secret" not in str(denied_named)
    assert allowed_route.is_ok()
    assert allowed_route.unwrap()["run"]["agent_id"] == "alpha"
    assert denied_route.is_err()
    assert denied_route.unwrap_err()["errorType"] == "FORBIDDEN"
    assert denied_route.unwrap_err()["details"]["policy"] == "allowed_capabilities"
    assert len(calls) == 2
    assert calls[0] == ("alpha", "research", {}, None, "allowed-run")
    assert calls[1][0:4] == ("alpha", "find", {}, None)

    capability_server = RunServer(
        WorkflowRegistry(),
        agent_registry=agents,
        auth_token="policy-token",
        auth_principal=Principal(
            "capability-operator",
            ("agent:invoke",),
            allowed_capabilities=("research",),
        ),
    )
    capability_url = capability_server.start()
    try:
        capability_denied = RunClient(
            capability_url, auth_token="policy-token"
        ).run_agent("beta", "secret")
    finally:
        capability_server.close()

    assert capability_denied.is_err()
    assert capability_denied.unwrap_err()["errorType"] == "FORBIDDEN"
    assert capability_denied.unwrap_err()["details"]["policy"] == (
        "allowed_capabilities"
    )


def test_agent_registry_route_validates_allowed_agent_ids():
    calls = []

    def handler(task, context, *, session_id, run_id):
        calls.append(task)
        return Result.ok(AgentRun("alpha", run_id, "completed", {"task": task}))

    agents = AgentRegistry()
    assert agents.register("alpha", handler, capabilities=["research"]).is_ok()

    unrestricted = agents.route("research", "unrestricted")
    valid_list = agents.route(
        "research",
        "valid-list",
        allowed_agent_ids=["alpha"],
    )
    empty_allowlist = agents.route("research", "empty", allowed_agent_ids=())
    invalid_policies = (
        "alpha",
        b"alpha",
        ("",),
        ("alpha", "alpha"),
        tuple(f"agent-{index}" for index in range(65)),
        (["secret"],),
        object(),
    )
    invalid_results = [
        agents.route("research", "invalid", allowed_agent_ids=policy)
        for policy in invalid_policies
    ]

    assert unrestricted.is_ok()
    assert valid_list.is_ok()
    assert empty_allowlist.is_err()
    assert empty_allowlist.unwrap_err()["errorType"] == "AGENT_ROUTE_NOT_FOUND"
    assert all(result.is_err() for result in invalid_results)
    assert all(
        result.unwrap_err()["errorType"] == "AGENT_ALLOWLIST_INVALID"
        for result in invalid_results
    )
    assert all("secret" not in str(result.unwrap_err()) for result in invalid_results)
    assert calls == ["unrestricted", "valid-list"]


def test_run_server_resolves_distinct_principals_before_agent_routes():
    calls = []
    resolver_calls = []

    def make_handler(agent_id):
        def handler(task, context, *, session_id, run_id):
            calls.append((agent_id, task))
            return Result.ok(
                AgentRun(agent_id, run_id, "completed", {"agent": agent_id})
            )

        return handler

    agents = AgentRegistry()
    assert agents.register(
        "alpha", make_handler("alpha"), capabilities=["research"]
    ).is_ok()
    assert agents.register(
        "beta", make_handler("beta"), capabilities=["billing"]
    ).is_ok()

    def resolve(token):
        resolver_calls.append(token)
        if token == "alpha-token":
            return Result.ok(
                Principal(
                    "alpha-operator",
                    ("agent:read", "agent:invoke"),
                    allowed_agent_ids=("alpha",),
                    allowed_capabilities=("research",),
                )
            )
        if token == "beta-token":
            return Principal(
                "beta-operator",
                ("agent:read", "agent:invoke"),
                allowed_agent_ids=("beta",),
                allowed_capabilities=("billing",),
            )
        if token == "rejected-token":
            return Result.err(
                {"errorType": "TOKEN_REJECTED", "message": "private reason"}
            )
        if token == "broken-token":
            raise RuntimeError("private resolver details")
        return object()

    server = RunServer(
        WorkflowRegistry(),
        agent_registry=agents,
        auth_principal_resolver=resolve,
        max_body_bytes=128,
    )
    base_url = server.start()

    try:
        alpha_client = RunClient(base_url, auth_token="alpha-token")
        beta_client = RunClient(base_url, auth_token="beta-token")
        alpha_listing = alpha_client.list_agents()
        beta_listing = beta_client.list_agents()
        alpha_run = alpha_client.run_agent("alpha", "find", run_id="alpha-run")
        beta_route = beta_client.route_agent("billing", "charge")
        denied_status, denied = _request(
            f"{base_url}/v1/agents/alpha/runs",
            method="POST",
            payload={"task": "secret " + "x" * 500},
            headers={"Authorization": "Bearer beta-token"},
        )
        rejected = RunClient(base_url, auth_token="rejected-token").healthz()
        broken = RunClient(base_url, auth_token="broken-token").healthz()
        unknown = RunClient(base_url, auth_token="unknown-token").healthz()
        missing = RunClient(base_url).healthz()
    finally:
        server.close()

    assert alpha_listing.is_ok()
    assert alpha_listing.unwrap() == {
        "agents": [{"agent_id": "alpha", "capabilities": ["research"]}]
    }
    assert beta_listing.is_ok()
    assert beta_listing.unwrap() == {
        "agents": [{"agent_id": "beta", "capabilities": ["billing"]}]
    }
    assert alpha_run.is_ok()
    assert alpha_run.unwrap()["run"]["agent_id"] == "alpha"
    assert beta_route.is_ok()
    assert beta_route.unwrap()["run"]["agent_id"] == "beta"
    assert denied_status == 403
    assert denied["error"]["errorType"] == "FORBIDDEN"
    assert denied["error"]["details"]["principal_id"] == "beta-operator"
    assert denied["error"]["details"]["policy"] == "allowed_agent_ids"
    assert "secret" not in str(denied)
    assert rejected.is_err()
    assert rejected.unwrap_err()["errorType"] == "UNAUTHORIZED"
    assert "private reason" not in str(rejected.unwrap_err())
    assert broken.is_err()
    assert broken.unwrap_err()["errorType"] == "UNAUTHORIZED"
    assert "private resolver details" not in str(broken.unwrap_err())
    assert unknown.is_err()
    assert unknown.unwrap_err()["errorType"] == "UNAUTHORIZED"
    assert missing.is_err()
    assert missing.unwrap_err()["errorType"] == "UNAUTHORIZED"
    assert resolver_calls == [
        "alpha-token",
        "beta-token",
        "alpha-token",
        "beta-token",
        "beta-token",
        "rejected-token",
        "broken-token",
        "unknown-token",
    ]
    assert calls == [("alpha", "find"), ("beta", "charge")]


def test_run_server_rejects_ambiguous_principal_resolver_configuration():
    with pytest.raises(TypeError):
        RunServer(
            WorkflowRegistry(),
            auth_principal_resolver="not-callable",
        )
    with pytest.raises(ValueError):
        RunServer(
            WorkflowRegistry(),
            auth_token="static-token",
            auth_principal_resolver=lambda token: Principal("operator"),
        )
    with pytest.raises(ValueError):
        RunServer(
            WorkflowRegistry(),
            auth_principal=Principal("operator"),
            auth_principal_resolver=lambda token: Principal("resolved"),
        )


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


def test_authenticated_run_client_round_trips_approval_control_operations():
    registry = WorkflowRegistry()
    assert registry.register(_workflow()).is_ok()
    store = InMemoryApprovalStore()
    assert store.create(_approval_request()).is_ok()
    server = RunServer(
        registry,
        auth_token="approval-token",
        approval_store=store,
    )
    base_url = server.start()

    try:
        client = RunClient(base_url, auth_token="approval-token")
        pending = client.list_pending_approvals(limit=10)
        inspected = client.get_approval("remote-approval")
        decided = client.decide_approval(
            "remote-approval",
            True,
            edited_arguments={"value": "approved"},
        )
        consumed = store.consume("remote-approval")
        unauthorized = RunClient(base_url).list_pending_approvals()
    finally:
        server.close()

    assert pending.is_ok()
    assert pending.unwrap()["approvals"][0]["approval_id"] == "remote-approval"
    assert inspected.is_ok()
    assert inspected.unwrap()["approval"]["status"] == "pending"
    assert decided.is_ok()
    assert decided.unwrap()["approval"]["status"] == "approved"
    assert decided.unwrap()["approval"]["decision"]["edited_arguments"] == {
        "value": "approved"
    }
    assert consumed.is_ok()
    assert unauthorized.is_err()
    assert unauthorized.unwrap_err()["errorType"] == "UNAUTHORIZED"


def test_run_server_approval_control_fails_closed_without_store_and_bounds_inputs():
    registry = WorkflowRegistry()
    assert registry.register(_workflow()).is_ok()
    server = RunServer(registry)
    base_url = server.start()
    try:
        unavailable = RunClient(base_url).list_pending_approvals()
    finally:
        server.close()

    assert unavailable.is_err()
    assert unavailable.unwrap_err()["errorType"] == "APPROVAL_STORE_UNAVAILABLE"

    with pytest.raises(ValueError, match="approval_store"):
        RunServer(registry, approval_store=InMemoryApprovalStore())

    client = RunClient("http://127.0.0.1:1")
    assert client.list_pending_approvals(0).unwrap_err()["errorType"] == (
        "APPROVAL_LIMIT_INVALID"
    )
    assert client.decide_approval("approval", "yes").unwrap_err()["errorType"] == (
        "APPROVAL_DECISION_INVALID"
    )
    assert (
        client.decide_approval("approval", True, edited_arguments=[]).unwrap_err()[
            "errorType"
        ]
        == "APPROVAL_DECISION_INVALID"
    )


def test_run_server_rejects_invalid_remote_approval_decision_before_store_mutation():
    registry = WorkflowRegistry()
    assert registry.register(_workflow()).is_ok()
    store = InMemoryApprovalStore()
    assert store.create(_approval_request("invalid-approval")).is_ok()
    server = RunServer(
        registry,
        auth_token="approval-token",
        approval_store=store,
    )
    base_url = server.start()
    try:
        status, payload = _request(
            f"{base_url}/v1/approvals/invalid-approval/decide",
            method="POST",
            payload={"approved": "yes", "edited_arguments": {"value": "bad"}},
            headers={"Authorization": "Bearer approval-token"},
        )
    finally:
        server.close()

    assert status == 400
    assert payload["error"]["errorType"] == "APPROVAL_DECISION_INVALID"
    assert store.get("invalid-approval").unwrap().status == "pending"


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


def test_authenticated_agent_transport_round_trips_bounded_host_handler():
    calls = []

    def handler(task, context, *, session_id, run_id):
        calls.append((task, dict(context), session_id, run_id))
        return Result.ok(
            AgentRun(
                agent_id="researcher",
                run_id=run_id,
                status="completed",
                result={"answer": f"done: {task}", "context": dict(context)},
            )
        )

    agents = AgentRegistry()
    assert agents.register("researcher", handler).is_ok()
    with pytest.raises(ValueError):
        RunServer(WorkflowRegistry(), agent_registry=agents)

    server = RunServer(
        WorkflowRegistry(),
        agent_registry=agents,
        auth_token="agent-token",
    )
    base_url = server.start()
    try:
        client = RunClient(base_url, auth_token="agent-token")
        result = client.run_agent(
            "researcher",
            "find the release notes",
            {"tenant": "local", "limit": 3},
            session_id="session-1",
            run_id="agent-run-1",
        )
        unauthorized = RunClient(base_url).run_agent("researcher", "blocked")
    finally:
        server.close()

    assert result.is_ok()
    assert result.unwrap()["run"] == {
        "agent_id": "researcher",
        "run_id": "agent-run-1",
        "status": "completed",
        "result": {
            "answer": "done: find the release notes",
            "context": {"tenant": "local", "limit": 3},
        },
        "error": None,
    }
    assert calls == [
        (
            "find the release notes",
            {"tenant": "local", "limit": 3},
            "session-1",
            "agent-run-1",
        )
    ]
    assert unauthorized.is_err()
    assert unauthorized.unwrap_err()["errorType"] == "UNAUTHORIZED"


def test_agent_transport_bounds_inputs_and_normalizes_host_failures():
    def failing_handler(task, context, *, session_id, run_id):
        raise RuntimeError("private provider detail")

    agents = AgentRegistry()
    assert agents.register("failing", failing_handler).is_ok()
    server = RunServer(
        WorkflowRegistry(),
        agent_registry=agents,
        auth_token="agent-token",
    )
    base_url = server.start()
    try:
        client = RunClient(base_url, auth_token="agent-token")
        bad_context = client.run_agent("failing", "task", [])  # type: ignore[arg-type]
        bad_task = client.run_agent("failing", "")
        missing = client.run_agent("missing", "task")
        failed = client.run_agent("failing", "task")
    finally:
        server.close()

    assert bad_context.is_err()
    assert bad_context.unwrap_err()["errorType"] == "AGENT_CONTEXT_INVALID"
    assert bad_task.is_err()
    assert bad_task.unwrap_err()["errorType"] == "AGENT_TASK_INVALID"
    assert missing.is_err()
    assert missing.unwrap_err()["errorType"] == "AGENT_NOT_FOUND"
    assert failed.is_err()
    assert failed.unwrap_err()["errorType"] == "AGENT_HANDLER_ERROR"
    assert failed.unwrap_err()["message"] == "Registered agent handler failed."
    assert failed.unwrap_err()["details"]["agent_id"] == "failing"


def test_remote_handoff_target_delivers_allowlisted_payload_and_binds_run_id():
    calls = []

    def handler(task, context, *, session_id, run_id):
        calls.append((task, dict(context), session_id, run_id))
        return Result.ok(
            AgentRun(
                "remote-specialist",
                run_id,
                "completed",
                result={"answer": "remote result", "project": context["project"]},
            )
        )

    agents = AgentRegistry()
    assert agents.register("remote-specialist", handler).is_ok()
    server = RunServer(
        WorkflowRegistry(),
        agent_registry=agents,
        auth_token="remote-token",
    )
    base_url = server.start()
    try:
        from maple.autonomy.tools import create_handoff_tool

        handoffs = InMemoryHandoffStore()
        target = RemoteHandoffTarget(
            "remote-specialist",
            RunClient(base_url, auth_token="remote-token"),
            session_id="remote-session",
        )
        tool = create_handoff_tool(
            target,
            requires_approval=False,
            allowed_context_keys=["project"],
            handoff_store=handoffs,
            source_agent_id="source-agent",
            persist_result=True,
        )
        result = tool.execute(
            task="Summarize the remote release",
            context={"project": "MAPLE"},
            handoff_id="remote-handoff-1",
        )
    finally:
        server.close()

    assert result.is_ok()
    assert result.unwrap() == {
        "agent_id": "remote-specialist",
        "goal_id": "remote-handoff-1",
        "status": "completed",
        "result": {"answer": "remote result", "project": "MAPLE"},
        "handoff_id": "remote-handoff-1",
    }
    assert calls == [
        (
            "Summarize the remote release",
            {"project": "MAPLE"},
            "remote-session",
            "remote-handoff-1",
        )
    ]
    record = handoffs.get("remote-handoff-1").unwrap()
    assert record is not None
    assert record.status == "completed"
    assert record.target_goal_id == "remote-handoff-1"
    assert "Summarize the remote release" not in str(record.to_dict())


def test_remote_handoff_target_rejects_unauthorized_and_incomplete_runs_without_leaks():
    class IncompleteClient(RunClient):
        def run_agent(self, *args, **kwargs):
            return Result.ok(
                {
                    "run": {
                        "agent_id": "remote-specialist",
                        "run_id": "remote-run",
                        "status": "paused",
                        "result": {"private": "not exposed"},
                        "error": None,
                    }
                }
            )

    target = RemoteHandoffTarget(
        "remote-specialist", IncompleteClient("http://127.0.0.1:1")
    )
    incomplete = target.pursue_goal("task", handoff_id="remote-run")

    assert incomplete.is_err()
    assert incomplete.unwrap_err()["errorType"] == "REMOTE_HANDOFF_INCOMPLETE"
    assert "private" not in str(incomplete.unwrap_err())

    class MalformedClient(RunClient):
        def run_agent(self, *args, **kwargs):
            return Result.ok({"run": {"agent_id": "remote-specialist"}})

    malformed = RemoteHandoffTarget(
        "remote-specialist", MalformedClient("http://127.0.0.1:1")
    ).pursue_goal("task")
    assert malformed.is_err()
    assert malformed.unwrap_err()["errorType"] == "REMOTE_HANDOFF_RESULT_INVALID"

    class FailedClient(RunClient):
        def run_agent(self, *args, **kwargs):
            return Result.ok(
                {
                    "run": {
                        "agent_id": "remote-specialist",
                        "run_id": "remote-run",
                        "status": "completed",
                        "result": None,
                        "error": {
                            "errorType": "PRIVATE_REMOTE_FAILURE",
                            "message": "private provider detail",
                        },
                    }
                }
            )

    failed = RemoteHandoffTarget(
        "remote-specialist", FailedClient("http://127.0.0.1:1")
    ).pursue_goal("task")
    assert failed.is_err()
    assert failed.unwrap_err()["errorType"] == "REMOTE_HANDOFF_FAILED"
    assert "private provider detail" not in str(failed.unwrap_err())

    invalid_handoff_id = RemoteHandoffTarget(
        "remote-specialist", IncompleteClient("http://127.0.0.1:1")
    ).pursue_goal("task", handoff_id="bad\x7f-id")
    assert invalid_handoff_id.is_err()
    assert invalid_handoff_id.unwrap_err()["errorType"] == (
        "REMOTE_HANDOFF_INPUT_INVALID"
    )

    with pytest.raises(ValueError):
        RemoteHandoffTarget("", IncompleteClient("http://127.0.0.1:1"))
    with pytest.raises(ValueError):
        RemoteHandoffTarget(
            "remote\n-specialist", IncompleteClient("http://127.0.0.1:1")
        )
    with pytest.raises(TypeError):
        RemoteHandoffTarget("remote-specialist", object())
    with pytest.raises(ValueError):
        RemoteHandoffTarget(
            "remote-specialist",
            IncompleteClient("http://127.0.0.1:1"),
            session_id="bad\n-session",
        )

    server = RunServer(
        WorkflowRegistry(),
        agent_registry=AgentRegistry(),
        auth_token="required-token",
    )
    base_url = server.start()
    try:
        unauthorized_target = RemoteHandoffTarget(
            "remote-specialist", RunClient(base_url)
        )
        handoffs = InMemoryHandoffStore()
        from maple.autonomy.tools import create_handoff_tool

        unauthorized_tool = create_handoff_tool(
            unauthorized_target,
            requires_approval=False,
            handoff_store=handoffs,
            source_agent_id="source-agent",
        )
        unauthorized = unauthorized_tool.execute(
            task="task", handoff_id="unauthorized-run"
        )
    finally:
        server.close()

    assert unauthorized.is_err()
    assert unauthorized.unwrap_err()["errorType"] == "HANDOFF_TARGET_FAILED"
    assert unauthorized.unwrap_err()["details"]["target_error_type"] == (
        "REMOTE_HANDOFF_FAILED"
    )
    assert "UNAUTHORIZED" not in str(unauthorized.unwrap_err())
    assert "private" not in str(unauthorized.unwrap_err())
    failed_record = handoffs.get("unauthorized-run").unwrap()
    assert failed_record is not None
    assert failed_record.status == "failed"
    assert failed_record.error_type == "HANDOFF_TARGET_FAILED"


def test_remote_handoff_target_rejects_cancelled_request_without_calling_client():
    class CountingClient(RunClient):
        def __init__(self):
            super().__init__("http://127.0.0.1:1")
            self.calls = 0

        def run_agent(self, *args, **kwargs):
            self.calls += 1
            return Result.err({"errorType": "SHOULD_NOT_RUN", "message": "bad"})

    class Cancelled:
        def is_cancelled(self):
            return True

    client = CountingClient()
    result = RemoteHandoffTarget("remote-specialist", client).pursue_goal(
        "task", cancellation=Cancelled()
    )

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "EXECUTION_CANCELLED"
    assert client.calls == 0


@pytest.mark.asyncio
async def test_remote_handoff_target_supports_async_context_delivery():
    calls = []

    def handler(task, context, *, session_id, run_id):
        calls.append((task, dict(context), session_id, run_id))
        return Result.ok(
            AgentRun("remote-async", run_id, "completed", result={"ok": True})
        )

    agents = AgentRegistry()
    assert agents.register("remote-async", handler).is_ok()
    server = RunServer(
        WorkflowRegistry(), agent_registry=agents, auth_token="async-token"
    )
    base_url = server.start()
    try:
        from maple.autonomy.tools import create_handoff_tool

        handoffs = InMemoryHandoffStore()
        target = RemoteHandoffTarget(
            "remote-async", RunClient(base_url, auth_token="async-token")
        )
        tool = create_handoff_tool(
            target,
            requires_approval=False,
            allowed_context_keys=["request"],
            handoff_store=handoffs,
            source_agent_id="source-agent",
        )
        result = await tool.execute_async(
            task="Run asynchronously",
            context={"request": "async"},
            handoff_id="remote-async-handoff",
        )
    finally:
        server.close()

    assert result.is_ok()
    assert result.unwrap()["goal_id"] == "remote-async-handoff"
    assert calls == [
        ("Run asynchronously", {"request": "async"}, None, "remote-async-handoff")
    ]


def test_agent_registry_rejects_result_identity_and_non_json_values():
    def wrong_identity(task, context, *, session_id, run_id):
        return Result.ok(AgentRun("other", run_id, "completed", result={}))

    def non_json(task, context, *, session_id, run_id):
        return Result.ok(AgentRun("json", run_id, "completed", result=object()))

    def malformed_error(task, context, *, session_id, run_id):
        return Result.err({"message": "missing error type"})

    agents = AgentRegistry()
    assert agents.register("wrong", wrong_identity).is_ok()
    assert agents.register("json", non_json).is_ok()
    assert agents.register("error", malformed_error).is_ok()

    identity = agents.run("wrong", "task", {})
    invalid = agents.run("json", "task", {})
    malformed = agents.run("error", "task", {})

    assert identity.is_err()
    assert identity.unwrap_err()["errorType"] == "AGENT_RESULT_INVALID"
    assert invalid.is_err()
    assert invalid.unwrap_err()["errorType"] == "AGENT_RESULT_INVALID"
    assert malformed.is_err()
    assert malformed.unwrap_err()["errorType"] == "AGENT_RESULT_INVALID"


def test_agent_registry_cancellation_requires_cancelled_result_and_redacts_failures():
    def handler(task, context, *, session_id, run_id):
        return Result.ok(AgentRun("cancelable", run_id, "paused", result={}))

    def wrong_status(run_id):
        return Result.ok(AgentRun("wrong-status", run_id, "completed", result={}))

    def raising(run_id):
        raise RuntimeError("private cancellation detail")

    agents = AgentRegistry()
    assert agents.register("wrong-status", handler, cancel_handler=wrong_status).is_ok()
    assert agents.register("raising", handler, cancel_handler=raising).is_ok()

    wrong = agents.cancel("wrong-status", "run-1")
    failed = agents.cancel("raising", "run-1")

    assert wrong.is_err()
    assert wrong.unwrap_err()["errorType"] == "AGENT_CANCEL_RESULT_INVALID"
    assert failed.is_err()
    assert failed.unwrap_err()["errorType"] == "AGENT_CANCEL_HANDLER_ERROR"
    assert "private cancellation detail" not in str(failed.unwrap_err())


def test_agent_registry_lists_bounded_descriptors_and_routes_exact_match():
    calls = []

    def handler(task, context, *, session_id, run_id):
        calls.append((task, dict(context), session_id, run_id))
        return Result.ok(
            AgentRun(
                "alpha",
                run_id,
                "completed",
                result={"agent": "alpha", "task": task},
            )
        )

    def zeta_handler(task, context, *, session_id, run_id):
        return Result.ok(
            AgentRun("zeta", run_id, "completed", result={"agent": "zeta"})
        )

    agents = AgentRegistry()
    assert agents.register(
        "zeta", zeta_handler, capabilities=["shared", "research"]
    ).is_ok()
    assert agents.register("alpha", handler, capabilities=["shared"]).is_ok()

    listed = agents.list_agents()
    assert listed.is_ok()
    assert listed.unwrap() == [
        AgentDescriptor("alpha", ("shared",)),
        AgentDescriptor("zeta", ("research", "shared")),
    ]
    listed.unwrap()[0].to_dict()["capabilities"].append("mutated")
    assert agents.list_agents().unwrap()[0] == AgentDescriptor("alpha", ("shared",))

    routed = agents.route(
        "shared",
        "find",
        {"project": "MAPLE"},
        session_id="session",
        run_id="route-run",
    )
    assert routed.is_ok()
    assert routed.unwrap().agent_id == "alpha"
    assert calls == [("find", {"project": "MAPLE"}, "session", "route-run")]
    research = agents.route("research", "find", run_id="research-run")
    assert research.is_ok()
    assert research.unwrap().agent_id == "zeta"
    missing = agents.route("missing", "find")
    assert missing.is_err()
    assert missing.unwrap_err()["errorType"] == "AGENT_ROUTE_NOT_FOUND"

    assert agents.register("invalid", handler, capabilities=[" bad"]).is_err()
    assert agents.register("duplicate", handler, capabilities=["one", "one"]).is_err()


def test_authenticated_agent_capability_listing_and_routing_round_trip():
    calls = []

    def make_handler(agent_id):
        def handler(task, context, *, session_id, run_id):
            calls.append((agent_id, task, dict(context), session_id, run_id))
            return Result.ok(
                AgentRun(agent_id, run_id, "completed", {"agent": agent_id})
            )

        return handler

    agents = AgentRegistry()
    assert agents.register(
        "zeta", make_handler("zeta"), capabilities=["research"]
    ).is_ok()
    assert agents.register(
        "alpha", make_handler("alpha"), capabilities=["research"]
    ).is_ok()
    server = RunServer(
        WorkflowRegistry(), agent_registry=agents, auth_token="route-token"
    )
    base_url = server.start()
    try:
        client = RunClient(base_url, auth_token="route-token")
        raw_listing = client.list_agents()
        typed_listing = client.list_agents_typed()
        routed = client.route_agent_typed(
            "research",
            "summarize",
            {"project": "MAPLE"},
            session_id="route-session",
            run_id="route-run",
        )
        missing = client.route_agent("unknown", "summarize")
        unauthorized_listing = RunClient(base_url).list_agents()
        unauthorized_route = RunClient(base_url).route_agent("research", "summarize")
    finally:
        server.close()

    assert raw_listing.is_ok()
    assert raw_listing.unwrap()["agents"] == [
        {"agent_id": "alpha", "capabilities": ["research"]},
        {"agent_id": "zeta", "capabilities": ["research"]},
    ]
    assert typed_listing.is_ok()
    assert typed_listing.unwrap() == [
        AgentDescriptor("alpha", ("research",)),
        AgentDescriptor("zeta", ("research",)),
    ]
    assert routed.is_ok()
    assert routed.unwrap() == AgentRun(
        "alpha", "route-run", "completed", {"agent": "alpha"}
    )
    assert calls == [
        ("alpha", "summarize", {"project": "MAPLE"}, "route-session", "route-run")
    ]
    assert missing.is_err()
    assert missing.unwrap_err()["errorType"] == "AGENT_ROUTE_NOT_FOUND"
    assert unauthorized_listing.is_err()
    assert unauthorized_listing.unwrap_err()["errorType"] == "UNAUTHORIZED"
    assert unauthorized_route.is_err()
    assert unauthorized_route.unwrap_err()["errorType"] == "UNAUTHORIZED"

    unavailable_server = RunServer(WorkflowRegistry(), auth_token="route-token")
    unavailable_url = unavailable_server.start()
    try:
        unavailable = RunClient(unavailable_url, auth_token="route-token").list_agents()
    finally:
        unavailable_server.close()
    assert unavailable.is_err()
    assert unavailable.unwrap_err()["errorType"] == "AGENT_REGISTRY_UNAVAILABLE"

    scoped_server = RunServer(
        WorkflowRegistry(),
        agent_registry=agents,
        auth_token="route-token",
        auth_principal=Principal("invoker", ("agent:invoke",)),
    )
    scoped_url = scoped_server.start()
    try:
        scoped_client = RunClient(scoped_url, auth_token="route-token")
        scoped_listing = scoped_client.list_agents()
        scoped_route = scoped_client.route_agent("research", "scoped")
    finally:
        scoped_server.close()
    assert scoped_listing.is_err()
    assert scoped_listing.unwrap_err()["errorType"] == "FORBIDDEN"
    assert scoped_route.is_ok()


def test_typed_agent_route_rejects_malformed_selected_identity():
    class MalformedClient(RunClient):
        def route_agent(self, *args, **kwargs):
            return Result.ok(
                {
                    "run": {
                        "agent_id": "",
                        "run_id": "route-run",
                        "status": "completed",
                        "result": {"private": "not trusted"},
                        "error": None,
                    }
                }
            )

    result = MalformedClient("http://127.0.0.1:1").route_agent_typed(
        "research", "task", run_id="route-run"
    )
    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "AGENT_RESPONSE_INVALID"
    assert "not trusted" not in str(result.unwrap_err())


def test_typed_remote_agent_methods_return_validated_agent_runs():
    class TypedClient(RunClient):
        def __init__(self):
            super().__init__("http://127.0.0.1:1")

        def run_agent(self, *args, **kwargs):
            return Result.ok(
                {
                    "run": {
                        "agent_id": "researcher",
                        "run_id": "typed-run",
                        "status": "paused",
                        "result": {"state": "waiting"},
                        "error": None,
                    }
                }
            )

        def resume_agent_run(self, *args, **kwargs):
            return Result.ok(
                {
                    "run": {
                        "agent_id": "researcher",
                        "run_id": "typed-run",
                        "status": "completed",
                        "result": {"answer": "ready"},
                        "error": None,
                    }
                }
            )

        def cancel_agent_run(self, *args, **kwargs):
            return Result.ok(
                {
                    "run": {
                        "agent_id": "researcher",
                        "run_id": "typed-run",
                        "status": "cancelled",
                        "result": None,
                        "error": {
                            "errorType": "AGENT_RUN_CANCELLED",
                            "message": "Cancellation was requested.",
                        },
                    }
                }
            )

    client = TypedClient()
    started = client.run_agent_typed("researcher", "wait", run_id="typed-run")
    resumed = client.resume_agent_run_typed("researcher", "typed-run")
    cancelled = client.cancel_agent_run_typed("researcher", "typed-run")

    assert started.is_ok()
    assert isinstance(started.unwrap(), AgentRun)
    assert started.unwrap().status == "paused"
    assert resumed.is_ok()
    assert resumed.unwrap().result == {"answer": "ready"}
    assert cancelled.is_ok()
    assert cancelled.unwrap().status == "cancelled"
    assert cancelled.unwrap().error == {
        "errorType": "AGENT_RUN_CANCELLED",
        "message": "Cancellation was requested.",
    }


def test_typed_remote_agent_methods_fail_closed_on_invalid_envelopes():
    class InvalidClient(RunClient):
        def __init__(self, payload):
            super().__init__("http://127.0.0.1:1")
            self.payload = payload

        def run_agent(self, *args, **kwargs):
            return Result.ok(self.payload)

    malformed = InvalidClient({"run": {"agent_id": "researcher"}})
    malformed_result = malformed.run_agent_typed("researcher", "task")
    assert malformed_result.is_err()
    assert malformed_result.unwrap_err()["errorType"] == "AGENT_RESPONSE_INVALID"

    mismatched = InvalidClient(
        {
            "run": {
                "agent_id": "other",
                "run_id": "typed-run",
                "status": "completed",
                "result": {"private": "not exposed"},
                "error": None,
            }
        }
    )
    mismatched_result = mismatched.run_agent_typed(
        "researcher", "task", run_id="typed-run"
    )
    assert mismatched_result.is_err()
    assert mismatched_result.unwrap_err()["errorType"] == "AGENT_RESPONSE_INVALID"
    assert "private" not in str(mismatched_result.unwrap_err())

    class WrongCancelClient(RunClient):
        def __init__(self):
            super().__init__("http://127.0.0.1:1")

        def cancel_agent_run(self, *args, **kwargs):
            return Result.ok(
                {
                    "run": {
                        "agent_id": "researcher",
                        "run_id": "typed-run",
                        "status": "completed",
                        "result": {"private": "not exposed"},
                        "error": None,
                    }
                }
            )

    wrong_cancel = WrongCancelClient().cancel_agent_run_typed("researcher", "typed-run")
    assert wrong_cancel.is_err()
    assert wrong_cancel.unwrap_err()["errorType"] == "AGENT_RESPONSE_INVALID"
    assert "private" not in str(wrong_cancel.unwrap_err())


def test_authenticated_durable_agent_run_inspection_and_resume():
    run_store = InMemoryAgentRunStore()
    assert run_store.save(
        AgentRunCheckpoint(
            run_id="durable-agent-run",
            agent_id="researcher",
            description="Resume the release review.",
            status="paused",
            step_count=2,
            pending_approval_id="approval-1",
            result={"status": "waiting"},
        )
    ).is_ok()
    resume_calls = []
    cancel_calls = []

    def handler(task, context, *, session_id, run_id):
        return Result.ok(
            AgentRun("researcher", run_id, "paused", result={"status": "waiting"})
        )

    def resume_handler(run_id):
        resume_calls.append(run_id)
        return Result.ok(
            AgentRun("researcher", run_id, "completed", result={"answer": "ready"})
        )

    def cancel_handler(run_id):
        cancel_calls.append(run_id)
        return Result.ok(
            AgentRun(
                "researcher",
                run_id,
                "cancelled",
                error={
                    "errorType": "AGENT_RUN_CANCELLED",
                    "message": "Cancellation was requested.",
                },
            )
        )

    agents = AgentRegistry()
    assert agents.register(
        "researcher",
        handler,
        resume_handler=resume_handler,
        cancel_handler=cancel_handler,
    ).is_ok()
    server = RunServer(
        WorkflowRegistry(),
        agent_registry=agents,
        agent_run_store=run_store,
        auth_token="agent-token",
    )
    base_url = server.start()
    try:
        client = RunClient(base_url, auth_token="agent-token")
        inspected = client.inspect_agent_run("researcher", "durable-agent-run")
        wrong_agent = client.inspect_agent_run("other", "durable-agent-run")
        resumed = client.resume_agent_run("researcher", "durable-agent-run")
        cancelled = client.cancel_agent_run("researcher", "durable-agent-run")
        unauthorized = RunClient(base_url).inspect_agent_run(
            "researcher", "durable-agent-run"
        )
    finally:
        server.close()

    assert inspected.is_ok()
    inspected_run = inspected.unwrap()["run"]
    assert inspected_run["status"] == "paused"
    assert inspected_run["step_count"] == 2
    assert inspected_run["result"] == {"status": "waiting"}
    assert "messages" not in inspected_run
    assert "reasoning_steps" not in inspected_run
    assert wrong_agent.is_err()
    assert wrong_agent.unwrap_err()["errorType"] == "AGENT_RUN_NOT_FOUND"
    assert resumed.is_ok()
    assert resumed.unwrap()["run"]["status"] == "completed"
    assert resume_calls == ["durable-agent-run"]
    assert cancelled.is_ok()
    assert cancelled.unwrap()["run"]["status"] == "cancelled"
    assert cancelled.unwrap()["run"]["error"]["errorType"] == "AGENT_RUN_CANCELLED"
    assert cancel_calls == ["durable-agent-run"]
    assert unauthorized.is_err()
    assert unauthorized.unwrap_err()["errorType"] == "UNAUTHORIZED"


def test_authenticated_agent_run_history_is_bounded_redacted_and_authorized():
    run_store = InMemoryAgentRunStore(max_history=3)
    checkpoint = None
    for index in range(4):
        candidate = AgentRunCheckpoint(
            run_id="history-run",
            agent_id="researcher",
            description=f"Private task {index}",
            status="paused" if index < 3 else "completed",
            step_count=index + 1,
            output_retries_used=index,
            pending_approval_id=f"approval-{index}" if index < 3 else None,
            result={"secret": f"private-result-{index}"},
            error=(
                {
                    "errorType": "PRIVATE_ERROR",
                    "message": "private failure detail",
                }
                if index == 2
                else None
            ),
            token_usage={"prompt_tokens": index + 1},
        )
        saved = run_store.save(
            candidate,
            expected_version=checkpoint.version if checkpoint is not None else None,
        )
        assert saved.is_ok()
        checkpoint = saved.unwrap()

    server = RunServer(
        WorkflowRegistry(),
        agent_run_store=run_store,
        auth_token="agent-token",
        auth_principal=Principal("reader", ("agent:read",)),
    )
    base_url = server.start()
    history_url = f"{base_url}/v1/agents/researcher/runs/history-run/history"
    try:
        client = RunClient(base_url, auth_token="agent-token")
        history = client.inspect_agent_run_history("researcher", "history-run", limit=2)
        wrong_agent = client.inspect_agent_run_history("other", "history-run")
        unauthorized = RunClient(base_url).inspect_agent_run_history(
            "researcher", "history-run"
        )
        invalid_limit_status, invalid_limit = _request(
            f"{history_url}?limit=101",
            headers={"Authorization": "Bearer agent-token"},
        )
        unknown_query_status, unknown_query = _request(
            f"{history_url}?unexpected=1",
            headers={"Authorization": "Bearer agent-token"},
        )
        duplicate_query_status, duplicate_query = _request(
            f"{history_url}?limit=1&limit=2",
            headers={"Authorization": "Bearer agent-token"},
        )
    finally:
        server.close()

    assert history.is_ok()
    snapshots = history.unwrap()["history"]
    assert [snapshot["version"] for snapshot in snapshots] == [3, 4]
    assert snapshots[-1]["status"] == "completed"
    assert snapshots[-1]["token_usage"]["prompt_tokens"] == 4
    for snapshot in snapshots:
        assert "description" not in snapshot
        assert "result" not in snapshot
        assert "error" not in snapshot
        assert "messages" not in snapshot
        assert "reasoning_steps" not in snapshot
    assert wrong_agent.is_err()
    assert wrong_agent.unwrap_err()["errorType"] == "AGENT_RUN_NOT_FOUND"
    assert unauthorized.is_err()
    assert unauthorized.unwrap_err()["errorType"] == "UNAUTHORIZED"
    for status, payload in (
        (invalid_limit_status, invalid_limit),
        (unknown_query_status, unknown_query),
        (duplicate_query_status, duplicate_query),
    ):
        assert status == 400
        assert payload["error"]["errorType"] == "AGENT_RUN_HISTORY_LIMIT_INVALID"


def test_agent_run_history_preserves_legacy_store_compatibility_and_fails_closed():
    checkpoint = AgentRunCheckpoint(
        run_id="legacy-run",
        agent_id="researcher",
        description="Legacy store run",
        status="paused",
    )

    class LegacyStore:
        def load(self, run_id):
            return Result.ok(checkpoint if run_id == checkpoint.run_id else None)

    server = RunServer(
        WorkflowRegistry(), agent_run_store=LegacyStore(), auth_token="agent-token"
    )
    base_url = server.start()
    try:
        history = RunClient(
            base_url, auth_token="agent-token"
        ).inspect_agent_run_history("researcher", "legacy-run")
    finally:
        server.close()

    assert history.is_err()
    assert history.unwrap_err()["errorType"] == "AGENT_RUN_HISTORY_UNAVAILABLE"


def test_agent_run_history_rejects_cross_agent_store_records():
    checkpoint = AgentRunCheckpoint(
        run_id="history-run",
        agent_id="researcher",
        description="Valid current checkpoint",
        status="completed",
    )

    class InvalidHistoryStore:
        def load(self, run_id):
            return Result.ok(checkpoint if run_id == checkpoint.run_id else None)

        def history(self, run_id):
            return Result.ok(
                [
                    AgentRunCheckpoint(
                        run_id=run_id,
                        agent_id="other",
                        description="Cross-agent record",
                        status="completed",
                    )
                ]
            )

    server = RunServer(
        WorkflowRegistry(),
        agent_run_store=InvalidHistoryStore(),
        auth_token="agent-token",
    )
    base_url = server.start()
    try:
        history = RunClient(
            base_url, auth_token="agent-token"
        ).inspect_agent_run_history("researcher", "history-run")
    finally:
        server.close()

    assert history.is_err()
    assert history.unwrap_err()["errorType"] == "AGENT_RUN_HISTORY_INVALID"


def test_durable_agent_transport_fails_closed_without_store_or_resume_handler():
    def handler(task, context, *, session_id, run_id):
        return Result.ok(AgentRun("researcher", run_id, "completed", result={}))

    agents = AgentRegistry()
    assert agents.register("researcher", handler).is_ok()
    server = RunServer(
        WorkflowRegistry(), agent_registry=agents, auth_token="agent-token"
    )
    base_url = server.start()
    try:
        client = RunClient(base_url, auth_token="agent-token")
        unavailable = client.inspect_agent_run("researcher", "run-1")
        unsupported = client.resume_agent_run("researcher", "run-1")
        unsupported_cancel = client.cancel_agent_run("researcher", "run-1")
    finally:
        server.close()

    assert unavailable.is_err()
    assert unavailable.unwrap_err()["errorType"] == "AGENT_RUN_STORE_UNAVAILABLE"
    assert unsupported.is_err()
    assert unsupported.unwrap_err()["errorType"] == "AGENT_RESUME_UNAVAILABLE"
    assert unsupported_cancel.is_err()
    assert unsupported_cancel.unwrap_err()["errorType"] == "AGENT_CANCEL_UNAVAILABLE"


def test_authenticated_event_transport_ingests_redacted_events_and_preserves_local_order():
    stream = EventStream(max_events=4)
    with pytest.raises(ValueError):
        RunServer(WorkflowRegistry(), event_stream=stream)

    server = RunServer(
        WorkflowRegistry(),
        event_stream=stream,
        auth_token="event-token",
    )
    base_url = server.start()
    try:
        client = RunClient(base_url, auth_token="event-token")
        first = client.publish_event(
            "remote.model.completed",
            {"status": "ok", "secret": "not-retained"},
            run_id="remote-run",
        )
        second = client.publish_event("remote.tool.completed", {"status": "ok"})
        unauthorized = RunClient(base_url).publish_event("blocked", {})
    finally:
        server.close()

    assert first.is_ok()
    assert first.unwrap()["event"]["sequence"] == 1
    assert first.unwrap()["event"]["payload"]["secret"] == "[REDACTED]"
    assert second.is_ok()
    retained = stream.snapshot().unwrap()
    assert [event.sequence for event in retained] == [1, 2]
    assert [event.event_type for event in retained] == [
        "remote.model.completed",
        "remote.tool.completed",
    ]
    assert unauthorized.is_err()
    assert unauthorized.unwrap_err()["errorType"] == "UNAUTHORIZED"


def test_authenticated_event_batch_transport_preserves_order_and_redaction():
    stream = EventStream(max_events=4)
    server = RunServer(
        WorkflowRegistry(),
        event_stream=stream,
        auth_token="event-token",
    )
    base_url = server.start()
    try:
        client = RunClient(base_url, auth_token="event-token")
        batch = client.publish_events(
            [
                {
                    "event_type": "remote.batch.first",
                    "payload": {"status": "ok", "secret": "not-retained"},
                    "run_id": "batch-run",
                },
                {
                    "event_type": "remote.batch.second",
                    "payload": {"status": "ok"},
                },
            ]
        )
        unauthorized = RunClient(base_url).publish_events(
            [{"event_type": "blocked", "payload": {}}]
        )
    finally:
        server.close()

    assert batch.is_ok()
    response = batch.unwrap()
    assert [item["index"] for item in response["published"]] == [0, 1]
    assert response["failed"] == []
    assert response["published"][0]["event"]["sequence"] == 1
    assert response["published"][1]["event"]["sequence"] == 2
    assert response["published"][0]["event"]["payload"]["secret"] == "[REDACTED]"
    retained = stream.snapshot().unwrap()
    assert [event.sequence for event in retained] == [1, 2]
    assert [event.event_type for event in retained] == [
        "remote.batch.first",
        "remote.batch.second",
    ]
    assert unauthorized.is_err()
    assert unauthorized.unwrap_err()["errorType"] == "UNAUTHORIZED"


def test_event_batch_transport_returns_partial_item_failures_without_retry():
    stream = EventStream(max_events=4)
    server = RunServer(
        WorkflowRegistry(),
        event_stream=stream,
        auth_token="event-token",
    )
    base_url = server.start()
    try:
        status, response = _request(
            f"{base_url}/v1/events/batch",
            method="POST",
            payload={
                "events": [
                    {"event_type": "remote.before", "payload": {}},
                    {"payload": {}},
                    {"event_type": "remote.after", "payload": {}},
                ]
            },
            headers={"Authorization": "Bearer event-token"},
        )
    finally:
        server.close()

    assert status == 200
    assert [item["index"] for item in response["published"]] == [0, 2]
    assert [item["index"] for item in response["failed"]] == [1]
    assert response["failed"][0]["error"]["errorType"] == "EVENT_INPUT_INVALID"
    retained = stream.snapshot().unwrap()
    assert [event.sequence for event in retained] == [1, 2]
    assert [event.event_type for event in retained] == [
        "remote.before",
        "remote.after",
    ]


def test_event_batch_transport_deduplicates_explicit_source_sequences():
    stream = EventStream(max_events=10)
    server = RunServer(
        WorkflowRegistry(),
        event_stream=stream,
        event_deduplication_store=InMemoryEventDeduplicationStore(),
        auth_token="event-token",
    )
    base_url = server.start()

    try:
        client = RunClient(base_url, auth_token="event-token")
        first = client.publish_events(
            [{"sequence": 1, "event_type": "remote.one", "payload": {"value": 1}}],
            source_id="source-a",
        )
        duplicate = client.publish_events(
            [{"sequence": 1, "event_type": "remote.one", "payload": {"value": 1}}],
            source_id="source-a",
        )
        conflict = client.publish_events(
            [{"sequence": 1, "event_type": "remote.one", "payload": {"value": 2}}],
            source_id="source-a",
        )
        remote = client.read_events(EventCursor(), limit=10)
    finally:
        server.close()

    assert first.is_ok()
    assert duplicate.is_ok()
    assert duplicate.unwrap()["published"][0]["event"]["sequence"] == 1
    assert conflict.is_ok()
    assert conflict.unwrap()["failed"][0]["error"]["errorType"] == (
        "EVENT_DEDUPLICATION_CONFLICT"
    )
    assert remote.is_ok()
    assert len(remote.unwrap()["batch"]["events"]) == 1


def test_event_batch_transport_enforces_structural_bounds_before_attempts():
    stream = EventStream(max_events=128)
    server = RunServer(
        WorkflowRegistry(),
        event_stream=stream,
        auth_token="event-token",
    )
    base_url = server.start()
    try:
        valid_status, valid_response = _request(
            f"{base_url}/v1/events/batch",
            method="POST",
            payload={
                "events": [
                    {"event_type": f"remote.{index}", "payload": {}}
                    for index in range(100)
                ]
            },
            headers={"Authorization": "Bearer event-token"},
        )
        oversized_status, oversized_response = _request(
            f"{base_url}/v1/events/batch",
            method="POST",
            payload={
                "events": [
                    {"event_type": "remote.oversized", "payload": {}}
                    for _ in range(101)
                ]
            },
            headers={"Authorization": "Bearer event-token"},
        )
    finally:
        server.close()

    assert valid_status == 200
    assert len(valid_response["published"]) == 100
    assert oversized_status == 400
    assert oversized_response["error"]["errorType"] == "EVENT_BATCH_INVALID"
    retained = stream.snapshot().unwrap()
    assert len(retained) == 100
    assert retained[-1].sequence == 100


def test_run_client_publish_events_validates_batch_shape_and_items():
    client = RunClient("http://127.0.0.1:1")

    empty = client.publish_events([])
    oversized = client.publish_events(
        [{"event_type": "remote.event", "payload": {}} for _ in range(101)]
    )
    invalid_item = client.publish_events(["not-an-event"])
    missing_payload = client.publish_events([{"event_type": "remote.event"}])
    invalid_run = client.publish_events(
        [{"event_type": "remote.event", "payload": {}, "run_id": "bad\nrun"}]
    )

    assert empty.is_err()
    assert empty.unwrap_err()["errorType"] == "EVENT_BATCH_INVALID"
    assert oversized.is_err()
    assert oversized.unwrap_err()["errorType"] == "EVENT_BATCH_INVALID"
    assert invalid_item.is_err()
    assert invalid_item.unwrap_err()["errorType"] == "EVENT_BATCH_INVALID"
    assert missing_payload.is_err()
    assert missing_payload.unwrap_err()["errorType"] == "EVENT_BATCH_INVALID"
    assert invalid_run.is_err()
    assert invalid_run.unwrap_err()["errorType"] == "EVENT_INPUT_INVALID"


def test_event_transport_round_trips_the_existing_http_exporter_and_fails_closed():
    destination = EventStream()
    server = RunServer(
        WorkflowRegistry(),
        event_stream=destination,
        auth_token="event-token",
    )
    base_url = server.start()
    try:
        exporter = HttpEventExporter(
            f"{base_url}/v1/events",
            auth_token="event-token",
        )
        source = EventStream(exporter=exporter)
        published = source.publish(
            "remote.model.chunk",
            {"content": "metadata-only", "token": "private"},
            run_id="exported-run",
        )
        unavailable = RunClient(base_url, auth_token="event-token")._request(
            "POST", ("v1", "events"), {"event_type": "missing-payload"}
        )
    finally:
        server.close()

    assert published.is_ok()
    assert source.metrics()["exporter_failures"] == 0
    remote = destination.snapshot().unwrap()
    assert len(remote) == 1
    assert remote[0].event_type == "remote.model.chunk"
    assert remote[0].payload["token"] == "[REDACTED]"
    assert remote[0].run_id == "exported-run"
    assert unavailable.is_err()
    assert unavailable.unwrap_err()["errorType"] == "EVENT_INPUT_INVALID"


def test_event_transport_reports_missing_stream_and_invalid_client_inputs():
    server = RunServer(WorkflowRegistry(), auth_token="event-token")
    base_url = server.start()
    try:
        client = RunClient(base_url, auth_token="event-token")
        unavailable = client.publish_event("remote.event", {})
        invalid_type = client.publish_event("", {})
        invalid_run = client.publish_event("remote.event", {}, run_id="bad\nrun")
    finally:
        server.close()

    assert unavailable.is_err()
    assert unavailable.unwrap_err()["errorType"] == "EVENT_STREAM_UNAVAILABLE"
    assert invalid_type.is_err()
    assert invalid_type.unwrap_err()["errorType"] == "EVENT_INPUT_INVALID"
    assert invalid_run.is_err()
    assert invalid_run.unwrap_err()["errorType"] == "EVENT_INPUT_INVALID"


def test_authenticated_event_transport_reads_redacted_batches_by_cursor():
    stream = EventStream(max_events=2)
    server = RunServer(
        WorkflowRegistry(),
        event_stream=stream,
        auth_token="event-token",
    )
    base_url = server.start()
    try:
        client = RunClient(base_url, auth_token="event-token")
        assert client.publish_event("remote.one", {"secret": "hidden"}).is_ok()
        assert client.publish_event(
            "remote.two", {"value": 2, "secret": "retained-but-redacted"}
        ).is_ok()
        assert client.publish_event("remote.three", {"value": 3}).is_ok()

        page = client.read_events(EventCursor(sequence=1), limit=1)
        tail = client.read_events(EventCursor(sequence=2), limit=2)
        expired = client.read_events(EventCursor(sequence=0))
        invalid_limit = client._request("GET", ("v1", "events"), query={"limit": "0"})
        unknown_query = client._request("GET", ("v1", "events"), query={"unknown": "1"})
        unauthorized = RunClient(base_url).read_events()
    finally:
        server.close()

    assert page.is_ok()
    page_batch = page.unwrap()["batch"]
    assert [event["sequence"] for event in page_batch["events"]] == [2]
    assert page_batch["events"][0]["payload"]["secret"] == "[REDACTED]"
    assert page_batch["next_cursor"] == {"sequence": 2}
    assert page_batch["oldest_sequence"] == 2
    assert page_batch["latest_sequence"] == 3
    assert tail.is_ok()
    assert [event["sequence"] for event in tail.unwrap()["batch"]["events"]] == [3]
    assert expired.is_err()
    assert expired.unwrap_err()["errorType"] == "EVENT_CURSOR_EXPIRED"
    assert invalid_limit.is_err()
    assert invalid_limit.unwrap_err()["errorType"] == "EVENT_QUERY_INVALID"
    assert unknown_query.is_err()
    assert unknown_query.unwrap_err()["errorType"] == "EVENT_QUERY_INVALID"
    assert unauthorized.is_err()
    assert unauthorized.unwrap_err()["errorType"] == "UNAUTHORIZED"


def test_authenticated_event_transport_searches_redacted_trace_window():
    stream = EventStream(max_events=4)
    assert stream.publish(
        "model.started",
        {"trace_id": "trace-a", "secret": "hidden"},
        run_id="run-a",
    ).is_ok()
    assert stream.publish(
        "tool.started", {"trace_id": "trace-b"}, run_id="run-a"
    ).is_ok()
    assert stream.publish(
        "model.finished", {"trace_id": "trace-a"}, run_id="run-b"
    ).is_ok()
    server = RunServer(
        WorkflowRegistry(),
        event_stream=stream,
        auth_token="event-token",
        auth_principal=Principal("reader", ("event:read",)),
    )
    base_url = server.start()
    try:
        client = RunClient(base_url, auth_token="event-token")
        by_trace = client.search_events(trace_id="trace-a", limit=1)
        by_run = client.search_events(run_id="run-a")
        missing_filter = client.search_events()
        invalid_limit = client.search_events(trace_id="trace-a", limit=0)
        unknown_query = client._request(
            "GET",
            ("v1", "events", "search"),
            query={"trace_id": "trace-a", "unknown": "1"},
        )
        unauthorized = RunClient(base_url).search_events(trace_id="trace-a")
    finally:
        server.close()

    restricted = RunServer(
        WorkflowRegistry(),
        event_stream=stream,
        auth_token="restricted-token",
        auth_principal=Principal("restricted", ("agent:read",)),
    )
    restricted_url = restricted.start()
    try:
        forbidden = RunClient(
            restricted_url, auth_token="restricted-token"
        ).search_events(trace_id="trace-a")
    finally:
        restricted.close()

    assert by_trace.is_ok()
    trace_batch = by_trace.unwrap()["batch"]
    assert [event["sequence"] for event in trace_batch["events"]] == [1]
    assert trace_batch["events"][0]["payload"]["secret"] == "[REDACTED]"
    assert trace_batch["next_cursor"] == {"sequence": 1}
    assert by_run.is_ok()
    assert [event["event_type"] for event in by_run.unwrap()["batch"]["events"]] == [
        "model.started",
        "tool.started",
    ]
    assert missing_filter.is_err()
    assert missing_filter.unwrap_err()["errorType"] == "EVENT_SEARCH_INVALID"
    assert invalid_limit.is_err()
    assert invalid_limit.unwrap_err()["errorType"] == "EVENT_SEARCH_INVALID"
    assert unknown_query.is_err()
    assert unknown_query.unwrap_err()["errorType"] == "EVENT_SEARCH_INVALID"
    assert unauthorized.is_err()
    assert unauthorized.unwrap_err()["errorType"] == "UNAUTHORIZED"
    assert forbidden.is_err()
    assert forbidden.unwrap_err()["errorType"] == "FORBIDDEN"


def test_authenticated_handoff_transport_preserves_store_ownership_state():
    store = InMemoryHandoffStore()
    record = HandoffRecord.pending(
        "remote-handoff",
        "source",
        "target",
        "a" * 64,
        "b" * 64,
    )
    with pytest.raises(ValueError):
        RunServer(WorkflowRegistry(), handoff_store=store)

    server = RunServer(
        WorkflowRegistry(),
        handoff_store=store,
        auth_token="handoff-token",
    )
    base_url = server.start()
    try:
        client = RunClient(base_url, auth_token="handoff-token")
        created = client.create_handoff(record)
        listed = client.list_open_handoffs(10)
        inspected = client.get_handoff("remote-handoff")
        wrong_owner = client.accept_handoff("remote-handoff", "other")
        accepted = client.accept_handoff("remote-handoff", "target")
        completed = client.complete_handoff("remote-handoff", "target", "target-goal")
        unauthorized = RunClient(base_url).list_open_handoffs()
    finally:
        server.close()

    assert created.is_ok()
    assert created.unwrap()["handoff"]["status"] == "pending"
    assert listed.is_ok()
    assert listed.unwrap()["handoffs"][0]["handoff_id"] == "remote-handoff"
    assert inspected.is_ok()
    assert inspected.unwrap()["handoff"]["task_digest"] == "a" * 64
    assert "secret task" not in str(inspected.unwrap())
    assert wrong_owner.is_err()
    assert wrong_owner.unwrap_err()["errorType"] == "HANDOFF_OWNER_ERROR"
    assert accepted.is_ok()
    assert accepted.unwrap()["handoff"]["owner_id"] == "target"
    assert completed.is_ok()
    assert completed.unwrap()["handoff"]["status"] == "completed"
    assert completed.unwrap()["handoff"]["owner_id"] == "source"
    assert unauthorized.is_err()
    assert unauthorized.unwrap_err()["errorType"] == "UNAUTHORIZED"


def test_authenticated_handoff_transport_redacts_persisted_result():
    store = InMemoryHandoffStore()
    record = HandoffRecord.pending(
        "remote-result",
        "source",
        "target",
        "a" * 64,
        "b" * 64,
    )
    assert store.create(record).is_ok()
    assert store.accept("remote-result", "target").is_ok()
    assert store.complete(
        "remote-result",
        "target",
        "target-goal",
        result={
            "agent_id": "target",
            "goal_id": "target-goal",
            "status": "completed",
            "result": {"secret": "local-only"},
        },
    ).is_ok()

    server = RunServer(
        WorkflowRegistry(),
        handoff_store=store,
        auth_token="handoff-token",
    )
    base_url = server.start()
    try:
        inspected = RunClient(base_url, auth_token="handoff-token").get_handoff(
            "remote-result"
        )
    finally:
        server.close()

    assert inspected.is_ok()
    payload = inspected.unwrap()["handoff"]
    assert payload["status"] == "completed"
    assert "result" not in payload
    assert "local-only" not in str(payload)


def test_authenticated_handoff_transport_delivers_result_through_scoped_route():
    store = InMemoryHandoffStore()
    record = HandoffRecord.pending(
        "remote-delivery",
        "source",
        "target",
        "a" * 64,
        "b" * 64,
    )
    server = RunServer(
        WorkflowRegistry(),
        handoff_store=store,
        auth_token="handoff-token",
        auth_principal=Principal(
            "handoff-operator",
            ("handoff:read", "handoff:write", "handoff:result"),
        ),
    )
    base_url = server.start()
    try:
        client = RunClient(base_url, auth_token="handoff-token")
        assert client.create_handoff(record).is_ok()
        pending = client.get_handoff_result("remote-delivery")
        assert client.accept_handoff("remote-delivery", "target").is_ok()
        unavailable = client.get_handoff_result("remote-delivery")
        completed = client.complete_handoff(
            "remote-delivery",
            "target",
            "target-goal",
            result={"answer": "ready", "metadata": {"source": "target"}},
        )
        inspected = client.get_handoff("remote-delivery")
        delivered = client.get_handoff_result("remote-delivery")
    finally:
        server.close()

    assert pending.is_err()
    assert pending.unwrap_err()["errorType"] == "HANDOFF_RESULT_UNAVAILABLE"
    assert unavailable.is_err()
    assert unavailable.unwrap_err()["errorType"] == "HANDOFF_RESULT_UNAVAILABLE"
    assert completed.is_ok()
    assert "result" not in completed.unwrap()["handoff"]
    assert inspected.is_ok()
    assert "result" not in inspected.unwrap()["handoff"]
    assert delivered.is_ok()
    assert delivered.unwrap()["handoff"] == {
        "handoff_id": "remote-delivery",
        "status": "completed",
        "target_goal_id": "target-goal",
        "result": {"answer": "ready", "metadata": {"source": "target"}},
    }


def test_handoff_result_transport_requires_dedicated_principal_scope():
    store = InMemoryHandoffStore()
    record = HandoffRecord.pending(
        "remote-scope",
        "source",
        "target",
        "a" * 64,
    )
    assert store.create(record).is_ok()
    assert store.accept("remote-scope", "target").is_ok()
    assert store.complete(
        "remote-scope", "target", "target-goal", result={"answer": "secret"}
    ).is_ok()
    server = RunServer(
        WorkflowRegistry(),
        handoff_store=store,
        auth_token="handoff-token",
        auth_principal=Principal("reader", ("handoff:read",)),
    )
    base_url = server.start()
    try:
        client = RunClient(base_url, auth_token="handoff-token")
        inspected = client.get_handoff("remote-scope")
        denied = client.get_handoff_result("remote-scope")
    finally:
        server.close()

    assert inspected.is_ok()
    assert "result" not in inspected.unwrap()["handoff"]
    assert denied.is_err()
    assert denied.unwrap_err()["errorType"] == "FORBIDDEN"


def test_handoff_result_transport_rejects_invalid_payload_without_mutation():
    store = InMemoryHandoffStore()
    record = HandoffRecord.pending(
        "remote-invalid-result",
        "source",
        "target",
        "a" * 64,
    )
    assert store.create(record).is_ok()
    assert store.accept("remote-invalid-result", "target").is_ok()
    server = RunServer(
        WorkflowRegistry(),
        handoff_store=store,
        auth_token="handoff-token",
    )
    base_url = server.start()
    complete_url = f"{base_url}/v1/handoffs/remote-invalid-result/complete"
    try:
        client = RunClient(base_url, auth_token="handoff-token")
        client_rejected = client.complete_handoff(
            "remote-invalid-result",
            "target",
            "target-goal",
            result=[],  # type: ignore[arg-type]
        )
        invalid_status, invalid = _request(
            complete_url,
            method="POST",
            payload={
                "target_agent_id": "target",
                "target_goal_id": "target-goal",
                "result": [],
            },
            headers={"Authorization": "Bearer handoff-token"},
        )
        oversized_status, oversized = _request(
            complete_url,
            method="POST",
            payload={
                "target_agent_id": "target",
                "target_goal_id": "target-goal",
                "result": {"value": "x" * 70_000},
            },
            headers={"Authorization": "Bearer handoff-token"},
        )
    finally:
        server.close()

    assert client_rejected.is_err()
    assert client_rejected.unwrap_err()["errorType"] == "HANDOFF_RESULT_INVALID"
    assert invalid_status == 400
    assert invalid["error"]["errorType"] == "HANDOFF_RESULT_INVALID"
    assert oversized_status == 400
    assert oversized["error"]["errorType"] == "HANDOFF_RESULT_INVALID"
    stored = store.get("remote-invalid-result")
    assert stored.is_ok()
    assert stored.unwrap().status == "accepted"
    assert stored.unwrap().result is None


def test_handoff_transport_preserves_legacy_complete_signature_without_result():
    class LegacyHandoffStore:
        def __init__(self):
            self._store = InMemoryHandoffStore()

        def create(self, record):
            return self._store.create(record)

        def get(self, handoff_id):
            return self._store.get(handoff_id)

        def accept(self, handoff_id, target_agent_id):
            return self._store.accept(handoff_id, target_agent_id)

        def complete(self, handoff_id, target_agent_id, target_goal_id):
            return self._store.complete(handoff_id, target_agent_id, target_goal_id)

        def fail(self, handoff_id, target_agent_id, error_type):
            return self._store.fail(handoff_id, target_agent_id, error_type)

        def list_open(self, limit=100):
            return self._store.list_open(limit)

    store = LegacyHandoffStore()
    record = HandoffRecord.pending(
        "legacy-complete",
        "source",
        "target",
        "a" * 64,
    )
    server = RunServer(
        WorkflowRegistry(),
        handoff_store=store,
        auth_token="handoff-token",
    )
    base_url = server.start()
    try:
        client = RunClient(base_url, auth_token="handoff-token")
        created = client.create_handoff(record)
        accepted = client.accept_handoff("legacy-complete", "target")
        completed = client.complete_handoff("legacy-complete", "target", "target-goal")
    finally:
        server.close()

    assert created.is_ok()
    assert accepted.is_ok()
    assert completed.is_ok()
    assert completed.unwrap()["handoff"]["status"] == "completed"


def test_handoff_transport_fails_closed_without_store_and_bounds_client_inputs():
    server = RunServer(WorkflowRegistry(), auth_token="token")
    base_url = server.start()
    try:
        unavailable = RunClient(base_url, auth_token="token").list_open_handoffs()
    finally:
        server.close()

    client = RunClient("http://127.0.0.1:1", timeout_seconds=0.1)
    bad_record = client.create_handoff(object())  # type: ignore[arg-type]
    bad_limit = client.list_open_handoffs(0)

    assert unavailable.is_err()
    assert unavailable.unwrap_err()["errorType"] == "HANDOFF_STORE_UNAVAILABLE"
    assert bad_record.is_err()
    assert bad_record.unwrap_err()["errorType"] == "HANDOFF_RECORD_INVALID"
    assert bad_limit.is_err()
    assert bad_limit.unwrap_err()["errorType"] == "HANDOFF_LIMIT_INVALID"
