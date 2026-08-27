"""Tests for bounded event streaming and payload redaction."""

import json
import math
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from maple.autonomy.events import (
    AgentEvent,
    EventCursor,
    EventStream,
    FileEventJournal,
    HttpEventExporter,
    RedactionPolicy,
)
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
    metrics = stream.metrics()
    assert metrics["retained_events"] == 2
    assert metrics["max_events"] == 2
    assert metrics["dropped_events"] == 1
    assert metrics["subscriber_count"] == 1
    assert metrics["published_events"] == 3
    assert metrics["subscriber_failures"] == 0
    assert metrics["exporter_failures"] == 0
    assert metrics["publish_latency_total_ms"] >= 0
    assert metrics["publish_latency_max_ms"] >= metrics["publish_latency_avg_ms"]
    assert metrics["publish_latency_sample_count"] == 2
    assert 0 <= metrics["publish_latency_p50_ms"]
    assert metrics["publish_latency_p95_ms"] >= metrics["publish_latency_p50_ms"]
    assert metrics["publish_latency_p99_ms"] >= metrics["publish_latency_p95_ms"]


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

    published_metrics = EventStream(exporter=BrokenExporter())
    published = published_metrics.publish("safe", {})
    invalid = EventStream(exporter=object()).publish("safe", {})

    assert published.is_ok()
    assert published_metrics.metrics()["exporter_failures"] == 1
    assert invalid.is_err()
    assert invalid.unwrap_err()["errorType"] == "EVENT_CONFIG_INVALID"


def test_subscriber_failure_is_isolated_and_counted():
    def broken_subscriber(event):
        raise RuntimeError("subscriber unavailable")

    stream = EventStream()
    assert stream.subscribe(broken_subscriber).is_ok()

    published = stream.publish("safe", {})

    assert published.is_ok()
    assert stream.metrics()["subscriber_failures"] == 1


