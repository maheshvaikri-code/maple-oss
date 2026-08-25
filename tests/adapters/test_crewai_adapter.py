"""Offline tests for CrewAI adapter MAPLE tool boundaries."""

from types import SimpleNamespace

from maple.adapters.crewai_adapter import CrewAIAdapter
from maple.core.result import Result
from maple.core.types import Priority
from maple.resources import ResourceManager


class DummyAgent:
    def __init__(self) -> None:
        self.resource_manager = ResourceManager()

    def send(self, message):
        return Result.ok(str(message.message_id))

    def establish_link(self, target_agent):
        return Result.ok(f"link-{target_agent}")


def test_crewai_tools_are_bound_and_communication_is_structured() -> None:
    adapter = CrewAIAdapter(DummyAgent())
    tools = adapter._get_maple_enhanced_tools()

    result = adapter._maple_communicate_tool("agent-peer", "hello", "HIGH")

    assert [tool["name"] for tool in tools] == [
        "maple_communicate",
        "maple_resource_request",
        "maple_secure_link",
    ]
    assert result["status"] == "success"
    assert result["message_id"]


def test_crewai_resource_tool_uses_injected_manager() -> None:
    agent = DummyAgent()
    agent.resource_manager.register_resource("compute", 4)

    result = CrewAIAdapter(agent)._maple_resource_tool("compute", 2, "HIGH")

    assert result["status"] == "success"
    assert result["allocation"]["resources"] == {"compute": 2}


def test_crewai_priority_mapping_is_bounded() -> None:
    assert (
        CrewAIAdapter._map_crew_priority(SimpleNamespace(priority="HIGH"))
        == Priority.HIGH
    )
    assert (
        CrewAIAdapter._map_crew_priority(SimpleNamespace(priority="unknown"))
        == Priority.MEDIUM
    )
