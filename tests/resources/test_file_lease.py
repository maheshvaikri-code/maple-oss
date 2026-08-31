"""Regression coverage for the cross-process durable lease boundary."""

import subprocess
import sys
from pathlib import Path

import pytest

from maple.resources.lease import FileLeaseManager


class _Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def test_file_lease_persists_state_and_fences_stale_holder(
    tmp_path: Path,
) -> None:
    root = tmp_path / "leases"
    first_manager = FileLeaseManager(root)
    lease = first_manager.acquire("device-1", "agent-a", 60).unwrap()

    restarted_manager = FileLeaseManager(root)
    assert restarted_manager.is_valid(lease) is True
    blocked = restarted_manager.acquire("device-1", "agent-b", 60)
    assert blocked.unwrap_err()["errorType"] == "RESOURCE_HELD"

    assert restarted_manager.release(lease).unwrap() is True
    replacement = restarted_manager.acquire("device-1", "agent-b", 60).unwrap()
    assert replacement.token > lease.token
    assert first_manager.release(lease).unwrap() is False
    assert restarted_manager.holder_of("device-1") == "agent-b"


def test_file_lease_expiry_allows_reacquisition_with_new_fence(
    tmp_path: Path,
) -> None:
    clock = _Clock()
    manager = FileLeaseManager(tmp_path / "leases", clock=clock)
    lease = manager.acquire("device-1", "agent-a", 10).unwrap()

    clock.now = 111.0
    replacement = manager.acquire("device-1", "agent-b", 10).unwrap()

    assert replacement.token > lease.token
    assert manager.is_valid(lease) is False
    assert manager.is_valid(replacement) is True


def test_file_lease_state_is_shared_with_a_child_process(tmp_path: Path) -> None:
    root = tmp_path / "leases"
    manager = FileLeaseManager(root)
    manager.acquire("device-1", "agent-a", 60).unwrap()
    script = (
        "import sys; "
        "from maple.resources.lease import FileLeaseManager; "
        "result = FileLeaseManager(sys.argv[1]).acquire('device-1', 'agent-b', 60); "
        "print(result.unwrap_err()['errorType'] if result.is_err() else 'ACQUIRED')"
    )

    completed = subprocess.run(
        [sys.executable, "-c", script, str(root)],
        cwd=str(Path.cwd()),
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )

    assert completed.stdout.strip() == "RESOURCE_HELD"


def test_file_lease_corrupt_state_fails_closed(tmp_path: Path) -> None:
    root = tmp_path / "leases"
    manager = FileLeaseManager(root)
    manager.acquire("device-1", "agent-a", 60).unwrap()
    state_path = next(root.glob("*.json"))
    state_path.write_text("{", encoding="utf-8")

    result = manager.acquire("device-1", "agent-b", 60)

    assert result.unwrap_err()["errorType"] == "LEASE_STORAGE_ERROR"
    assert manager.holder_of("device-1") is None


def test_file_lease_rejects_unbounded_inputs(tmp_path: Path) -> None:
    manager = FileLeaseManager(tmp_path / "leases")

    assert manager.acquire("", "agent-a", 60).unwrap_err()["errorType"] == (
        "INVALID_RESOURCE_OR_HOLDER"
    )
    assert manager.acquire("device-1", "agent-a", 0).unwrap_err()["errorType"] == (
        "INVALID_TTL"
    )
    with pytest.raises(ValueError):
        FileLeaseManager(tmp_path / "other", lock_timeout_seconds=0)
