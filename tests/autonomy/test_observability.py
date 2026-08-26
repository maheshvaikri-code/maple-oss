"""Tests for the observability module."""

import json
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from maple.autonomy.observability import (
    AgentSnapshot,
    DecisionLogger,
    DecisionTrace,
    SpanRecorder,
    TraceSpan,
)


def make_trace(agent_id="agent-1", goal_id="goal-1", step=0, duration_ms=100.0):
    return DecisionTrace(
        agent_id=agent_id,
        goal_id=goal_id,
        step_number=step,
        timestamp=time.time(),
        prompt_summary=f"Step {step}",
        response_summary=f"Response for step {step}",
        tool_calls=[{"name": "search", "args": {"q": "test"}}] if step % 2 == 0 else [],
        token_usage={
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
        },
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
            agent_id="a",
            goal_id="g",
            step_number=0,
            timestamp=time.time(),
            prompt_summary="",
            response_summary="",
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
        trace = make_trace(step=0)
        trace.provider_request_id = "provider-1"
        logger.log_decision(trace)
        logger.log_decision(make_trace(step=1))

        exported = logger.export_json()
        parsed = json.loads(exported)
        assert len(parsed) == 2
        assert parsed[0]["step_number"] == 0
        assert "agent_id" in parsed[0]
        assert parsed[0]["provider_request_id"] == "provider-1"

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


class TestTraceSpan:
    def test_creation_and_validation(self):
        span = TraceSpan(
            trace_id="trace-1",
            span_id="span-1",
            name="model",
            start_time=1.0,
            attributes={"step": 1},
        )

        assert span.status == "running"
        assert span.to_dict()["attributes"] == {"step": 1}

        with pytest.raises(ValueError, match="finite"):
            TraceSpan(
                trace_id="trace-1",
                span_id="span-2",
                name="model",
                start_time=float("nan"),
            )
        with pytest.raises(ValueError, match="terminal"):
            TraceSpan(
                trace_id="trace-1",
                span_id="span-3",
                name="model",
                start_time=1.0,
                status="ok",
            )

    def test_recorder_redacts_and_finishes_once(self):
        recorder = SpanRecorder(max_spans=4)
        started = recorder.start_span(
            "model",
            trace_id="trace-1",
            attributes={"token": "secret", "step": 1},
            start_time=1.0,
        )

        assert started.is_ok()
        span = started.unwrap()
        assert span.attributes["token"] == "[REDACTED]"
        finished = recorder.finish_span(
            span.span_id,
            status="ok",
            attributes={"total_tokens": 4},
            end_time=2.0,
        )

        assert finished.is_ok()
        assert finished.unwrap().status == "ok"
        assert finished.unwrap().attributes["total_tokens"] == 4
        again = recorder.finish_span(span.span_id, status="error", end_time=3.0)
        assert again.is_err()
        assert again.unwrap_err()["errorType"] == "SPAN_ALREADY_FINISHED"

    def test_recorder_enforces_parent_trace_and_retention(self):
        recorder = SpanRecorder(max_spans=2)
        parent = recorder.start_span("parent", trace_id="trace-1").unwrap()
        child = recorder.start_span(
            "child", trace_id="trace-1", parent_span_id=parent.span_id
        )
        assert child.is_ok()
        mismatch = recorder.start_span(
            "mismatch", trace_id="trace-2", parent_span_id=parent.span_id
        )
        assert mismatch.is_err()
        assert mismatch.unwrap_err()["errorType"] == "SPAN_TRACE_MISMATCH"

        recorder.start_span("evicting")
        assert recorder.get_span(parent.span_id).is_err()
        assert recorder.metrics() == {
            "retained_spans": 2,
            "max_spans": 2,
            "dropped_spans": 1,
            "open_spans": 2,
            "sample_rate_basis_points": 10000,
            "sampled_out_spans": 0,
            "completed_spans": 0,
            "latency_total_ms": 0,
            "latency_max_ms": 0,
            "latency_avg_ms": 0,
            "error_spans": 0,
            "cancelled_spans": 0,
        }

    def test_recorder_sampling_and_latency_metrics(self):
        with pytest.raises(ValueError, match="sample_rate"):
            SpanRecorder(sample_rate=-0.1)
        with pytest.raises(ValueError, match="sample_rate"):
            SpanRecorder(sample_rate=1.1)

        sampled = SpanRecorder(sample_rate=0.0)
        excluded = sampled.start_span("sampled", trace_id="trace-1")
        assert excluded.is_err()
        assert excluded.unwrap_err()["errorType"] == "SPAN_SAMPLED_OUT"
        assert sampled.metrics()["sampled_out_spans"] == 1
        assert sampled.metrics()["sample_rate_basis_points"] == 0

        recorder = SpanRecorder()
        success = recorder.start_span("success", start_time=1.0).unwrap()
        failure = recorder.start_span("failure", start_time=2.0).unwrap()
        cancelled = recorder.start_span("cancelled", start_time=3.0).unwrap()
        assert recorder.finish_span(success.span_id, end_time=1.125).is_ok()
        assert recorder.finish_span(
            failure.span_id, status="error", end_time=2.5
        ).is_ok()
        assert recorder.finish_span(
            cancelled.span_id, status="cancelled", end_time=3.25
        ).is_ok()

        metrics = recorder.metrics()
        assert metrics["completed_spans"] == 3
        assert metrics["latency_total_ms"] == 875
        assert metrics["latency_max_ms"] == 500
        assert metrics["latency_avg_ms"] == 291
        assert metrics["error_spans"] == 1
        assert metrics["cancelled_spans"] == 1

    def test_recorder_rejects_nested_attributes_and_exports_json(self):
        recorder = SpanRecorder()
        invalid = recorder.start_span("model", attributes={"payload": {"raw": 1}})

        assert invalid.is_err()
        assert invalid.unwrap_err()["errorType"] == "SPAN_ATTRIBUTES_INVALID"
        span = recorder.start_span("model", trace_id="trace-1").unwrap()
        exported = recorder.export_json(trace_id=span.trace_id)
        assert exported.is_ok()
        assert '"span_id":"' + span.span_id + '"' in exported.unwrap()

    def test_trace_span_rejects_oversized_serialized_attributes(self):
        with pytest.raises(ValueError, match="byte limit"):
            TraceSpan(
                trace_id="trace-1",
                span_id="span-1",
                name="model",
                start_time=1.0,
                attributes={f"key-{index}": "x" * 1024 for index in range(32)},
            )

    def test_recorder_is_thread_safe_for_concurrent_starts(self):
        recorder = SpanRecorder(max_spans=32)

        def start(index):
            return recorder.start_span(
                "worker", trace_id="trace-concurrent", attributes={"index": index}
            )

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(start, range(16)))

        assert all(result.is_ok() for result in results)
        retained = recorder.snapshot(trace_id="trace-concurrent").unwrap()
        assert len(retained) == 16
        assert len({span.span_id for span in retained}) == 16


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
        agent.tool_registry.register(
            Tool(
                name="test_tool",
                description="test",
                parameters={},
                handler=lambda: Result.ok(None),
            )
        )

        snapshot = AgentSnapshot.capture(agent)
        assert "test_tool" in snapshot["registered_tools"]
