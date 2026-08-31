import asyncio
from typing import Any, Dict

from maple.adapters.mcp_adapter import MCPAdapter
from maple.core.result import Result
from maple.resources.manager import ResourceManager
from maple.resources.negotiation import ResourceNegotiator
from maple.resources.specification import ResourceRequest


class DummyAgent:
    agent_id = "agent-test"


class DummyNegotiator(ResourceNegotiator):
    def __init__(self) -> None:
        pass

    def request_resources(
        self, request: ResourceRequest, agent_id: str, timeout: str = "30s"
    ) -> Result[Dict[str, Any], Dict[str, Any]]:
        assert request.compute is not None
        assert agent_id == "agent-peer"
        assert timeout == "2s"
        return Result.ok({"compute": request.compute.preferred})


def test_resource_management_fails_closed_when_not_configured() -> None:
    result = asyncio.run(
        MCPAdapter(DummyAgent(), {}).handle_mcp_tool_call(
            "maple_resource_management", {"action": "allocate"}
        )
    )

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "RESOURCE_MANAGEMENT_UNAVAILABLE"


def test_resource_management_allocates_and_releases_with_injected_manager() -> None:
    manager = ResourceManager()
    manager.register_resource("compute", 8)
    adapter = MCPAdapter(DummyAgent(), {}, resource_manager=manager)

    allocated = asyncio.run(
        adapter.handle_mcp_tool_call(
            "maple_resource_management",
            {"action": "allocate", "resources": {"compute": {"min": 2}}},
        )
    )

    assert allocated.is_ok()
    allocation = allocated.unwrap()["allocation"]
    assert allocation["resources"] == {"compute": 2}
    assert manager.get_available_resources()["compute"] == 6

    released = asyncio.run(
        adapter.handle_mcp_tool_call(
            "maple_resource_management",
            {"action": "release", "allocation_id": allocation["allocation_id"]},
        )
    )

    assert released.is_ok()
    assert manager.get_available_resources()["compute"] == 8


def test_resource_management_rejects_malformed_request() -> None:
    adapter = MCPAdapter(DummyAgent(), {}, resource_manager=ResourceManager())

    result = asyncio.run(
        adapter.handle_mcp_tool_call(
            "maple_resource_management", {"action": "allocate", "resources": []}
        )
    )

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "MCP_RESOURCE_ARGUMENT_INVALID"


def test_resource_management_reports_unknown_allocation() -> None:
    adapter = MCPAdapter(DummyAgent(), {}, resource_manager=ResourceManager())

    result = asyncio.run(
        adapter.handle_mcp_tool_call(
            "maple_resource_management",
            {"action": "release", "allocation_id": "missing"},
        )
    )

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "RESOURCE_ALLOCATION_NOT_FOUND"


def test_resource_management_negotiates_off_event_loop() -> None:
    adapter = MCPAdapter(DummyAgent(), {}, resource_negotiator=DummyNegotiator())

    result = asyncio.run(
        adapter.handle_mcp_tool_call(
            "maple_resource_management",
            {
                "action": "negotiate",
                "agent_id": "agent-peer",
                "timeout": "2s",
                "resources": {"compute": {"min": 3}},
            },
        )
    )

    assert result.is_ok()
    assert result.unwrap()["resources"] == {"compute": 3}
