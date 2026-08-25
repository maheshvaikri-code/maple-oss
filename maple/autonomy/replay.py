"""Bounded execution records for crash-window workflow replay."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Protocol, Tuple, Union

from ..core.result import Result

Error = Dict[str, Any]
_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_EXECUTION_KEY = re.compile(r"^[A-Za-z0-9_.:-]{1,512}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_MAX_JSON_DEPTH = 16
_MAX_JSON_ITEMS = 10_000

DEFAULT_MAX_RECORDS = 10_000
DEFAULT_MAX_RUN_RECORDS = 100
DEFAULT_MAX_RECORD_BYTES = 256 * 1024


def _error(error_type: str, message: str, **details: Any) -> Error:
    result: Error = {"errorType": error_type, "message": message}
    if details:
        result["details"] = details
    return result


def _valid_identifier(value: Any, field_name: str) -> Optional[Error]:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        return _error(
            "REPLAY_INPUT_INVALID",
            f"{field_name} must contain 1-128 letters, numbers, '_', '.', ':', or '-'.",
            field=field_name,
        )
    return None


def _valid_execution_key(value: Any) -> Optional[Error]:
    if not isinstance(value, str) or not _EXECUTION_KEY.fullmatch(value):
        return _error(
            "REPLAY_INPUT_INVALID",
            "execution_key must contain bounded identifier characters.",
            field="execution_key",
        )
    return None


def _valid_digest(value: Any) -> Optional[Error]:
    if not isinstance(value, str) or not _DIGEST.fullmatch(value):
        return _error(
            "REPLAY_INPUT_INVALID",
            "input_digest must be a lowercase SHA-256 hex digest.",
            field="input_digest",
        )
    return None


def _validate_json_value(
    value: Any,
    *,
    path: str = "$",
    depth: int = 0,
) -> Optional[Error]:
    if depth > _MAX_JSON_DEPTH:
        return _error(
            "REPLAY_VALUE_INVALID", "Replay value is nested too deeply.", path=path
        )
    if value is None or isinstance(value, (bool, int, str)):
        return None
    if isinstance(value, float):
        if math.isfinite(value):
            return None
        return _error(
            "REPLAY_VALUE_INVALID",
            "Replay value contains a non-finite number.",
            path=path,
        )
    if isinstance(value, list):
        if len(value) > _MAX_JSON_ITEMS:
            return _error(
                "REPLAY_VALUE_INVALID", "Replay list is too large.", path=path
            )
        for index, item in enumerate(value):
            error = _validate_json_value(item, path=f"{path}[{index}]", depth=depth + 1)
            if error:
                return error
        return None
    if isinstance(value, dict):
        if len(value) > _MAX_JSON_ITEMS:
            return _error(
                "REPLAY_VALUE_INVALID", "Replay object is too large.", path=path
            )
        for key, item in value.items():
            if not isinstance(key, str):
                return _error(
                    "REPLAY_VALUE_INVALID",
                    "Replay object keys must be strings.",
                    path=path,
                )
            error = _validate_json_value(item, path=f"{path}.{key}", depth=depth + 1)
            if error:
                return error
        return None
    return _error(
        "REPLAY_VALUE_INVALID",
        "Replay output must be JSON-compatible.",
        path=path,
        value_type=type(value).__name__,
    )


def _copy_json(
    value: Mapping[str, Any], max_bytes: int
) -> Result[Dict[str, Any], Error]:
    if not isinstance(value, Mapping):
        return Result.err(
            _error("REPLAY_VALUE_INVALID", "Replay output must be an object.")
        )
    value_error = _validate_json_value(dict(value))
    if value_error:
        return Result.err(value_error)
    try:
        encoded = json.dumps(
            dict(value), ensure_ascii=False, allow_nan=False, separators=(",", ":")
        )
        if len(encoded.encode("utf-8")) > max_bytes:
            return Result.err(
                _error(
                    "REPLAY_RECORD_SIZE",
                    "Replay output exceeds the configured record byte limit.",
                    max_record_bytes=max_bytes,
                )
            )
        return Result.ok(json.loads(encoded))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        return Result.err(
            _error(
                "REPLAY_VALUE_INVALID",
                "Replay output is not JSON serializable.",
                reason=str(exc)[:256],
            )
        )


@dataclass(frozen=True)
class ExecutionRecord:
    """One normalized node output keyed to one deterministic invocation."""

    execution_key: str
    run_id: str
    workflow_name: str
    node_name: str
    step_count: int
    input_digest: str
    output: Dict[str, Any]
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_key": self.execution_key,
            "run_id": self.run_id,
            "workflow_name": self.workflow_name,
            "node_name": self.node_name,
            "step_count": self.step_count,
            "input_digest": self.input_digest,
            "output": dict(self.output),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ExecutionRecord":
        if not isinstance(data, Mapping):
            raise ValueError("replay record must be an object")
        required = (
            "execution_key",
            "run_id",
            "workflow_name",
            "node_name",
            "step_count",
            "input_digest",
            "output",
            "created_at",
        )
        if any(name not in data for name in required):
            raise ValueError("replay record is missing a required field")
        if _valid_execution_key(data["execution_key"]):
            raise ValueError("invalid replay execution key")
        for name in ("run_id", "workflow_name", "node_name"):
            if _valid_identifier(data[name], name):
                raise ValueError(f"invalid replay {name}")
        step_count = data["step_count"]
        if (
            not isinstance(step_count, int)
            or isinstance(step_count, bool)
            or step_count < 0
        ):
            raise ValueError("invalid replay step count")
        if _valid_digest(data["input_digest"]):
            raise ValueError("invalid replay input digest")
        if not isinstance(data["output"], Mapping):
            raise ValueError("replay output must be an object")
        try:
            created_at = float(data["created_at"])
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("invalid replay timestamp") from exc
        if not math.isfinite(created_at):
            raise ValueError("invalid replay timestamp")
        output_error = _validate_json_value(dict(data["output"]))
        if output_error:
            raise ValueError(output_error["message"])
        return cls(
            execution_key=data["execution_key"],
            run_id=data["run_id"],
            workflow_name=data["workflow_name"],
            node_name=data["node_name"],
            step_count=step_count,
            input_digest=data["input_digest"],
            output=dict(data["output"]),
            created_at=created_at,
        )


class ExecutionJournal(Protocol):
    """Thread-safe persistence contract for normalized workflow outputs."""

    def load(
        self, execution_key: str, input_digest: str
    ) -> Result[Optional[ExecutionRecord], Error]: ...

    def save(self, record: ExecutionRecord) -> Result[ExecutionRecord, Error]: ...

    def clear(self, run_id: str) -> Result[int, Error]: ...


class _ExecutionJournalSupport:
    def _configure_limits(
        self, *, max_records: int, max_run_records: int, max_record_bytes: int
    ) -> None:
        values = (max_records, max_run_records, max_record_bytes)
        if any(
            not isinstance(value, int) or isinstance(value, bool) or value <= 0
            for value in values
        ):
            raise ValueError("replay journal limits must be positive integers")
        self.max_records = max_records
        self.max_run_records = max_run_records
        self.max_record_bytes = max_record_bytes

    def _validate_lookup(
        self, execution_key: str, input_digest: str
    ) -> Optional[Error]:
        return _valid_execution_key(execution_key) or _valid_digest(input_digest)

    def _copy_record(self, record: ExecutionRecord) -> Result[ExecutionRecord, Error]:
        if not isinstance(record, ExecutionRecord):
            return Result.err(
                _error("REPLAY_RECORD_INVALID", "Expected an ExecutionRecord.")
            )
        try:
            encoded = json.dumps(
                record.to_dict(),
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            )
            if len(encoded.encode("utf-8")) > self.max_record_bytes:
                return Result.err(
                    _error(
                        "REPLAY_RECORD_SIZE",
                        "Replay record exceeds the configured byte limit.",
                        max_record_bytes=self.max_record_bytes,
                    )
                )
            return Result.ok(ExecutionRecord.from_dict(json.loads(encoded)))
        except (TypeError, ValueError, OverflowError, json.JSONDecodeError) as exc:
            return Result.err(
                _error(
                    "REPLAY_RECORD_INVALID",
                    "Replay record is invalid.",
                    reason=str(exc)[:256],
                )
            )


class InMemoryExecutionJournal(_ExecutionJournalSupport):
    """Thread-safe bounded journal for tests and single-process hosts."""

    def __init__(
        self,
        *,
        max_records: int = DEFAULT_MAX_RECORDS,
        max_run_records: int = DEFAULT_MAX_RUN_RECORDS,
        max_record_bytes: int = DEFAULT_MAX_RECORD_BYTES,
    ) -> None:
        self._configure_limits(
            max_records=max_records,
            max_run_records=max_run_records,
            max_record_bytes=max_record_bytes,
        )
        self._records: Dict[str, ExecutionRecord] = {}
        self._lock = threading.RLock()

    def load(
        self, execution_key: str, input_digest: str
    ) -> Result[Optional[ExecutionRecord], Error]:
        validation = self._validate_lookup(execution_key, input_digest)
        if validation:
            return Result.err(validation)
        with self._lock:
            record = self._records.get(execution_key)
            if record is None:
                return Result.ok(None)
            if record.input_digest != input_digest:
                return Result.err(
                    _error(
                        "REPLAY_INPUT_CONFLICT",
                        "Execution key was recorded for different input.",
                        execution_key=execution_key,
                    )
                )
            return self._copy_record(record)

    def save(self, record: ExecutionRecord) -> Result[ExecutionRecord, Error]:
        copied = self._copy_record(record)
        if copied.is_err():
            return Result.err(copied.unwrap_err())
        candidate = copied.unwrap()
        with self._lock:
            existing = self._records.get(candidate.execution_key)
            if existing is not None:
                if (
                    existing.input_digest == candidate.input_digest
                    and existing.output == candidate.output
                ):
                    return self._copy_record(existing)
                return Result.err(
                    _error(
                        "REPLAY_CONFLICT",
                        "Execution key already has a different record.",
                        execution_key=candidate.execution_key,
                    )
                )
            if len(self._records) >= self.max_records:
                return Result.err(
                    _error(
                        "REPLAY_RECORD_LIMIT", "Replay journal record limit reached."
                    )
                )
            run_count = sum(
                item.run_id == candidate.run_id for item in self._records.values()
            )
            if run_count >= self.max_run_records:
                return Result.err(
                    _error(
                        "REPLAY_RUN_RECORD_LIMIT",
                        "Replay journal run record limit reached.",
                        run_id=candidate.run_id,
                    )
                )
            self._records[candidate.execution_key] = candidate
            return self._copy_record(candidate)

    def clear(self, run_id: str) -> Result[int, Error]:
        validation = _valid_identifier(run_id, "run_id")
        if validation:
            return Result.err(validation)
        with self._lock:
            keys = [
                key for key, record in self._records.items() if record.run_id == run_id
            ]
            for key in keys:
                del self._records[key]
            return Result.ok(len(keys))


class FileExecutionJournal(_ExecutionJournalSupport):
    """Atomic JSON-file journal for local process-restart recovery."""

    _PREFIX = "maple-replay-"

    def __init__(
        self,
        directory: Union[str, Path],
        *,
        max_records: int = DEFAULT_MAX_RECORDS,
        max_run_records: int = DEFAULT_MAX_RUN_RECORDS,
        max_record_bytes: int = DEFAULT_MAX_RECORD_BYTES,
    ) -> None:
        self._configure_limits(
            max_records=max_records,
            max_run_records=max_run_records,
            max_record_bytes=max_record_bytes,
        )
        self.directory = Path(directory)
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ValueError("replay journal directory is unavailable") from exc
        if not self.directory.is_dir():
            raise ValueError("replay journal path must be a directory")
        self._lock = threading.RLock()

    def _path(self, execution_key: str) -> Path:
        digest = hashlib.sha256(execution_key.encode("utf-8")).hexdigest()
        return self.directory / f"{self._PREFIX}{digest}.json"

    def _read_unlocked(
        self, execution_key: str
    ) -> Result[Optional[ExecutionRecord], Error]:
        path = self._path(execution_key)
        if not path.exists():
            return Result.ok(None)
        try:
            if path.stat().st_size > self.max_record_bytes:
                return Result.err(
                    _error("REPLAY_LOAD_ERROR", "Replay record exceeds the byte limit.")
                )
            data = json.loads(path.read_text(encoding="utf-8"))
            record = ExecutionRecord.from_dict(data)
            if record.execution_key != execution_key:
                return Result.err(
                    _error(
                        "REPLAY_LOAD_ERROR",
                        "Replay record key does not match its path.",
                    )
                )
            return Result.ok(record)
        except (
            OSError,
            TypeError,
            ValueError,
            OverflowError,
            json.JSONDecodeError,
        ) as exc:
            return Result.err(
                _error(
                    "REPLAY_LOAD_ERROR",
                    "Failed to load replay record.",
                    reason=str(exc)[:256],
                )
            )

    def _write_unlocked(
        self, record: ExecutionRecord
    ) -> Result[ExecutionRecord, Error]:
        copied = self._copy_record(record)
        if copied.is_err():
            return Result.err(copied.unwrap_err())
        candidate = copied.unwrap()
        payload = json.dumps(
            candidate.to_dict(),
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
        temporary_path: Optional[Path] = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=str(self.directory),
                prefix=".maple-replay-",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary_path = Path(handle.name)
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(str(temporary_path), str(self._path(candidate.execution_key)))
            temporary_path = None
            return Result.ok(candidate)
        except (OSError, TypeError, ValueError) as exc:
            return Result.err(
                _error(
                    "REPLAY_SAVE_ERROR",
                    "Failed to save replay record.",
                    reason=str(exc)[:256],
                )
            )
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink()
                except OSError:
                    pass

    def _records_unlocked(self) -> Result[Tuple[ExecutionRecord, ...], Error]:
        records = []
        for path in self.directory.glob(f"{self._PREFIX}*.json"):
            loaded = self._read_unlocked_from_path(path)
            if loaded.is_err():
                return Result.err(loaded.unwrap_err())
            if loaded.unwrap() is not None:
                records.append(loaded.unwrap())
                if len(records) > self.max_records:
                    return Result.err(
                        _error(
                            "REPLAY_RECORD_LIMIT",
                            "Replay journal record limit reached.",
                        )
                    )
        return Result.ok(tuple(records))

    def _read_unlocked_from_path(
        self, path: Path
    ) -> Result[Optional[ExecutionRecord], Error]:
        try:
            if path.stat().st_size > self.max_record_bytes:
                return Result.err(
                    _error("REPLAY_LOAD_ERROR", "Replay record exceeds the byte limit.")
                )
            record = ExecutionRecord.from_dict(
                json.loads(path.read_text(encoding="utf-8"))
            )
            if path.name != self._path(record.execution_key).name:
                return Result.err(
                    _error(
                        "REPLAY_LOAD_ERROR",
                        "Replay record key does not match its path.",
                    )
                )
            return Result.ok(record)
        except (
            OSError,
            TypeError,
            ValueError,
            OverflowError,
            json.JSONDecodeError,
        ) as exc:
            return Result.err(
                _error(
                    "REPLAY_LOAD_ERROR",
                    "Failed to inspect replay records.",
                    reason=str(exc)[:256],
                )
            )

    def load(
        self, execution_key: str, input_digest: str
    ) -> Result[Optional[ExecutionRecord], Error]:
        validation = self._validate_lookup(execution_key, input_digest)
        if validation:
            return Result.err(validation)
        with self._lock:
            loaded = self._read_unlocked(execution_key)
            if loaded.is_err() or loaded.unwrap() is None:
                return loaded
            record = loaded.unwrap()
            if record.input_digest != input_digest:
                return Result.err(
                    _error(
                        "REPLAY_INPUT_CONFLICT",
                        "Execution key was recorded for different input.",
                        execution_key=execution_key,
                    )
                )
            return self._copy_record(record)

    def save(self, record: ExecutionRecord) -> Result[ExecutionRecord, Error]:
        copied = self._copy_record(record)
        if copied.is_err():
            return Result.err(copied.unwrap_err())
        candidate = copied.unwrap()
        with self._lock:
            existing = self._read_unlocked(candidate.execution_key)
            if existing.is_err():
                return Result.err(existing.unwrap_err())
            if existing.unwrap() is not None:
                stored = existing.unwrap()
                if (
                    stored.input_digest == candidate.input_digest
                    and stored.output == candidate.output
                ):
                    return self._copy_record(stored)
                return Result.err(
                    _error(
                        "REPLAY_CONFLICT",
                        "Execution key already has a different record.",
                        execution_key=candidate.execution_key,
                    )
                )
            records = self._records_unlocked()
            if records.is_err():
                return Result.err(records.unwrap_err())
            if len(records.unwrap()) >= self.max_records:
                return Result.err(
                    _error(
                        "REPLAY_RECORD_LIMIT", "Replay journal record limit reached."
                    )
                )
            run_count = sum(
                item.run_id == candidate.run_id for item in records.unwrap()
            )
            if run_count >= self.max_run_records:
                return Result.err(
                    _error(
                        "REPLAY_RUN_RECORD_LIMIT",
                        "Replay journal run record limit reached.",
                        run_id=candidate.run_id,
                    )
                )
            return self._write_unlocked(candidate)

    def clear(self, run_id: str) -> Result[int, Error]:
        validation = _valid_identifier(run_id, "run_id")
        if validation:
            return Result.err(validation)
        with self._lock:
            records = self._records_unlocked()
            if records.is_err():
                return Result.err(records.unwrap_err())
            removed = 0
            for record in records.unwrap():
                if record.run_id == run_id:
                    try:
                        self._path(record.execution_key).unlink(missing_ok=True)
                        removed += 1
                    except OSError as exc:
                        return Result.err(
                            _error(
                                "REPLAY_DELETE_ERROR",
                                "Failed to clear replay records.",
                                reason=str(exc)[:256],
                            )
                        )
            return Result.ok(removed)


__all__ = [
    "DEFAULT_MAX_RECORD_BYTES",
    "DEFAULT_MAX_RECORDS",
    "DEFAULT_MAX_RUN_RECORDS",
    "ExecutionJournal",
    "ExecutionRecord",
    "FileExecutionJournal",
    "InMemoryExecutionJournal",
]
