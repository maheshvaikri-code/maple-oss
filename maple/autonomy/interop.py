# Copyright (C) 2025 Mahesh Vaijainthymala Krishnamoorthy
# (Mahesh Vaikri)
#
# This file is part of MAPLE - Multi Agent Protocol Language Engine.
#
# MAPLE - Multi Agent Protocol Language Engine is free software: you can
# redistribute it and/or modify it under the terms of the GNU Affero General
# Public License as published by the Free Software Foundation, either version 3
# of the License, or (at your option) any later version.
# MAPLE - Multi Agent Protocol Language Engine is distributed in the hope that
# it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty
# of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero
# General Public License for more details. You should have received a copy of
# the GNU Affero General Public License along with MAPLE - Multi Agent Protocol
# Language Engine. If not, see <https://www.gnu.org/licenses/>.
"""Strict JSON interop envelope for MAPLE adapter contracts."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional

from ..core.result import Result

Error = Dict[str, Any]
_FIELDS = {"schema_version", "protocol", "message_type", "payload", "metadata"}


def _error(error_type: str, message: str, **details: Any) -> Error:
    error: Error = {"errorType": error_type, "message": message}
    if details:
        error["details"] = details
    return error


def _bounded_text(value: Any, field_name: str, max_length: int) -> Optional[Error]:
    if not isinstance(value, str) or not value or len(value) > max_length:
        return _error(
            "INTEROP_INPUT_INVALID", f"{field_name} is not bounded and non-empty."
        )
    if any(ord(char) < 32 for char in value):
        return _error(
            "INTEROP_INPUT_INVALID", f"{field_name} contains a control character."
        )
    return None


@dataclass(frozen=True)
class InteropEnvelope:
    """Versioned, strict, source-neutral envelope for adapter payloads."""

    protocol: str
    message_type: str
    payload: Mapping[str, Any]
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = "1.0"

    def validate(self, *, max_bytes: int = 1_048_576) -> Optional[Error]:
        for field_name, value, max_length in (
            ("schema_version", self.schema_version, 32),
            ("protocol", self.protocol, 128),
            ("message_type", self.message_type, 256),
        ):
            error = _bounded_text(value, field_name, max_length)
            if error is not None:
                return error
        if self.schema_version != "1.0":
            return _error(
                "INTEROP_SCHEMA_UNSUPPORTED", "only schema version 1.0 is supported."
            )
        if not isinstance(self.payload, Mapping) or not isinstance(
            self.metadata, Mapping
        ):
            return _error(
                "INTEROP_INPUT_INVALID", "payload and metadata must be objects."
            )
        if (
            not isinstance(max_bytes, int)
            or isinstance(max_bytes, bool)
            or max_bytes <= 0
        ):
            return _error("INTEROP_CONFIG_INVALID", "max_bytes must be positive.")
        try:
            encoded = json.dumps(
                self.to_dict(), ensure_ascii=False, allow_nan=False
            ).encode("utf-8")
        except (TypeError, ValueError, OverflowError):
            return _error("INTEROP_NON_JSON", "envelope must be JSON serializable.")
        if len(encoded) > max_bytes:
            return _error(
                "INTEROP_PAYLOAD_TOO_LARGE", "envelope exceeds the byte limit."
            )
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Return the strict envelope mapping."""
        return {
            "schema_version": self.schema_version,
            "protocol": self.protocol,
            "message_type": self.message_type,
            "payload": dict(self.payload),
            "metadata": dict(self.metadata),
        }

    def to_json(self, *, max_bytes: int = 1_048_576) -> Result[str, Error]:
        """Serialize a validated envelope."""
        validation = self.validate(max_bytes=max_bytes)
        if validation is not None:
            return Result.err(validation)
        return Result.ok(json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True))

    @classmethod
    def from_dict(
        cls, value: Mapping[str, Any], *, max_bytes: int = 1_048_576
    ) -> Result["InteropEnvelope", Error]:
        """Parse a strict envelope mapping and reject unknown fields."""
        if not isinstance(value, Mapping):
            return Result.err(
                _error("INTEROP_INPUT_INVALID", "envelope must be an object.")
            )
        if not all(isinstance(key, str) for key in value):
            return Result.err(
                _error("INTEROP_INPUT_INVALID", "envelope field names must be strings.")
            )
        unknown = set(value) - _FIELDS
        if unknown:
            return Result.err(
                _error(
                    "INTEROP_UNKNOWN_FIELD",
                    "envelope contains unknown fields.",
                    fields=sorted(unknown),
                )
            )
        missing = _FIELDS - set(value)
        if missing:
            return Result.err(
                _error(
                    "INTEROP_INPUT_INVALID",
                    "envelope is missing required fields.",
                    fields=sorted(missing),
                )
            )
        envelope = cls(
            schema_version=value["schema_version"],
            protocol=value["protocol"],
            message_type=value["message_type"],
            payload=value["payload"],
            metadata=value["metadata"],
        )
        validation = envelope.validate(max_bytes=max_bytes)
        if validation is not None:
            return Result.err(validation)
        return Result.ok(envelope)

    @classmethod
    def from_json(
        cls, value: str, *, max_bytes: int = 1_048_576
    ) -> Result["InteropEnvelope", Error]:
        """Parse JSON into a strict envelope."""
        if not isinstance(value, str) or len(value.encode("utf-8")) > max_bytes:
            return Result.err(
                _error(
                    "INTEROP_PAYLOAD_TOO_LARGE", "JSON envelope exceeds the byte limit."
                )
            )
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return Result.err(
                _error("INTEROP_INVALID_JSON", "envelope is not valid JSON.")
            )
        return cls.from_dict(parsed, max_bytes=max_bytes)


def round_trip_json(
    envelope: InteropEnvelope, *, max_bytes: int = 1_048_576
) -> Result[InteropEnvelope, Error]:
    """Serialize and parse an envelope for adapter contract tests."""
    encoded = envelope.to_json(max_bytes=max_bytes)
    if encoded.is_err():
        return Result.err(encoded.unwrap_err())
    return InteropEnvelope.from_json(encoded.unwrap(), max_bytes=max_bytes)
