"""Tests for durable approval request and decision storage."""

import pytest

from maple.autonomy.approval import (
    ApprovalRequest,
    FileApprovalStore,
    InMemoryApprovalStore,
)


def _request(approval_id="approval-1"):
    return ApprovalRequest(
        approval_id=approval_id,
        tool_call_id="call-1",
        tool_name="write_state",
        arguments={"key": "status", "value": "ready"},
    )


def test_in_memory_approval_lifecycle_is_single_use():
    store = InMemoryApprovalStore()

    created = store.create(_request())
    assert created.is_ok()
    assert created.unwrap().status == "pending"
    assert [item.approval_id for item in store.list_pending().unwrap()] == [
        "approval-1"
    ]

    decided = store.decide(
        "approval-1",
        approved=True,
        edited_arguments={"key": "status", "value": "edited"},
    )
    assert decided.is_ok()
    assert decided.unwrap().status == "approved"
    assert decided.unwrap().decision.approved is True
    assert decided.unwrap().decision.edited_arguments == {
        "key": "status",
        "value": "edited",
    }

    consumed = store.consume("approval-1")
    assert consumed.is_ok()
    assert consumed.unwrap().status == "consumed"

    replay = store.consume("approval-1")
    assert replay.is_err()
    assert replay.unwrap_err()["errorType"] == "APPROVAL_NOT_APPROVED"


def test_in_memory_approval_execution_outcome_is_bounded_and_idempotent():
    store = InMemoryApprovalStore()
    assert store.create(_request()).is_ok()
    assert store.decide("approval-1", approved=True).is_ok()
    assert store.consume("approval-1").is_ok()

    recorded = store.record_execution(
        "approval-1", {"content": '{"ok": true}', "is_error": False}
    )
    replayed = store.record_execution(
        "approval-1", {"content": '{"ok": true}', "is_error": False}
    )
    conflict = store.record_execution(
        "approval-1", {"content": '{"ok": false}', "is_error": False}
    )
    oversized = store.record_execution(
        "approval-1", {"content": "x" * 131_073, "is_error": False}
    )

    assert recorded.is_ok()
    assert recorded.unwrap().execution_result == {
        "content": '{"ok": true}',
        "is_error": False,
    }
    assert replayed.is_ok()
    assert conflict.is_err()
    assert conflict.unwrap_err()["errorType"] == "APPROVAL_EXECUTION_CONFLICT"
    assert oversized.is_err()
    assert oversized.unwrap_err()["errorType"] == "APPROVAL_EXECUTION_TOO_LARGE"


def test_decision_conflict_and_invalid_list_limit_fail_closed():
    store = InMemoryApprovalStore()
    assert store.create(_request()).is_ok()
    assert store.decide("approval-1", approved=False).is_ok()

    conflict = store.decide("approval-1", approved=True)
    invalid_limit = store.list_pending(limit=0)

    assert conflict.is_err()
    assert conflict.unwrap_err()["errorType"] == "APPROVAL_CONFLICT"
    assert invalid_limit.is_err()
    assert invalid_limit.unwrap_err()["errorType"] == "APPROVAL_LIMIT_INVALID"


def test_file_approval_survives_store_recreation(tmp_path):
    first_store = FileApprovalStore(tmp_path)
    assert first_store.create(_request()).is_ok()
    assert first_store.decide(
        "approval-1", approved=True, edited_arguments={"value": "edited"}
    ).is_ok()

    restarted_store = FileApprovalStore(tmp_path)
    loaded = restarted_store.get("approval-1")

    assert loaded.is_ok()
    assert loaded.unwrap().status == "approved"
    assert loaded.unwrap().decision.approved is True
    assert loaded.unwrap().decision.edited_arguments == {"value": "edited"}

    consumed = restarted_store.consume("approval-1")
    assert consumed.is_ok()
    assert consumed.unwrap().status == "consumed"
    assert restarted_store.record_execution(
        "approval-1", {"content": '{"ok": true}', "is_error": False}
    ).is_ok()

    replayed_store = FileApprovalStore(tmp_path)
    replayed = replayed_store.get("approval-1")
    assert replayed.is_ok()
    assert replayed.unwrap().execution_result == {
        "content": '{"ok": true}',
        "is_error": False,
    }


def test_approval_trace_correlation_survives_round_trip_and_file_restart(tmp_path):
    request = ApprovalRequest(
        approval_id="approval-correlated",
        tool_call_id="call-1",
        tool_name="write_state",
        arguments={"key": "status"},
        trace_id="trace-123",
        span_id="span-456",
    )
    encoded = request.to_dict()
    decoded = ApprovalRequest.from_dict(encoded)
    store = FileApprovalStore(tmp_path)
    assert store.create(request).is_ok()
    restarted = store.get("approval-correlated")

    assert decoded.trace_id == "trace-123"
    assert decoded.span_id == "span-456"
    assert restarted.is_ok()
    assert restarted.unwrap().trace_id == "trace-123"
    assert restarted.unwrap().span_id == "span-456"


def test_invalid_approval_trace_correlation_is_rejected():
    with pytest.raises(ValueError):
        ApprovalRequest(
            approval_id="approval-invalid-trace",
            tool_call_id="call-1",
            tool_name="write_state",
            arguments={},
            trace_id="bad\ntrace",
        )


def test_invalid_arguments_are_rejected_before_persistence():
    store = InMemoryApprovalStore()
    invalid = store.create(
        ApprovalRequest(
            approval_id="approval-1",
            tool_call_id="call-1",
            tool_name="write_state",
            arguments={"bad": object()},
        )
    )

    assert invalid.is_err()
    assert invalid.unwrap_err()["errorType"] == "APPROVAL_INVALID"
    assert store.get("approval-1").unwrap() is None


def test_invalid_or_denied_edits_leave_in_memory_request_pending():
    store = InMemoryApprovalStore()
    assert store.create(_request()).is_ok()

    invalid = store.decide(
        "approval-1", approved=True, edited_arguments={"bad": object()}
    )
    denied_with_edit = store.decide(
        "approval-1", approved=False, edited_arguments={"value": "blocked"}
    )
    pending = store.get("approval-1").unwrap()

    assert invalid.is_err()
    assert invalid.unwrap_err()["errorType"] == "APPROVAL_DECISION_INVALID"
    assert denied_with_edit.is_err()
    assert denied_with_edit.unwrap_err()["errorType"] == "APPROVAL_DECISION_INVALID"
    assert pending is not None
    assert pending.status == "pending"
    assert pending.decision is None


def test_oversized_file_edit_is_rejected_without_rewriting_record(tmp_path):
    store = FileApprovalStore(tmp_path)
    assert store.create(_request()).is_ok()

    invalid = store.decide(
        "approval-1", approved=True, edited_arguments={"value": "x" * 70_000}
    )
    loaded = FileApprovalStore(tmp_path).get("approval-1").unwrap()

    assert invalid.is_err()
    assert invalid.unwrap_err()["errorType"] == "APPROVAL_DECISION_INVALID"
    assert loaded is not None
    assert loaded.status == "pending"
    assert loaded.decision is None
