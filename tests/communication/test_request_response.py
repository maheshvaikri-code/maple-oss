"""Tests for maple.communication.request_response - RequestResponsePattern."""

import pytest
import threading
from unittest.mock import MagicMock
from maple.communication.request_response import (
    RequestResponsePattern, RequestConfig
)
from maple.core.message import Message
from maple.core.result import Result
from maple.core.types import Priority


@pytest.fixture
def mock_agent():
    agent = MagicMock()
    agent.agent_id = "rr_test_agent"
    agent.send = MagicMock(return_value=Result.ok("msg_123"))
    return agent


@pytest.fixture
def rr(mock_agent):
    config = RequestConfig(timeout_seconds=1.0, max_retries=3, retry_delay=0.1)
    return RequestResponsePattern(mock_agent, config)


class TestRequestConfig:
    """Test RequestConfig dataclass."""

    def test_defaults(self):
        rc = RequestConfig()
        assert rc.timeout_seconds == 30.0
        assert rc.max_retries == 3
        assert rc.retry_delay == 1.0
        assert rc.correlation_tracking is True

    def test_custom(self):
        rc = RequestConfig(timeout_seconds=5.0, max_retries=1)
        assert rc.timeout_seconds == 5.0
        assert rc.max_retries == 1


class TestCreateResponse:
    """Test response creation helpers."""

    def test_create_response(self, rr):
        original = Message(
            message_type="REQUEST",
            sender="agent_a",
            receiver="rr_test_agent",
            payload={"query": "status"},
            metadata={"correlationId": "corr_123"}
        )
        response = rr.create_response(
            original, "RESPONSE", {"status": "ok"}
        )
        assert response.message_type == "RESPONSE"
        assert response.receiver == "agent_a"
        assert response.metadata['correlationId'] == "corr_123"
        assert response.metadata['isResponse'] is True
        assert response.payload['status'] == "ok"

    def test_create_error_response(self, rr):
        original = Message(
            message_type="REQUEST",
            sender="agent_a",
            receiver="rr_test_agent",
            payload={},
            metadata={"correlationId": "corr_456"}
        )
        error_resp = rr.create_error_response(
            original, "VALIDATION_ERROR", "Invalid input", {"field": "name"}
        )
        assert error_resp.message_type == "ERROR"
        assert error_resp.receiver == "agent_a"
        assert error_resp.payload['errorType'] == "VALIDATION_ERROR"
        assert error_resp.payload['message'] == "Invalid input"
        assert error_resp.payload['details']['field'] == "name"


class TestHandleResponse:
    """Test response handling."""

    def test_handle_response_no_correlation(self, rr):
        msg = Message(message_type="RESPONSE", payload={}, metadata={})
        handled = rr.handle_response(msg)
        assert handled is False

    def test_handle_response_unknown_correlation(self, rr):
        msg = Message(
            message_type="RESPONSE",
            payload={},
            metadata={"correlationId": "unknown_123"}
        )
        handled = rr.handle_response(msg)
        assert handled is False

    def test_handle_success_response(self, rr):
        # Manually add a pending request
        event = threading.Event()
        request_info = {
            'event': event,
            'response': None,
            'error': None,
            'timestamp': 0
        }
        rr.pending_requests["corr_789"] = request_info

        msg = Message(
            message_type="RESPONSE",
            payload={"data": "result"},
            metadata={"correlationId": "corr_789"}
        )
        handled = rr.handle_response(msg)
        assert handled is True
        assert request_info['response'] is msg
        assert event.is_set()

    def test_handle_error_response(self, rr):
        event = threading.Event()
        request_info = {
            'event': event,
            'response': None,
            'error': None,
            'timestamp': 0
        }
        rr.pending_requests["corr_err"] = request_info

        msg = Message(
            message_type="ERROR",
            payload={"errorType": "NOT_FOUND", "message": "Resource not found"},
            metadata={"correlationId": "corr_err"}
        )
        handled = rr.handle_response(msg)
        assert handled is True
        assert request_info['error'] is not None
        assert request_info['error']['errorType'] == "NOT_FOUND"


class TestSendRequest:
    """Test sending requests."""

    def test_send_request_timeout(self, rr):
        result = rr.send_request("other_agent", "QUERY", {"q": "status"}, timeout=0.1)
        assert result.is_err()
        assert result.unwrap_err()['errorType'] == 'REQUEST_TIMEOUT'

    def test_send_request_send_failure(self, mock_agent):
        mock_agent.send = MagicMock(return_value=Result.err({"errorType": "SEND_ERROR"}))
        rr = RequestResponsePattern(mock_agent, RequestConfig(timeout_seconds=0.1))
        result = rr.send_request("other", "QUERY", {})
        assert result.is_err()


class TestCleanupExpiredRequests:
    """Test expired request cleanup."""

    def test_cleanup_no_expired(self, rr):
        count = rr.cleanup_expired_requests()
        assert count == 0

    def test_cleanup_expired(self, rr):
        import time
        event = threading.Event()
        rr.pending_requests["old_req"] = {
            'event': event,
            'response': None,
            'error': None,
            'timestamp': time.time() - 1000  # Very old
        }
        count = rr.cleanup_expired_requests()
        assert count == 1
        assert "old_req" not in rr.pending_requests
        assert event.is_set()


class TestStatistics:
    """Test statistics."""

    def test_empty_stats(self, rr):
        stats = rr.get_statistics()
        assert stats['pending_requests'] == 0
        assert stats['oldest_request_age'] is None
        assert stats['config']['timeout_seconds'] == 1.0

    def test_stats_with_pending(self, rr):
        import time
        rr.pending_requests["req_1"] = {
            'event': threading.Event(),
            'response': None,
            'error': None,
            'timestamp': time.time() - 5
        }
        stats = rr.get_statistics()
        assert stats['pending_requests'] == 1
        assert stats['oldest_request_age'] >= 4  # At least 4 seconds old
