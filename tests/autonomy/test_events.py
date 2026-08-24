"""Tests for bounded event streaming and payload redaction."""

from maple.autonomy.events import EventStream, RedactionPolicy


def test_publish_redacts_nested_secrets_and_preserves_sequence():
    stream = EventStream(max_events=10)
    received = []
    stream.subscribe(received.append)

    result = stream.publish(
        "tool.completed",
        {
            "status": "ok",
            "credentials": {"api_key": "hidden", "region": "test"},
            "items": [{"token": "also-hidden"}],
        },
        run_id="run-1",
    )

    assert result.is_ok()
    event = result.unwrap()
    assert event.sequence == 1
    assert event.run_id == "run-1"
    assert event.payload["credentials"] == {"api_key": "[REDACTED]", "region": "test"}
    assert event.payload["items"] == [{"token": "[REDACTED]"}]
    assert received == [event]


def test_ring_buffer_tracks_evictions_and_snapshot_order():
    stream = EventStream(max_events=2)
    stream.publish("one", {})
    stream.publish("two", {})
    stream.publish("three", {})

    snapshot = stream.snapshot(after_sequence=0)

    assert snapshot.is_ok()
    assert [event.sequence for event in snapshot.unwrap()] == [2, 3]
    assert stream.dropped_count == 1


def test_payload_bounds_and_malformed_values_fail_closed():
    stream = EventStream(
        max_payload_bytes=20,
        redaction=RedactionPolicy(max_depth=2, max_string_length=5),
    )
    too_large = stream.publish("large", "123456")
    too_deep = stream.publish("deep", {"a": {"b": {"c": True}}})
    non_json = stream.publish("bad", {"object": object()})

    assert too_large.is_err()
    assert too_large.unwrap_err()["errorType"] == "EVENT_PAYLOAD_TOO_LARGE"
    assert too_deep.is_err()
    assert too_deep.unwrap_err()["errorType"] == "EVENT_PAYLOAD_TOO_DEEP"
    assert non_json.is_err()
    assert non_json.unwrap_err()["errorType"] == "EVENT_NON_JSON_PAYLOAD"


def test_wait_for_and_query_validation():
    stream = EventStream()
    timed_out = stream.wait_for(0, timeout=0)
    invalid = stream.snapshot(after_sequence=-1)
    stream.publish("ready", {"value": 1})
    received = stream.wait_for(0, timeout=0.1)

    assert timed_out.is_err()
    assert timed_out.unwrap_err()["errorType"] == "EVENT_WAIT_TIMEOUT"
    assert invalid.is_err()
    assert invalid.unwrap_err()["errorType"] == "EVENT_QUERY_INVALID"
    assert received.is_ok()
    assert received.unwrap()[0].event_type == "ready"


def test_subscriber_failures_do_not_break_publish_and_unsubscribe_works():
    stream = EventStream(max_subscribers=1)

    def broken(event):
        raise RuntimeError("subscriber failure")

    subscription = stream.subscribe(broken)
    over_limit = stream.subscribe(lambda event: None)
    published = stream.publish("safe", {})
    removed = stream.unsubscribe(subscription.unwrap())
    missing = stream.unsubscribe(subscription.unwrap())

    assert subscription.is_ok()
    assert over_limit.is_err()
    assert over_limit.unwrap_err()["errorType"] == "EVENT_SUBSCRIBER_LIMIT"
    assert published.is_ok()
    assert removed.unwrap() is True
    assert missing.unwrap() is False
