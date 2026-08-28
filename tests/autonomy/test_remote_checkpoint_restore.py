"""Regression tests for authenticated remote agent checkpoint transfer."""

import json
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple

from maple.autonomy import (
    AgentRunCheckpoint,
    InMemoryAgentRunStore,
    Principal,
    RunClient,
    RunServer,
    SessionMessage,
    WorkflowRegistry,
)
from maple.core.result import Result


def _checkpoint(
    *, run_id: str = "remote-run", agent_id: str = "researcher", status: str = "paused"
) -> AgentRunCheckpoint:
    return AgentRunCheckpoint(
        run_id=run_id,
        agent_id=agent_id,
        description="Transfer the private release review.",
        status=status,
        messages=(
            SessionMessage(role="user", content="Keep this message private."),
            SessionMessage(role="assistant", content="The review is paused."),
        ),
        reasoning_steps=({"step": 1, "kind": "model", "private_note": "retain me"},),
        step_count=1,
        pending_approval_id="approval-1" if status == "paused" else None,
        token_usage={"prompt_tokens": 12, "completion_tokens": 4},
        result={"private": "checkpoint result"},
    )


def _request(
    url: str,
    *,
    method: str = "GET",
    payload: Optional[Dict[str, Any]] = None,
    token: str = "restore-token",
) -> Tuple[int, Dict[str, Any]]:
    data = None
    headers = {"Authorization": f"Bearer {token}"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def test_remote_checkpoint_export_restore_round_trip_preserves_full_state() -> None:
    source_store = InMemoryAgentRunStore()
    source_saved = source_store.save(_checkpoint())
    assert source_saved.is_ok()
    source_checkpoint = source_saved.unwrap()
    destination_store = InMemoryAgentRunStore()

    principal = Principal("checkpoint-operator", ("agent:restore",))
    with RunServer(
        WorkflowRegistry(),
        agent_run_store=source_store,
        auth_token="restore-token",
        auth_principal=principal,
    ) as source, RunServer(
        WorkflowRegistry(),
        agent_run_store=destination_store,
        auth_token="restore-token",
        auth_principal=principal,
    ) as destination:
        source_client = RunClient(source.url, auth_token="restore-token")
        destination_client = RunClient(destination.url, auth_token="restore-token")

        exported = source_client.export_agent_run_checkpoint("researcher", "remote-run")
        assert exported.is_ok()
        payload = exported.unwrap()["checkpoint"]
        assert payload["messages"][0]["content"] == "Keep this message private."
        assert payload["reasoning_steps"][0]["private_note"] == "retain me"

        restored = destination_client.restore_agent_run_checkpoint(
            "researcher", source_checkpoint
        )
        assert restored.is_ok()
        receipt = restored.unwrap()["checkpoint"]
        assert receipt["version"] == 1
        assert "messages" not in receipt
        assert "reasoning_steps" not in receipt
        assert "result" not in receipt

    restored_checkpoint = destination_store.load("remote-run").unwrap()
    assert restored_checkpoint is not None
    restored_payload = restored_checkpoint.to_dict()
    source_payload = source_checkpoint.to_dict()
    assert restored_payload["updated_at"] >= source_payload["updated_at"]
    restored_payload.pop("updated_at")
    source_payload.pop("updated_at")
    assert restored_payload == source_payload


def test_remote_checkpoint_export_requires_distinct_restore_scope() -> None:
    store = InMemoryAgentRunStore()
    assert store.save(_checkpoint()).is_ok()
    server = RunServer(
        WorkflowRegistry(),
        agent_run_store=store,
        auth_token="restore-token",
        auth_principal=Principal("reader", ("agent:read",)),
    )
    base_url = server.start()
    try:
        result = RunClient(
            base_url, auth_token="restore-token"
        ).export_agent_run_checkpoint("researcher", "remote-run")
    finally:
        server.close()

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "FORBIDDEN"


def test_remote_checkpoint_restore_rejects_invalid_identity_and_terminal_state() -> (
    None
):
    store = InMemoryAgentRunStore()
    server = RunServer(
        WorkflowRegistry(),
        agent_run_store=store,
        auth_token="restore-token",
        auth_principal=Principal("operator", ("agent:restore",)),
    )
    base_url = server.start()
    try:
        mismatched = _checkpoint(agent_id="other")
        mismatched_payload = mismatched.to_dict()
        status, response = _request(
            f"{base_url}/v1/agents/researcher/runs/remote-run/restore",
            method="POST",
            payload={"checkpoint": mismatched_payload},
        )
        terminal = _checkpoint(status="completed")
        terminal_status, terminal_response = _request(
            f"{base_url}/v1/agents/researcher/runs/remote-run/restore",
            method="POST",
            payload={"checkpoint": terminal.to_dict()},
        )
        malformed_status, malformed_response = _request(
            f"{base_url}/v1/agents/researcher/runs/remote-run/restore",
            method="POST",
            payload={"checkpoint": {"run_id": "remote-run"}},
        )
    finally:
        server.close()

    assert status == 409
    assert response["error"]["errorType"] == "AGENT_RUN_CHECKPOINT_IDENTITY_MISMATCH"
    assert terminal_status == 409
    assert terminal_response["error"]["errorType"] == (
        "AGENT_RUN_CHECKPOINT_NOT_RESUMABLE"
    )
    assert malformed_status == 400
    assert malformed_response["error"]["errorType"] == "AGENT_RUN_CHECKPOINT_INVALID"
    assert store.load("remote-run").unwrap() is None


def test_remote_checkpoint_restore_uses_destination_cas_and_preserves_existing_state() -> (
    None
):
    destination_store = InMemoryAgentRunStore()
    existing = _checkpoint()
    assert destination_store.save(existing).is_ok()
    before = destination_store.load("remote-run").unwrap()
    assert before is not None

    server = RunServer(
        WorkflowRegistry(),
        agent_run_store=destination_store,
        auth_token="restore-token",
        auth_principal=Principal("operator", ("agent:restore",)),
    )
    base_url = server.start()
    try:
        stale = _checkpoint()
        result = RunClient(
            base_url, auth_token="restore-token"
        ).restore_agent_run_checkpoint("researcher", stale, expected_version=0)
    finally:
        server.close()

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "RUN_CHECKPOINT_CONFLICT"
    after = destination_store.load("remote-run").unwrap()
    assert after is not None
    assert after.to_dict() == before.to_dict()


def test_remote_checkpoint_restore_reports_legacy_store_without_save() -> None:
    checkpoint = _checkpoint()

    class LegacyStore:
        def load(
            self, run_id: str
        ) -> Result[Optional[AgentRunCheckpoint], Dict[str, Any]]:
            return (
                Result.ok(checkpoint)
                if run_id == checkpoint.run_id
                else Result.ok(None)
            )

    server = RunServer(
        WorkflowRegistry(),
        agent_run_store=LegacyStore(),
        auth_token="restore-token",
    )
    base_url = server.start()
    try:
        result = RunClient(
            base_url, auth_token="restore-token"
        ).restore_agent_run_checkpoint("researcher", checkpoint)
    finally:
        server.close()

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "AGENT_RUN_RESTORE_UNAVAILABLE"
