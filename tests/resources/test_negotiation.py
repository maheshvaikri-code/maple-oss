"""Tests for maple.resources.negotiation - ResourceNegotiator."""

import pytest
from unittest.mock import MagicMock
from maple.resources.negotiation import ResourceNegotiator
from maple.resources.specification import ResourceRequest, ResourceRange
from maple.core.message import Message
from maple.core.result import Result


@pytest.fixture
def mock_agent():
    agent = MagicMock()
    agent.agent_id = "negotiator_agent"
    agent.send = MagicMock(return_value=Result.ok("msg_1"))
    return agent


@pytest.fixture
def negotiator(mock_agent):
    return ResourceNegotiator(mock_agent)


class TestNegotiatorInit:
    """Test negotiator initialization."""

    def test_init(self, negotiator, mock_agent):
        assert negotiator.agent is mock_agent
        assert len(negotiator.pending_requests) == 0
        assert len(negotiator.pending_offers) == 0


class TestHandleRequest:
    """Test handling resource requests."""

    def test_handle_request_accepted(self, negotiator):
        msg = Message(
            message_type="RESOURCE_REQUEST",
            sender="agent_b",
            payload={
                'request_id': 'req_1',
                'resources': ResourceRequest(
                    compute=ResourceRange(min=4, preferred=8)
                ).to_dict()
            }
        )
        evaluator = lambda req: Result.ok({"compute": 8, "memory": 16384})
        response = negotiator.handle_request(msg, evaluator)
        assert response.message_type == "RESOURCE_OFFER"
        assert response.receiver == "agent_b"
        assert response.payload['resources']['compute'] == 8

    def test_handle_request_rejected(self, negotiator):
        msg = Message(
            message_type="RESOURCE_REQUEST",
            sender="agent_b",
            payload={
                'request_id': 'req_2',
                'resources': ResourceRequest(
                    compute=ResourceRange(min=100)
                ).to_dict()
            }
        )
        evaluator = lambda req: Result.err({
            'message': 'Insufficient resources',
            'details': {'shortfall': 'compute'}
        })
        response = negotiator.handle_request(msg, evaluator)
        assert response.message_type == "RESOURCE_REJECTION"
        assert response.receiver == "agent_b"

    def test_handle_request_stores_offer(self, negotiator):
        msg = Message(
            message_type="RESOURCE_REQUEST",
            sender="agent_b",
            payload={
                'request_id': 'req_3',
                'resources': ResourceRequest(compute=ResourceRange(min=4)).to_dict()
            }
        )
        evaluator = lambda req: Result.ok({"compute": 4})
        negotiator.handle_request(msg, evaluator)
        assert 'req_3' in negotiator.pending_offers


class TestHandleMessage:
    """Test message routing."""

    def test_handle_offer_response(self, negotiator):
        import queue
        q = queue.Queue()
        negotiator.pending_requests["req_10"] = q

        msg = Message(
            message_type="RESOURCE_OFFER",
            sender="provider",
            payload={'request_id': 'req_10', 'resources': {'compute': 8}}
        )
        result = negotiator.handle_message(msg)
        assert result is not None  # Returns ack
        assert q.qsize() == 1

    def test_handle_unrelated_message(self, negotiator):
        msg = Message(
            message_type="UNRELATED",
            sender="other",
            payload={}
        )
        result = negotiator.handle_message(msg)
        assert result is None

    def test_handle_offer_no_pending(self, negotiator):
        msg = Message(
            message_type="RESOURCE_OFFER",
            sender="provider",
            payload={'request_id': 'nonexistent'}
        )
        result = negotiator.handle_message(msg)
        assert result is None  # Not handled
