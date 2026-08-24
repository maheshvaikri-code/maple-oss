"""Tests for MAPLE's native workflow and checkpoint boundary."""

import json

from maple.autonomy import (
    FileCheckpointStore,
    InMemoryCheckpointStore,
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
