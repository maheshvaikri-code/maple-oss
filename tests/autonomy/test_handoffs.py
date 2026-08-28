"""Tests for bounded local handoff identity and ownership records."""

import asyncio
import hashlib
import threading

import pytest

from maple.autonomy.execution import CancellationToken
from maple.autonomy.handoffs import (
    FileHandoffStore,
    HandoffRecord,
    InMemoryHandoffStore,
)
from maple.autonomy.tools import create_agent_tool, create_handoff_tool
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


class CancellationAwareTarget:
    agent_id = "cooperative-specialist"

    def __init__(self):
        self.started = threading.Event()
        self.received_token = None

    def pursue_goal(self, description, *, cancellation=None):
        self.received_token = cancellation
        self.started.set()
        assert cancellation is not None
        cancellation.wait(2)
        return Result.ok(
            type(
                "Goal",
                (),
                {
                    "goal_id": "cancelled-child",
                    "status": "cancelled",
                    "result": None,
                },
            )()
        )


class AsyncCancellationAwareTarget:
    agent_id = "async-cooperative-specialist"

    def __init__(self):
        self.started = threading.Event()
        self.received_token = None

    async def pursue_goal(self, description, *, cancellation=None):
        self.received_token = cancellation
        self.started.set()
        assert cancellation is not None
        await asyncio.get_running_loop().run_in_executor(None, cancellation.wait, 2)
        return Result.ok(
            type(
                "Goal",
                (),
                {
                    "goal_id": "cancelled-child",
                    "status": "cancelled",
                    "result": None,
                },
            )()
        )

    async def pursue_goal_async(self, description, *, cancellation=None):
        return await self.pursue_goal(description, cancellation=cancellation)


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


def test_handoff_result_is_bounded_and_legacy_records_remain_loadable():
    store = InMemoryHandoffStore()
    assert store.create(make_record("handoff-result")).is_ok()
    assert store.accept("handoff-result", "target").is_ok()

    result = {"agent_id": "target", "goal_id": "goal-1", "status": "completed"}
    completed = store.complete("handoff-result", "target", "goal-1", result=result)

    assert completed.is_ok()
    assert completed.unwrap().result == result
    result["goal_id"] = "mutated-after-save"
    assert store.get("handoff-result").unwrap().result["goal_id"] == "goal-1"

    legacy_payload = completed.unwrap().to_dict()
    legacy_payload.pop("result")
    legacy = HandoffRecord.from_dict(legacy_payload)
    assert legacy.result is None

    oversized = store.complete(
        "handoff-result", "target", "goal-1", result={"value": "x" * 70_000}
    )
    assert oversized.is_err()
    assert oversized.unwrap_err()["errorType"] == "HANDOFF_RESULT_INVALID"

    cyclic = {}
    cyclic["self"] = cyclic
    assert store.create(make_record("handoff-recursive")).is_ok()
    assert store.accept("handoff-recursive", "target").is_ok()
    recursive = store.complete(
        "handoff-recursive",
        "target",
        "goal-1",
        result={"value": cyclic},
    )
    assert recursive.is_err()
    assert recursive.unwrap_err()["errorType"] == "HANDOFF_RESULT_INVALID"


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
    completed = restarted.complete(
        "handoff-file",
        "target",
        "goal-file",
        result={
            "agent_id": "target",
            "goal_id": "goal-file",
            "status": "completed",
            "result": {"answer": "persisted"},
        },
    )

    assert loaded.is_ok()
    assert loaded.unwrap().status == "accepted"
    assert loaded.unwrap().owner_id == "target"
    assert completed.is_ok()
    assert completed.unwrap().status == "completed"
    assert completed.unwrap().result["result"] == {"answer": "persisted"}
    assert (directory / "handoff-file.json").exists()
    assert "secret task" not in (directory / "handoff-file.json").read_text()

    after_restart = FileHandoffStore(directory).get("handoff-file")
    assert after_restart.is_ok()
    assert after_restart.unwrap().result == completed.unwrap().result


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
    assert store.get(payload["handoff_id"]).unwrap().result is None


