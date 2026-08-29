"""Tests for MAPLE's native workflow and checkpoint boundary."""

import json
import threading

import pytest

from maple.autonomy import (
    FileCheckpointStore,
    HistoryCheckpointStore,
    InMemoryCheckpointStore,
    RetryPolicy,
    Workflow,
    WorkflowPause,
)
from maple.core.result import Result


def _build_linear_workflow(store, calls):
    workflow = Workflow("approval_flow", checkpoint_store=store)

    def start(context):
        calls.append("start")
        return {"prepared": True}

    def approval(context):
        calls.append("approval")
        if context.resume_value is None:
            raise WorkflowPause({"question": "approve?"})
        return {"approved": context.resume_value}

    def finish(context):
        calls.append("finish")
        return {"finished": True}

    assert workflow.add_node("start", start).is_ok()
    assert workflow.add_node("approval", approval).is_ok()
    assert workflow.add_node("finish", finish).is_ok()
    assert workflow.set_entry_point("start").is_ok()
    assert workflow.add_edge("start", "approval").is_ok()
    assert workflow.add_edge("approval", "finish").is_ok()
    assert workflow.add_edge("finish").is_ok()
    return workflow


def test_workflow_pauses_and_resumes_without_rerunning_completed_nodes():
    calls = []
    store = InMemoryCheckpointStore()
    workflow = _build_linear_workflow(store, calls)

    first = workflow.run({"request": "demo"}, run_id="run-1")

    assert first.is_ok()
    paused = first.unwrap()
    assert paused.status == "interrupted"
    assert paused.completed_nodes == ["start"]
    assert paused.interrupt_payload == {"question": "approve?"}
    assert calls == ["start", "approval"]

    resumed = workflow.resume("run-1", resume_value="yes")

    assert resumed.is_ok()
    completed = resumed.unwrap()
    assert completed.status == "completed"
    assert completed.state == {
        "request": "demo",
        "prepared": True,
        "approved": "yes",
        "finished": True,
    }
    assert completed.completed_nodes == ["start", "approval", "finish"]
    assert calls == ["start", "approval", "approval", "finish"]


def test_file_checkpoint_survives_store_recreation(tmp_path):
    calls = []
    first_store = FileCheckpointStore(tmp_path)
    workflow = _build_linear_workflow(first_store, calls)

    first = workflow.run({}, run_id="file-run")
    assert first.is_ok()
    assert first.unwrap().status == "interrupted"

    restarted_store = FileCheckpointStore(tmp_path)
    resumed = workflow.resume(
        "file-run", resume_value=True, checkpoint_store=restarted_store
    )

    assert resumed.is_ok()
    assert resumed.unwrap().status == "completed"
    assert resumed.unwrap().checkpoint_version >= 5


def test_conditional_route_sees_node_updates():
    workflow = Workflow("routing")
    assert workflow.add_node("classify", lambda context: {"route": "right"}).is_ok()
    assert workflow.add_node("left", lambda context: {"selected": "left"}).is_ok()
    assert workflow.add_node("right", lambda context: {"selected": "right"}).is_ok()
    assert workflow.set_entry_point("classify").is_ok()
    assert workflow.add_conditional_edges(
        "classify",
        lambda state: state["route"],
        {"left": "left", "right": "right"},
    ).is_ok()
    assert workflow.add_edge("left").is_ok()
    assert workflow.add_edge("right").is_ok()

    result = workflow.run({})

    assert result.is_ok()
    assert result.unwrap().state["selected"] == "right"


def test_invalid_graph_rejects_unreachable_nodes():
    workflow = Workflow("invalid")
    assert workflow.add_node("entry", lambda context: None).is_ok()
    assert workflow.add_node("orphan", lambda context: None).is_ok()
    assert workflow.set_entry_point("entry").is_ok()

    result = workflow.run({})

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "UNREACHABLE_NODE"


