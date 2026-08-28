from dataclasses import dataclass
from typing import Any, Mapping, Optional

import pytest

from maple import (
    AgentRegistry,
    AgentRun,
    AutonomousAgentRemoteAdapter,
    InMemoryAgentRunStore,
    Result,
    RunClient,
    RunServer,
    WorkflowRegistry,
)


@dataclass
class _Goal:
    run_id: str
    status: str
    result: Any = None


class _NativeAgent:
    agent_id = "researcher"

    def __init__(self) -> None:
        self.run_store = None
        self.calls = []

    def set_run_store(self, store) -> None:
        self.run_store = store

    def pursue_goal_with_context(
        self,
        description: str,
        context: Mapping[str, Any],
        *,
        session_id: Optional[str],
        run_id: Optional[str],
    ):
        self.calls.append((description, dict(context), session_id, run_id))
        return Result.ok(
            _Goal(run_id=run_id, status="completed", result={"answer": description})
        )

    def resume_run(self, run_id: str, *, cancellation=None):
        return Result.ok(
            _Goal(run_id=run_id, status="completed", result={"resumed": True})
        )


def test_native_agent_remote_adapter_binds_store_and_registers_start_and_resume():
    agent = _NativeAgent()
    store = InMemoryAgentRunStore()
    adapter = AutonomousAgentRemoteAdapter(agent, run_store=store)
    registry = AgentRegistry()

    registered = adapter.register(registry, capabilities=["research"])
    started = registry.run(
        "researcher",
        "summarize",
        {"project": "MAPLE"},
        session_id="session-1",
        run_id="native-run-1",
    )
    resumed = registry.resume("researcher", "native-run-1")

    assert registered.is_ok()
    assert agent.run_store is store
    assert started.is_ok()
    assert started.unwrap() == AgentRun(
        "researcher", "native-run-1", "completed", {"answer": "summarize"}
    )
    assert resumed.is_ok()
    assert resumed.unwrap() == AgentRun(
        "researcher", "native-run-1", "completed", {"resumed": True}
    )
    assert registry.list_agents().unwrap()[0].capabilities == ("research",)
    assert agent.calls == [
        ("summarize", {"project": "MAPLE"}, "session-1", "native-run-1")
    ]


def test_native_agent_remote_adapter_round_trips_authenticated_typed_transport():
    agent = _NativeAgent()
    store = InMemoryAgentRunStore()
    registry = AgentRegistry()
    assert (
        AutonomousAgentRemoteAdapter(agent, run_store=store).register(registry).is_ok()
    )

    with RunServer(
        WorkflowRegistry(),
        agent_registry=registry,
        agent_run_store=store,
        auth_token="native-token",
    ) as server:
        client = RunClient(server.url, auth_token="native-token")
        started = client.run_agent_typed(
            "researcher",
            "remote task",
            {"source": "test"},
            session_id="remote-session",
            run_id="remote-native-run",
        )
        resumed = client.resume_agent_run_typed("researcher", "remote-native-run")

    assert started.is_ok()
    assert started.unwrap().status == "completed"
    assert started.unwrap().result == {"answer": "remote task"}
    assert resumed.is_ok()
    assert resumed.unwrap().result == {"resumed": True}


def test_native_agent_remote_adapter_routes_by_capability():
    agent = _NativeAgent()
    registry = AgentRegistry()
    assert (
        AutonomousAgentRemoteAdapter(agent, run_store=InMemoryAgentRunStore())
        .register(registry, capabilities=["research"])
        .is_ok()
    )

    routed = registry.route("research", "remote task", run_id="routed-run")

    assert routed.is_ok()
    assert routed.unwrap() == AgentRun(
        "researcher", "routed-run", "completed", {"answer": "remote task"}
    )


def test_native_agent_remote_adapter_sanitizes_errors_and_rejects_invalid_goals():
    class ErrorAgent(_NativeAgent):
        def pursue_goal_with_context(self, *args, **kwargs):
            return Result.err(
                {
                    "errorType": "PRIVATE_PROVIDER_ERROR",
                    "message": "private provider detail",
                }
            )

    error_registry = AgentRegistry()
    assert (
        AutonomousAgentRemoteAdapter(ErrorAgent(), run_store=InMemoryAgentRunStore())
        .register(error_registry)
        .is_ok()
    )
    failed = error_registry.run("researcher", "task", run_id="error-run")
    assert failed.is_err()
    assert failed.unwrap_err()["errorType"] == "AGENT_RUNTIME_ERROR"
    assert "private provider detail" not in str(failed.unwrap_err())

    class InvalidAgent(_NativeAgent):
        def pursue_goal_with_context(self, *args, **kwargs):
            return Result.ok(_Goal("other-run", "running", {"private": True}))

    invalid_registry = AgentRegistry()
    assert (
        AutonomousAgentRemoteAdapter(InvalidAgent(), run_store=InMemoryAgentRunStore())
        .register(invalid_registry)
        .is_ok()
    )
    invalid = invalid_registry.run("researcher", "task", run_id="expected-run")
    assert invalid.is_err()
    assert invalid.unwrap_err()["errorType"] == "AGENT_RUNTIME_RESULT_INVALID"
    assert "private" not in str(invalid.unwrap_err())


def test_native_agent_remote_adapter_registers_only_explicit_cancel_callback():
    agent = _NativeAgent()
    registry = AgentRegistry()
    adapter = AutonomousAgentRemoteAdapter(agent, run_store=InMemoryAgentRunStore())
    assert adapter.register(
        registry,
        cancel_handler=lambda run_id: Result.ok(
            AgentRun(
                "researcher",
                run_id,
                "cancelled",
                error={
                    "errorType": "AGENT_RUN_CANCELLED",
                    "message": "cancelled",
                },
            )
        ),
    ).is_ok()
    cancelled = registry.cancel("researcher", "cancel-run")
    assert cancelled.is_ok()
    assert cancelled.unwrap().status == "cancelled"


def test_native_agent_remote_adapter_validates_dependencies():
    with pytest.raises(TypeError, match="run_store"):
        AutonomousAgentRemoteAdapter(_NativeAgent(), run_store=object())
    with pytest.raises(ValueError, match="agent_id"):
        AutonomousAgentRemoteAdapter(
            type("InvalidAgent", (), {"agent_id": "bad\n-id"})(),
            run_store=InMemoryAgentRunStore(),
        )
