"""Regression coverage for bounded remote human-input notification delivery."""

import json
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional, Tuple

import pytest

from maple.autonomy import (
    HttpHumanInputNotifier,
    HumanInputNotification,
    HumanInputRequest,
    InMemoryHumanInputStore,
    Principal,
    RunClient,
    RunServer,
    WorkflowRegistry,
)
from maple.core.result import Result


def _request(
    url: str,
    *,
    method: str = "GET",
    payload: Optional[Dict[str, Any]] = None,
    token: Optional[str] = None,
) -> Tuple[int, Dict[str, Any]]:
    data = None
    headers = {"Accept": "application/json"}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            return int(response.status), json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return int(exc.code), json.loads(exc.read().decode("utf-8"))


def _request_model(interaction_id: str = "remote-notification-1") -> HumanInputRequest:
    return HumanInputRequest(
        interaction_id=interaction_id,
        run_id="remote-notification-run",
        tool_call_id="remote-notification-call",
        prompt="Confirm the deployment.",
        input_schema={
            "type": "object",
            "properties": {"confirmed": {"type": "boolean"}},
            "required": ["confirmed"],
            "additionalProperties": False,
        },
        max_rounds=2,
    )


class RecordingNotificationHandler:
    def __init__(self, *, allowed: bool = True) -> None:
        self.allowed = allowed
        self.notifications: List[HumanInputNotification] = []

    def notify(
        self, notification: HumanInputNotification
    ) -> Result[None, Dict[str, Any]]:
        self.notifications.append(notification)
        if not self.allowed:
            return Result.err(
                {"errorType": "HOST_REJECTED", "message": "notification rejected"}
            )
        return Result.ok(None)


def test_notification_round_trip_ignores_future_fields_and_excludes_response_data() -> (
    None
):
    notification = HumanInputNotification.from_request(_request_model(), "created")
    encoded = notification.to_dict()
    encoded["future_field"] = {"ignored": True}
    encoded["response"] = {"secret": "must-not-cross"}

    parsed = HumanInputNotification.from_dict(encoded)

    assert parsed == notification
    assert "response" not in parsed.to_dict()
    assert "future_field" not in parsed.to_dict()


def test_http_notifier_delivers_created_responded_and_continued_transitions() -> None:
    handler = RecordingNotificationHandler()
    server = RunServer(
        WorkflowRegistry(),
        auth_token="receiver-token",
        auth_principal=Principal("receiver", ("interaction:notify",)),
        human_input_notification_handler=handler,
    )
    base_url = server.start()
    try:
        notifier = HttpHumanInputNotifier(
            f"{base_url}/v1/interactions/notifications",
            auth_token="receiver-token",
        )
        store = InMemoryHumanInputStore(notifier=notifier)

        assert store.create(_request_model()).is_ok()
        assert store.respond(
            "remote-notification-1", {"confirmed": True}, actor_id="operator"
        ).is_ok()
        assert store.continue_round(
            "remote-notification-1",
            "Confirm the second step.",
            {"type": "object", "required": ["confirmed"]},
            actor_id="operator",
        ).is_ok()
    finally:
        server.close()

    assert [item.event_type for item in handler.notifications] == [
        "created",
        "responded",
        "continued",
    ]
    assert all("response" not in item.to_dict() for item in handler.notifications)


def test_notification_scope_denial_does_not_invoke_receiver() -> None:
    handler = RecordingNotificationHandler()
    server = RunServer(
        WorkflowRegistry(),
        auth_token="receiver-token",
        auth_principal=Principal("reader", ("interaction:read",)),
        human_input_notification_handler=handler,
    )
    base_url = server.start()
    try:
        result = RunClient(
            base_url, auth_token="receiver-token"
        ).publish_human_input_notification(
            HumanInputNotification.from_request(_request_model(), "created")
        )
    finally:
        server.close()

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "FORBIDDEN"
    assert handler.notifications == []