def test_duplicate_run_id_is_rejected():
    store = InMemoryCheckpointStore()
    workflow = Workflow("single", checkpoint_store=store)
    assert workflow.add_node("only", lambda context: {"ok": True}).is_ok()
    assert workflow.set_entry_point("only").is_ok()

    assert workflow.run({}, run_id="same").is_ok()
    duplicate = workflow.run({}, run_id="same")

    assert duplicate.is_err()
    assert duplicate.unwrap_err()["errorType"] == "RUN_ID_EXISTS"


def test_explicit_empty_run_id_is_rejected_without_creating_a_checkpoint():
    store = InMemoryCheckpointStore()
    workflow = Workflow("explicit_id", checkpoint_store=store)
    assert workflow.add_node("only", lambda context: {"ok": True}).is_ok()
    assert workflow.set_entry_point("only").is_ok()

    invalid = workflow.run({}, run_id="")

    assert invalid.is_err()
    assert invalid.unwrap_err()["errorType"] == "INVALID_IDENTIFIER"
    assert workflow.run({}, run_id="after-empty").is_ok()


def test_node_result_error_is_checkpointed_as_failed():
    store = InMemoryCheckpointStore()
    workflow = Workflow("failure", checkpoint_store=store)
    assert workflow.add_node(
        "broken",
        lambda context: Result.err(
            {"errorType": "DEPENDENCY_DOWN", "message": "try later"}
        ),
    ).is_ok()
    assert workflow.set_entry_point("broken").is_ok()

    result = workflow.run({})

    assert result.is_ok()
    assert result.unwrap().status == "failed"
    assert result.unwrap().error["errorType"] == "DEPENDENCY_DOWN"
    checkpoint = store.load(result.unwrap().run_id).unwrap()
    assert checkpoint.status == "failed"


def test_node_retry_policy_retries_with_bounded_context_and_persists_count():
    calls = []

    def flaky(context):
        calls.append(context.retry_count)
        if len(calls) < 3:
            raise RuntimeError("temporary dependency failure")
        return {"recovered": True}

    store = InMemoryCheckpointStore()
    workflow = Workflow(
        "retrying",
        checkpoint_store=store,
        retry_policies={"flaky": RetryPolicy(max_retries=2)},
    )
    assert workflow.add_node("flaky", flaky).is_ok()
    assert workflow.set_entry_point("flaky").is_ok()

    result = workflow.run({}, run_id="retry-run")

    assert result.is_ok()
    completed = result.unwrap()
    assert completed.status == "completed"
    assert completed.state == {"recovered": True}
    assert calls == [0, 1, 2]
    assert completed.retry_counts == {"flaky": 2}
    checkpoint = store.load("retry-run").unwrap()
    assert checkpoint is not None
    assert checkpoint.retry_counts == {"flaky": 2}
    assert checkpoint.retry_after is None


def test_node_retry_policy_exhaustion_is_typed_and_bounded():
    calls = []

    def broken(context):
        calls.append(context.retry_count)
        return Result.err({"errorType": "DEPENDENCY_DOWN", "message": "retry"})

    workflow = Workflow(
        "retry-exhaustion",
        retry_policies={"broken": RetryPolicy(max_retries=1)},
    )
    assert workflow.add_node("broken", broken).is_ok()
    assert workflow.set_entry_point("broken").is_ok()

    result = workflow.run({})

    assert result.is_ok()
    failed = result.unwrap()
    assert failed.status == "failed"
    assert failed.error["errorType"] == "NODE_RETRY_EXHAUSTED"
    assert failed.error["details"]["retry_count"] == 1
    assert calls == [0, 1]


