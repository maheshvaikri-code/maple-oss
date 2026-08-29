"""Tests for bounded event streaming and payload redaction."""

import json
import math
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from maple.autonomy.events import (
    AgentEvent,
    EventCursor,
    EventDelivery,
    EventDeliveryFailure,
    EventForwarder,
    EventForwarderScheduler,
    EventForwardReport,
    EventStream,
    FileEventCursorStore,
    FileEventDeduplicationStore,
    FileEventJournal,
    HttpEventBatchSender,
    HttpEventExporter,
    InMemoryEventCursorStore,
    InMemoryEventDeduplicationStore,
    RedactionPolicy,
)
from maple.autonomy.execution import CancellationToken
from maple.core.result import Result


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


def test_search_matches_exact_redacted_trace_run_and_event_filters():
    stream = EventStream(max_events=4)
    stream.publish(
        "model.started",
        {"trace_id": "trace-a", "secret": "hidden"},
        run_id="run-a",
    )
    stream.publish(
        "model.finished",
        {"trace_id": "trace-b", "nested": {"trace_id": "trace-a"}},
        run_id="run-a",
    )
    stream.publish("tool.started", {"trace_id": "trace-a"}, run_id="run-b")

    by_trace = stream.search(trace_id="trace-a", limit=1)
    by_run = stream.search(run_id="run-a")
    by_type = stream.search(event_type="tool.started")
    next_page = stream.search(trace_id="trace-a", after_sequence=1)

    assert by_trace.is_ok()
    assert [event.sequence for event in by_trace.unwrap().events] == [1]
    assert by_trace.unwrap().events[0].payload["secret"] == "[REDACTED]"
    assert by_trace.unwrap().next_cursor.sequence == 1
    assert by_run.is_ok()
    assert [event.event_type for event in by_run.unwrap().events] == [
        "model.started",
        "model.finished",
    ]
    assert by_type.is_ok()
    assert [event.run_id for event in by_type.unwrap().events] == ["run-b"]
    assert next_page.is_ok()
    assert [event.sequence for event in next_page.unwrap().events] == [3]


def test_search_requires_bounded_filters_and_preserves_cursor_expiry():
    stream = EventStream(max_events=2)
    stream.publish("one", {}, run_id="run-a")
    stream.publish("two", {}, run_id="run-a")
    stream.publish("three", {}, run_id="run-a")

    missing_filter = stream.search()
    invalid_filter = stream.search(trace_id="bad\ntrace")
    expired = stream.search(run_id="run-a", after_sequence=0)

    assert missing_filter.is_err()
    assert missing_filter.unwrap_err()["errorType"] == "EVENT_SEARCH_INVALID"
    assert invalid_filter.is_err()
    assert invalid_filter.unwrap_err()["errorType"] == "EVENT_SEARCH_INVALID"
    assert expired.is_err()
    assert expired.unwrap_err()["errorType"] == "EVENT_CURSOR_EXPIRED"


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


def test_in_memory_event_cursor_store_is_monotonic():
    store = InMemoryEventCursorStore()

    advanced = store.save(EventCursor(sequence=3))
    regressed = store.save(EventCursor(sequence=2))

    assert advanced.is_ok()
    assert store.load().unwrap().sequence == 3
    assert regressed.is_err()
    assert regressed.unwrap_err()["errorType"] == "EVENT_CURSOR_CONFLICT"


def test_file_event_cursor_store_rehydrates_and_rejects_regression(tmp_path):
    store = FileEventCursorStore(tmp_path)
    assert store.save(EventCursor(sequence=4)).is_ok()

    restarted = FileEventCursorStore(tmp_path)
    loaded = restarted.load()
    regressed = restarted.save(EventCursor(sequence=3))
    persisted = json.loads(store.path.read_text(encoding="utf-8"))

    assert loaded.is_ok()
    assert loaded.unwrap().sequence == 4
    assert persisted == {"version": 1, "cursor": {"sequence": 4}}
    assert regressed.is_err()
    assert regressed.unwrap_err()["errorType"] == "EVENT_CURSOR_CONFLICT"