def test_notification_requires_bearer_authentication() -> None:
    handler = RecordingNotificationHandler()
    server = RunServer(
        WorkflowRegistry(),
        auth_token="receiver-token",
        human_input_notification_handler=handler,
    )
    base_url = server.start()
    try:
        result = RunClient(base_url).publish_human_input_notification(
            HumanInputNotification.from_request(_request_model(), "created")
        )
    finally:
        server.close()

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "UNAUTHORIZED"
    assert handler.notifications == []


def test_malformed_notification_is_rejected_before_receiver_callback() -> None:
    handler = RecordingNotificationHandler()
    server = RunServer(
        WorkflowRegistry(),
        auth_token="receiver-token",
        human_input_notification_handler=handler,
    )
    base_url = server.start()
    try:
        status, payload = _request(
            f"{base_url}/v1/interactions/notifications",
            method="POST",
            payload={"notification": {"event_type": "created"}},
            token="receiver-token",
        )
    finally:
        server.close()

    assert status == 400
    assert payload["error"]["errorType"] == "HUMAN_INPUT_NOTIFICATION_INVALID"
    assert handler.notifications == []


def test_oversized_notification_is_rejected_before_receiver_callback() -> None:
    handler = RecordingNotificationHandler()
    server = RunServer(
        WorkflowRegistry(),
        auth_token="receiver-token",
        max_body_bytes=64,
        human_input_notification_handler=handler,
    )
    base_url = server.start()
    try:
        status, payload = _request(
            f"{base_url}/v1/interactions/notifications",
            method="POST",
            payload={
                "notification": HumanInputNotification.from_request(
                    _request_model(), "created"
                ).to_dict()
            },
            token="receiver-token",
        )
    finally:
        server.close()

    assert status == 413
    assert payload["error"]["errorType"] == "REQUEST_TOO_LARGE"
    assert handler.notifications == []


def test_notification_failure_preserves_persisted_state_without_retry() -> None:
    handler = RecordingNotificationHandler(allowed=False)
    server = RunServer(
        WorkflowRegistry(),
        auth_token="receiver-token",
        human_input_notification_handler=handler,
    )
    base_url = server.start()
    try:
        notifier = HttpHumanInputNotifier(
            f"{base_url}/v1/interactions/notifications",
            auth_token="receiver-token",
        )
        store = InMemoryHumanInputStore(notifier=notifier)
        created = store.create(_request_model("remote-notification-failure"))
        persisted = store.get("remote-notification-failure").unwrap()
    finally:
        server.close()

    assert created.is_err()
    assert created.unwrap_err()["errorType"] == "HUMAN_INPUT_NOTIFICATION_ERROR"
    assert len(handler.notifications) == 1
    assert persisted is not None
    assert persisted.status == "pending"


def test_http_notifier_requires_https_for_non_loopback_and_rejects_bad_ack() -> None:
    with pytest.raises(ValueError, match="requires https"):
        HttpHumanInputNotifier("http://example.test/notifications")

    class BadAckHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            self.rfile.read(length)
            body = b'{"accepted":false}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:
            return

    http_server = ThreadingHTTPServer(("127.0.0.1", 0), BadAckHandler)
    thread = threading.Thread(target=http_server.serve_forever, daemon=True)
    thread.start()
    try:
        endpoint = f"http://127.0.0.1:{http_server.server_port}/notifications"
        result = HttpHumanInputNotifier(endpoint).notify(
            HumanInputNotification.from_request(_request_model(), "created")
        )
    finally:
        http_server.shutdown()
        thread.join(timeout=2)
        http_server.server_close()

    assert result.is_err()
    assert (
        result.unwrap_err()["errorType"] == "HUMAN_INPUT_NOTIFICATION_RESPONSE_INVALID"
    )


def test_receiver_without_callback_returns_typed_unavailable_error() -> None:
    server = RunServer(WorkflowRegistry(), auth_token="receiver-token")
    base_url = server.start()
    try:
        result = RunClient(
            base_url, auth_token="receiver-token"
        ).publish_human_input_notification(
            HumanInputNotification.from_request(_request_model(), "created")
        )
    finally:
        server.close()

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "HUMAN_INPUT_NOTIFICATION_UNAVAILABLE"