def test_parallel_branch_retry_is_checkpointed_and_replayed_with_context():
    calls = []
    history_store = HistoryCheckpointStore(InMemoryCheckpointStore())

    def start(context):
        return {"prepared": True}

    def flaky(context):
        calls.append(context.retry_count)
        if context.retry_count == 0:
            return Result.err({"errorType": "DEPENDENCY_DOWN", "message": "try again"})
        return {"recovered": True}

    workflow = Workflow(
        "parallel-retry",
        checkpoint_store=history_store,
        retry_policies={"flaky": RetryPolicy(max_retries=1, base_delay_seconds=0.01)},
    )
    workflow.add_node("start", start)
    workflow.add_node("flaky", flaky)
    workflow.add_node("join", lambda context: {"joined": True})
    workflow.set_entry_point("start")
    workflow.add_fan_out("start", ("flaky",), "join")
    workflow.add_edge("join")

    result = workflow.run({}, run_id="parallel-retry-run")

    assert result.is_ok()
    completed = result.unwrap()
    assert completed.status == "completed"
    assert completed.state == {
        "prepared": True,
        "recovered": True,
        "joined": True,
    }
    assert calls == [0, 1]
    assert completed.branch_retry_counts == {}
    snapshots = history_store.history("parallel-retry-run").unwrap()
    scheduled = [
        item
        for item in snapshots
        if item.error and item.error.get("errorType") == "NODE_RETRY_SCHEDULED"
    ]
    assert len(scheduled) == 1
    assert scheduled[0].branch_retry_counts == {"flaky": 1}
    assert scheduled[0].branch_retry_after["flaky"] > scheduled[0].updated_at


def test_parallel_branch_retry_exhaustion_is_typed_and_bounded():
    calls = []
    workflow = Workflow(
        "parallel-retry-exhaustion",
        retry_policies={"broken": RetryPolicy(max_retries=1)},
    )
    workflow.add_node("start", lambda context: None)

    def broken(context):
        calls.append(context.retry_count)
        return Result.err(
            {"errorType": "DEPENDENCY_DOWN", "message": "still unavailable"}
        )

    workflow.add_node("broken", broken)
    workflow.add_node("join", lambda context: None)
    workflow.set_entry_point("start")
    workflow.add_fan_out("start", ("broken",), "join")
    workflow.add_edge("join")

    result = workflow.run({}, run_id="parallel-retry-exhaustion-run")

    assert result.is_ok()
    failed = result.unwrap()
    assert failed.status == "failed"
    assert failed.error["errorType"] == "NODE_RETRY_EXHAUSTED"
    assert failed.error["details"]["node"] == "broken"
    assert failed.error["details"]["retry_count"] == 1
    assert calls == [0, 1]


def test_retry_policy_rejects_unbounded_configuration():
    with pytest.raises(ValueError, match="max_retries"):
        RetryPolicy(max_retries=9)
    with pytest.raises(ValueError, match="max_delay_seconds"):
        RetryPolicy(base_delay_seconds=2, max_delay_seconds=1)


def test_malformed_file_checkpoint_fails_closed(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"run_id": "bad"}), encoding="utf-8")
    store = FileCheckpointStore(tmp_path)

    result = store.load("bad")

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "CHECKPOINT_LOAD_ERROR"


def test_non_json_initial_state_is_rejected_before_checkpoint_write():
    store = InMemoryCheckpointStore()
    workflow = Workflow("json_boundary", checkpoint_store=store)
    assert workflow.add_node("only", lambda context: None).is_ok()
    assert workflow.set_entry_point("only").is_ok()

    result = workflow.run({"bad": object()}, run_id="json-run")

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "INVALID_STATE_VALUE"
    assert store.load("json-run").unwrap() is None


def test_non_json_node_error_is_replaced_with_persistable_failure():
    store = InMemoryCheckpointStore()
    workflow = Workflow("error_boundary", checkpoint_store=store)
    assert workflow.add_node(
        "broken",
        lambda context: Result.err({"errorType": "BAD", "details": object()}),
    ).is_ok()
    assert workflow.set_entry_point("broken").is_ok()

    result = workflow.run({})

    assert result.is_ok()
    assert result.unwrap().status == "failed"
    assert result.unwrap().error["errorType"] == "WORKFLOW_FAILURE_NOT_SERIALIZABLE"