def test_handoff_tool_replays_opt_in_persisted_result_without_reinvoking_target():
    class CountingTarget(HandoffTarget):
        def __init__(self):
            self.calls = 0

        def pursue_goal(self, description):
            self.calls += 1
            return super().pursue_goal(description)

    target = CountingTarget()
    store = InMemoryHandoffStore()
    tool = create_handoff_tool(
        target,
        requires_approval=False,
        handoff_store=store,
        source_agent_id="source",
        persist_result=True,
    )

    first = tool.execute(task="Research MAPLE", handoff_id="replay-sync")
    replay = tool.execute(task="Research MAPLE", handoff_id="replay-sync")

    assert first.is_ok()
    assert replay.is_ok()
    assert replay.unwrap() == first.unwrap()
    assert target.calls == 1
    stored_result = dict(first.unwrap())
    stored_result.pop("handoff_id")
    assert store.get("replay-sync").unwrap().result == stored_result
    assert tool.to_llm_definition().parameters["properties"]["handoff_id"] == {
        "type": "string",
        "maxLength": 256,
        "description": (
            "Optional caller-owned ID for replaying a completed persisted handoff."
        ),
    }


def test_handoff_tool_rejects_unsafe_stored_result_instead_of_replaying():
    store = InMemoryHandoffStore()
    matching_record = HandoffRecord.pending(
        "replay-invalid",
        "source",
        "specialist",
        hashlib.sha256(b'"Research MAPLE"').hexdigest(),
    )
    assert store.create(matching_record).is_ok()
    assert store.accept("replay-invalid", "specialist").is_ok()
    assert store.complete(
        "replay-invalid",
        "specialist",
        "goal-1",
        result={
            "agent_id": "specialist",
            "goal_id": "other-goal",
            "status": "completed",
        },
    ).is_ok()
    tool = create_handoff_tool(
        HandoffTarget(),
        requires_approval=False,
        handoff_store=store,
        source_agent_id="source",
        persist_result=True,
    )

    replay = tool.execute(task="Research MAPLE", handoff_id="replay-invalid")

    assert replay.is_err()
    assert replay.unwrap_err()["errorType"] == "HANDOFF_RESULT_INVALID"


def test_handoff_tool_rejects_result_replay_without_local_store():
    with pytest.raises(ValueError, match="handoff_store"):
        create_handoff_tool(HandoffTarget(), persist_result=True)

    tool = create_handoff_tool(HandoffTarget(), requires_approval=False)
    result = tool.execute(task="Research MAPLE", handoff_id="replay-without-store")
    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "HANDOFF_STORE_UNAVAILABLE"


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


def test_opt_in_handoff_replay_does_not_retry_failed_terminal_record():
    class FailingTarget(HandoffTarget):
        def __init__(self):
            self.calls = 0

        def pursue_goal(self, description):
            self.calls += 1
            return Result.err({"errorType": "TARGET_FAILURE"})

    target = FailingTarget()
    tool = create_handoff_tool(
        target,
        requires_approval=False,
        handoff_store=InMemoryHandoffStore(),
        source_agent_id="source",
        persist_result=True,
    )

    first = tool.execute(task="Research MAPLE", handoff_id="failed-replay")
    retry = tool.execute(task="Research MAPLE", handoff_id="failed-replay")

    assert first.is_err()
    assert first.unwrap_err()["errorType"] == "HANDOFF_TARGET_FAILED"
    assert retry.is_err()
    assert retry.unwrap_err()["errorType"] == "HANDOFF_ALREADY_FAILED"
    assert target.calls == 1


def test_opt_in_handoff_replay_does_not_retry_resultless_completed_record():
    store = InMemoryHandoffStore()
    first_tool = create_handoff_tool(
        HandoffTarget(),
        requires_approval=False,
        handoff_store=store,
        source_agent_id="source",
    )
    second_tool = create_handoff_tool(
        HandoffTarget(),
        requires_approval=False,
        handoff_store=store,
        source_agent_id="source",
        persist_result=True,
    )

    first = first_tool.execute(task="Research MAPLE", handoff_id="resultless-replay")
    retry = second_tool.execute(task="Research MAPLE", handoff_id="resultless-replay")

    assert first.is_ok()
    assert retry.is_err()
    assert retry.unwrap_err()["errorType"] == "HANDOFF_REPLAY_UNAVAILABLE"


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


