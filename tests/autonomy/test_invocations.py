"""Regression coverage for bounded agent invocation idempotency stores."""

import json
import threading
from pathlib import Path

from maple.autonomy.invocations import (
    AgentInvocationResponse,
    FileAgentInvocationDeduplicationStore,
    InMemoryAgentInvocationDeduplicationStore,
    fingerprint_agent_invocation,
    normalize_agent_idempotency_key,
)


class _Clock:
    def __init__(self, value=100.0):
        self.value = value

    def __call__(self):
        return self.value


def _digest(target_id="agent:alpha", **request):
    result = fingerprint_agent_invocation(target_id, request)
    assert result.is_ok()
    return result.unwrap()


def _response(answer="ok"):
    return AgentInvocationResponse(
        201,
        {
            "run": {
                "agent_id": "alpha",
                "run_id": "run-1",
                "status": "completed",
                "result": {"answer": answer},
            }
        },
    )


def _assert_error(result, error_type):
    assert result.is_err()
    assert result.unwrap_err()["errorType"] == error_type


def test_in_memory_store_replays_detached_response_and_suppresses_pending_duplicate():
    store = InMemoryAgentInvocationDeduplicationStore()
    digest = _digest(task="one")

    assert store.claim("agent:alpha", "key-1", digest).unwrap() is None
    _assert_error(
        store.claim("agent:alpha", "key-1", digest),
        "AGENT_INVOCATION_IN_PROGRESS",
    )

    assert store.complete("agent:alpha", "key-1", digest, _response()).is_ok()
    replay = store.claim("agent:alpha", "key-1", digest)
    assert replay.is_ok()
    replayed = replay.unwrap()
    assert replayed is not None
    replayed.payload["run"]["result"]["answer"] = "mutated"

    second_replay = store.claim("agent:alpha", "key-1", digest)
    assert second_replay.is_ok()
    assert second_replay.unwrap().payload["run"]["result"]["answer"] == "ok"


def test_in_memory_store_rejects_same_key_conflict_without_mutating_completed_record():
    store = InMemoryAgentInvocationDeduplicationStore()
    first_digest = _digest(task="one")
    second_digest = _digest(task="two")

    assert store.claim("agent:alpha", "key-1", first_digest).is_ok()
    assert store.complete("agent:alpha", "key-1", first_digest, _response()).is_ok()
    _assert_error(
        store.claim("agent:alpha", "key-1", second_digest),
        "AGENT_INVOCATION_CONFLICT",
    )
    replay = store.claim("agent:alpha", "key-1", first_digest)
    assert replay.is_ok()
    assert replay.unwrap().payload["run"]["result"]["answer"] == "ok"


def test_in_memory_store_abort_releases_only_pending_claim():
    store = InMemoryAgentInvocationDeduplicationStore()
    digest = _digest(task="one")

    assert store.claim("agent:alpha", "key-1", digest).is_ok()
    assert store.abort("agent:alpha", "key-1", digest).is_ok()
    assert store.claim("agent:alpha", "key-1", digest).unwrap() is None
    assert store.complete("agent:alpha", "key-1", digest, _response()).is_ok()
    assert store.abort("agent:alpha", "key-1", digest).is_ok()
    assert store.claim("agent:alpha", "key-1", digest).unwrap() is not None


def test_in_memory_store_expires_records_and_does_not_evict_pending_claims():
    clock = _Clock()
    store = InMemoryAgentInvocationDeduplicationStore(
        max_entries=1, ttl_seconds=10, clock=clock
    )
    first_digest = _digest(task="one")
    second_digest = _digest(task="two")
    assert store.claim("agent:alpha", "key-1", first_digest).is_ok()
    _assert_error(
        store.claim("agent:alpha", "key-2", second_digest),
        "AGENT_INVOCATION_CAPACITY",
    )
    clock.value = 111
    assert store.claim("agent:alpha", "key-2", second_digest).unwrap() is None


def test_in_memory_store_evicts_completed_record_before_new_claim():
    store = InMemoryAgentInvocationDeduplicationStore(max_entries=1)
    first_digest = _digest(task="one")
    second_digest = _digest(task="two")
    assert store.claim("agent:alpha", "key-1", first_digest).is_ok()
    assert store.complete("agent:alpha", "key-1", first_digest, _response()).is_ok()
    assert store.claim("agent:alpha", "key-2", second_digest).unwrap() is None


