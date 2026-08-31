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
"""Bounded idempotency records for authenticated agent invocations."""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Protocol, Union, cast

from ..core.result import Result
from .durable_leases import DurableRecordLease

Error = Dict[str, Any]

DEFAULT_MAX_AGENT_INVOCATION_ENTRIES = 10_000
DEFAULT_AGENT_INVOCATION_TTL_SECONDS = 24 * 60 * 60.0
DEFAULT_MAX_AGENT_INVOCATION_BYTES = 16 * 1024 * 1024
DEFAULT_MAX_AGENT_INVOCATION_RESPONSE_BYTES = 2 * 1024 * 1024
_MAX_AGENT_INVOCATION_ENTRIES = 100_000
_MAX_AGENT_INVOCATION_TTL_SECONDS = 7 * 24 * 60 * 60.0
_MAX_AGENT_INVOCATION_BYTES = 128 * 1024 * 1024
_MAX_IDEMPOTENCY_KEY_BYTES = 256
_MAX_TARGET_ID_BYTES = 512
_MAX_REQUEST_DIGEST_BYTES = 64
_MAX_FINGERPRINT_REQUEST_BYTES = 64 * 1024
_INVOCATION_STORE_VERSION = 1
_INVOCATION_FILENAME = "invocations.json"
_INVOCATION_TEMP_PREFIX = ".maple-invocations-"


def _error(error_type: str, message: str, **details: Any) -> Error:
    result: Error = {"errorType": error_type, "message": message}
    if details:
        result["details"] = details
    return result


def _bounded_identifier(
    value: Any, *, name: str, max_bytes: int, error_type: str
) -> Optional[Error]:
    if not isinstance(value, str) or not value:
        return _error(error_type, f"{name} must be a non-empty string.")
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in value):
        return _error(error_type, f"{name} must not contain control characters.")
    if len(value.encode("utf-8")) > max_bytes:
        return _error(
            error_type,
            f"{name} exceeds the configured byte limit.",
            max_bytes=max_bytes,
        )
    return None


def normalize_agent_idempotency_key(value: Any) -> Result[Optional[str], Error]:
    """Validate an optional caller-owned idempotency key."""

    if value is None:
        return Result.ok(None)
    invalid = _bounded_identifier(
        value,
        name="idempotency_key",
        max_bytes=_MAX_IDEMPOTENCY_KEY_BYTES,
        error_type="AGENT_INVOCATION_KEY_INVALID",
    )
    if invalid is not None:
        return Result.err(invalid)
    return Result.ok(value)


def fingerprint_agent_invocation(
    target_id: str, request: Mapping[str, Any]
) -> Result[str, Error]:
    """Return a canonical digest for one already-normalized invocation."""

    target_error = _bounded_identifier(
        target_id,
        name="target_id",
        max_bytes=_MAX_TARGET_ID_BYTES,
        error_type="AGENT_INVOCATION_TARGET_INVALID",
    )
    if target_error is not None:
        return Result.err(target_error)
    if not isinstance(request, Mapping):
        return Result.err(
            _error(
                "AGENT_INVOCATION_REQUEST_INVALID",
                "invocation request must be an object.",
            )
        )
    try:
        encoded = json.dumps(
            {"target_id": target_id, "request": dict(request)},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError, RecursionError):
        return Result.err(
            _error(
                "AGENT_INVOCATION_REQUEST_INVALID",
                "invocation request must be JSON serializable.",
            )
        )
    if len(encoded) > _MAX_FINGERPRINT_REQUEST_BYTES:
        return Result.err(
            _error(
                "AGENT_INVOCATION_REQUEST_INVALID",
                "invocation request exceeds the fingerprint byte limit.",
                max_bytes=_MAX_FINGERPRINT_REQUEST_BYTES,
            )
        )
    return Result.ok(hashlib.sha256(encoded).hexdigest())