def test_http_event_exporter_sends_redacted_event_with_bearer_auth():
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            length = int(self.headers["Content-Length"])
            received.append(
                (self.headers.get("Authorization"), json.loads(self.rfile.read(length)))
            )
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, format, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        exporter = HttpEventExporter(
            f"http://127.0.0.1:{server.server_address[1]}/events",
            auth_token="local-token",
        )
        stream = EventStream(exporter=exporter)
        published = stream.publish(
            "tool.completed",
            {"status": "ok", "secret": "never-sent"},
            run_id="run-http-export",
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert published.is_ok()
    assert received[0][0] == "Bearer local-token"
    assert received[0][1]["payload"]["secret"] == "[REDACTED]"
    assert received[0][1]["run_id"] == "run-http-export"


def test_http_event_exporter_is_bounded_and_requires_secure_remote_transport():
    with pytest.raises(ValueError):
        HttpEventExporter("http://example.test/events")
    with pytest.raises(ValueError):
        HttpEventExporter("http://127.0.0.1:1/events", auth_token="bad\r\ntoken")

    exporter = HttpEventExporter(
        "http://127.0.0.1:1/events", timeout_seconds=0.1, max_event_bytes=32
    )
    event = AgentEvent(
        sequence=1,
        event_type="large",
        timestamp=1.0,
        payload={"value": "x" * 100},
    )

    with pytest.raises(ValueError):
        exporter.export(event)

    for invalid_timeout in (math.nan, math.inf, -math.inf):
        with pytest.raises(ValueError):
            HttpEventExporter(
                "http://127.0.0.1:1/events", timeout_seconds=invalid_timeout
            )


def test_http_event_exporter_failure_isolated_from_event_publish():
    exporter = HttpEventExporter("http://127.0.0.1:1/events", timeout_seconds=0.1)
    stream = EventStream(exporter=exporter)

    published = stream.publish("safe", {})

    assert published.is_ok()
    assert stream.metrics()["exporter_failures"] == 1


def test_file_event_journal_rehydrates_redacted_events_and_sequence(tmp_path):
    journal = FileEventJournal(tmp_path, max_events=2)
    stream = EventStream(max_events=2, journal=journal)
    first = stream.publish("one", {"secret": "not-persisted", "value": 1})
    stream.publish("two", {"value": 2})
    stream.publish("three", {"value": 3})

    assert first.is_ok()
    persisted = json.loads(journal.path.read_text(encoding="utf-8"))
    assert [event["sequence"] for event in persisted["events"]] == [2, 3]
    assert persisted["events"][0]["payload"] == {"value": 2}

    restarted = EventStream(
        max_events=2,
        journal=FileEventJournal(tmp_path, max_events=2),
    )
    restored = restarted.read(EventCursor(sequence=1))
    next_event = restarted.publish("four", {"value": 4})

    assert restored.is_ok()
    assert [event.sequence for event in restored.unwrap().events] == [2, 3]
    assert next_event.is_ok()
    assert next_event.unwrap().sequence == 4


def test_file_event_journal_preserves_cursor_expiry_after_restart(tmp_path):
    stream = EventStream(
        max_events=2,
        journal=FileEventJournal(tmp_path, max_events=2),
    )
    stream.publish("one", {})
    stream.publish("two", {})
    stream.publish("three", {})

    restarted = EventStream(
        max_events=2,
        journal=FileEventJournal(tmp_path, max_events=2),
    )
    expired = restarted.read(EventCursor(sequence=0))

    assert expired.is_err()
    assert expired.unwrap_err()["errorType"] == "EVENT_CURSOR_EXPIRED"
    assert expired.unwrap_err()["details"]["oldest_sequence"] == 2


def test_file_event_journal_rejects_malformed_state_and_bounds_writes(tmp_path):
    journal = FileEventJournal(tmp_path, max_events=2, max_bytes=160)
    stream = EventStream(max_events=2, journal=journal)
    callbacks = []
    stream.subscribe(callbacks.append)

    too_large = stream.publish("large", {"value": "x" * 200})

    assert too_large.is_err()
    assert too_large.unwrap_err()["errorType"] == "EVENT_JOURNAL_SIZE"
    assert callbacks == []
    assert stream.snapshot().unwrap() == []

    journal.path.write_text(
        json.dumps(
            {
                "version": 1,
                "events": [
                    {
                        "sequence": 2,
                        "event_type": "two",
                        "timestamp": 1.0,
                        "payload": {},
                        "run_id": None,
                    },
                    {
                        "sequence": 1,
                        "event_type": "one",
                        "timestamp": 1.0,
                        "payload": {},
                        "run_id": None,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        EventStream(max_events=2, journal=FileEventJournal(tmp_path, max_events=2))


def test_file_event_journal_rejects_nonfinite_and_unrepresentable_records(tmp_path):
    journal = FileEventJournal(tmp_path, max_events=2)

    nonfinite = journal.append(
        AgentEvent(sequence=1, event_type="bad", timestamp=math.inf, payload={})
    )
    oversized_timestamp = journal.append(
        AgentEvent(sequence=1, event_type="bad", timestamp=10**400, payload={})
    )

    assert nonfinite.is_err()
    assert nonfinite.unwrap_err()["errorType"] == "EVENT_JOURNAL_RECORD_INVALID"
    assert oversized_timestamp.is_err()
    assert (
        oversized_timestamp.unwrap_err()["errorType"] == "EVENT_JOURNAL_RECORD_INVALID"
    )
    assert not journal.path.exists()


def test_journal_failure_prevents_callbacks_and_memory_publication():
    class BrokenJournal:
        max_events = 10

        def load(self):
            from maple.core.result import Result

            return Result.ok([])

        def append(self, event):
            from maple.core.result import Result

            return Result.err(
                {
                    "errorType": "EVENT_JOURNAL_SAVE_ERROR",
                    "message": "journal unavailable",
                }
            )

    received = []
    stream = EventStream(max_events=10, journal=BrokenJournal())
    stream.subscribe(received.append)
    result = stream.publish("safe", {})

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "EVENT_JOURNAL_SAVE_ERROR"
    assert received == []
    assert stream.snapshot().unwrap() == []
    assert stream.metrics()["journal_failures"] == 1
