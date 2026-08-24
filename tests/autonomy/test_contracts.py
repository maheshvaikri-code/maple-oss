"""Tests for typed JSON-schema and guardrail boundaries."""

from maple.autonomy.contracts import (
    parse_structured_output,
    run_guardrails,
    schema_guardrail,
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


def test_schema_pattern_is_rejected_to_avoid_unbounded_regex_execution():
    result = validate_json_schema("value", {"type": "string", "pattern": "value"})

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "SCHEMA_VALIDATION_ERROR"
