"""Tests for durable approval request and decision storage."""

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

    decided = store.decide("approval-1", approved=True)
    assert decided.is_ok()
    assert decided.unwrap().status == "approved"
    assert decided.unwrap().decision.approved is True

    consumed = store.consume("approval-1")
    assert consumed.is_ok()
    assert consumed.unwrap().status == "consumed"

    replay = store.consume("approval-1")
    assert replay.is_err()
    assert replay.unwrap_err()["errorType"] == "APPROVAL_NOT_APPROVED"


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
    assert first_store.decide("approval-1", approved=True).is_ok()

    restarted_store = FileApprovalStore(tmp_path)
    loaded = restarted_store.get("approval-1")

    assert loaded.is_ok()
    assert loaded.unwrap().status == "approved"
    assert loaded.unwrap().decision.approved is True

    consumed = restarted_store.consume("approval-1")
    assert consumed.is_ok()
    assert consumed.unwrap().status == "consumed"


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
