"""Tests for maple.broker.queue - MessageQueue."""

import pytest
from maple.broker.queue import MessageQueue, QueueType
from maple.core.message import Message
from maple.core.types import Priority


@pytest.fixture
def queue():
    return MessageQueue(queue_type=QueueType.PRIORITY, max_size=100)


class TestEnqueueDequeue:
    """Test basic enqueue/dequeue operations."""

    def test_enqueue(self, queue):
        msg = Message(message_type="TEST", payload={"data": 1})
        result = queue.enqueue(msg)
        assert result.is_ok()
        assert queue.size() == 1

    def test_dequeue(self, queue):
        msg = Message(message_type="TEST", payload={"data": 1})
        queue.enqueue(msg)
        result = queue.dequeue(timeout=1.0)
        assert result.is_ok()
        dequeued = result.unwrap()
        assert dequeued.message_type == "TEST"

    def test_dequeue_empty(self, queue):
        result = queue.dequeue(timeout=0.1)
        assert result.is_err()

    def test_fifo_order(self, queue):
        queue.enqueue(Message(message_type="FIRST", payload={}))
        queue.enqueue(Message(message_type="SECOND", payload={}))

        m1 = queue.dequeue(timeout=1.0).unwrap()
        m2 = queue.dequeue(timeout=1.0).unwrap()
        assert m1.message_type == "FIRST"
        assert m2.message_type == "SECOND"


class TestPriorityOrdering:
    """Test priority-based message ordering."""

    def test_high_priority_first(self, queue):
        queue.enqueue(Message(message_type="LOW", payload={}), priority=Priority.LOW)
        queue.enqueue(Message(message_type="HIGH", payload={}), priority=Priority.HIGH)

        msg = queue.dequeue(timeout=1.0).unwrap()
        assert msg.message_type == "HIGH"


class TestQueueCapacity:
    """Test queue size limits."""

    def test_is_empty(self, queue):
        assert queue.is_empty() is True
        queue.enqueue(Message(message_type="TEST", payload={}))
        assert queue.is_empty() is False

    def test_is_full(self):
        small_queue = MessageQueue(max_size=2)
        small_queue.enqueue(Message(message_type="A", payload={}))
        small_queue.enqueue(Message(message_type="B", payload={}))
        assert small_queue.is_full() is True

    def test_enqueue_full_queue(self):
        small_queue = MessageQueue(max_size=1)
        small_queue.enqueue(Message(message_type="A", payload={}))
        result = small_queue.enqueue(Message(message_type="B", payload={}))
        assert result.is_err()

    def test_clear(self, queue):
        queue.enqueue(Message(message_type="A", payload={}))
        queue.enqueue(Message(message_type="B", payload={}))
        cleared = queue.clear()
        assert cleared == 2
        assert queue.size() == 0


class TestPeek:
    """Test peek operation."""

    def test_peek_empty(self, queue):
        result = queue.peek()
        assert result.is_ok()
        assert result.unwrap() is None

    def test_peek_doesnt_remove(self, queue):
        queue.enqueue(Message(message_type="TEST", payload={}))
        queue.peek()
        assert queue.size() == 1


class TestRetry:
    """Test message retry."""

    def test_retry_message(self, queue):
        msg = Message(message_type="RETRY_ME", payload={})
        result = queue.retry_message(msg)
        assert result.is_ok()
        assert queue.size() >= 1


class TestQueueStatistics:
    """Test queue statistics."""

    def test_statistics(self, queue):
        queue.enqueue(Message(message_type="A", payload={}))
        stats = queue.get_statistics()
        assert isinstance(stats, dict)
        assert stats['current_size'] >= 1

    def test_queue_contents(self, queue):
        queue.enqueue(Message(message_type="A", payload={}))
        contents = queue.get_queue_contents()
        assert isinstance(contents, list)
        assert len(contents) >= 1
