"""Integration tests for crash-window workflow replay."""

import hashlib

from maple.autonomy import (
    ExecutionRecord,
    InMemoryCheckpointStore,
    InMemoryExecutionJournal,
    Workflow,
)
from maple.core.result import Result


class _FailSecondSaveStore:
    def __init__(self):
        self.base = InMemoryCheckpointStore()
        self.save_count = 0

    def load(self, run_id):
        return self.base.load(run_id)

    def save(self, checkpoint, expected_version=None):
        self.save_count += 1
        if self.save_count == 2:
            return Result.err(
                {"errorType": "CHECKPOINT_SAVE_ERROR", "message": "simulated crash window"}
            )
        return self.base.save(checkpoint, expected_version=expected_version)


def test_recover_reuses_output_written_before_checkpoint_failure():
    store = _FailSecondSaveStore()
    journal = InMemoryExecutionJournal()
    calls = []
    keys = []
    workflow = Workflow(
        "recovery_flow",
        checkpoint_store=store,
        execution_journal=journal,
    )

    def start(context):
        calls.append("start")
        keys.append(context.execution_key)
        return {"prepared": True}

    workflow.add_node("start", start)
    workflow.set_entry_point("start")
    workflow.add_edge("start")

    first = workflow.run({}, run_id="recover-run")
    recovered = workflow.recover("recover-run")

    assert first.is_err()
    assert first.unwrap_err()["errorType"] == "CHECKPOINT_SAVE_ERROR"
    assert recovered.is_ok()
    assert recovered.unwrap().status == "completed"
    assert recovered.unwrap().state["prepared"] is True
    assert calls == ["start"]
    assert keys == ["recover-run:0:start"]


def test_recovery_rejects_non_running_checkpoints():
    store = InMemoryCheckpointStore()
    workflow = Workflow("recovery_status", checkpoint_store=store)
    workflow.add_node("start", lambda context: None)
    workflow.set_entry_point("start")
    workflow.add_edge("start")

    assert workflow.run({}, run_id="done-run").is_ok()
    result = workflow.recover("done-run")

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "INVALID_RECOVERY"


def test_replay_record_metadata_mismatch_fails_closed():
    journal = InMemoryExecutionJournal()
    workflow = Workflow("metadata_flow", execution_journal=journal)
    workflow.add_node("start", lambda context: {"ok": True})
    workflow.set_entry_point("start")
    workflow.add_edge("start")
    assert journal.save(
        ExecutionRecord(
            execution_key="metadata-run:0:start",
            run_id="metadata-run",
            workflow_name="other_flow",
            node_name="start",
            step_count=0,
            input_digest=hashlib.sha256(
                b'{"resume_value":null,"state":{}}'
            ).hexdigest(),
            output={"ok": True},
        )
    ).is_ok()

    result = workflow.run({}, run_id="metadata-run")

    assert result.is_ok()
    assert result.unwrap().status == "failed"
    assert result.unwrap().error["errorType"] == "REPLAY_RECORD_INVALID"
