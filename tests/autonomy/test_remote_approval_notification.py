"""Regression coverage for bounded remote approval notification delivery."""

import json
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional, Tuple

import pytest

from maple.autonomy import (
    ApprovalNotification,
    ApprovalRequest,
    FileApprovalStore,
    HttpApprovalNotifier,
    InMemoryApprovalStore,
    Principal,
    RunClient,
    RunServer,
    WorkflowRegistry,
)
from maple.core.result import Result


def _request(approval_id: str = "remote-approval-1") -> ApprovalRequest:
    return ApprovalRequest(
        approval_id=approval_id,
        tool_call_id="remote-approval-call",
        tool_name="deploy_service",
        arguments={"service": "api", "environment": "staging"},
        trace_id="trace-approval",
        span_id="span-approval",
    )


def _request_http(
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


class RecordingApprovalHandler:
    def __init__(self, *, allowed: bool = True) -> None:
        self.allowed = allowed
        self.notifications: List[ApprovalNotification] = []

    def notify(
        self, notification: ApprovalNotification
    ) -> Result[None, Dict[str, Any]]:
        self.notifications.append(notification)
        if not self.allowed:
            return Result.err(
                {"errorType": "HOST_REJECTED", "message": "notification rejected"}
            )
        return Result.ok(None)


def test_approval_notification_round_trip_excludes_execution_result() -> None:
    notification = ApprovalNotification.from_request(_request(), "created")
    encoded = notification.to_dict()
    encoded["future_field"] = {"ignored": True}
    encoded["execution_result"] = {"content": "secret", "is_error": False}

    parsed = ApprovalNotification.from_dict(encoded)

    assert parsed == notification
    assert "execution_result" not in parsed.to_dict()
    assert "future_field" not in parsed.to_dict()


def test_approval_notification_enforces_event_and_status_invariants() -> None:
    notification = ApprovalNotification.from_request(_request(), "created").to_dict()
    notification["status"] = "approved"

    with pytest.raises(ValueError, match="event and status"):
        ApprovalNotification.from_dict(notification)

    with pytest.raises(ValueError, match="event type"):
        ApprovalNotification.from_request(_request(), "consumed")


def test_http_notifier_delivers_created_approved_and_denied_transitions() -> None:
    handler = RecordingApprovalHandler()
    server = RunServer(
        WorkflowRegistry(),
        auth_token="receiver-token",
        auth_principal=Principal("receiver", ("approval:notify",)),
        approval_notification_handler=handler,
    )
    base_url = server.start()
    try:
        notifier = HttpApprovalNotifier(
            f"{base_url}/v1/approvals/notifications",
            auth_token="receiver-token",
        )
        store = InMemoryApprovalStore(notifier=notifier)
        assert store.create(_request()).is_ok()
        assert store.decide(
            "remote-approval-1", True, edited_arguments={"safe": True}
        ).is_ok()
        assert store.create(_request("remote-approval-2")).is_ok()
        assert store.decide("remote-approval-2", False).is_ok()
    finally:
        server.close()

    assert [item.event_type for item in handler.notifications] == [
        "created",
        "approved",
        "created",
        "denied",
    ]
    assert handler.notifications[1].decision is not None
    assert handler.notifications[1].decision.edited_arguments == {"safe": True}
    assert all(
        "execution_result" not in item.to_dict() for item in handler.notifications
    )


def test_file_approval_store_notifies_after_persistence(tmp_path: Any) -> None:
    handler = RecordingApprovalHandler()
    store = FileApprovalStore(tmp_path, notifier=handler)

    assert store.create(_request("file-approval-1")).is_ok()
    decided = store.decide("file-approval-1", True)

    assert decided.is_ok()
    assert [item.event_type for item in handler.notifications] == [
        "created",
        "approved",
    ]
    assert (
        FileApprovalStore(tmp_path).get("file-approval-1").unwrap().status == "approved"
    )


def test_notification_failure_preserves_authoritative_approval_state() -> None:
    handler = RecordingApprovalHandler(allowed=False)
    store = InMemoryApprovalStore(notifier=handler)

    created = store.create(_request("failed-approval-1"))
    persisted_created = store.get("failed-approval-1").unwrap()
    decided = store.decide("failed-approval-1", True)
    persisted_decided = store.get("failed-approval-1").unwrap()

    assert created.is_err()
    assert created.unwrap_err()["errorType"] == "APPROVAL_NOTIFICATION_ERROR"
    assert decided.is_err()
    assert persisted_created is not None and persisted_created.status == "pending"
    assert persisted_decided is not None and persisted_decided.status == "approved"
    assert len(handler.notifications) == 2


def test_notification_scope_denial_does_not_invoke_receiver() -> None:
    handler = RecordingApprovalHandler()
    server = RunServer(
        WorkflowRegistry(),
        auth_token="receiver-token",
        auth_principal=Principal("reader", ("approval:read",)),
        approval_notification_handler=handler,
    )
    base_url = server.start()
    try:
        result = RunClient(
            base_url, auth_token="receiver-token"
        ).publish_approval_notification(
            ApprovalNotification.from_request(_request(), "created")
        )
    finally:
        server.close()

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "FORBIDDEN"
    assert handler.notifications == []


def test_notification_requires_bearer_authentication() -> None:
    handler = RecordingApprovalHandler()
    server = RunServer(
        WorkflowRegistry(),
        auth_token="receiver-token",
        approval_notification_handler=handler,
    )
    base_url = server.start()
    try:
        result = RunClient(base_url).publish_approval_notification(
            ApprovalNotification.from_request(_request(), "created")
        )
    finally:
        server.close()

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "UNAUTHORIZED"
    assert handler.notifications == []


def test_malformed_notification_is_rejected_before_receiver_callback() -> None:
    handler = RecordingApprovalHandler()
    server = RunServer(
        WorkflowRegistry(),
        auth_token="receiver-token",
        approval_notification_handler=handler,
    )
    base_url = server.start()
    try:
        status, payload = _request_http(
            f"{base_url}/v1/approvals/notifications",
            method="POST",
            payload={"notification": {"event_type": "created"}},
            token="receiver-token",
        )
    finally:
        server.close()

    assert status == 400
    assert payload["error"]["errorType"] == "APPROVAL_NOTIFICATION_INVALID"
    assert handler.notifications == []


def test_oversized_notification_is_rejected_before_receiver_callback() -> None:
    handler = RecordingApprovalHandler()
    server = RunServer(
        WorkflowRegistry(),
        auth_token="receiver-token",
        max_body_bytes=64,
        approval_notification_handler=handler,
    )
    base_url = server.start()
    try:
        status, payload = _request_http(
            f"{base_url}/v1/approvals/notifications",
            method="POST",
            payload={
                "notification": ApprovalNotification.from_request(
                    _request(), "created"
                ).to_dict()
            },
            token="receiver-token",
        )
    finally:
        server.close()

    assert status == 413
    assert payload["error"]["errorType"] == "REQUEST_TOO_LARGE"
    assert handler.notifications == []


def test_receiver_does_not_mutate_configured_approval_store() -> None:
    handler = RecordingApprovalHandler()
    store = InMemoryApprovalStore()
    server = RunServer(
        WorkflowRegistry(),
        auth_token="receiver-token",
        approval_store=store,
        approval_notification_handler=handler,
    )
    base_url = server.start()
    try:
        result = RunClient(
            base_url, auth_token="receiver-token"
        ).publish_approval_notification(
            ApprovalNotification.from_request(_request(), "created")
        )
    finally:
        server.close()

    assert result.is_ok()
    assert store.get("remote-approval-1").unwrap() is None


def test_http_notifier_requires_https_for_non_loopback_and_rejects_bad_ack() -> None:
    with pytest.raises(ValueError, match="requires https"):
        HttpApprovalNotifier("http://example.test/notifications")

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
        result = HttpApprovalNotifier(endpoint).notify(
            ApprovalNotification.from_request(_request(), "created")
        )
    finally:
        http_server.shutdown()
        thread.join(timeout=2)
        http_server.server_close()

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "APPROVAL_NOTIFICATION_RESPONSE_INVALID"


def test_receiver_without_callback_returns_typed_unavailable_error() -> None:
    server = RunServer(WorkflowRegistry(), auth_token="receiver-token")
    base_url = server.start()
    try:
        result = RunClient(
            base_url, auth_token="receiver-token"
        ).publish_approval_notification(
            ApprovalNotification.from_request(_request(), "created")
        )
    finally:
        server.close()

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "APPROVAL_NOTIFICATION_UNAVAILABLE"