def test_history_store_retains_immutable_checkpoint_snapshots():
    history_store = HistoryCheckpointStore(InMemoryCheckpointStore(), max_history=10)
    workflow = Workflow("history", checkpoint_store=history_store)
    workflow.add_node("first", lambda context: {"first": True})
    workflow.add_node("second", lambda context: {"second": True})
    workflow.set_entry_point("first")
    workflow.add_edge("first", "second")
    workflow.add_edge("second")

    result = workflow.run({}, run_id="history-run")
    snapshots = history_store.history("history-run")

    assert result.is_ok()
    assert snapshots.is_ok()
    assert [item.version for item in snapshots.unwrap()] == [1, 2, 3]
    assert [item.next_node for item in snapshots.unwrap()] == ["first", "second", None]
    assert snapshots.unwrap()[1].state == {"first": True}
    assert snapshots.unwrap()[0].state == {}


def test_history_store_trims_old_snapshots_and_validates_limit():
    history_store = HistoryCheckpointStore(InMemoryCheckpointStore(), max_history=2)
    workflow = Workflow("trimmed_history", checkpoint_store=history_store)
    workflow.add_node("only", lambda context: {"ok": True})
    workflow.set_entry_point("only")
    workflow.run({}, run_id="trimmed-run")

    trimmed = history_store.history("trimmed-run", limit=2)
    invalid = history_store.history("trimmed-run", limit=3)

    assert trimmed.is_ok()
    assert [item.version for item in trimmed.unwrap()] == [1, 2]
    assert invalid.is_err()
    assert invalid.unwrap_err()["errorType"] == "HISTORY_LIMIT_INVALID"


def test_history_store_does_not_claim_history_for_missing_runs():
    history_store = HistoryCheckpointStore(InMemoryCheckpointStore())

    result = history_store.history("missing-run")

    assert result.is_ok()
    assert result.unwrap() == []


def test_fan_out_runs_branches_concurrently_and_commits_ordered_merge():
    barrier = threading.Barrier(2)
    calls = []
    workflow = Workflow("parallel", max_parallel_branches=2)

    def start(context):
        calls.append("start")
        return {"prepared": True}

    def left(context):
        calls.append("left")
        barrier.wait(timeout=2)
        return {"left": "done"}

    def right(context):
        calls.append("right")
        barrier.wait(timeout=2)
        return {"right": "done"}

    def join(context):
        assert context.state["left"] == "done"
        assert context.state["right"] == "done"
        calls.append("join")
        return {"joined": True}

    for name, handler in (
        ("start", start),
        ("left", left),
        ("right", right),
        ("join", join),
    ):
        assert workflow.add_node(name, handler).is_ok()
    assert workflow.set_entry_point("start").is_ok()
    assert workflow.add_fan_out("start", ("left", "right"), "join").is_ok()
    assert workflow.add_edge("join").is_ok()

    result = workflow.run({}, run_id="parallel-run")

    assert result.is_ok()
    completed = result.unwrap()
    assert completed.status == "completed"
    assert completed.state == {
        "prepared": True,
        "left": "done",
        "right": "done",
        "joined": True,
    }
    assert completed.completed_nodes == ["start", "left", "right", "join"]
    assert completed.step_count == 2
    assert calls[0] == "start"
    assert set(calls[1:3]) == {"left", "right"}
    assert calls[3] == "join"


