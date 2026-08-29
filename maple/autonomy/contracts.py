"""Typed JSON-schema and guardrail contracts for MAPLE agent boundaries."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Mapping, Optional, Type, Union

from ..core.result import Result

Error = Dict[str, Any]
GuardrailResult = Union[Result[None, Error], bool, None]
Guardrail = Callable[[Any], GuardrailResult]
_MAX_GUARDRAIL_EVENT_TEXT = 128
_GUARDRAIL_EVENT_STATUSES = ("started", "passed", "rejected", "failed")


@dataclass(frozen=True)
class GuardrailEvent:
    """Bounded metadata for one guardrail lifecycle transition."""

    stage: str
    index: int
    status: str
    trace_id: Optional[str] = None
    span_id: Optional[str] = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.stage, str)
            or not self.stage
            or len(self.stage) > _MAX_GUARDRAIL_EVENT_TEXT
            or any(ord(char) < 32 for char in self.stage)
        ):
            raise ValueError("guardrail event stage must be bounded text")
        if (
            isinstance(self.index, bool)
            or not isinstance(self.index, int)
            or self.index < 0
        ):
            raise ValueError("guardrail event index must be a non-negative integer")
        if self.status not in _GUARDRAIL_EVENT_STATUSES:
            raise ValueError("guardrail event status is invalid")
        for name, value in (("trace_id", self.trace_id), ("span_id", self.span_id)):
            if value is not None and (
                not isinstance(value, str)
                or not value
                or len(value) > _MAX_GUARDRAIL_EVENT_TEXT
                or any(ord(char) < 32 for char in value)
            ):
                raise ValueError(f"guardrail event {name} must be bounded text")

    def to_dict(self) -> Dict[str, Any]:
        """Return metadata without copying the guarded value or error payload."""
        payload: Dict[str, Any] = {
            "stage": self.stage,
            "index": self.index,
            "status": self.status,
        }
        if self.trace_id is not None:
            payload["trace_id"] = self.trace_id
        if self.span_id is not None:
            payload["span_id"] = self.span_id
        return payload


GuardrailObserver = Callable[[GuardrailEvent], None]


def _error(error_type: str, message: str, **details: Any) -> Error:
    result: Error = {"errorType": error_type, "message": message}
    if details:
        result["details"] = details
    return result


def _schema_error(message: str, path: str, **details: Any) -> Result[None, Error]:
    return Result.err(_error("SCHEMA_VALIDATION_ERROR", message, path=path, **details))


def _type_matches(value: Any, expected: str) -> bool:
    if expected == "null":
        return value is None
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return False


def validate_json_schema(
    value: Any,
    schema: Optional[Mapping[str, Any]],
    *,
    path: str = "$",
    depth: int = 0,
    max_depth: int = 16,
    max_items: int = 10_000,
) -> Result[None, Error]:
    """Validate the bounded JSON-Schema subset used at MAPLE boundaries.

    Supported keywords are ``type``, ``properties``, ``required``,
    ``additionalProperties``, ``items``, ``enum``, ``const``, string length,
    array/object size, and numeric bounds. Unsupported keywords are ignored so
    providers can emit richer schemas without breaking local validation, except
    ``pattern``, which is rejected because the standard-library regex engine
    has no execution deadline.
    """
    if schema is None:
        return Result.ok(None)
    if not isinstance(schema, Mapping):
        return _schema_error("Schema must be an object.", path)
    if depth > max_depth:
        return _schema_error("Schema value nesting is too deep.", path)
    if max_items <= 0:
        return _schema_error("Schema item limit must be positive.", path)

    if "enum" in schema:
        enum_values = schema["enum"]
        if not isinstance(enum_values, list):
            return _schema_error("enum must be an array.", path)
        if value not in enum_values:
            return _schema_error("Value is not one of the allowed enum values.", path)
    if "const" in schema and value != schema["const"]:
        return _schema_error("Value does not match const.", path)

    expected = schema.get("type")
    if expected is not None:
        expected_types = expected if isinstance(expected, list) else [expected]
        if not expected_types or not all(
            isinstance(item, str) for item in expected_types
        ):
            return _schema_error("type must be a string or array of strings.", path)
        if not any(_type_matches(value, item) for item in expected_types):
            return _schema_error("Value has the wrong type.", path, expected=expected)

    if isinstance(value, str):
        min_length = schema.get("minLength")
        max_length = schema.get("maxLength")
        if isinstance(min_length, int) and len(value) < min_length:
            return _schema_error("String is shorter than minLength.", path)
        if isinstance(max_length, int) and len(value) > max_length:
            return _schema_error("String is longer than maxLength.", path)
        pattern = schema.get("pattern")
        if pattern is not None:
            # Python's regular-expression engine has no execution deadline.
            # Reject this keyword instead of exposing callers to a
            # schema-controlled regular-expression denial of service.
            return _schema_error(
                "pattern is not supported by the bounded validator.", path
            )

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if isinstance(minimum, (int, float)) and value < minimum:
            return _schema_error("Number is below minimum.", path)
        if isinstance(maximum, (int, float)) and value > maximum:
            return _schema_error("Number is above maximum.", path)

    if isinstance(value, list):
        if len(value) > max_items:
            return _schema_error("Array exceeds item limit.", path)
        min_items = schema.get("minItems")
        max_schema_items = schema.get("maxItems")
        if isinstance(min_items, int) and len(value) < min_items:
            return _schema_error("Array is shorter than minItems.", path)
        if isinstance(max_schema_items, int) and len(value) > max_schema_items:
            return _schema_error("Array is longer than maxItems.", path)
        item_schema = schema.get("items")
        if item_schema is not None:
            for index, item in enumerate(value):
                item_result = validate_json_schema(
                    item,
                    item_schema,
                    path=f"{path}[{index}]",
                    depth=depth + 1,
                    max_depth=max_depth,
                    max_items=max_items,
                )
                if item_result.is_err():
                    return item_result

    if isinstance(value, dict):
        if len(value) > max_items:
            return _schema_error("Object exceeds property limit.", path)
        min_properties = schema.get("minProperties")
        max_properties = schema.get("maxProperties")
        if isinstance(min_properties, int) and len(value) < min_properties:
            return _schema_error("Object has too few properties.", path)
        if isinstance(max_properties, int) and len(value) > max_properties:
            return _schema_error("Object has too many properties.", path)

        required = schema.get("required", [])
        if not isinstance(required, list) or not all(
            isinstance(item, str) for item in required
        ):
            return _schema_error("required must be an array of strings.", path)
        for key in required:
            if key not in value:
                return _schema_error("Required property is missing.", f"{path}.{key}")

        properties = schema.get("properties", {})
        if not isinstance(properties, Mapping):
            return _schema_error("properties must be an object.", path)
        if len(properties) > max_items:
            return _schema_error("Schema properties exceed the item limit.", path)
        additional = schema.get("additionalProperties", True)
        for key, item in value.items():
            child_path = f"{path}.{key}"
            if key in properties:
                property_result = validate_json_schema(
                    item,
                    properties[key],
                    path=child_path,
                    depth=depth + 1,
                    max_depth=max_depth,
                    max_items=max_items,
                )
                if property_result.is_err():
                    return property_result
            elif additional is False:
                return _schema_error("Additional property is not allowed.", child_path)
            elif isinstance(additional, Mapping):
                additional_result = validate_json_schema(
                    item,
                    additional,
                    path=child_path,
                    depth=depth + 1,
                    max_depth=max_depth,
                    max_items=max_items,
                )
                if additional_result.is_err():
                    return additional_result
    return Result.ok(None)


def _parse_json_value(
    content: Optional[str],
    *,
    max_bytes: int,
) -> Result[Any, Error]:
    """Parse one bounded JSON response without applying a schema."""
    if not isinstance(content, str) or not content.strip():
        return Result.err(
            _error("STRUCTURED_OUTPUT_EMPTY", "Structured output was empty.")
        )
    if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or max_bytes <= 0:
        return Result.err(
            _error(
                "STRUCTURED_OUTPUT_CONFIG_INVALID",
                "max_bytes must be a positive integer.",
            )
        )
    if len(content.encode("utf-8")) > max_bytes:
        return Result.err(
            _error(
                "STRUCTURED_OUTPUT_TOO_LARGE",
                "Structured output exceeds the byte limit.",
            )
        )

    def reject_non_standard_constant(value: str) -> None:
        raise ValueError(f"non-standard JSON numeric constant: {value}")

    try:
        return Result.ok(
            json.loads(content, parse_constant=reject_non_standard_constant)
        )
    except (RecursionError, TypeError, ValueError) as exc:
        return Result.err(
            _error(
                "STRUCTURED_OUTPUT_INVALID_JSON",
                "Structured output was not valid JSON.",
                reason=str(exc)[:256],
            )
        )


def parse_structured_output(
    content: Optional[str],
    schema: Optional[Mapping[str, Any]],
    *,
    max_bytes: int = 1_048_576,
) -> Result[Any, Error]:
    """Parse and validate a model response when a structured schema is set."""
    if schema is None:
        return Result.ok(content or "")
    parsed = _parse_json_value(content, max_bytes=max_bytes)
    if parsed.is_err():
        return Result.err(parsed.unwrap_err())
    value = parsed.unwrap()
    validation = validate_json_schema(value, schema)
    if validation.is_err():
        return Result.err(validation.unwrap_err())
    return Result.ok(value)


def structured_model_schema(model: Any) -> Result[Dict[str, Any], Error]:
    """Return the JSON Schema advertised by a Pydantic-style model class.

    Pydantic v2 exposes ``model_json_schema`` while v1 exposes ``schema``.
    Supporting both keeps the MAPLE boundary additive for hosts that still
    carry a v1 model, without importing or reconstructing arbitrary classes.
    """
    if not isinstance(model, type):
        return Result.err(
            _error(
                "STRUCTURED_OUTPUT_MODEL_INVALID",
                "output_model must be a model class.",
            )
        )
    schema_factory = getattr(model, "model_json_schema", None)
    if not callable(schema_factory):
        schema_factory = getattr(model, "schema", None)
    if not callable(schema_factory):
        return Result.err(
            _error(
                "STRUCTURED_OUTPUT_MODEL_INVALID",
                "output_model must expose model_json_schema() or schema().",
            )
        )
    try:
        schema = schema_factory()
    except Exception as exc:
        return Result.err(
            _error(
                "STRUCTURED_OUTPUT_MODEL_INVALID",
                "output_model schema generation failed.",
                exception=type(exc).__name__,
            )
        )
    if not isinstance(schema, Mapping):
        return Result.err(
            _error(
                "STRUCTURED_OUTPUT_MODEL_INVALID",
                "output_model schema must be a mapping.",
            )
        )
    return Result.ok(dict(schema))


def validate_typed_value(value: Any, model: Type[Any]) -> Result[Any, Error]:
    """Validate an in-memory value with a Pydantic-style model class."""
    if not isinstance(model, type):
        return Result.err(
            _error(
                "STRUCTURED_OUTPUT_MODEL_INVALID",
                "model must be a model class.",
            )
        )
    validator = getattr(model, "model_validate", None)
    if not callable(validator):
        validator = getattr(model, "parse_obj", None)
    if not callable(validator):
        return Result.err(
            _error(
                "STRUCTURED_OUTPUT_MODEL_INVALID",
                "model must expose model_validate() or parse_obj().",
            )
        )
    try:
        return Result.ok(validator(value))
    except Exception as exc:
        return Result.err(
            _error(
                "STRUCTURED_OUTPUT_MODEL_INVALID",
                "Value did not satisfy model.",
                exception=type(exc).__name__,
            )
        )


def parse_typed_output(
    content: Optional[str],
    model: Type[Any],
    *,
    max_bytes: int = 1_048_576,
) -> Result[Any, Error]:
    """Parse bounded JSON and return a validated Pydantic model instance.

    Model validation is performed by the model itself rather than by the
    intentionally small JSON-Schema validator above. This preserves nested
    ``$ref`` semantics and the model's own field constraints.
    """
    parsed = _parse_json_value(content, max_bytes=max_bytes)
    if parsed.is_err():
        return Result.err(parsed.unwrap_err())
    validated = validate_typed_value(parsed.unwrap(), model)
    if validated.is_err():
        error = validated.unwrap_err()
        error["message"] = "Structured output did not satisfy output_model."
        return Result.err(error)
    return validated


def run_guardrails(
    value: Any,
    guardrails: List[Guardrail],
    *,
    stage: str,
    observer: Optional[GuardrailObserver] = None,
    trace_id: Optional[str] = None,
    span_id: Optional[str] = None,
) -> Result[None, Error]:
    """Run guardrails in order and fail closed on a malformed guardrail.

    The optional observer receives only bounded lifecycle metadata. Observer
    failures are isolated and never change the guardrail decision.
    """

    def emit(index: int, status: str) -> None:
        if observer is None:
            return
        try:
            observer(
                GuardrailEvent(
                    stage=stage,
                    index=index,
                    status=status,
                    trace_id=trace_id,
                    span_id=span_id,
                )
            )
        except Exception:
            # Observability must not weaken the fail-closed policy boundary.
            return

    for index, guardrail in enumerate(guardrails):
        emit(index, "started")
        checker = getattr(guardrail, "check", guardrail)
        if not callable(checker):
            emit(index, "failed")
            return Result.err(
                _error(
                    "GUARDRAIL_ERROR",
                    "Guardrail is not callable.",
                    stage=stage,
                    index=index,
                )
            )
        try:
            result = checker(value)
        except Exception as exc:
            emit(index, "failed")
            return Result.err(
                _error(
                    "GUARDRAIL_ERROR",
                    "Guardrail raised an exception.",
                    stage=stage,
                    index=index,
                    reason=type(exc).__name__,
                )
            )
        if isinstance(result, Result):
            if result.is_err():
                error = result.unwrap_err()
                if isinstance(error, dict):
                    emit(index, "rejected")
                    return Result.err(
                        _error(
                            "GUARDRAIL_REJECTED",
                            error.get("message", "Guardrail rejected the value."),
                            stage=stage,
                            index=index,
                            cause=error.get("errorType", "GUARDRAIL_REJECTED"),
                        )
                    )
                emit(index, "rejected")
                return Result.err(
                    _error(
                        "GUARDRAIL_REJECTED",
                        "Guardrail rejected the value.",
                        stage=stage,
                        index=index,
                    )
                )
            emit(index, "passed")
            continue
        if result is None or result is True:
            emit(index, "passed")
            continue
        if result is False:
            emit(index, "rejected")
            return Result.err(
                _error(
                    "GUARDRAIL_REJECTED",
                    "Guardrail rejected the value.",
                    stage=stage,
                    index=index,
                )
            )
        emit(index, "failed")
        return Result.err(
            _error(
                "GUARDRAIL_ERROR",
                "Guardrail returned an invalid result.",
                stage=stage,
                index=index,
            )
        )
    return Result.ok(None)


def schema_guardrail(schema: Mapping[str, Any]) -> Guardrail:
    """Create a guardrail that rejects values failing a JSON schema."""

    def check(value: Any) -> Result[None, Error]:
        return validate_json_schema(value, schema)

    return check