def test_file_event_cursor_store_rejects_malformed_state_without_advancing(tmp_path):
    store = FileEventCursorStore(tmp_path)
    store.path.write_text(
        json.dumps({"version": True, "cursor": {"sequence": 3}}),
        encoding="utf-8",
    )

    loaded = store.load()
    attempted_save = store.save(EventCursor(sequence=4))

    assert loaded.is_err()
    assert loaded.unwrap_err()["errorType"] == "EVENT_CURSOR_LOAD_ERROR"
    assert attempted_save.is_err()
    assert attempted_save.unwrap_err()["errorType"] == "EVENT_CURSOR_LOAD_ERROR"
    assert json.loads(store.path.read_text(encoding="utf-8"))["version"] is True


def test_event_forwarder_advances_only_through_contiguous_successes():
    source = EventStream(max_events=5)
    source.publish("one", {})
    source.publish("two", {})
    source.publish("three", {})
    cursor_store = InMemoryEventCursorStore()
    calls = []
    failure = EventDeliveryFailure(
        index=1,
        error={"errorType": "REMOTE_REJECTED", "message": "rejected"},
    )

    class Sender:
        def __init__(self):
            self.responses = [
                EventDelivery(published=(0, 2), failed=(failure,)),
                EventDelivery(published=(0, 1), failed=()),
            ]

        def send(self, events):
            calls.append([event.sequence for event in events])
            return Result.ok(self.responses.pop(0))

    forwarder = EventForwarder(source, Sender(), cursor_store, max_batch_size=3)
    first = forwarder.forward()
    second = forwarder.forward()

    assert first.is_ok()
    assert first.unwrap().attempted == 3
    assert first.unwrap().published == (0, 2)
    assert first.unwrap().failed == (failure,)
    assert first.unwrap().next_cursor.sequence == 1
    assert second.is_ok()
    assert second.unwrap().cursor.sequence == 1
    assert second.unwrap().next_cursor.sequence == 3
    assert calls == [[1, 2, 3], [2, 3]]
    assert cursor_store.load().unwrap().sequence == 3


def test_event_forwarder_preserves_cursor_when_sender_fails():
    source = EventStream()
    source.publish("one", {})
    cursor_store = InMemoryEventCursorStore()

    class Sender:
        def send(self, events):
            return Result.err(
                {"errorType": "EVENT_FORWARD_TRANSPORT_ERROR", "message": "offline"}
            )

    result = EventForwarder(source, Sender(), cursor_store).forward()

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "EVENT_FORWARD_TRANSPORT_ERROR"
    assert cursor_store.load().unwrap().sequence == 0


def test_event_forwarder_preserves_cursor_when_cursor_save_fails():
    source = EventStream()
    source.publish("one", {})

    class CursorStore:
        def load(self):
            return Result.ok(EventCursor())

        def save(self, cursor):
            return Result.err(
                {"errorType": "EVENT_CURSOR_SAVE_ERROR", "message": "disk full"}
            )

    class Sender:
        def send(self, events):
            return Result.ok(EventDelivery(published=(0,), failed=()))

    result = EventForwarder(source, Sender(), CursorStore()).forward()

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "EVENT_CURSOR_SAVE_ERROR"


def test_event_forwarder_fails_closed_when_source_cursor_expired():
    source = EventStream(max_events=2)
    source.publish("one", {})
    source.publish("two", {})
    source.publish("three", {})
    calls = []

    class Sender:
        def send(self, events):
            calls.append(events)
            return Result.ok(EventDelivery(published=(0,), failed=()))

    result = EventForwarder(
        source, Sender(), InMemoryEventCursorStore(), max_batch_size=1
    ).forward()

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "EVENT_CURSOR_EXPIRED"
    assert calls == []