def test_fan_out_pause_resumes_from_group_boundary(tmp_path):
    calls = []
    workflow = Workflow(
        "parallel_pause",
        checkpoint_store=FileCheckpointStore(tmp_path),
        max_parallel_branches=2,
    )

    def start(context):
        calls.append("start")
        return {"prepared": True}

    def approval(context):
        calls.append("approval")
        if context.resume_value is None:
            raise WorkflowPause({"question": "approve branch?"})
        return {"approved": context.resume_value}

    def other(context):
        calls.append("other")
        return {"other": True}

    workflow.add_node("start", start)
    workflow.add_node("approval", approval)
    workflow.add_node("other", other)
    workflow.add_node("join", lambda context: {"joined": True})
    workflow.set_entry_point("start")
    workflow.add_fan_out("start", ("approval", "other"), "join")
    workflow.add_edge("join")

    first = workflow.run({}, run_id="parallel-pause-run")

    assert first.is_ok()
    assert first.unwrap().status == "interrupted"
    assert first.unwrap().completed_nodes == []
    assert first.unwrap().interrupt_payload == {
        "branch": "approval",
        "payload": {"question": "approve branch?"},
        "fan_out": ["approval", "other"],
    }

    resumed = workflow.resume("parallel-pause-run", resume_value="yes")

    assert resumed.is_ok()
    assert resumed.unwrap().status == "completed"
    assert resumed.unwrap().state["approved"] == "yes"
    assert resumed.unwrap().state["other"] is True
    assert calls[0] == "start"
    assert set(calls[1:3]) == {"approval", "other"}
    assert calls[3] == "start"
    assert set(calls[4:6]) == {"approval", "other"}


def test_fan_out_rejects_colliding_branch_state_and_preserves_checkpoint_boundary():
    store = InMemoryCheckpointStore()
    workflow = Workflow("parallel_conflict", checkpoint_store=store)
    workflow.add_node("start", lambda context: None)
    workflow.add_node("left", lambda context: {"value": "left"})
    workflow.add_node("right", lambda context: {"value": "right"})
    workflow.set_entry_point("start")
    workflow.add_fan_out("start", ("left", "right"), "join")
    workflow.add_node("join", lambda context: None)
    workflow.add_edge("join")

    result = workflow.run({}, run_id="parallel-conflict-run")

    assert result.is_ok()
    failed = result.unwrap()
    assert failed.status == "failed"
    assert failed.error["errorType"] == "PARALLEL_STATE_CONFLICT"
    assert failed.completed_nodes == []
    checkpoint = store.load("parallel-conflict-run").unwrap()
    assert checkpoint.status == "failed"
    assert checkpoint.completed_nodes == []


def test_fan_out_rejects_branch_count_above_configured_bound():
    workflow = Workflow("parallel_limit", max_parallel_branches=2)

    result = workflow.add_fan_out("start", ("one", "two", "three"), "join")

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "PARALLELISM_EXCEEDED"


def test_subworkflow_maps_state_without_leaking_child_context():
    child = Workflow("child_mapping")
    child.add_node(
        "transform",
        lambda context: {
            "child_result": context.state["child_input"] * 2,
            "child_secret": "not-exported",
        },
    )
    child.set_entry_point("transform")
    child.add_edge("transform")

    parent = Workflow("parent_mapping")
    assert parent.add_subworkflow(
        "child_step",
        child,
        input_map={"request": "child_input"},
        output_map={"child_result": "answer"},
    ).is_ok()
    parent.set_entry_point("child_step")
    parent.add_edge("child_step")

    result = parent.run({"request": 21, "parent_only": "kept"}, run_id="mapping-run")

    assert result.is_ok()
    completed = result.unwrap()
    assert completed.status == "completed"
    assert completed.state == {
        "request": 21,
        "parent_only": "kept",
        "answer": 42,
    }


def test_subworkflow_missing_input_fails_before_child_execution():
    calls = []
    child = Workflow("child_missing_input")
    child.add_node("only", lambda context: calls.append("child"))
    child.set_entry_point("only")
    child.add_edge("only")

    parent = Workflow("parent_missing_input")
    parent.add_subworkflow(
        "child_step", child, input_map={"required": "child_required"}
    )
    parent.set_entry_point("child_step")
    parent.add_edge("child_step")

    result = parent.run({}, run_id="missing-input-run")

    assert result.is_ok()
    failed = result.unwrap()
    assert failed.status == "failed"
    assert failed.error["errorType"] == "SUBWORKFLOW_INPUT_MISSING"
    assert calls == []