def test_file_store_replays_completed_response_after_restart_without_raw_request_data(
    tmp_path: Path,
):
    digest = _digest(task="private prompt", context={"secret": "not retained"})
    store = FileAgentInvocationDeduplicationStore(tmp_path)
    assert store.claim("agent:alpha", "key-1", digest).is_ok()
    assert store.complete("agent:alpha", "key-1", digest, _response()).is_ok()

    persisted = (tmp_path / "invocations.json").read_text(encoding="utf-8")
    assert "private prompt" not in persisted
    assert "not retained" not in persisted

    restarted = FileAgentInvocationDeduplicationStore(tmp_path)
    replay = restarted.claim("agent:alpha", "key-1", digest)
    assert replay.is_ok()
    assert replay.unwrap().payload["run"]["result"]["answer"] == "ok"


def test_file_store_rejects_malformed_state_without_rewriting_it(tmp_path: Path):
    path = tmp_path / "invocations.json"
    original = '{"version": 999, "records": []}'
    path.write_text(original, encoding="utf-8")
    store = FileAgentInvocationDeduplicationStore(tmp_path)

    _assert_error(
        store.claim("agent:alpha", "key-1", _digest(task="one")),
        "AGENT_INVOCATION_LOAD_ERROR",
    )
    assert path.read_text(encoding="utf-8") == original


def test_file_store_rejects_oversized_response_before_mutating_claim(tmp_path: Path):
    store = FileAgentInvocationDeduplicationStore(tmp_path, max_response_bytes=32)
    digest = _digest(task="one")
    assert store.claim("agent:alpha", "key-1", digest).is_ok()
    _assert_error(
        store.complete("agent:alpha", "key-1", digest, _response()),
        "AGENT_INVOCATION_RESPONSE_INVALID",
    )
    _assert_error(
        store.claim("agent:alpha", "key-1", digest),
        "AGENT_INVOCATION_IN_PROGRESS",
    )


def test_file_store_serializes_concurrent_claims_to_one_winner(tmp_path: Path):
    stores = [
        FileAgentInvocationDeduplicationStore(tmp_path),
        FileAgentInvocationDeduplicationStore(tmp_path),
    ]
    digest = _digest(task="one")
    barrier = threading.Barrier(2)
    results = [None, None]

    def claim(index):
        barrier.wait()
        results[index] = stores[index].claim("agent:alpha", "key-1", digest)

    threads = [threading.Thread(target=claim, args=(index,)) for index in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert all(result is not None for result in results)
    successful_claims = [result for result in results if result.is_ok()]
    pending_errors = [
        result
        for result in results
        if result.is_err()
        and result.unwrap_err()["errorType"] == "AGENT_INVOCATION_IN_PROGRESS"
    ]
    assert len(successful_claims) == 1
    assert successful_claims[0].unwrap() is None
    assert len(pending_errors) == 1


def test_fingerprint_is_canonical_and_target_bound():
    first = fingerprint_agent_invocation(
        "agent:alpha", {"task": "one", "context": {"a": 1, "b": 2}}
    )
    reordered = fingerprint_agent_invocation(
        "agent:alpha", {"context": {"b": 2, "a": 1}, "task": "one"}
    )
    other_target = fingerprint_agent_invocation(
        "agent:beta", {"task": "one", "context": {"a": 1, "b": 2}}
    )
    assert first.is_ok() and reordered.is_ok() and other_target.is_ok()
    assert first.unwrap() == reordered.unwrap()
    assert first.unwrap() != other_target.unwrap()


def test_key_and_fingerprint_boundaries_fail_closed():
    assert normalize_agent_idempotency_key(None).unwrap() is None
    assert normalize_agent_idempotency_key("key").unwrap() == "key"
    _assert_error(
        normalize_agent_idempotency_key("a" * 257),
        "AGENT_INVOCATION_KEY_INVALID",
    )
    _assert_error(
        fingerprint_agent_invocation("agent:alpha", {"value": float("nan")}),
        "AGENT_INVOCATION_REQUEST_INVALID",
    )


def test_file_store_state_is_json_and_retains_only_bounded_record_shape(tmp_path: Path):
    store = FileAgentInvocationDeduplicationStore(tmp_path)
    digest = _digest(task="one")
    assert store.claim("agent:alpha", "key-1", digest).is_ok()
    data = json.loads((tmp_path / "invocations.json").read_text(encoding="utf-8"))
    assert set(data) == {"version", "records"}
    assert set(data["records"][0]) == {
        "idempotency_key",
        "target_id",
        "request_digest",
        "response",
        "expires_at",
    }