@dataclass(frozen=True)
class AgentInvocationResponse:
    """A detached bounded HTTP response retained for keyed replay."""

    status_code: int
    payload: Dict[str, Any]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.status_code, int)
            or isinstance(self.status_code, bool)
            or not 100 <= self.status_code <= 599
        ):
            raise ValueError("status_code must be an HTTP status between 100 and 599")
        if not isinstance(self.payload, Mapping):
            raise ValueError("payload must be an object")
        copied = _copy_payload(
            self.payload, DEFAULT_MAX_AGENT_INVOCATION_RESPONSE_BYTES
        )
        object.__setattr__(self, "payload", copied)

    @classmethod
    def from_dict(cls, value: Any) -> "AgentInvocationResponse":
        if not isinstance(value, Mapping):
            raise ValueError("invocation response must be an object")
        status_code = value.get("status_code")
        payload = value.get("payload")
        if (
            not isinstance(status_code, int)
            or isinstance(status_code, bool)
            or not isinstance(payload, Mapping)
        ):
            raise ValueError("invocation response has invalid fields")
        return cls(status_code, dict(payload))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status_code": self.status_code,
            "payload": _copy_payload(
                self.payload, DEFAULT_MAX_AGENT_INVOCATION_RESPONSE_BYTES
            ),
        }


def _copy_payload(value: Mapping[str, Any], max_bytes: int) -> Dict[str, Any]:
    try:
        encoded = json.dumps(
            dict(value), ensure_ascii=False, allow_nan=False, separators=(",", ":")
        ).encode("utf-8")
        if len(encoded) > max_bytes:
            raise ValueError("payload exceeds the configured byte limit")
        copied = json.loads(encoded.decode("utf-8"))
    except (TypeError, ValueError, OverflowError, UnicodeError, RecursionError) as exc:
        raise ValueError("payload must be bounded JSON") from exc
    if not isinstance(copied, dict):
        raise ValueError("payload must be an object")
    return copied


class AgentInvocationDeduplicationStore(Protocol):
    """Host-owned claim/complete/abort contract for keyed invocations."""

    def claim(
        self, target_id: str, idempotency_key: str, request_digest: str
    ) -> Result[Optional[AgentInvocationResponse], Error]:
        """Reserve a key or return its completed response."""

    def complete(
        self,
        target_id: str,
        idempotency_key: str,
        request_digest: str,
        response: AgentInvocationResponse,
    ) -> Result[AgentInvocationResponse, Error]:
        """Commit the normalized response for an active claim."""

    def abort(
        self, target_id: str, idempotency_key: str, request_digest: str
    ) -> Result[None, Error]:
        """Release an incomplete claim without removing a completed response."""


@dataclass(frozen=True)
class _InvocationRecord:
    target_id: str
    request_digest: str
    response: Optional[AgentInvocationResponse]
    expires_at: float


def _validate_claim_inputs(
    target_id: Any, idempotency_key: Any, request_digest: Any
) -> Optional[Error]:
    target_error = _bounded_identifier(
        target_id,
        name="target_id",
        max_bytes=_MAX_TARGET_ID_BYTES,
        error_type="AGENT_INVOCATION_TARGET_INVALID",
    )
    if target_error is not None:
        return target_error
    key_result = normalize_agent_idempotency_key(idempotency_key)
    if key_result.is_err():
        return cast(Error, key_result.unwrap_err())
    if not isinstance(idempotency_key, str):
        return _error(
            "AGENT_INVOCATION_KEY_INVALID",
            "idempotency_key must be supplied to the store.",
        )
    if (
        not isinstance(request_digest, str)
        or len(request_digest) != _MAX_REQUEST_DIGEST_BYTES
        or any(character not in "0123456789abcdef" for character in request_digest)
    ):
        return _error(
            "AGENT_INVOCATION_DIGEST_INVALID",
            "request_digest must be a lowercase SHA-256 hexadecimal digest.",
        )
    return None


