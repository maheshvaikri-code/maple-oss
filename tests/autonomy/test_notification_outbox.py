"""Regression coverage for bounded durable notification outboxes."""

import json
import threading
from typing import Any, Dict, List

from maple.autonomy import (
    ApprovalNotification,
    ApprovalRequest,
    FileApprovalNotificationOutbox,
    FileApprovalStore,
    FileHumanInputNotificationOutbox,
    FileHumanInputStore,
    HumanInputNotification,
    HumanInputRequest,
    InMemoryApprovalStore,
    InMemoryHumanInputStore,
)
from maple.core.result import Result


class RecordingTarget:
    def __init__(self) -> None:
        self.notifications: List[Any] = []
        self.fail = False

    def notify(self, notification: Any) -> Result[None, Dict[str, Any]]:
        self.notifications.append(notification)
        if self.fail:
            return Result.err(
                {"errorType": "HOST_UNAVAILABLE", "message": "private detail"}
            )
        return Result.ok(None)


class BlockingTarget:
    def __init__(self, outbox: Any) -> None:
        self.outbox = outbox
        self.started = threading.Event()
        self.release = threading.Event()
        self.observer_completed = threading.Event()

    def notify(self, notification: Any) -> Result[None, Dict[str, Any]]:
        self.started.set()

        def observe() -> None:
            assert self.outbox.list_pending().is_ok()
            self.observer_completed.set()

        observer = threading.Thread(target=observe)
        observer.start()
        observer.join(timeout=1)
        self.release.wait(timeout=1)
        return Result.ok(None)


def _approval_request(approval_id: str = "outbox-approval") -> ApprovalRequest:
    return ApprovalRequest(
        approval_id=approval_id,
        tool_call_id="outbox-call",
        tool_name="write_state",
        arguments={"key": "status", "value": "ready"},
    )


def _human_request(interaction_id: str = "outbox-input") -> HumanInputRequest:
    return HumanInputRequest(
        interaction_id=interaction_id,
        run_id="outbox-run",
        tool_call_id="outbox-input-call",
        prompt="Provide a code.",
        input_schema={"type": "object", "required": ["code"]},
    )


def test_approval_outbox_is_atomic_restartable_and_deduplicated(tmp_path: Any) -> None:
    target = RecordingTarget()
    directory = tmp_path / "approval-outbox"
    outbox = FileApprovalNotificationOutbox(directory, target=target)
    notification = ApprovalNotification.from_request(_approval_request(), "created")

    assert outbox.notify(notification).is_ok()
    assert outbox.notify(notification).is_ok()
    assert len(list(directory.glob("*.json"))) == 1

    restarted = FileApprovalNotificationOutbox(directory, target=target)
    assert restarted.list_pending().unwrap() == [notification]
    report = restarted.drain()

    assert report.is_ok()
    assert report.unwrap().to_dict() == {
        "attempted": 1,
        "delivered": 1,
        "failed": 0,
        "pending": 0,
        "failure_details": [],
    }
    assert target.notifications == [notification]
    assert restarted.drain().unwrap().attempted == 0
    stored = json.loads(next(directory.glob("*.json")).read_text(encoding="utf-8"))
    assert stored["state"] == "delivered"


def test_failed_delivery_is_retained_and_retried_only_by_explicit_drain(
    tmp_path: Any,
) -> None:
    target = RecordingTarget()
    target.fail = True
    outbox = FileHumanInputNotificationOutbox(tmp_path / "human-outbox", target=target)
    notification = HumanInputNotification.from_request(_human_request(), "created")
    assert outbox.notify(notification).is_ok()

    failed = outbox.drain()
    assert failed.is_ok()
    assert failed.unwrap().attempted == 1
    assert failed.unwrap().failed == 1
    assert failed.unwrap().pending == 1
    assert failed.unwrap().failure_details[0]["notification_id"]
    assert outbox.list_pending().unwrap() == [notification]
    record = json.loads(next((tmp_path / "human-outbox").glob("*.json")).read_text())
    assert record["last_error"] == {
        "errorType": "NOTIFICATION_OUTBOX_DELIVERY_ERROR",
        "message": "downstream notifier rejected notification.",
    }
    assert "private detail" not in json.dumps(record)

    target.fail = False
    delivered = outbox.drain()
    assert delivered.is_ok()
    assert delivered.unwrap().delivered == 1
    assert delivered.unwrap().pending == 0
    assert len(target.notifications) == 2


