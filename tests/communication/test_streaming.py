"""Tests for maple.communication.streaming - Stream."""

import pytest
from unittest.mock import MagicMock
from maple.communication.streaming import Stream, StreamOptions
from maple.core.message import Message
from maple.core.result import Result


@pytest.fixture
def mock_agent():
    agent = MagicMock()
    agent.agent_id = "stream_test_agent"
    agent.register_stream_handler = MagicMock()
    agent.send = MagicMock(return_value=Result.ok("msg_1"))
    agent.stream_handlers = {}
    return agent


@pytest.fixture
def stream(mock_agent):
    return Stream(mock_agent, "test_stream")


class TestStreamOptions:
    """Test StreamOptions class."""

    def test_defaults(self):
        opts = StreamOptions()
        assert opts.compression is False
        assert opts.chunk_size == "1MB"
        assert opts.buffer_size == "10MB"

    def test_custom(self):
        opts = StreamOptions(compression=True, chunk_size="4MB", buffer_size="32MB")
        assert opts.compression is True
        assert opts.chunk_size == "4MB"


class TestStreamCreation:
    """Test stream creation."""

    def test_create(self, stream, mock_agent):
        assert stream.name == "test_stream"
        assert stream.closed is False
        assert stream.stream_id is not None
        mock_agent.register_stream_handler.assert_called_once()

    def test_custom_options(self, mock_agent):
        opts = StreamOptions(compression=True)
        s = Stream(mock_agent, "test", options=opts)
        assert s.options.compression is True


class TestSend:
    """Test stream send."""

    def test_send_data(self, stream):
        stream.subscribers = ["agent_b"]
        result = stream.send({"value": 42})
        assert result.is_ok()

    def test_send_to_closed_stream(self, stream):
        stream.closed = True
        result = stream.send({"value": 42})
        assert result.is_err()
        assert result.unwrap_err()['errorType'] == 'STREAM_CLOSED'

    def test_send_to_multiple_subscribers(self, stream, mock_agent):
        stream.subscribers = ["a1", "a2", "a3"]
        stream.send({"value": 1})
        assert mock_agent.send.call_count == 3


class TestReceive:
    """Test stream receive."""

    def test_receive_timeout(self, stream):
        result = stream.receive(timeout=0.1)
        assert result.is_err()
        assert result.unwrap_err()['errorType'] == 'TIMEOUT'

    def test_receive_data(self, stream):
        stream.buffer.put("test_data")
        result = stream.receive(timeout=1.0)
        assert result.is_ok()
        assert result.unwrap() == "test_data"


class TestClose:
    """Test stream close."""

    def test_close(self, stream, mock_agent):
        stream.subscribers = ["agent_b"]
        result = stream.close()
        assert result.is_ok()
        assert stream.closed is True

    def test_close_already_closed(self, stream):
        stream.closed = True
        result = stream.close()
        assert result.is_ok()


class TestHandleMessage:
    """Test message handling."""

    def test_handle_stream_data(self, stream):
        msg = Message(
            message_type="STREAM_DATA",
            sender="agent_b",
            payload={"data": "hello", "stream_name": "test", "stream_id": stream.stream_id}
        )
        stream._handle_message(msg)
        assert stream.buffer.qsize() == 1

    def test_handle_subscribe(self, stream):
        msg = Message(
            message_type="STREAM_SUBSCRIBE",
            sender="agent_b",
            payload={"stream_name": "test", "stream_id": stream.stream_id}
        )
        stream._handle_message(msg)
        assert "agent_b" in stream.subscribers

    def test_handle_close(self, stream):
        msg = Message(
            message_type="STREAM_CLOSE",
            sender="agent_b",
            payload={"stream_name": "test", "stream_id": stream.stream_id}
        )
        stream._handle_message(msg)
        assert stream.closed is True

    def test_duplicate_subscriber_ignored(self, stream):
        msg = Message(
            message_type="STREAM_SUBSCRIBE",
            sender="agent_b",
            payload={}
        )
        stream._handle_message(msg)
        stream._handle_message(msg)
        assert stream.subscribers.count("agent_b") == 1
