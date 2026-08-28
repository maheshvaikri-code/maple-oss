"""Regression coverage for FileAgentRunStore cross-process ownership."""

from pathlib import Path
from typing import Optional

from maple.autonomy.runs import AgentRunCheckpoint, FileAgentRunStore
from maple.autonomy.sessions import SessionMessage
from maple.resources.lease import FileLeaseManager


def _checkpoint(
    run_id: str = "run-lease-1",
    *,
    status: str = "running",
    pending_approval_id: Optional[str] = None,
) -> AgentRunCheckpoint:
    return AgentRunCheckpoint(
        run_id=run_id,
        agent_id="agent-1",
        description="Lease a durable run",
        status=status,
        messages=(SessionMessage(role="user", content="hello"),),
        reasoning_steps=(),
        step_count=0,
        pending_approval_id=pending_approval_id,
        token_usage={"total_tokens": 0},
    )


def test_file_run_store_fails_closed_when_run_lease_is_held(tmp_path: Path) -> None:
    store = FileAgentRunStore(tmp_path)
    saved = store.save(_checkpoint())
    assert saved.is_ok()

    external_leases = FileLeaseManager(tmp_path / ".maple-leases")
    held = external_leases.acquire("run:run-lease-1", "external-holder", 60).unwrap()

    blocked_load = store.load("run-lease-1")
    blocked_save = store.save(
        _checkpoint(status="paused", pending_approval_id="approval-1"),
        expected_version=1,
    )

    assert blocked_load.is_err()
    assert blocked_load.unwrap_err()["errorType"] == "RUN_CHECKPOINT_LEASE_ERROR"
    assert blocked_save.is_err()
    assert blocked_save.unwrap_err()["errorType"] == "RUN_CHECKPOINT_LEASE_ERROR"
    assert external_leases.release(held).unwrap() is True
    loaded = store.load("run-lease-1").unwrap()
    assert loaded is not None
    assert loaded.status == "running"
    assert loaded.version == 1


def test_file_run_store_releases_run_lease_after_compare_and_set_save(
    tmp_path: Path,
) -> None:
    first_store = FileAgentRunStore(tmp_path)
    second_store = FileAgentRunStore(tmp_path)
    assert first_store.save(_checkpoint()).is_ok()

    updated = second_store.save(
        _checkpoint(status="paused", pending_approval_id="approval-1"),
        expected_version=1,
    )
    loaded = first_store.load("run-lease-1")

    assert updated.is_ok()
    assert loaded.is_ok()
    assert loaded.unwrap() is not None
    assert loaded.unwrap().status == "paused"
    assert loaded.unwrap().version == 2
