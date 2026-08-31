"""Tests for typed JSON-schema and guardrail boundaries."""

import pytest
from pydantic import BaseModel

from maple.autonomy.contracts import (
    GuardrailEvent,
    parse_structured_output,
    parse_typed_output,
    run_guardrails,
    schema_guardrail,
    structured_model_schema,
    validate_json_schema,
)
from maple.autonomy.tools import Tool
from maple.core.result import Result

REPORT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "minLength": 1},
        "count": {"type": "integer", "minimum": 0},
    },
    "required": ["title", "count"],
    "additionalProperties": False,
}


class TypedReport(BaseModel):
    title: str
    count: int


class TypedToolInput(BaseModel):
    title: str
    count: int


class TypedToolOutput(BaseModel):
    summary: str


def test_json_schema_accepts_valid_nested_value():
    result = validate_json_schema({"title": "Report", "count": 2}, REPORT_SCHEMA)

    assert result.is_ok()


def test_json_schema_rejects_missing_and_extra_properties():
    missing = validate_json_schema({"title": "Report"}, REPORT_SCHEMA)
    extra = validate_json_schema(
        {"title": "Report", "count": 2, "secret": "unexpected"}, REPORT_SCHEMA
    )

    assert missing.is_err()
    assert missing.unwrap_err()["errorType"] == "SCHEMA_VALIDATION_ERROR"
    assert extra.is_err()
    assert extra.unwrap_err()["details"]["path"] == "$.secret"


def test_structured_output_parses_and_validates_json():
    result = parse_structured_output('{"title":"Report","count":2}', REPORT_SCHEMA)
    invalid = parse_structured_output('{"title":"Report"}', REPORT_SCHEMA)

    assert result.is_ok()
    assert result.unwrap()["count"] == 2
    assert invalid.is_err()


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_structured_output_rejects_non_standard_numeric_constants(constant):
    result = parse_structured_output(constant, {"type": "number"})

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "STRUCTURED_OUTPUT_INVALID_JSON"


def test_structured_output_accepts_finite_json_numbers():
    result = parse_structured_output(
        '{"score":1.5}',
        {
            "type": "object",
            "required": ["score"],
            "properties": {"score": {"type": "number"}},
        },
    )

    assert result.is_ok()
    assert result.unwrap()["score"] == 1.5


def test_structured_output_normalizes_decoder_recursion_failure(monkeypatch):
    def raise_recursion_error(*args, **kwargs):
        raise RecursionError("decoder nesting limit")

    monkeypatch.setattr("maple.autonomy.contracts.json.loads", raise_recursion_error)

    result = parse_structured_output("[0]", {"type": "array"})

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "STRUCTURED_OUTPUT_INVALID_JSON"


def test_typed_output_returns_validated_model_and_advertises_schema():
    schema = structured_model_schema(TypedReport)
    result = parse_typed_output('{"title":"Report","count":2}', TypedReport)

    assert schema.is_ok()
    assert "properties" in schema.unwrap()
    assert result.is_ok()
    assert isinstance(result.unwrap(), TypedReport)
    assert result.unwrap().count == 2


def test_typed_output_rejects_invalid_model_and_model_class():
    invalid = parse_typed_output('{"title":"Report"}', TypedReport)
    invalid_class = structured_model_schema(object())

    assert invalid.is_err()
    assert invalid.unwrap_err()["errorType"] == "STRUCTURED_OUTPUT_MODEL_INVALID"
    assert invalid_class.is_err()
    assert invalid_class.unwrap_err()["errorType"] == "STRUCTURED_OUTPUT_MODEL_INVALID"


def test_guardrail_rejects_and_exception_fails_closed():
    rejected = run_guardrails(
        "unsafe",
        [lambda value: False],
        stage="test",
    )

    def broken(value):
        raise RuntimeError("guardrail unavailable")

    failed_closed = run_guardrails("value", [broken], stage="test")

    assert rejected.is_err()
    assert rejected.unwrap_err()["errorType"] == "GUARDRAIL_REJECTED"
    assert failed_closed.is_err()
    assert failed_closed.unwrap_err()["errorType"] == "GUARDRAIL_ERROR"


