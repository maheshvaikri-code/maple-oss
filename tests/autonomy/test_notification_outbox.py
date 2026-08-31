"""Regression coverage for bounded durable notification outboxes."""

from __future__ import annotations

import json
import threading
from typing import Any, Dict, List

import pytest

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
from maple.resources.lease import FileLeaseManager


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


def test_outbox_enforces_record_and_queue_byte_bounds(tmp_path: Any) -> None:
    notification = ApprovalNotification.from_request(
        _approval_request("bounded"), "created"
    )
    too_small_record = FileApprovalNotificationOutbox(
        tmp_path / "record", target=RecordingTarget(), max_record_bytes=64
    )
    oversized = too_small_record.notify(notification)

    assert oversized.is_err()
    assert oversized.unwrap_err()["errorType"] == "NOTIFICATION_OUTBOX_RECORD_TOO_LARGE"

    too_small_queue = FileApprovalNotificationOutbox(
        tmp_path / "queue", target=RecordingTarget(), max_queue_bytes=1
    )
    full = too_small_queue.notify(notification)

    assert full.is_err()
    assert full.unwrap_err()["errorType"] == "NOTIFICATION_OUTBOX_FULL"
    assert list((tmp_path / "queue").glob("*.json")) == []


def test_outbox_limits_are_typed_and_bounded(tmp_path: Any) -> None:
    outbox = FileApprovalNotificationOutbox(tmp_path, target=RecordingTarget())

    assert (
        outbox.list_pending(limit=0).unwrap_err()["errorType"]
        == "NOTIFICATION_OUTBOX_LIMIT_INVALID"
    )
    assert (
        outbox.drain(max_items=1_001).unwrap_err()["errorType"]
        == "NOTIFICATION_OUTBOX_DRAIN_LIMIT_INVALID"
    )


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


def test_optional_file_lease_fences_competing_outbox_drainers(tmp_path: Any) -> None:
    lease_root = tmp_path / "leases"
    outbox_directory = tmp_path / "outbox"
    first_manager = FileLeaseManager(lease_root)
    second_manager = FileLeaseManager(lease_root)
    first_started = threading.Event()
    release_target = threading.Event()

    class HoldingTarget:
        def __init__(self) -> None:
            self.notifications: List[Any] = []

        def notify(self, notification: Any) -> Result[None, Dict[str, Any]]:
            self.notifications.append(notification)
            first_started.set()
            assert release_target.wait(timeout=2)
            return Result.ok(None)

    first_target = HoldingTarget()
    second_target = RecordingTarget()
    first_outbox = FileApprovalNotificationOutbox(
        outbox_directory,
        target=first_target,
        lease_manager=first_manager,
        lease_ttl_seconds=10,
    )
    second_outbox = FileApprovalNotificationOutbox(
        outbox_directory,
        target=second_target,
        lease_manager=second_manager,
        lease_ttl_seconds=10,
    )
    notification = ApprovalNotification.from_request(_approval_request(), "created")
    assert first_outbox.notify(notification).is_ok()

    first_result: List[Result[Any, Dict[str, Any]]] = []
    drain_thread = threading.Thread(
        target=lambda: first_result.append(first_outbox.drain())
    )
    drain_thread.start()
    assert first_started.wait(timeout=2)

    denied = second_outbox.drain()

    assert denied.is_err()
    assert denied.unwrap_err()["errorType"] == "NOTIFICATION_OUTBOX_DRAIN_UNAVAILABLE"
    assert second_target.notifications == []
    release_target.set()
    drain_thread.join(timeout=2)
    assert not drain_thread.is_alive()
    assert first_result[0].is_ok()
    assert first_result[0].unwrap().delivered == 1


def test_outbox_drain_release_failure_preserves_committed_report(
    tmp_path: Any,
) -> None:
    class ReleaseFailureManager:
        def acquire(
            self, resource: str, holder: str, ttl_seconds: float
        ) -> Result[Any, Any]:
            return Result.ok(object())

        def release(self, lease: Any) -> Result[bool, Any]:
            return Result.ok(False)

    target = RecordingTarget()
    outbox = FileApprovalNotificationOutbox(
        tmp_path / "release-failure",
        target=target,
        lease_manager=ReleaseFailureManager(),  # type: ignore[arg-type]
    )
    assert outbox.notify(
        ApprovalNotification.from_request(_approval_request("release"), "created")
    ).is_ok()

    result = outbox.drain()

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == (
        "NOTIFICATION_OUTBOX_DRAIN_LEASE_RELEASE_ERROR"
    )
    assert result.unwrap_err()["details"]["drain_report"]["delivered"] == 1
    assert target.notifications
    assert outbox.list_pending().unwrap() == []


def test_outbox_release_failure_is_attached_to_typed_drain_error(
    tmp_path: Any,
) -> None:
    class ReleaseFailureManager:
        def acquire(
            self, resource: str, holder: str, ttl_seconds: float
        ) -> Result[Any, Any]:
            return Result.ok(object())

        def release(self, lease: Any) -> Result[bool, Any]:
            return Result.ok(False)

    directory = tmp_path / "invalid-release"
    directory.mkdir()
    invalid_record = directory / "invalid.json"
    invalid_record.write_text("{}", encoding="utf-8")
    outbox = FileApprovalNotificationOutbox(
        directory,
        target=RecordingTarget(),
        lease_manager=ReleaseFailureManager(),  # type: ignore[arg-type]
    )

    result = outbox.drain()

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "NOTIFICATION_OUTBOX_RECORD_INVALID"
    assert result.unwrap_err()["details"]["lease_release_error"] == (
        "NOTIFICATION_OUTBOX_DRAIN_LEASE_RELEASE_ERROR"
    )


def test_outbox_drain_lease_ttl_is_finite_and_bounded(tmp_path: Any) -> None:
    with pytest.raises(ValueError):
        FileApprovalNotificationOutbox(
            tmp_path / "zero", target=RecordingTarget(), lease_ttl_seconds=0
        )
    with pytest.raises(ValueError):
        FileApprovalNotificationOutbox(
            tmp_path / "too-large",
            target=RecordingTarget(),
            lease_ttl_seconds=604_800.1,
        )


def test_outbox_drain_lease_storage_failure_is_typed_and_does_not_target(
    tmp_path: Any,
) -> None:
    class AcquisitionFailureManager:
        def acquire(
            self, resource: str, holder: str, ttl_seconds: float
        ) -> Result[Any, Any]:
            return Result.err({"errorType": "LEASE_STORAGE_ERROR"})

        def release(self, lease: Any) -> Result[bool, Any]:
            return Result.ok(True)

    target = RecordingTarget()
    outbox = FileApprovalNotificationOutbox(
        tmp_path / "acquisition-failure",
        target=target,
        lease_manager=AcquisitionFailureManager(),  # type: ignore[arg-type]
    )
    assert outbox.notify(
        ApprovalNotification.from_request(_approval_request("acquire"), "created")
    ).is_ok()

    result = outbox.drain()

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "NOTIFICATION_OUTBOX_DRAIN_LEASE_ERROR"
    assert target.notifications == []
