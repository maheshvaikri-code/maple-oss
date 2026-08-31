"""Offline tests for LangGraph adapter recovery decisions."""

from maple.adapters.langgraph_adapter import LangGraphAdapter


def _state() -> dict:
    return {
        "messages": [],
        "maple_context": {},
        "resource_state": {"optimization_level": "standard"},
        "performance_metrics": {"recovery_count": 0},
        "error_context": None,
    }


def test_recovery_strategy_prioritizes_resource_reallocation() -> None:
    assert (
        LangGraphAdapter._determine_recovery_strategy(
            {"errorType": "RESOURCE_EXHAUSTED", "recoverable": True}
        )
        == "resource_reallocation"
    )


def test_recovery_strategy_degrades_nonrecoverable_errors() -> None:
    assert (
        LangGraphAdapter._determine_recovery_strategy(
            {"errorType": "INVALID_INPUT", "recoverable": False}
        )
        == "graceful_degradation"
    )


def test_resource_reallocation_is_bounded_and_recorded() -> None:
    state = _state()

    LangGraphAdapter._reallocate_resources(state)
    LangGraphAdapter._reallocate_resources(state)

    assert state["resource_state"] == {
        "optimization_level": "maximum",
        "reallocation_count": 2,
    }
