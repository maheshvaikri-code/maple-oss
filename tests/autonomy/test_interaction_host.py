"""Regression coverage for bounded human-input host callbacks."""

from pathlib import Path
from typing import Any, Dict, List

from maple.autonomy.interactions import (
    FileHumanInputStore,
    HumanInputNotification,
    HumanInputRequest,
    InMemoryHumanInputStore,
)
from maple.core.result import Result


def _request(interaction_id: str = "host-input-1") -> HumanInputRequest:
    return HumanInputRequest(
        interaction_id=interaction_id,
        run_id="run-host-1",
        tool_call_id="call-host-1",
        prompt="Confirm the deployment.",
        input_schema={
            "type": "object",
            "properties": {"confirmed": {"type": "boolean"}},
            "required": ["confirmed"],
        },
    )


class RecordingHost:
    def __init__(self, *, allowed: bool) -> None:
        self.allowed = allowed
        self.authorization_calls: List[Dict[str, Any]] = []
        self.notifications: List[HumanInputNotification] = []

    def authorize(
        self, actor_id: str, action: str, request: HumanInputRequest
    ) -> Result[bool, Dict[str, Any]]:
        self.authorization_calls.append(
            {
                "actor_id": actor_id,
                "action": action,
                "interaction_id": request.interaction_id,
                "status": request.status,
            }
        )
        return Result.ok(self.allowed)

    def notify(
        self, notification: HumanInputNotification
    ) -> Result[None, Dict[str, Any]]:
        self.notifications.append(notification)
        return Result.ok(None)


def test_file_store_authorizes_host_mutations_and_notifies_without_response_data(
    tmp_path: Path,
) -> None:
    host = RecordingHost(allowed=False)
    store = FileHumanInputStore(tmp_path, notifier=host, authorizer=host)
    assert store.create(_request()).is_ok()

    missing_actor = store.respond("host-input-1", {"confirmed": True})
    denied = store.respond("host-input-1", {"confirmed": True}, actor_id="operator-1")

    assert missing_actor.is_err()
    assert missing_actor.unwrap_err()["errorType"] == "HUMAN_INPUT_ACTOR_REQUIRED"
    assert denied.is_err()
    assert denied.unwrap_err()["errorType"] == "HUMAN_INPUT_UNAUTHORIZED"
    assert len(host.authorization_calls) == 1
    assert host.authorization_calls[0]["action"] == "respond"
    assert len(host.notifications) == 1
    assert host.notifications[0].event_type == "created"
    assert "response" not in host.notifications[0].to_dict()

    pending = store.get("host-input-1").unwrap()
    assert pending is not None
    assert pending.status == "pending"

    host.allowed = True
    accepted = store.respond("host-input-1", {"confirmed": True}, actor_id="operator-1")

    assert accepted.is_ok()
    assert accepted.unwrap().status == "responded"
    assert len(host.notifications) == 2
    assert host.notifications[1].event_type == "responded"
    assert host.notifications[1].actor_id == "operator-1"
    assert "response" not in host.notifications[1].to_dict()


def test_notification_failure_is_typed_but_persisted_state_remains_authoritative():
    class FailingNotifier:
        def notify(
            self, notification: HumanInputNotification
        ) -> Result[None, Dict[str, Any]]:
            return Result.err({"errorType": "HOST_UNAVAILABLE", "message": "try later"})

    store = InMemoryHumanInputStore(notifier=FailingNotifier())
    created = store.create(_request("host-input-2"))

    assert created.is_err()
    assert created.unwrap_err()["errorType"] == "HUMAN_INPUT_NOTIFICATION_ERROR"
    persisted = store.get("host-input-2").unwrap()
    assert persisted is not None
    assert persisted.status == "pending"