def test_http_event_batch_sender_redacts_and_parses_complete_acknowledgement():
    received = []

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_POST(self):  # noqa: N802
            length = int(self.headers["Content-Length"])
            received.append(
                (
                    self.headers.get("Authorization"),
                    json.loads(self.rfile.read(length)),
                )
            )
            body = json.dumps(
                {
                    "published": [{"index": 0}, {"index": 1}],
                    "failed": [],
                }
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            self.wfile.flush()

        def log_message(self, format, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        sender = HttpEventBatchSender(
            f"http://127.0.0.1:{server.server_address[1]}/v1/events/batch",
            auth_token="batch-token",
        )
        result = sender.send(
            [
                AgentEvent(
                    sequence=1,
                    event_type="one",
                    timestamp=1.0,
                    payload={"secret": "hidden"},
                ),
                AgentEvent(
                    sequence=2,
                    event_type="two",
                    timestamp=2.0,
                    payload={"value": 2},
                ),
            ]
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert result.is_ok()
    assert result.unwrap().published == (0, 1)
    assert result.unwrap().failed == ()
    assert received[0][0] == "Bearer batch-token"
    assert received[0][1]["events"][0]["payload"]["secret"] == "[REDACTED]"
    assert "sequence" not in received[0][1]["events"][0]


def test_http_event_batch_sender_rejects_incomplete_acknowledgement():
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            length = int(self.headers["Content-Length"])
            self.rfile.read(length)
            body = b'{"published":[{"index":0}],"failed":[]}'
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        sender = HttpEventBatchSender(
            f"http://127.0.0.1:{server.server_address[1]}/v1/events/batch"
        )
        result = sender.send(
            [
                AgentEvent(1, "one", 1.0, {}),
                AgentEvent(2, "two", 2.0, {}),
            ]
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "EVENT_DELIVERY_INVALID"


def test_http_event_batch_sender_rejects_oversized_request_before_network():
    sender = HttpEventBatchSender(
        "http://127.0.0.1:1/v1/events/batch",
        max_request_bytes=1,
    )

    result = sender.send([AgentEvent(1, "one", 1.0, {})])

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "EVENT_FORWARD_REQUEST_TOO_LARGE"


def test_event_forwarder_scheduler_run_once_drains_only_the_configured_bound():
    class Sender:
        def send(self, events):
            return Result.ok(
                EventDelivery(
                    published=tuple(range(len(events))),
                    failed=(),
                )
            )

    source = EventStream(max_events=10)
    for index in range(3):
        assert source.publish(f"event-{index}", {"index": index}).is_ok()
    forwarder = EventForwarder(
        source,
        Sender(),
        InMemoryEventCursorStore(),
        max_batch_size=1,
    )
    scheduler = EventForwarderScheduler(
        forwarder,
        interval_seconds=1.0,
        max_batches_per_tick=2,
    )

    tick = scheduler.run_once()

    assert tick.is_ok()
    assert len(tick.unwrap()) == 2
    assert tick.unwrap()[-1].next_cursor.sequence == 2
    stats = scheduler.metrics()
    assert stats.ticks == 1
    assert stats.batches == 2
    assert stats.events_attempted == 2
    assert stats.events_published == 2


def test_event_forwarder_scheduler_background_lifecycle_is_explicit_and_owned():
    delivered = threading.Event()

    class Sender:
        def send(self, events):
            delivered.set()
            return Result.ok(
                EventDelivery(
                    published=tuple(range(len(events))),
                    failed=(),
                )
            )

    source = EventStream(max_events=4)
    assert source.publish("scheduled", {}).is_ok()
    forwarder = EventForwarder(
        source,
        Sender(),
        InMemoryEventCursorStore(),
        max_batch_size=1,
    )
    scheduler = EventForwarderScheduler(forwarder, interval_seconds=0.02)

    assert scheduler.start().is_ok()
    assert delivered.wait(2.0)
    assert scheduler.stop(timeout_seconds=2.0).is_ok()
    assert not scheduler.metrics().running
    assert scheduler.metrics().batches == 1


def test_event_forwarder_scheduler_stop_timeout_keeps_worker_owned():
    started = threading.Event()
    release = threading.Event()

    class BlockingForwarder:
        def forward(self):
            started.set()
            release.wait(2.0)
            return Result.ok(EventForwardReport(EventCursor(), EventCursor(), (), ()))

    scheduler = EventForwarderScheduler(
        BlockingForwarder(),
        interval_seconds=0.02,
    )
    assert scheduler.start().is_ok()
    assert started.wait(2.0)

    timed_out = scheduler.stop(timeout_seconds=0.01)
    release.set()
    stopped = scheduler.stop(timeout_seconds=2.0)

    assert timed_out.is_err()
    assert timed_out.unwrap_err()["errorType"] == "EVENT_SCHEDULER_STOP_TIMEOUT"
    assert stopped.is_ok()
    assert not scheduler.metrics().running


def test_event_forwarder_scheduler_sanitizes_forward_errors():
    class FailingForwarder:
        def forward(self):
            return Result.err(
                {"errorType": "REMOTE_FAILURE", "message": "secret-token"}
            )

    scheduler = EventForwarderScheduler(FailingForwarder())

    result = scheduler.run_once()
    stats = scheduler.metrics()

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "EVENT_SCHEDULER_FORWARD_ERROR"
    assert stats.forward_errors == 1
    assert stats.last_error is not None
    assert stats.last_error["details"]["cause"] == "REMOTE_FAILURE"
    assert "secret-token" not in str(stats.last_error)


def test_event_deduplication_store_claims_completes_and_replays_redacted_events():
    store = InMemoryEventDeduplicationStore(max_entries=2, ttl_seconds=10.0)
    source_event = AgentEvent(
        sequence=1,
        event_type="agent.completed",
        timestamp=0.0,
        payload={"secret": "hidden", "status": "ok"},
        run_id="run-1",
    )

    claimed = store.claim("source-a", 1, source_event)
    pending = store.claim("source-a", 1, source_event)
    assert claimed.is_ok()
    assert claimed.unwrap() is None
    assert pending.is_err()
    assert pending.unwrap_err()["errorType"] == "EVENT_DEDUPLICATION_IN_PROGRESS"

    destination_event = AgentEvent(
        sequence=7,
        event_type="agent.completed",
        timestamp=1.0,
        payload={"secret": "[REDACTED]", "status": "ok"},
        run_id="run-1",
    )
    completed = store.complete("source-a", 1, destination_event)
    replayed = store.claim("source-a", 1, source_event)
    conflict = store.claim(
        "source-a",
        1,
        AgentEvent(
            sequence=1,
            event_type="agent.completed",
            timestamp=0.0,
            payload={"secret": "different", "status": "ok"},
            run_id="run-1",
        ),
    )

    assert completed.is_ok()
    assert replayed.is_ok()
    assert replayed.unwrap() == destination_event
    assert conflict.is_err()
    assert conflict.unwrap_err()["errorType"] == "EVENT_DEDUPLICATION_CONFLICT"
    assert store.metrics() == {"retained_claims": 1, "max_entries": 2}


def test_file_event_deduplication_store_replays_completed_claim_after_restart(tmp_path):
    now = [100.0]
    source_event = AgentEvent(
        sequence=1,
        event_type="agent.completed",
        timestamp=0.0,
        payload={"secret": "source-only", "status": "ok"},
        run_id="run-1",
    )
    destination_event = AgentEvent(
        sequence=7,
        event_type="agent.completed",
        timestamp=1.0,
        payload={"status": "ok"},
        run_id="run-1",
    )
    store = FileEventDeduplicationStore(
        tmp_path, ttl_seconds=10.0, clock=lambda: now[0]
    )

    assert store.claim("source-a", 1, source_event).unwrap() is None
    completed = store.complete("source-a", 1, destination_event)
    assert completed.is_ok()

    restarted = FileEventDeduplicationStore(
        tmp_path, ttl_seconds=10.0, clock=lambda: now[0]
    )
    replayed = restarted.claim("source-a", 1, source_event)

    assert replayed.is_ok()
    assert replayed.unwrap() == destination_event
    assert replayed.unwrap() is not destination_event
    persisted = json.loads(restarted.path.read_text(encoding="utf-8"))
    assert "source-only" not in str(persisted)
    assert persisted["records"][0]["event"]["payload"] == {"status": "ok"}


def test_file_event_deduplication_store_fences_pending_claims_and_allows_abort(
    tmp_path,
):
    source_event = AgentEvent(
        sequence=1,
        event_type="agent.started",
        timestamp=0.0,
        payload={"status": "ok"},
    )
    first = FileEventDeduplicationStore(tmp_path)
    second = FileEventDeduplicationStore(tmp_path)

    assert first.claim("source-a", 1, source_event).unwrap() is None
    pending = second.claim("source-a", 1, source_event)
    assert pending.is_err()
    assert pending.unwrap_err()["errorType"] == "EVENT_DEDUPLICATION_IN_PROGRESS"
    assert first.abort("source-a", 1).is_ok()
    assert second.claim("source-a", 1, source_event).unwrap() is None


def test_file_event_deduplication_store_rejects_bad_state_without_repairing_file(
    tmp_path,
):
    store = FileEventDeduplicationStore(tmp_path)
    store.path.write_text(
        json.dumps({"version": 1, "records": [{"source_id": "bad"}]}),
        encoding="utf-8",
    )
    before = store.path.read_bytes()
    source_event = AgentEvent(
        sequence=1,
        event_type="agent.completed",
        timestamp=0.0,
        payload={},
    )

    result = store.claim("source-a", 1, source_event)

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "EVENT_DEDUPLICATION_LOAD_ERROR"
    assert store.path.read_bytes() == before


def test_file_event_deduplication_store_bounds_capacity_and_expiry_without_partial_write(
    tmp_path,
):
    now = [100.0]
    source_one = AgentEvent(
        sequence=1,
        event_type="one",
        timestamp=0.0,
        payload={},
    )
    source_two = AgentEvent(
        sequence=2,
        event_type="two",
        timestamp=0.0,
        payload={},
    )
    store = FileEventDeduplicationStore(
        tmp_path, max_entries=1, ttl_seconds=1.0, clock=lambda: now[0]
    )
    assert store.claim("source-a", 1, source_one).is_ok()
    before = store.path.read_bytes()
    capacity = store.claim("source-b", 2, source_two)
    assert capacity.is_err()
    assert capacity.unwrap_err()["errorType"] == "EVENT_DEDUPLICATION_CAPACITY"
    assert store.path.read_bytes() == before

    now[0] = 102.0
    expired = store.claim("source-b", 2, source_two)
    assert expired.is_ok()
    assert expired.unwrap() is None


def test_file_event_deduplication_store_rejects_oversized_state_without_mutation(
    tmp_path,
):
    store = FileEventDeduplicationStore(tmp_path, max_bytes=128)
    source_event = AgentEvent(
        sequence=1,
        event_type="agent.completed",
        timestamp=0.0,
        payload={},
    )

    result = store.claim("source-a", 1, source_event)

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "EVENT_DEDUPLICATION_SIZE"
    assert not store.path.exists()


def test_file_event_deduplication_store_rejects_oversized_completion_without_mutation(
    tmp_path,
):
    store = FileEventDeduplicationStore(tmp_path, max_bytes=400)
    source_event = AgentEvent(
        sequence=1,
        event_type="agent.completed",
        timestamp=0.0,
        payload={},
    )
    destination_event = AgentEvent(
        sequence=2,
        event_type="agent.completed",
        timestamp=0.0,
        payload={"value": "x" * 500},
    )
    assert store.claim("source-a", 1, source_event).is_ok()
    before = store.path.read_bytes()

    result = store.complete("source-a", 1, destination_event)

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "EVENT_DEDUPLICATION_SIZE"
    assert store.path.read_bytes() == before
    pending = store.claim("source-a", 1, source_event)
    assert pending.is_err()
    assert pending.unwrap_err()["errorType"] == "EVENT_DEDUPLICATION_IN_PROGRESS"


def test_file_event_deduplication_store_serializes_concurrent_local_instances(
    tmp_path,
):
    source_event = AgentEvent(
        sequence=1,
        event_type="agent.completed",
        timestamp=0.0,
        payload={"status": "ok"},
    )
    stores = [FileEventDeduplicationStore(tmp_path) for _ in range(2)]
    results = [None, None]

    def claim(index):
        results[index] = stores[index].claim("source-a", 1, source_event)

    threads = [threading.Thread(target=claim, args=(index,)) for index in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5.0)

    assert all(result is not None for result in results)
    assert sum(result.is_ok() and result.unwrap() is None for result in results) == 1
    assert (
        sum(
            result.is_err()
            and result.unwrap_err()["errorType"] == "EVENT_DEDUPLICATION_IN_PROGRESS"
            for result in results
        )
        == 1
    )


def test_http_event_batch_sender_deduplicates_replayed_source_sequences():
    from maple.autonomy import RunClient, RunServer, WorkflowRegistry

    destination = EventStream(max_events=10)
    server = RunServer(
        WorkflowRegistry(),
        event_stream=destination,
        event_deduplication_store=InMemoryEventDeduplicationStore(),
        auth_token="forward-token",
    )
    base_url = server.start()
    try:
        source = EventStream(max_events=10)
        source.publish("one", {"secret": "hidden"})
        events = source.snapshot().unwrap()
        sender = HttpEventBatchSender(
            f"{base_url}/v1/events/batch",
            auth_token="forward-token",
            source_id="source-a",
        )
        first = sender.send(events)
        second = sender.send(events)
        remote = RunClient(base_url, auth_token="forward-token").read_events(
            EventCursor(), limit=10
        )
    finally:
        server.close()

    assert first.is_ok()
    assert second.is_ok()
    assert first.unwrap().published == (0,)
    assert second.unwrap().published == (0,)
    assert remote.is_ok()
    remote_events = remote.unwrap()["batch"]["events"]
    assert len(remote_events) == 1
    assert remote_events[0]["payload"]["secret"] == "[REDACTED]"


def test_http_event_batch_sender_replays_durable_claim_after_receiver_restart(
    tmp_path,
):
    from maple.autonomy import RunServer, WorkflowRegistry

    destination = EventStream(max_events=10)
    source = EventStream(max_events=10)
    source.publish("one", {"secret": "hidden"})
    events = source.snapshot().unwrap()
    sender = None

    for server_index in range(2):
        durable_store = FileEventDeduplicationStore(tmp_path / "dedup")
        server = RunServer(
            WorkflowRegistry(),
            event_stream=destination,
            event_deduplication_store=durable_store,
            auth_token="forward-token",
        )
        base_url = server.start()
        try:
            sender = HttpEventBatchSender(
                f"{base_url}/v1/events/batch",
                auth_token="forward-token",
                source_id="source-a",
            )
            delivered = sender.send(events)
        finally:
            server.close()
        assert delivered.is_ok(), f"receiver restart {server_index} failed"

    assert sender is not None
    assert delivered.unwrap().published == (0,)
    assert len(destination.snapshot().unwrap()) == 1


def test_file_event_forwarder_replays_authenticated_batches_after_restart(tmp_path):
    from maple.autonomy.server import RunClient, RunServer, WorkflowRegistry

    destination = EventStream(max_events=10)
    server = RunServer(
        WorkflowRegistry(),
        event_stream=destination,
        auth_token="forward-token",
    )
    base_url = server.start()
    try:
        source_directory = tmp_path / "source"
        source = EventStream(
            max_events=10,
            journal=FileEventJournal(source_directory / "journal", max_events=10),
        )
        source.publish("one", {"secret": "hidden"})
        source.publish("two", {"value": 2})
        source.publish("three", {"value": 3})
        sender = HttpEventBatchSender(
            f"{base_url}/v1/events/batch", auth_token="forward-token"
        )
        cursor_directory = tmp_path / "cursor"
        first_forwarder = EventForwarder(
            source,
            sender,
            FileEventCursorStore(cursor_directory),
            max_batch_size=2,
        )
        first = first_forwarder.forward()
        second = first_forwarder.forward()

        restarted_source = EventStream(
            max_events=10,
            journal=FileEventJournal(source_directory / "journal", max_events=10),
        )
        restarted = EventForwarder(
            restarted_source,
            HttpEventBatchSender(
                f"{base_url}/v1/events/batch", auth_token="forward-token"
            ),
            FileEventCursorStore(cursor_directory),
            max_batch_size=2,
        )
        empty = restarted.forward()
        remote = RunClient(base_url, auth_token="forward-token").read_events(
            EventCursor(), limit=10
        )
    finally:
        server.close()

    assert first.is_ok()
    assert second.is_ok()
    assert first.unwrap().next_cursor.sequence == 2
    assert second.unwrap().next_cursor.sequence == 3
    assert empty.is_ok()
    assert empty.unwrap().attempted == 0
    assert remote.is_ok()
    remote_events = remote.unwrap()["batch"]["events"]
    assert [event["event_type"] for event in remote_events] == ["one", "two", "three"]
    assert remote_events[0]["payload"]["secret"] == "[REDACTED]"
