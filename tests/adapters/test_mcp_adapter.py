import asyncio

from maple.adapters.mcp_adapter import MCPAdapter


class DummyAgent:
    agent_id = "agent-test"


def test_resource_management_fails_closed_when_not_configured() -> None:
    result = asyncio.run(
        MCPAdapter(DummyAgent(), {}).handle_mcp_tool_call(
            "maple_resource_management", {"action": "allocate"}
        )
    )

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "RESOURCE_MANAGEMENT_UNAVAILABLE"