def test_store_notifiers_enqueue_after_local_state_is_written(tmp_path: Any) -> None:
    approval_target = RecordingTarget()
    approval_outbox = FileApprovalNotificationOutbox(
        tmp_path / "approval-outbox", target=approval_target
    )
    approval_store = FileApprovalStore(
        tmp_path / "approval-store", notifier=approval_outbox
    )
    assert approval_store.create(_approval_request("stored-approval")).is_ok()
    assert approval_store.get("stored-approval").unwrap() is not None
    assert len(approval_outbox.list_pending().unwrap()) == 1

    human_target = RecordingTarget()
    human_outbox = FileHumanInputNotificationOutbox(
        tmp_path / "human-outbox", target=human_target
    )
    human_store = InMemoryHumanInputStore(notifier=human_outbox)
    assert human_store.create(_human_request("stored-input")).is_ok()
    pending = human_outbox.list_pending().unwrap()
    assert len(pending) == 1
    assert isinstance(pending[0], HumanInputNotification)


def test_outbox_rejects_new_records_at_bound_but_accepts_duplicate(
    tmp_path: Any,
) -> None:
    target = RecordingTarget()
    outbox = FileApprovalNotificationOutbox(tmp_path, target=target, max_records=1)
    first = ApprovalNotification.from_request(_approval_request("first"), "created")
    second = ApprovalNotification.from_request(_approval_request("second"), "created")

    assert outbox.notify(first).is_ok()
    assert outbox.notify(first).is_ok()
    full = outbox.notify(second)
    assert full.is_err()
    assert full.unwrap_err()["errorType"] == "NOTIFICATION_OUTBOX_FULL"
    assert len(outbox.list_pending().unwrap()) == 1


def test_malformed_record_fails_closed_without_repair(tmp_path: Any) -> None:
    target = RecordingTarget()
    directory = tmp_path / "malformed"
    directory.mkdir()
    path = directory / "bad.json"
    path.write_text("{}", encoding="utf-8")
    outbox = FileApprovalNotificationOutbox(directory, target=target)

    result = outbox.list_pending()

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "NOTIFICATION_OUTBOX_RECORD_INVALID"
    assert path.read_text(encoding="utf-8") == "{}"
    assert target.notifications == []


def test_target_exception_is_sanitized_and_record_remains_pending(
    tmp_path: Any,
) -> None:
    class RaisingTarget:
        def notify(self, notification: Any) -> Result[None, Dict[str, Any]]:
            raise RuntimeError("secret endpoint response")

    outbox = FileApprovalNotificationOutbox(tmp_path, target=RaisingTarget())
    notification = ApprovalNotification.from_request(_approval_request(), "created")
    assert outbox.notify(notification).is_ok()

    report = outbox.drain().unwrap()

    assert report.failed == 1
    assert report.pending == 1
    assert "secret endpoint response" not in json.dumps(report.to_dict())


def test_target_runs_without_outbox_state_lock(tmp_path: Any) -> None:
    target_holder: List[BlockingTarget] = []
    outbox_directory = tmp_path / "lock-test"

    class DeferredTarget:
        def notify(self, notification: Any) -> Result[None, dict[str, Any]]:
            target = BlockingTarget(outbox)
            target_holder.append(target)
            target.started.set()

            def observe() -> None:
                assert outbox.list_pending().is_ok()
                target.observer_completed.set()

            observer = threading.Thread(target=observe)
            observer.start()
            observer.join(timeout=1)
            target.release.set()
            return Result.ok(None)

    outbox = FileApprovalNotificationOutbox(outbox_directory, target=DeferredTarget())
    assert outbox.notify(
        ApprovalNotification.from_request(_approval_request(), "created")
    ).is_ok()

    report = outbox.drain().unwrap()

    assert report.delivered == 1
    assert target_holder[0].observer_completed.is_set()


def test_built_in_store_notifier_compatibility_remains_local(tmp_path: Any) -> None:
    approval_target = RecordingTarget()
    approval_outbox = FileApprovalNotificationOutbox(
        tmp_path / "approval", target=approval_target
    )
    approval_store = InMemoryApprovalStore(notifier=approval_outbox)
    assert approval_store.create(_approval_request("memory-approval")).is_ok()
    assert isinstance(approval_outbox.list_pending().unwrap()[0], ApprovalNotification)

    human_target = RecordingTarget()
    human_outbox = FileHumanInputNotificationOutbox(
        tmp_path / "human", target=human_target
    )
    human_store = FileHumanInputStore(tmp_path / "human-store", notifier=human_outbox)
    assert human_store.create(_human_request("file-input")).is_ok()
    assert isinstance(human_outbox.list_pending().unwrap()[0], HumanInputNotification)