def test_subworkflow_pause_resumes_child_run_without_restarting_parent_nodes():
    calls = []
    child = Workflow("child_pause")

    def ask(context):
        calls.append("ask")
        if context.resume_value is None:
            raise WorkflowPause({"question": "choose"})
        return {"choice": context.resume_value}

    child.add_node("ask", ask)
    child.set_entry_point("ask")
    child.add_edge("ask")

    parent = Workflow("parent_pause")
    parent.add_subworkflow("child_step", child)
    parent.set_entry_point("child_step")
    parent.add_edge("child_step")

    first = parent.run({"request": "demo"}, run_id="nested-pause-run")

    assert first.is_ok()
    paused = first.unwrap()
    assert paused.status == "interrupted"
    assert paused.completed_nodes == []
    assert paused.interrupt_payload["subworkflow"] == "child_pause"
    assert paused.interrupt_payload["payload"] == {"question": "choose"}
    assert calls == ["ask"]

    resumed = parent.resume("nested-pause-run", resume_value="yes")

    assert resumed.is_ok()
    completed = resumed.unwrap()
    assert completed.status == "completed"
    assert completed.state["choice"] == "yes"
    assert calls == ["ask", "ask"]


def test_subworkflow_rejects_self_reference_and_duplicate_mapping_targets():
    workflow = Workflow("subworkflow_validation")

    self_result = workflow.add_subworkflow("self", workflow)
    duplicate_result = workflow.add_subworkflow(
        "duplicate",
        Workflow("child_validation"),
        input_map={"one": "same", "two": "same"},
    )

    assert self_result.is_err()
    assert self_result.unwrap_err()["errorType"] == "INVALID_SUBWORKFLOW"
    assert duplicate_result.is_err()
    assert duplicate_result.unwrap_err()["errorType"] == "DUPLICATE_SUBWORKFLOW_TARGET"


def test_subworkflow_malformed_child_checkpoint_fails_closed():
    class MalformedStore(InMemoryCheckpointStore):
        def load(self, run_id):
            return Result.ok({"not": "a checkpoint"})

    child = Workflow("child_malformed", checkpoint_store=MalformedStore())
    child.add_node("only", lambda context: None)
    child.set_entry_point("only")
    child.add_edge("only")

    parent = Workflow("parent_malformed")
    parent.add_subworkflow("child_step", child)
    parent.set_entry_point("child_step")
    parent.add_edge("child_step")

    result = parent.run({}, run_id="malformed-child-run")

    assert result.is_ok()
    assert result.unwrap().status == "failed"
    assert result.unwrap().error["errorType"] == "SUBWORKFLOW_CHECKPOINT_INVALID"


def test_subworkflow_mapping_limits_accept_boundary_and_reject_overflow():
    child = Workflow("child_limits")
    parent = Workflow("parent_limits")
    mapping_255 = {f"parent-{i}": f"child-{i}" for i in range(255)}
    mapping_256 = {f"parent-{i}": f"child-{i}" for i in range(256)}
    mapping_257 = {f"parent-{i}": f"child-{i}" for i in range(257)}

    assert parent.add_subworkflow("limit_255", child, input_map=mapping_255).is_ok()
    assert parent.add_subworkflow("limit_256", child, input_map=mapping_256).is_ok()
    overflow = parent.add_subworkflow("limit_257", child, input_map=mapping_257)
    valid_key = "k" * 256
    assert parent.add_subworkflow(
        "key_256", child, input_map={valid_key: valid_key}
    ).is_ok()
    long_key = "k" * 257
    invalid_key = parent.add_subworkflow(
        "key_257", child, input_map={long_key: "child"}
    )

    assert overflow.is_err()
    assert overflow.unwrap_err()["errorType"] == "SUBWORKFLOW_MAP_TOO_LARGE"
    assert invalid_key.is_err()
    assert invalid_key.unwrap_err()["errorType"] == "INVALID_SUBWORKFLOW_MAP"