def _validate_store_limits(
    max_entries: Any, ttl_seconds: Any, max_bytes: Optional[Any] = None
) -> None:
    if (
        not isinstance(max_entries, int)
        or isinstance(max_entries, bool)
        or not 1 <= max_entries <= _MAX_AGENT_INVOCATION_ENTRIES
    ):
        raise ValueError("max_entries must be between 1 and 100000")
    if (
        not isinstance(ttl_seconds, (int, float))
        or isinstance(ttl_seconds, bool)
        or not 0 < float(ttl_seconds) <= _MAX_AGENT_INVOCATION_TTL_SECONDS
        or not math.isfinite(float(ttl_seconds))
    ):
        raise ValueError("ttl_seconds must be finite and within seven days")
    if max_bytes is not None and (
        not isinstance(max_bytes, int)
        or isinstance(max_bytes, bool)
        or not 1 <= max_bytes <= _MAX_AGENT_INVOCATION_BYTES
    ):
        raise ValueError(
            f"max_bytes must be between 1 and {_MAX_AGENT_INVOCATION_BYTES}"
        )


def _validate_clock(clock: Any) -> None:
    if not callable(clock):
        raise TypeError("clock must be callable")


def _copy_response(
    response: AgentInvocationResponse, max_bytes: int
) -> Result[AgentInvocationResponse, Error]:
    if not isinstance(response, AgentInvocationResponse):
        return Result.err(
            _error(
                "AGENT_INVOCATION_RESPONSE_INVALID",
                "response must be an AgentInvocationResponse.",
            )
        )
    try:
        payload = _copy_payload(response.payload, max_bytes)
        copied = AgentInvocationResponse(response.status_code, payload)
    except (TypeError, ValueError, OverflowError, RecursionError):
        return Result.err(
            _error(
                "AGENT_INVOCATION_RESPONSE_INVALID",
                "response must be bounded JSON within the configured byte limit.",
                max_bytes=max_bytes,
            )
        )
    return Result.ok(copied)


def _now(clock: Callable[[], float]) -> Result[float, Error]:
    try:
        value = float(clock())
    except (OverflowError, TypeError, ValueError):
        return Result.err(
            _error("AGENT_INVOCATION_CLOCK_INVALID", "deduplication clock is invalid.")
        )
    if not math.isfinite(value):
        return Result.err(
            _error("AGENT_INVOCATION_CLOCK_INVALID", "deduplication clock is invalid.")
        )
    return Result.ok(value)


def _matching_record(
    record: _InvocationRecord, target_id: str, request_digest: str
) -> Optional[Error]:
    if record.target_id != target_id or record.request_digest != request_digest:
        return _error(
            "AGENT_INVOCATION_CONFLICT",
            "idempotency_key was previously used for different request content.",
        )
    return None


def _copy_record_response(
    response: Optional[AgentInvocationResponse], max_bytes: int
) -> Optional[AgentInvocationResponse]:
    if response is None:
        return None
    result = _copy_response(response, max_bytes)
    if result.is_err():
        raise ValueError(result.unwrap_err()["message"])
    return cast(AgentInvocationResponse, result.unwrap())


