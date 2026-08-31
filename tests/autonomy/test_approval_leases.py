"""Regression coverage for FileApprovalStore cross-process ownership."""

from pathlib import Path

from maple.autonomy.approval import ApprovalRequest, FileApprovalStore
from maple.resources.lease import FileLeaseManager


def _request(approval_id: str = "approval-lease-1") -> ApprovalRequest:
    return ApprovalRequest(
        approval_id=approval_id,
        tool_call_id="call-1",
        tool_name="write_state",
        arguments={"key": "status", "value": "ready"},
    )


def test_file_approval_store_fails_closed_when_record_lease_is_held(
    tmp_path: Path,
) -> None:
    store = FileApprovalStore(tmp_path)
    assert store.create(_request()).is_ok()

    external_leases = FileLeaseManager(tmp_path / ".maple-leases")
    held = external_leases.acquire(
        "approval:approval-lease-1", "external-holder", 60
    ).unwrap()

    blocked = store.decide("approval-lease-1", approved=True)

    assert blocked.is_err()
    assert blocked.unwrap_err()["errorType"] == "APPROVAL_LEASE_ERROR"
    assert external_leases.release(held).unwrap() is True
    pending = store.get("approval-lease-1").unwrap()
    assert pending is not None
    assert pending.status == "pending"
    assert pending.decision is None


def test_file_approval_store_releases_record_lease_after_decision(
    tmp_path: Path,
) -> None:
    first_store = FileApprovalStore(tmp_path)
    second_store = FileApprovalStore(tmp_path)
    assert first_store.create(_request()).is_ok()

    decided = second_store.decide("approval-lease-1", approved=True)
    consumed = first_store.consume("approval-lease-1")

    assert decided.is_ok()
    assert consumed.is_ok()
    assert consumed.unwrap().status == "consumed"
