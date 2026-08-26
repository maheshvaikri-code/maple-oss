"""Tests for bounded local handoff identity and ownership records."""

import pytest

from maple.autonomy.handoffs import (
    FileHandoffStore,
    HandoffRecord,
    InMemoryHandoffStore,
)
from maple.autonomy.tools import create_handoff_tool
from maple.core.result import Result


class HandoffTarget:
    agent_id = "specialist"

    def pursue_goal(self, description):
        return Result.ok(
            type(
                "Goal",
                (),
                {
                    "goal_id": "goal-1",
                    "status": "completed",
                    "result": {"answer": description.upper()},
                },
            )()
        )


class AsyncHandoffTarget(HandoffTarget):
    async def pursue_goal_async(self, description):
        return self.pursue_goal(description)


def make_record(handoff_id="handoff-1"):
    return HandoffRecord.pending(
        handoff_id,
        "source",
        "target",
        "a" * 64,
        "b" * 64,
    )


def test_in_memory_handoff_transfers_and_returns_ownership():
    store = InMemoryHandoffStore()

    created = store.create(make_record())
    accepted = store.accept("handoff-1", "target")
    wrong_owner = store.complete("handoff-1", "other", "goal-1")
    completed = store.complete("handoff-1", "target", "goal-1")

    assert created.is_ok()
    assert created.unwrap().status == "pending"
    assert created.unwrap().owner_id == "source"
    assert accepted.is_ok()
    assert accepted.unwrap().status == "accepted"
    assert accepted.unwrap().owner_id == "target"
    assert wrong_owner.is_err()
    assert wrong_owner.unwrap_err()["errorType"] == "HANDOFF_OWNER_ERROR"
    assert completed.is_ok()
    assert completed.unwrap().status == "completed"
    assert completed.unwrap().owner_id == "source"
    assert completed.unwrap().target_goal_id == "goal-1"
    assert store.list_open().unwrap() == []


def test_in_memory_handoff_failure_is_terminal_and_one_time():
    store = InMemoryHandoffStore()
    assert store.create(make_record("handoff-fail")).is_ok()
    assert store.accept("handoff-fail", "target").is_ok()

    failed = store.fail("handoff-fail", "target", "HANDOFF_TARGET_ERROR")
    repeated = store.fail("handoff-fail", "target", "OTHER")
    loaded = store.get("handoff-fail")

    assert failed.is_ok()
    assert failed.unwrap().status == "failed"
    assert failed.unwrap().owner_id == "source"
    assert failed.unwrap().error_type == "HANDOFF_TARGET_ERROR"
    assert repeated.is_err()
    assert repeated.unwrap_err()["errorType"] == "HANDOFF_STATE_CONFLICT"
    assert loaded.unwrap().status == "failed"


def test_file_handoff_store_survives_restart_and_uses_atomic_records(tmp_path):
    directory = tmp_path / "handoffs"
    first = FileHandoffStore(directory)
    assert first.create(make_record("handoff-file")).is_ok()
    assert first.accept("handoff-file", "target").is_ok()

    restarted = FileHandoffStore(directory)
    loaded = restarted.get("handoff-file")
    completed = restarted.complete("handoff-file", "target", "goal-file")

    assert loaded.is_ok()
    assert loaded.unwrap().status == "accepted"
    assert loaded.unwrap().owner_id == "target"
    assert completed.is_ok()
    assert completed.unwrap().status == "completed"
    assert (directory / "handoff-file.json").exists()
    assert "secret task" not in (directory / "handoff-file.json").read_text()


def test_handoff_tool_persists_identity_and_returns_handoff_id():
    store = InMemoryHandoffStore()
    tool = create_handoff_tool(
        HandoffTarget(),
        requires_approval=False,
        handoff_store=store,
        source_agent_id="source",
    )

    result = tool.execute(task="Research MAPLE")

    assert result.is_ok()
    payload = result.unwrap()
    assert isinstance(payload["handoff_id"], str)
    assert store.get(payload["handoff_id"]).unwrap().status == "completed"
    assert store.get(payload["handoff_id"]).unwrap().owner_id == "source"


def test_handoff_tool_marks_target_failure_without_leaking_error():
    class FailingTarget(HandoffTarget):
        def pursue_goal(self, description):
            return Result.err(
                {"errorType": "TARGET_FAILURE", "message": "private response"}
            )

    store = InMemoryHandoffStore()
    tool = create_handoff_tool(
        FailingTarget(),
        requires_approval=False,
        handoff_store=store,
        source_agent_id="source",
    )

    result = tool.execute(task="Research MAPLE")

    assert result.is_err()
    error = result.unwrap_err()
    handoff_id = error["details"]["handoff_id"]
    assert error["errorType"] == "HANDOFF_TARGET_FAILED"
    assert "private response" not in str(error)
    assert store.get(handoff_id).unwrap().status == "failed"


@pytest.mark.asyncio
async def test_async_handoff_persists_ownership_without_blocking_target_dispatch():
    store = InMemoryHandoffStore()
    tool = create_handoff_tool(
        AsyncHandoffTarget(),
        requires_approval=False,
        handoff_store=store,
        source_agent_id="source",
    )

    result = await tool.execute_async(task="Research MAPLE")

    assert result.is_ok()
    handoff_id = result.unwrap()["handoff_id"]
    assert store.get(handoff_id).unwrap().status == "completed"
