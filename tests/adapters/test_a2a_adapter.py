"""Security regressions for the A2A adapter transport boundary."""

from unittest.mock import Mock, patch

from maple.adapters.a2a_adapter import A2AAdapter


class DummyAgent:
    agent_id = "agent-a"


def test_registry_registration_uses_a_bounded_request_timeout():
    response = Mock(status_code=201)
    response.json.return_value = {"agent_id": "registered-agent"}
    adapter = A2AAdapter(
        DummyAgent(),
        {
            "base_url": "https://agent.example",
            "registry_url": "https://registry.example",
        },
    )

    with patch(
        "maple.adapters.a2a_adapter.requests.post", return_value=response
    ) as post:
        result = adapter.register_with_a2a_registry()

    assert result.unwrap() == "registered-agent"
    assert post.call_args.kwargs["timeout"] == 30
