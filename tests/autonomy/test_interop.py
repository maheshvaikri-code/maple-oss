"""Tests for strict adapter interop envelopes."""

from maple.autonomy.interop import InteropEnvelope, round_trip_json


def make_envelope():
    return InteropEnvelope(
        protocol="a2a",
        message_type="TASK",
        payload={"task": "research"},
        metadata={"trace_id": "trace-1"},
    )


def test_envelope_round_trip_preserves_wire_fields():
    result = round_trip_json(make_envelope())

    assert result.is_ok()
    restored = result.unwrap()
    assert restored.protocol == "a2a"
    assert restored.message_type == "TASK"
    assert restored.payload == {"task": "research"}
    assert restored.metadata["trace_id"] == "trace-1"


def test_envelope_rejects_unknown_fields_and_invalid_json():
    unknown = InteropEnvelope.from_dict(
        {
            **make_envelope().to_dict(),
            "unknown": True,
        }
    )
    non_string_key = InteropEnvelope.from_dict({1: True})
    invalid = InteropEnvelope.from_json("not-json")

    assert unknown.is_err()
    assert unknown.unwrap_err()["errorType"] == "INTEROP_UNKNOWN_FIELD"
    assert non_string_key.is_err()
    assert non_string_key.unwrap_err()["errorType"] == "INTEROP_INPUT_INVALID"
    assert invalid.is_err()
    assert invalid.unwrap_err()["errorType"] == "INTEROP_INVALID_JSON"


def test_envelope_bounds_non_json_and_version_fail_closed():
    non_json = InteropEnvelope(
        protocol="test",
        message_type="BAD",
        payload={"value": object()},
    ).to_json()
    unsupported = InteropEnvelope(
        protocol="test",
        message_type="VERSION",
        payload={},
        schema_version="2.0",
    ).to_json()
    oversized = make_envelope().to_json(max_bytes=10)

    assert non_json.is_err()
    assert non_json.unwrap_err()["errorType"] == "INTEROP_NON_JSON"
    assert unsupported.is_err()
    assert unsupported.unwrap_err()["errorType"] == "INTEROP_SCHEMA_UNSUPPORTED"
    assert oversized.is_err()
    assert oversized.unwrap_err()["errorType"] == "INTEROP_PAYLOAD_TOO_LARGE"