@pytest.mark.asyncio
async def test_async_handoff_tool_replays_opt_in_persisted_result_without_reinvoking_target():
    class CountingAsyncTarget(AsyncHandoffTarget):
        def __init__(self):
            self.calls = 0

        def pursue_goal(self, description):
            self.calls += 1
            return super().pursue_goal(description)

    target = CountingAsyncTarget()
    store = InMemoryHandoffStore()
    tool = create_handoff_tool(
        target,
        requires_approval=False,
        handoff_store=store,
        source_agent_id="source",
        persist_result=True,
    )

    first = await tool.execute_async(task="Research MAPLE", handoff_id="replay-async")
    replay = await tool.execute_async(task="Research MAPLE", handoff_id="replay-async")

    assert first.is_ok()
    assert replay.is_ok()
    assert replay.unwrap() == first.unwrap()
    assert target.calls == 1


def test_agent_tool_propagates_cancellation_to_native_child():
    target = CancellationAwareTarget()
    token = CancellationToken()
    tool = create_agent_tool(target, requires_approval=False)
    outcome = []

    worker = threading.Thread(
        target=lambda: outcome.append(tool.execute(cancellation=token, task="stop"))
    )
    worker.start()
    assert target.started.wait(1)
    token.cancel()
    worker.join(timeout=2)

    assert not worker.is_alive()
    assert target.received_token is token
    assert len(outcome) == 1
    assert outcome[0].is_err()
    assert outcome[0].unwrap_err()["errorType"] == "EXECUTION_CANCELLED"


def test_handoff_tool_propagates_cancellation_to_native_child():
    target = CancellationAwareTarget()
    token = CancellationToken()
    tool = create_handoff_tool(target, requires_approval=False)
    outcome = []

    worker = threading.Thread(
        target=lambda: outcome.append(tool.execute(cancellation=token, task="stop"))
    )
    worker.start()
    assert target.started.wait(1)
    token.cancel()
    worker.join(timeout=2)

    assert not worker.is_alive()
    assert target.received_token is token
    assert len(outcome) == 1
    assert outcome[0].is_err()
    assert outcome[0].unwrap_err()["errorType"] == "EXECUTION_CANCELLED"


def test_cancelled_handoff_finalizes_durable_record_as_failed():
    target = CancellationAwareTarget()
    token = CancellationToken()
    store = InMemoryHandoffStore()
    tool = create_handoff_tool(
        target,
        requires_approval=False,
        handoff_store=store,
        source_agent_id="source",
        persist_result=True,
    )
    outcome = []

    worker = threading.Thread(
        target=lambda: outcome.append(
            tool.execute(
                cancellation=token,
                task="stop",
                handoff_id="cancelled-replay",
            )
        )
    )
    worker.start()
    assert target.started.wait(1)
    token.cancel()
    worker.join(timeout=2)

    assert not worker.is_alive()
    assert len(outcome) == 1
    assert outcome[0].is_err()
    handoff_id = outcome[0].unwrap_err()["details"]["handoff_id"]
    record = store.get(handoff_id).unwrap()
    assert record is not None
    assert record.status == "failed"
    assert record.error_type == "EXECUTION_CANCELLED"
    retry = tool.execute(task="stop", handoff_id="cancelled-replay")
    assert retry.is_err()
    assert retry.unwrap_err()["errorType"] == "HANDOFF_ALREADY_FAILED"


def test_legacy_handoff_target_remains_compatible_with_parent_token():
    token = CancellationToken()
    tool = create_handoff_tool(HandoffTarget(), requires_approval=False)

    result = tool.execute(cancellation=token, task="legacy")

    assert result.is_ok()
    assert result.unwrap()["status"] == "completed"


@pytest.mark.asyncio
async def test_async_agent_tool_propagates_cancellation_to_native_child():
    target = AsyncCancellationAwareTarget()
    token = CancellationToken()
    tool = create_agent_tool(target, requires_approval=False)
    running = asyncio.create_task(tool.execute_async(cancellation=token, task="stop"))

    assert await asyncio.get_running_loop().run_in_executor(
        None, target.started.wait, 1
    )
    token.cancel()
    result = await running

    assert target.received_token is token
    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "EXECUTION_CANCELLED"


@pytest.mark.asyncio
async def test_async_handoff_tool_propagates_cancellation_to_native_child():
    target = AsyncCancellationAwareTarget()
    token = CancellationToken()
    tool = create_handoff_tool(target, requires_approval=False)
    running = asyncio.create_task(tool.execute_async(cancellation=token, task="stop"))

    assert await asyncio.get_running_loop().run_in_executor(
        None, target.started.wait, 1
    )
    token.cancel()
    result = await running

    assert target.received_token is token
    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "EXECUTION_CANCELLED"
