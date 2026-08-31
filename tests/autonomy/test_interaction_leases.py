"""Regression coverage for FileHumanInputStore cross-process ownership."""

from pathlib import Path

from maple.autonomy.interactions import FileHumanInputStore, HumanInputRequest
from maple.resources.lease import FileLeaseManager


def _request(interaction_id: str = "input-lease-1") -> HumanInputRequest:
    return HumanInputRequest(
        interaction_id=interaction_id,
        run_id="run-1",
        tool_call_id="call-input",
        prompt="Provide a code.",
        input_schema={"type": "object"},
    )


def test_file_human_input_store_fails_closed_when_record_lease_is_held(
    tmp_path: Path,
) -> None:
    store = FileHumanInputStore(tmp_path)
    assert store.create(_request()).is_ok()

    external_leases = FileLeaseManager(tmp_path / ".maple-leases")
    held = external_leases.acquire(
        "human-input:input-lease-1", "external-holder", 60
    ).unwrap()

    blocked = store.respond("input-lease-1", {"code": "blocked"})

    assert blocked.is_err()
    assert blocked.unwrap_err()["errorType"] == "HUMAN_INPUT_LEASE_ERROR"
    assert external_leases.release(held).unwrap() is True
    pending = store.get("input-lease-1").unwrap()
    assert pending is not None
    assert pending.status == "pending"
    assert pending.decision is None


def test_file_human_input_store_releases_record_lease_after_response(
    tmp_path: Path,
) -> None:
    first_store = FileHumanInputStore(tmp_path)
    second_store = FileHumanInputStore(tmp_path)
    assert first_store.create(_request()).is_ok()

    responded = second_store.respond("input-lease-1", {"code": "green"})
    consumed = first_store.consume("input-lease-1")

    assert responded.is_ok()
    assert consumed.is_ok()
    assert consumed.unwrap().status == "consumed"
