"""Tests for bounded event streaming and payload redaction."""

from maple.autonomy.events import EventCursor, EventStream, RedactionPolicy
from maple.autonomy.execution import CancellationToken


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
    assert stream.subscribe(lambda event: None).is_ok()
    stream.publish("one", {})
    stream.publish("two", {})
    stream.publish("three", {})

    snapshot = stream.snapshot(after_sequence=0)

    assert snapshot.is_ok()
    assert [event.sequence for event in snapshot.unwrap()] == [2, 3]
    assert stream.dropped_count == 1
    assert stream.metrics() == {
        "retained_events": 2,
        "max_events": 2,
        "dropped_events": 1,
        "subscriber_count": 1,
    }


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


def test_cursor_read_is_bounded_serializable_and_advances():
    stream = EventStream(max_events=3)
    stream.publish("one", {"value": 1})
    stream.publish("two", {"value": 2})

    first = stream.read(limit=1)
    assert first.is_ok()
    first_batch = first.unwrap()
    assert [event.event_type for event in first_batch.events] == ["one"]
    assert first_batch.next_cursor.to_dict() == {"sequence": 1}

    restored = EventCursor.from_dict(first_batch.next_cursor.to_dict())
    assert restored.is_ok()
    second = stream.read(restored.unwrap(), limit=2)
    assert second.is_ok()
    second_batch = second.unwrap()
    assert [event.event_type for event in second_batch.events] == ["two"]
    assert second_batch.latest_sequence == 2
    assert second_batch.to_dict()["next_cursor"] == {"sequence": 2}


def test_cursor_read_rejects_evicted_window_instead_of_silent_loss():
    stream = EventStream(max_events=2)
    stream.publish("one", {})
    stream.publish("two", {})
    stream.publish("three", {})

    result = stream.read(EventCursor(sequence=0))

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "EVENT_CURSOR_EXPIRED"
    assert result.unwrap_err()["details"] == {
        "cursor_sequence": 0,
        "oldest_sequence": 2,
        "latest_sequence": 3,
    }


def test_cursor_and_read_bounds_fail_closed():
    stream = EventStream(max_events=2)
    invalid_cursor = EventCursor.from_dict({"sequence": -1})
    invalid_limit = stream.read(limit=3)

    assert invalid_cursor.is_err()
    assert invalid_cursor.unwrap_err()["errorType"] == "EVENT_CURSOR_INVALID"
    assert invalid_limit.is_err()
    assert invalid_limit.unwrap_err()["errorType"] == "EVENT_QUERY_INVALID"


def test_wait_for_supports_cooperative_cancellation():
    token = CancellationToken()
    token.cancel()

    result = EventStream().wait_for(0, timeout=1, cancellation=token)

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "EVENT_CANCELLED"


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


def test_exporter_receives_redacted_event_without_affecting_publish():
    class Exporter:
        def __init__(self):
            self.events = []

        def export(self, event):
            self.events.append(event)

    exporter = Exporter()
    stream = EventStream(exporter=exporter)

    published = stream.publish(
        "model.completed",
        {"status": "ok", "secret": "not-exported"},
        run_id="run-export",
    )

    assert published.is_ok()
    assert exporter.events == [published.unwrap()]
    assert exporter.events[0].payload["secret"] == "[REDACTED]"


def test_exporter_failure_is_isolated_and_invalid_exporter_fails_closed():
    class BrokenExporter:
        def export(self, event):
            raise RuntimeError("sink unavailable")

    published = EventStream(exporter=BrokenExporter()).publish("safe", {})
    invalid = EventStream(exporter=object()).publish("safe", {})

    assert published.is_ok()
    assert invalid.is_err()
    assert invalid.unwrap_err()["errorType"] == "EVENT_CONFIG_INVALID"
