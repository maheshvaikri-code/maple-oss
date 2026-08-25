"""Offline tests for the OpenAI SDK adapter's MAPLE function boundary."""

from maple.adapters.openai_sdk_adapter import OpenAISDKAdapter
from maple.resources import ResourceManager


class AgentWithoutResources:
    pass


class AgentWithResources:
    def __init__(self) -> None:
        self.resource_manager = ResourceManager()


def _adapter(agent: object) -> OpenAISDKAdapter:
    adapter = object.__new__(OpenAISDKAdapter)
    adapter.maple_agent = agent
    return adapter


def test_resource_function_fails_closed_without_manager() -> None:
    result = _adapter(AgentWithoutResources()).handle_function_call(
        "maple_resource_request",
        {"resource_type": "compute", "amount": 1},
    )

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "RESOURCE_MANAGEMENT_UNAVAILABLE"


def test_resource_function_allocates_with_injected_manager() -> None:
    agent = AgentWithResources()
    agent.resource_manager.register_resource("compute", 4)

    result = _adapter(agent).handle_function_call(
        "maple_resource_request",
        {"resource_type": "compute", "amount": 2, "priority": "HIGH"},
    )

    assert result.is_ok()
    assert result.unwrap()["allocation"]["resources"] == {"compute": 2}
    assert agent.resource_manager.get_available_resources()["compute"] == 2
