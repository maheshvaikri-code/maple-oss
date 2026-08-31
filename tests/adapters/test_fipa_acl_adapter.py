"""Regression tests for FIPA ACL translation boundaries."""

from maple.adapters.fipa_acl_adapter import FIPAACLAdapter
from maple.core.message import Message


class DummyAgent:
    agent_id = "agent-a"


def test_fipa_translation_uses_the_mapped_performative():
    adapter = FIPAACLAdapter(DummyAgent())
    message = Message(
        message_type="REQUEST",
        sender="agent-a",
        receiver="agent-b",
        payload={"task": "inspect"},
    )

    translated = adapter.translate_maple_to_fipa(message)

    assert translated.startswith("(request")
