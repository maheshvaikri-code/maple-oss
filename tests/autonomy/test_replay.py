"""Tests for bounded workflow execution journals."""

import json

from maple.autonomy import (
    ExecutionRecord,
    FileExecutionJournal,
    InMemoryExecutionJournal,
)


def _record(key="run-1:0:start", run_id="run-1", output=None):
    return ExecutionRecord(
        execution_key=key,
        run_id=run_id,
        workflow_name="replay_flow",
        node_name="start",
        step_count=0,
        input_digest="a" * 64,
        output={"value": "done"} if output is None else output,
        created_at=1.0,
    )


def test_in_memory_journal_round_trip_is_bounded_and_idempotent():
    journal = InMemoryExecutionJournal(max_records=2, max_run_records=2)
    record = _record()

    saved = journal.save(record)
    loaded = journal.load(record.execution_key, record.input_digest)
    repeated = journal.save(record)

    assert saved.is_ok()
    assert loaded.is_ok()
    assert loaded.unwrap() == record
    assert repeated.is_ok()
    assert repeated.unwrap() == record


def test_journal_rejects_input_and_record_conflicts_without_mutation():
    journal = InMemoryExecutionJournal()
    record = _record()
    assert journal.save(record).is_ok()

    input_conflict = journal.load(record.execution_key, "b" * 64)
    record_conflict = journal.save(_record(output={"value": "other"}))

    assert input_conflict.is_err()
    assert input_conflict.unwrap_err()["errorType"] == "REPLAY_INPUT_CONFLICT"
    assert record_conflict.is_err()
    assert record_conflict.unwrap_err()["errorType"] == "REPLAY_CONFLICT"
    assert journal.load(record.execution_key, record.input_digest).unwrap() == record


def test_in_memory_journal_enforces_global_and_per_run_limits():
    journal = InMemoryExecutionJournal(max_records=1, max_run_records=1)
    assert journal.save(_record()).is_ok()

    global_limit = journal.save(
        _record(key="run-2:0:start", run_id="run-2")
    )

    assert global_limit.is_err()
    assert global_limit.unwrap_err()["errorType"] == "REPLAY_RECORD_LIMIT"
    assert journal.clear("run-1").unwrap() == 1
    assert journal.load("run-1:0:start", "a" * 64).unwrap() is None


def test_file_journal_survives_recreation_and_clear(tmp_path):
    record = _record()
    first = FileExecutionJournal(tmp_path)
    assert first.save(record).is_ok()

    second = FileExecutionJournal(tmp_path)
    loaded = second.load(record.execution_key, record.input_digest)

    assert loaded.is_ok()
    assert loaded.unwrap() == record
    assert second.clear("run-1").unwrap() == 1
    assert second.load(record.execution_key, record.input_digest).unwrap() is None


def test_file_journal_fails_closed_on_malformed_record(tmp_path):
    journal = FileExecutionJournal(tmp_path)
    path = journal._path("run-1:0:start")
    path.write_text(json.dumps({"not": "a replay record"}), encoding="utf-8")

    result = journal.load("run-1:0:start", "a" * 64)

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "REPLAY_LOAD_ERROR"


def test_file_journal_fails_closed_when_record_key_does_not_match_filename(tmp_path):
    journal = FileExecutionJournal(tmp_path)
    (tmp_path / "maple-replay-invalid.json").write_text(
        json.dumps(_record().to_dict()), encoding="utf-8"
    )

    result = journal.clear("run-1")

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "REPLAY_LOAD_ERROR"


def test_journal_rejects_oversized_output():
    journal = InMemoryExecutionJournal(max_record_bytes=128)

    result = journal.save(_record(output={"value": "x" * 1_000}))

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "REPLAY_RECORD_SIZE"