class InMemoryAgentInvocationDeduplicationStore:
    """Bounded process-local deduplication for keyed agent invocations.

    A pending claim suppresses concurrent duplicates; a completed response is
    replayable until its TTL expires or a completed record is evicted. This is
    not durable coordination or an exactly-once side-effect protocol.
    """

    def __init__(
        self,
        *,
        max_entries: int = DEFAULT_MAX_AGENT_INVOCATION_ENTRIES,
        ttl_seconds: float = DEFAULT_AGENT_INVOCATION_TTL_SECONDS,
        max_response_bytes: int = DEFAULT_MAX_AGENT_INVOCATION_RESPONSE_BYTES,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        _validate_store_limits(max_entries, ttl_seconds)
        if (
            not isinstance(max_response_bytes, int)
            or isinstance(max_response_bytes, bool)
            or not 1
            <= max_response_bytes
            <= DEFAULT_MAX_AGENT_INVOCATION_RESPONSE_BYTES
        ):
            raise ValueError("max_response_bytes must be between 1 and 2097152")
        _validate_clock(clock)
        self.max_entries = max_entries
        self.ttl_seconds = float(ttl_seconds)
        self.max_response_bytes = max_response_bytes
        self._clock = clock
        self._records: "OrderedDict[str, _InvocationRecord]" = OrderedDict()
        self._lock = threading.RLock()

    def _purge_expired(self, now: float) -> None:
        expired = [
            key for key, record in self._records.items() if record.expires_at <= now
        ]
        for key in expired:
            self._records.pop(key, None)

    def _evict_completed(self) -> bool:
        for key, record in self._records.items():
            if record.response is not None:
                self._records.pop(key)
                return True
        return False

    def claim(
        self, target_id: str, idempotency_key: str, request_digest: str
    ) -> Result[Optional[AgentInvocationResponse], Error]:
        """Reserve a key or return its detached completed response."""
        invalid = _validate_claim_inputs(target_id, idempotency_key, request_digest)
        if invalid is not None:
            return Result.err(invalid)
        now_result = _now(self._clock)
        if now_result.is_err():
            return Result.err(now_result.unwrap_err())
        now = now_result.unwrap()
        with self._lock:
            self._purge_expired(now)
            existing = self._records.get(idempotency_key)
            if existing is not None:
                conflict = _matching_record(existing, target_id, request_digest)
                if conflict is not None:
                    return Result.err(conflict)
                self._records.move_to_end(idempotency_key)
                if existing.response is None:
                    return Result.err(
                        _error(
                            "AGENT_INVOCATION_IN_PROGRESS",
                            "idempotency_key is currently being executed.",
                        )
                    )
                return Result.ok(
                    _copy_record_response(existing.response, self.max_response_bytes)
                )
            while len(self._records) >= self.max_entries:
                if not self._evict_completed():
                    return Result.err(
                        _error(
                            "AGENT_INVOCATION_CAPACITY",
                            "no completed invocation claim is available for eviction.",
                            max_entries=self.max_entries,
                        )
                    )
            expires_at = now + self.ttl_seconds
            if not math.isfinite(expires_at):
                return Result.err(
                    _error(
                        "AGENT_INVOCATION_CLOCK_INVALID",
                        "deduplication expiry is invalid.",
                    )
                )
            self._records[idempotency_key] = _InvocationRecord(
                target_id=target_id,
                request_digest=request_digest,
                response=None,
                expires_at=expires_at,
            )
        return Result.ok(None)

    def complete(
        self,
        target_id: str,
        idempotency_key: str,
        request_digest: str,
        response: AgentInvocationResponse,
    ) -> Result[AgentInvocationResponse, Error]:
        """Complete an active claim with a detached response."""
        invalid = _validate_claim_inputs(target_id, idempotency_key, request_digest)
        if invalid is not None:
            return Result.err(invalid)
        copied_result = _copy_response(response, self.max_response_bytes)
        if copied_result.is_err():
            return Result.err(copied_result.unwrap_err())
        now_result = _now(self._clock)
        if now_result.is_err():
            return Result.err(now_result.unwrap_err())
        with self._lock:
            self._purge_expired(now_result.unwrap())
            existing = self._records.get(idempotency_key)
            if existing is None:
                return Result.err(
                    _error(
                        "AGENT_INVOCATION_CLAIM_MISSING",
                        "idempotency_key has no active claim.",
                    )
                )
            conflict = _matching_record(existing, target_id, request_digest)
            if conflict is not None:
                return Result.err(conflict)
            if existing.response is not None:
                copied_existing = _copy_record_response(
                    existing.response, self.max_response_bytes
                )
                if copied_existing is None:
                    raise RuntimeError("completed invocation response disappeared")
                return Result.ok(copied_existing)
            completed = _InvocationRecord(
                target_id=existing.target_id,
                request_digest=existing.request_digest,
                response=copied_result.unwrap(),
                expires_at=existing.expires_at,
            )
            self._records[idempotency_key] = completed
            self._records.move_to_end(idempotency_key)
            copied_completed = _copy_record_response(
                completed.response, self.max_response_bytes
            )
            if copied_completed is None:
                raise RuntimeError("completed invocation response disappeared")
            return Result.ok(copied_completed)

    def abort(
        self, target_id: str, idempotency_key: str, request_digest: str
    ) -> Result[None, Error]:
        """Release an incomplete claim without removing a completed response."""
        invalid = _validate_claim_inputs(target_id, idempotency_key, request_digest)
        if invalid is not None:
            return Result.err(invalid)
        now_result = _now(self._clock)
        if now_result.is_err():
            return Result.err(now_result.unwrap_err())
        with self._lock:
            self._purge_expired(now_result.unwrap())
            existing = self._records.get(idempotency_key)
            if existing is None:
                return Result.ok(None)
            conflict = _matching_record(existing, target_id, request_digest)
            if conflict is not None:
                return Result.err(conflict)
            if existing.response is None:
                self._records.pop(idempotency_key, None)
        return Result.ok(None)

    def metrics(self) -> Dict[str, int]:
        """Return bounded local retention metrics without payloads."""
        now_result = _now(self._clock)
        if now_result.is_err():
            return {"retained_claims": 0, "max_entries": self.max_entries}
        with self._lock:
            self._purge_expired(now_result.unwrap())
            return {
                "retained_claims": len(self._records),
                "max_entries": self.max_entries,
            }


class FileAgentInvocationDeduplicationStore:
    """Bounded durable deduplication for one local agent host.

    Only idempotency identity, a request digest, expiry, and the normalized
    response are persisted. Each operation uses a local fencing lease and
    atomically replaces one JSON file. This remains a crash-window replay guard,
    not a distributed exactly-once side-effect protocol.
    """

    def __init__(
        self,
        directory: Union[str, Path],
        *,
        max_entries: int = DEFAULT_MAX_AGENT_INVOCATION_ENTRIES,
        ttl_seconds: float = DEFAULT_AGENT_INVOCATION_TTL_SECONDS,
        max_bytes: int = DEFAULT_MAX_AGENT_INVOCATION_BYTES,
        max_response_bytes: int = DEFAULT_MAX_AGENT_INVOCATION_RESPONSE_BYTES,
        lease_ttl_seconds: float = 30.0,
        clock: Callable[[], float] = time.time,
    ) -> None:
        _validate_store_limits(max_entries, ttl_seconds, max_bytes)
        if (
            not isinstance(max_response_bytes, int)
            or isinstance(max_response_bytes, bool)
            or not 1
            <= max_response_bytes
            <= DEFAULT_MAX_AGENT_INVOCATION_RESPONSE_BYTES
        ):
            raise ValueError("max_response_bytes must be between 1 and 2097152")
        _validate_clock(clock)
        self.max_entries = max_entries
        self.ttl_seconds = float(ttl_seconds)
        self.max_bytes = max_bytes
        self.max_response_bytes = max_response_bytes
        self._clock = clock
        self.directory = Path(directory).expanduser().resolve()
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ValueError("agent invocation directory is unavailable") from exc
        if not self.directory.is_dir():
            raise ValueError("agent invocation path must be a directory")
        self.path = self.directory / _INVOCATION_FILENAME
        self._lock = threading.RLock()
        try:
            self._lease = DurableRecordLease(
                self.directory,
                namespace="agent-invocation-deduplication",
                holder_label="file-agent-invocation-deduplication",
                lease_ttl_seconds=lease_ttl_seconds,
            )
        except (OSError, TypeError, ValueError) as exc:
            raise ValueError("agent invocation lease is unavailable") from exc

    @staticmethod
    def _load_error(message: str) -> Error:
        return _error("AGENT_INVOCATION_LOAD_ERROR", message)

    @staticmethod
    def _save_error(message: str, **details: Any) -> Error:
        return _error("AGENT_INVOCATION_SAVE_ERROR", message, **details)

    @staticmethod
    def _record_to_dict(
        idempotency_key: str, record: _InvocationRecord
    ) -> Dict[str, Any]:
        return {
            "idempotency_key": idempotency_key,
            "target_id": record.target_id,
            "request_digest": record.request_digest,
            "response": record.response.to_dict() if record.response else None,
            "expires_at": record.expires_at,
        }

    def _read_unlocked(
        self,
    ) -> Result["OrderedDict[str, _InvocationRecord]", Error]:
        records: "OrderedDict[str, _InvocationRecord]" = OrderedDict()
        if not self.path.exists():
            return Result.ok(records)
        try:
            if self.path.stat().st_size > self.max_bytes:
                return Result.err(
                    self._load_error("agent invocation state exceeds the byte limit.")
                )
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, TypeError, ValueError, json.JSONDecodeError):
            return Result.err(
                self._load_error("agent invocation state could not be loaded.")
            )
        if (
            not isinstance(data, Mapping)
            or data.get("version") != _INVOCATION_STORE_VERSION
            or not isinstance(data.get("records"), list)
            or len(data["records"]) > self.max_entries
        ):
            return Result.err(self._load_error("agent invocation state is invalid."))
        for raw_record in data["records"]:
            if not isinstance(raw_record, Mapping):
                return Result.err(self._load_error("invocation record is invalid."))
            key = raw_record.get("idempotency_key")
            target_id = raw_record.get("target_id")
            digest = raw_record.get("request_digest")
            key_error = _validate_claim_inputs(target_id, key, digest)
            if key_error is not None:
                return Result.err(
                    self._load_error("invocation record identity is invalid.")
                )
            if (
                not isinstance(key, str)
                or not isinstance(target_id, str)
                or not isinstance(digest, str)
            ):
                return Result.err(
                    self._load_error("invocation record identity is invalid.")
                )
            if key in records:
                return Result.err(
                    self._load_error("invocation state contains duplicate keys.")
                )
            expires_at = raw_record.get("expires_at")
            if (
                not isinstance(expires_at, (int, float))
                or isinstance(expires_at, bool)
                or not math.isfinite(float(expires_at))
            ):
                return Result.err(self._load_error("invocation expiry is invalid."))
            raw_response = raw_record.get("response")
            response: Optional[AgentInvocationResponse] = None
            if raw_response is not None:
                try:
                    response = AgentInvocationResponse.from_dict(raw_response)
                    response_result = _copy_response(response, self.max_response_bytes)
                except (TypeError, ValueError, OverflowError, RecursionError):
                    return Result.err(
                        self._load_error("invocation response is invalid.")
                    )
                if response_result.is_err():
                    return Result.err(
                        self._load_error("invocation response is invalid.")
                    )
                response = response_result.unwrap()
            records[key] = _InvocationRecord(
                target_id=target_id,
                request_digest=digest,
                response=response,
                expires_at=float(expires_at),
            )
        encoded = self._encode(records)
        if encoded.is_err():
            return Result.err(
                self._load_error("agent invocation state exceeds limits.")
            )
        return Result.ok(records)

    def _encode(
        self, records: "OrderedDict[str, _InvocationRecord]"
    ) -> Result[str, Error]:
        if len(records) > self.max_entries:
            return Result.err(
                _error(
                    "AGENT_INVOCATION_CAPACITY",
                    "agent invocation entry limit reached.",
                    max_entries=self.max_entries,
                )
            )
        try:
            encoded = json.dumps(
                {
                    "version": _INVOCATION_STORE_VERSION,
                    "records": [
                        self._record_to_dict(key, record)
                        for key, record in records.items()
                    ],
                },
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            )
        except (TypeError, ValueError, OverflowError, RecursionError):
            return Result.err(self._save_error("agent invocation state is invalid."))
        if len(encoded.encode("utf-8")) > self.max_bytes:
            return Result.err(
                _error(
                    "AGENT_INVOCATION_SIZE",
                    "agent invocation state exceeds the byte limit.",
                    max_bytes=self.max_bytes,
                )
            )
        return Result.ok(encoded)

    def _write_unlocked(
        self, records: "OrderedDict[str, _InvocationRecord]"
    ) -> Result[None, Error]:
        encoded = self._encode(records)
        if encoded.is_err():
            return Result.err(encoded.unwrap_err())
        temporary_path: Optional[Path] = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=str(self.directory),
                prefix=_INVOCATION_TEMP_PREFIX,
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary_path = Path(handle.name)
                handle.write(encoded.unwrap())
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(str(temporary_path), str(self.path))
            temporary_path = None
            return Result.ok(None)
        except (OSError, TypeError, ValueError) as exc:
            return Result.err(
                self._save_error(
                    "agent invocation state could not be saved.",
                    reason=type(exc).__name__,
                )
            )
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink()
                except OSError:
                    pass

    @staticmethod
    def _purge_expired(
        records: "OrderedDict[str, _InvocationRecord]", now: float
    ) -> bool:
        expired = [key for key, record in records.items() if record.expires_at <= now]
        for key in expired:
            records.pop(key, None)
        return bool(expired)

    @staticmethod
    def _evict_completed(records: "OrderedDict[str, _InvocationRecord]") -> bool:
        for key, record in records.items():
            if record.response is not None:
                records.pop(key)
                return True
        return False

    def _run(
        self, operation: str, callback: Callable[[], Result[Any, Error]]
    ) -> Result[Any, Error]:
        try:
            return self._lease.run(
                "store",
                operation,
                callback,
                acquire_error_type="AGENT_INVOCATION_LEASE_ERROR",
                acquire_error_message="agent invocation lease could not be acquired.",
                release_error_type="AGENT_INVOCATION_LEASE_RELEASE_ERROR",
                release_error_message="agent invocation lease could not be released.",
            )
        except Exception as exc:
            return Result.err(
                _error(
                    "AGENT_INVOCATION_ERROR",
                    "agent invocation store operation failed.",
                    operation=operation,
                    reason=type(exc).__name__,
                )
            )

    def claim(
        self, target_id: str, idempotency_key: str, request_digest: str
    ) -> Result[Optional[AgentInvocationResponse], Error]:
        """Durably reserve a key or return its detached response."""
        invalid = _validate_claim_inputs(target_id, idempotency_key, request_digest)
        if invalid is not None:
            return Result.err(invalid)

        def operation() -> Result[Optional[AgentInvocationResponse], Error]:
            now_result = _now(self._clock)
            if now_result.is_err():
                return Result.err(now_result.unwrap_err())
            current = self._read_unlocked()
            if current.is_err():
                return Result.err(current.unwrap_err())
            records = current.unwrap()
            changed = self._purge_expired(records, now_result.unwrap())
            existing = records.get(idempotency_key)
            if existing is not None:
                conflict = _matching_record(existing, target_id, request_digest)
                if conflict is not None:
                    return Result.err(conflict)
                if changed:
                    saved = self._write_unlocked(records)
                    if saved.is_err():
                        return Result.err(saved.unwrap_err())
                if existing.response is None:
                    return Result.err(
                        _error(
                            "AGENT_INVOCATION_IN_PROGRESS",
                            "idempotency_key is currently being executed.",
                        )
                    )
                return Result.ok(
                    _copy_record_response(existing.response, self.max_response_bytes)
                )
            while len(records) >= self.max_entries:
                if not self._evict_completed(records):
                    return Result.err(
                        _error(
                            "AGENT_INVOCATION_CAPACITY",
                            "no completed invocation claim is available for eviction.",
                            max_entries=self.max_entries,
                        )
                    )
            expires_at = now_result.unwrap() + self.ttl_seconds
            if not math.isfinite(expires_at):
                return Result.err(
                    _error(
                        "AGENT_INVOCATION_CLOCK_INVALID",
                        "deduplication expiry is invalid.",
                    )
                )
            records[idempotency_key] = _InvocationRecord(
                target_id=target_id,
                request_digest=request_digest,
                response=None,
                expires_at=expires_at,
            )
            saved = self._write_unlocked(records)
            if saved.is_err():
                return Result.err(saved.unwrap_err())
            return Result.ok(None)

        with self._lock:
            result = self._run("claim", operation)
        return (
            Result.err(result.unwrap_err())
            if result.is_err()
            else Result.ok(result.unwrap())
        )

    def complete(
        self,
        target_id: str,
        idempotency_key: str,
        request_digest: str,
        response: AgentInvocationResponse,
    ) -> Result[AgentInvocationResponse, Error]:
        """Durably complete a claim with a detached response."""
        invalid = _validate_claim_inputs(target_id, idempotency_key, request_digest)
        if invalid is not None:
            return Result.err(invalid)
        copied_result = _copy_response(response, self.max_response_bytes)
        if copied_result.is_err():
            return Result.err(copied_result.unwrap_err())

        def operation() -> Result[AgentInvocationResponse, Error]:
            now_result = _now(self._clock)
            if now_result.is_err():
                return Result.err(now_result.unwrap_err())
            current = self._read_unlocked()
            if current.is_err():
                return Result.err(current.unwrap_err())
            records = current.unwrap()
            self._purge_expired(records, now_result.unwrap())
            existing = records.get(idempotency_key)
            if existing is None:
                return Result.err(
                    _error(
                        "AGENT_INVOCATION_CLAIM_MISSING",
                        "idempotency_key has no active claim.",
                    )
                )
            conflict = _matching_record(existing, target_id, request_digest)
            if conflict is not None:
                return Result.err(conflict)
            if existing.response is not None:
                copied_existing = _copy_record_response(
                    existing.response, self.max_response_bytes
                )
                if copied_existing is None:
                    raise RuntimeError("completed invocation response disappeared")
                return Result.ok(copied_existing)
            completed = _InvocationRecord(
                target_id=existing.target_id,
                request_digest=existing.request_digest,
                response=copied_result.unwrap(),
                expires_at=existing.expires_at,
            )
            records[idempotency_key] = completed
            records.move_to_end(idempotency_key)
            saved = self._write_unlocked(records)
            if saved.is_err():
                return Result.err(saved.unwrap_err())
            copied_completed = _copy_record_response(
                completed.response, self.max_response_bytes
            )
            if copied_completed is None:
                raise RuntimeError("completed invocation response disappeared")
            return Result.ok(copied_completed)

        with self._lock:
            result = self._run("complete", operation)
        return (
            Result.err(result.unwrap_err())
            if result.is_err()
            else Result.ok(result.unwrap())
        )

    def abort(
        self, target_id: str, idempotency_key: str, request_digest: str
    ) -> Result[None, Error]:
        """Durably release a pending claim."""
        invalid = _validate_claim_inputs(target_id, idempotency_key, request_digest)
        if invalid is not None:
            return Result.err(invalid)

        def operation() -> Result[None, Error]:
            now_result = _now(self._clock)
            if now_result.is_err():
                return Result.err(now_result.unwrap_err())
            current = self._read_unlocked()
            if current.is_err():
                return Result.err(current.unwrap_err())
            records = current.unwrap()
            changed = self._purge_expired(records, now_result.unwrap())
            existing = records.get(idempotency_key)
            if existing is None:
                if changed:
                    saved = self._write_unlocked(records)
                    if saved.is_err():
                        return Result.err(saved.unwrap_err())
                return Result.ok(None)
            conflict = _matching_record(existing, target_id, request_digest)
            if conflict is not None:
                return Result.err(conflict)
            if existing.response is None:
                records.pop(idempotency_key, None)
                changed = True
            if changed:
                saved = self._write_unlocked(records)
                if saved.is_err():
                    return Result.err(saved.unwrap_err())
            return Result.ok(None)

        with self._lock:
            result = self._run("abort", operation)
        return (
            Result.err(result.unwrap_err())
            if result.is_err()
            else Result.ok(result.unwrap())
        )

    def metrics(self) -> Dict[str, int]:
        """Return bounded local retention metrics without payloads."""

        def operation() -> Result[Dict[str, int], Error]:
            now_result = _now(self._clock)
            if now_result.is_err():
                return Result.err(now_result.unwrap_err())
            current = self._read_unlocked()
            if current.is_err():
                return Result.err(current.unwrap_err())
            records = current.unwrap()
            changed = self._purge_expired(records, now_result.unwrap())
            if changed:
                saved = self._write_unlocked(records)
                if saved.is_err():
                    return Result.err(saved.unwrap_err())
            return Result.ok(
                {"retained_claims": len(records), "max_entries": self.max_entries}
            )

        with self._lock:
            result = self._run("metrics", operation)
        if result.is_err():
            return {"retained_claims": 0, "max_entries": self.max_entries}
        return cast(Dict[str, int], result.unwrap())
