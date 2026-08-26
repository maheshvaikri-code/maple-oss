"""Tests for durable human request/response records."""

from maple.autonomy.interactions import (
    FileHumanInputStore,
    HumanInputRequest,
    InMemoryHumanInputStore,
)


def _request(interaction_id="input-1", max_rounds=1):
    return HumanInputRequest(
        interaction_id=interaction_id,
        run_id="run-1",
        tool_call_id="call-input",
        prompt="Provide a code.",
        input_schema={
            "type": "object",
            "properties": {"code": {"type": "string", "minLength": 1}},
            "required": ["code"],
            "additionalProperties": False,
        },
        max_rounds=max_rounds,
    )


def test_in_memory_human_input_validates_response_and_consumes_once():
    store = InMemoryHumanInputStore()
    assert store.create(_request()).is_ok()

    invalid = store.respond("input-1", {"wrong": True})
    waiting = store.get("input-1").unwrap()
    assert invalid.is_err()
    assert invalid.unwrap_err()["errorType"] == "HUMAN_INPUT_RESPONSE_INVALID"
    assert waiting is not None
    assert waiting.status == "pending"

    responded = store.respond("input-1", {"code": "green"})
    consumed = store.consume("input-1")
    replay = store.consume("input-1")

    assert responded.is_ok()
    assert responded.unwrap().decision.response == {"code": "green"}
    assert consumed.is_ok()
    assert consumed.unwrap().status == "consumed"
    assert replay.is_err()
    assert replay.unwrap_err()["errorType"] == "HUMAN_INPUT_NOT_READY"


def test_rejection_is_durable_and_preserves_reason(tmp_path):
    first = FileHumanInputStore(tmp_path)
    assert first.create(_request()).is_ok()
    rejected = first.reject("input-1", "The request is not authorized.")
    assert rejected.is_ok()

    restarted = FileHumanInputStore(tmp_path)
    loaded = restarted.get("input-1").unwrap()

    assert loaded is not None
    assert loaded.status == "rejected"
    assert loaded.decision is not None
    assert loaded.decision.accepted is False
    assert loaded.decision.rejection_reason == "The request is not authorized."


def test_invalid_request_and_oversized_response_do_not_mutate_store(tmp_path):
    store = FileHumanInputStore(tmp_path)
    invalid = store.create(
        HumanInputRequest(
            interaction_id="input-1",
            run_id="run-1",
            tool_call_id="call-input",
            prompt="valid",
            input_schema={"type": "object"},
        )
    )
    assert invalid.is_ok()

    oversized = store.respond("input-1", {"value": "x" * 300_000})
    pending = FileHumanInputStore(tmp_path).get("input-1").unwrap()

    assert oversized.is_err()
    assert oversized.unwrap_err()["errorType"] == "HUMAN_INPUT_VALUE_TOO_LARGE"
    assert pending is not None
    assert pending.status == "pending"
    assert pending.decision is None


def test_in_memory_multi_round_preserves_history_and_enforces_bound():
    store = InMemoryHumanInputStore()
    assert store.create(_request(max_rounds=2)).is_ok()
    assert store.respond("input-1", {"code": "green"}).is_ok()

    continued = store.continue_round(
        "input-1",
        "Provide the replacement code.",
        {"type": "object", "required": ["code"]},
    )

    assert continued.is_ok()
    next_request = continued.unwrap()
    assert next_request.status == "pending"
    assert next_request.round_index == 1
    assert len(next_request.history) == 1
    assert next_request.history[0].decision.response == {"code": "green"}

    assert store.respond("input-1", {"code": "blue"}).is_ok()
    consumed = store.consume("input-1")
    assert consumed.is_ok()
    final_request = consumed.unwrap()
    assert final_request.round_index == 1
    assert final_request.decision is not None
    assert final_request.decision.response == {"code": "blue"}
    assert len(final_request.history) == 1

    limited = store.continue_round("input-1", "One more", {"type": "object"})
    assert limited.is_err()
    assert limited.unwrap_err()["errorType"] == "HUMAN_INPUT_ROUND_LIMIT"


def test_file_multi_round_history_survives_restart(tmp_path):
    first = FileHumanInputStore(tmp_path)
    assert first.create(_request(max_rounds=2)).is_ok()
    assert first.respond("input-1", {"code": "green"}).is_ok()
    assert first.continue_round(
        "input-1", "Confirm the replacement.", {"type": "object"}
    ).is_ok()

    restarted = FileHumanInputStore(tmp_path)
    pending = restarted.get("input-1").unwrap()

    assert pending is not None
    assert pending.status == "pending"
    assert pending.round_index == 1
    assert pending.history[0].decision.response == {"code": "green"}
