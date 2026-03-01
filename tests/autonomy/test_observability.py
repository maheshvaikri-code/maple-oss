"""Tests for the observability module."""

import json
import time
import pytest
from maple.autonomy.observability import DecisionTrace, DecisionLogger, AgentSnapshot


def make_trace(agent_id="agent-1", goal_id="goal-1", step=0, duration_ms=100.0):
    return DecisionTrace(
        agent_id=agent_id,
        goal_id=goal_id,
        step_number=step,
        timestamp=time.time(),
        prompt_summary=f"Step {step}",
        response_summary=f"Response for step {step}",
        tool_calls=[{"name": "search", "args": {"q": "test"}}] if step % 2 == 0 else [],
        token_usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        duration_ms=duration_ms,
    )


class TestDecisionTrace:
    def test_creation(self):
        trace = make_trace()
        assert trace.agent_id == "agent-1"
        assert trace.goal_id == "goal-1"
        assert trace.step_number == 0
        assert trace.duration_ms == 100.0

    def test_defaults(self):
        trace = DecisionTrace(
            agent_id="a", goal_id="g", step_number=0,
            timestamp=time.time(), prompt_summary="", response_summary="",
        )
        assert trace.tool_calls == []
        assert trace.tool_results == []
        assert trace.token_usage == {}
        assert trace.duration_ms == 0.0


class TestDecisionLogger:
    def test_log_and_retrieve(self):
        logger = DecisionLogger()
        t1 = make_trace(step=0)
        t2 = make_trace(step=1)
        logger.log_decision(t1)
        logger.log_decision(t2)

        traces = logger.get_traces()
        assert len(traces) == 2
        assert logger.trace_count == 2

    def test_filter_by_goal(self):
        logger = DecisionLogger()
        logger.log_decision(make_trace(goal_id="g1", step=0))
        logger.log_decision(make_trace(goal_id="g1", step=1))
        logger.log_decision(make_trace(goal_id="g2", step=0))

        g1_traces = logger.get_traces(goal_id="g1")
        assert len(g1_traces) == 2

        g2_traces = logger.get_traces(goal_id="g2")
        assert len(g2_traces) == 1

    def test_get_summary(self):
        logger = DecisionLogger()
        logger.log_decision(make_trace(goal_id="g1", step=0, duration_ms=100))
        logger.log_decision(make_trace(goal_id="g1", step=1, duration_ms=200))
        logger.log_decision(make_trace(goal_id="g1", step=2, duration_ms=150))

        summary = logger.get_summary("g1")
        assert summary["goal_id"] == "g1"
        assert summary["steps"] == 3
        assert summary["total_tokens"] == 450  # 150 * 3
        assert summary["total_duration_ms"] == 450  # 100 + 200 + 150
        assert summary["tool_calls"] == 2  # steps 0 and 2 have tool calls

    def test_get_summary_empty(self):
        logger = DecisionLogger()
        summary = logger.get_summary("nonexistent")
        assert summary["steps"] == 0

    def test_export_json(self):
        logger = DecisionLogger()
        logger.log_decision(make_trace(step=0))
        logger.log_decision(make_trace(step=1))

        exported = logger.export_json()
        parsed = json.loads(exported)
        assert len(parsed) == 2
        assert parsed[0]["step_number"] == 0
        assert "agent_id" in parsed[0]

    def test_export_json_filtered(self):
        logger = DecisionLogger()
        logger.log_decision(make_trace(goal_id="g1", step=0))
        logger.log_decision(make_trace(goal_id="g2", step=0))

        exported = logger.export_json(goal_id="g1")
        parsed = json.loads(exported)
        assert len(parsed) == 1

    def test_max_traces(self):
        logger = DecisionLogger(max_traces=5)
        for i in range(10):
            logger.log_decision(make_trace(step=i))
        assert logger.trace_count == 5
        # Oldest should be evicted
        traces = logger.get_traces()
        assert traces[0].step_number == 5


class TestAgentSnapshot:
    def test_capture_basic(self):
        class FakeAgent:
            agent_id = "test-agent"
            status = "running"
            messages_sent = 10
            messages_received = 8
            messages_failed = 1

        snapshot = AgentSnapshot.capture(FakeAgent())
        assert snapshot["agent_id"] == "test-agent"
        assert snapshot["status"] == "running"
        assert snapshot["messages_sent"] == 10
        assert snapshot["messages_received"] == 8
        assert snapshot["messages_failed"] == 1
        assert "timestamp" in snapshot

    def test_capture_with_memory(self):
        from maple.autonomy.memory import MemoryManager

        class FakeAgent:
            agent_id = "mem-agent"
            memory = MemoryManager(working_memory_tokens=4000)

        agent = FakeAgent()
        agent.memory.working.add("key", "some data")

        snapshot = AgentSnapshot.capture(agent)
        assert snapshot["working_memory"]["entries"] == 1
        assert snapshot["working_memory"]["max_tokens"] == 4000

    def test_capture_with_goals(self):
        from maple.autonomy.agent import Goal

        class FakeAgent:
            agent_id = "goal-agent"
            _active_goals = {
                "g1": Goal(goal_id="g1", description="Test goal", status="in_progress"),
            }

        snapshot = AgentSnapshot.capture(FakeAgent())
        assert "g1" in snapshot["active_goals"]
        assert snapshot["active_goals"]["g1"]["status"] == "in_progress"

    def test_capture_with_tools(self):
        from maple.autonomy.tools import ToolRegistry, Tool
        from maple.core.result import Result

        class FakeAgent:
            agent_id = "tool-agent"
            tool_registry = ToolRegistry()

        agent = FakeAgent()
        agent.tool_registry.register(Tool(
            name="test_tool", description="test", parameters={},
            handler=lambda: Result.ok(None),
        ))

        snapshot = AgentSnapshot.capture(agent)
        assert "test_tool" in snapshot["registered_tools"]