def test_guardrail_lifecycle_is_ordered_and_trace_linked_without_the_value():
    events = []
    result = run_guardrails(
        {"secret": "do-not-copy"},
        [lambda value: True, lambda value: Result.ok(None)],
        stage="agent:input",
        observer=events.append,
        trace_id="trace-1",
        span_id="span-1",
    )

    assert result.is_ok()
    assert [event.status for event in events] == [
        "started",
        "passed",
        "started",
        "passed",
    ]
    assert events[0].to_dict() == {
        "stage": "agent:input",
        "index": 0,
        "status": "started",
        "trace_id": "trace-1",
        "span_id": "span-1",
    }
    assert "secret" not in events[0].to_dict()


def test_guardrail_lifecycle_marks_rejection_and_isolates_observer_failure():
    events = []

    def broken_observer(event):
        events.append(event)
        raise RuntimeError("observer must not change policy")

    result = run_guardrails(
        "blocked",
        [lambda value: False, lambda value: True],
        stage="agent:input",
        observer=broken_observer,
    )

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "GUARDRAIL_REJECTED"
    assert [event.status for event in events] == ["started", "rejected"]


def test_guardrail_event_rejects_unbounded_metadata():
    with pytest.raises(ValueError, match="bounded text"):
        GuardrailEvent(stage="x" * 129, index=0, status="started")

    with pytest.raises(ValueError, match="bounded text"):
        GuardrailEvent(
            stage="agent:input",
            index=0,
            status="started",
            trace_id="x" * 129,
        )


def test_tool_validates_input_output_and_guardrails_before_returning():
    calls = []
    tool = Tool(
        name="report",
        description="Create a report",
        parameters={
            "type": "object",
            "required": ["title"],
            "properties": {"title": {"type": "string"}},
        },
        handler=lambda title: calls.append(title) or Result.ok({"ok": True}),
        result_schema={
            "type": "object",
            "required": ["ok"],
            "properties": {"ok": {"type": "boolean"}},
        },
        input_guardrails=[schema_guardrail({"type": "object", "required": ["title"]})],
    )

    invalid = tool.execute()
    valid = tool.execute(title="done")

    assert invalid.is_err()
    assert invalid.unwrap_err()["errorType"] == "TOOL_INPUT_INVALID"
    assert valid.is_ok()
    assert calls == ["done"]


def test_tool_rejects_invalid_output():
    tool = Tool(
        name="broken_output",
        description="Return an invalid result",
        parameters={"type": "object"},
        handler=lambda: Result.ok({"count": "not-an-integer"}),
        result_schema={"type": "object", "properties": {"count": {"type": "integer"}}},
    )

    result = tool.execute()

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "TOOL_OUTPUT_INVALID"


def test_tool_typed_models_validate_arguments_results_and_llm_schema():
    calls = []

    def handler(title, count):
        calls.append((title, count))
        return Result.ok({"summary": f"{title}:{count}"})

    tool = Tool(
        name="typed_report",
        description="Create a typed report",
        parameters={"type": "object"},
        handler=handler,
        input_model=TypedToolInput,
        output_model=TypedToolOutput,
    )

    definition = tool.to_llm_definition()
    valid = tool.execute(title="Report", count=2)
    invalid = tool.execute(title="Missing count")

    assert "properties" in definition.parameters
    assert valid.is_ok()
    assert isinstance(valid.unwrap(), TypedToolOutput)
    assert valid.unwrap().summary == "Report:2"
    assert invalid.is_err()
    assert invalid.unwrap_err()["errorType"] == "TOOL_INPUT_INVALID"
    assert calls == [("Report", 2)]


def test_tool_typed_output_rejects_invalid_result():
    tool = Tool(
        name="typed_report",
        description="Create a typed report",
        parameters={"type": "object"},
        handler=lambda: Result.ok({"unexpected": True}),
        output_model=TypedToolOutput,
    )

    result = tool.execute()

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "TOOL_OUTPUT_INVALID"


def test_schema_pattern_is_rejected_to_avoid_unbounded_regex_execution():
    result = validate_json_schema("value", {"type": "string", "pattern": "value"})

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "SCHEMA_VALIDATION_ERROR"
