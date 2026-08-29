"""Bounded local durability for host-owned notification delivery."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Mapping,
    Optional,
    Protocol,
    Tuple,
    Type,
    TypeVar,
    Union,
)

from ..core.result import Result

Error = Dict[str, Any]
NotificationT = TypeVar("NotificationT")
NotificationT_contra = TypeVar("NotificationT_contra", contravariant=True)

DEFAULT_MAX_NOTIFICATION_OUTBOX_RECORD_BYTES = 262_144
DEFAULT_MAX_NOTIFICATION_OUTBOX_RECORDS = 10_000
DEFAULT_MAX_NOTIFICATION_OUTBOX_BYTES = 64 * 1024 * 1024
DEFAULT_MAX_NOTIFICATION_OUTBOX_DRAIN = 1_000
_SCHEMA_VERSION = 1
_NOTIFICATION_ID = re.compile(r"^[0-9a-f]{64}$")


def _error(error_type: str, message: str, **details: Any) -> Error:
    result: Error = {"errorType": error_type, "message": message}
    if details:
        result["details"] = details
    return result


class NotificationOutboxTarget(Protocol[NotificationT_contra]):
    """Host-owned downstream notification boundary."""

    def notify(self, notification: NotificationT_contra) -> Result[None, Error]: ...


@dataclass(frozen=True)
class NotificationOutboxReport:
    """Bounded result of one explicit notification outbox drain."""

    attempted: int
    delivered: int
    failed: int
    pending: int
    failure_details: Tuple[Error, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "attempted": self.attempted,
            "delivered": self.delivered,
            "failed": self.failed,
            "pending": self.pending,
            "failure_details": [dict(detail) for detail in self.failure_details],
        }


@dataclass(frozen=True)
class _StoredNotification(Generic[NotificationT]):
    path: Path
    notification_id: str
    notification: NotificationT
    state: str
    attempts: int
    created_at: float
    updated_at: float
    last_error: Optional[Dict[str, str]]


class _RecordInvalid(ValueError):
    """Internal marker for fail-closed record parsing."""


class FileNotificationOutbox(Generic[NotificationT]):
    """Bounded, restart-safe file outbox for one notification type.

    ``notify`` only durably enqueues. ``drain`` is explicit and calls the
    host-owned target outside the outbox lock. Delivery is at-least-once: a
    process crash after target success and before the delivered mark can
    result in a later duplicate.
    """

    def __init__(
        self,
        directory: Union[str, Path],
        *,
        target: NotificationOutboxTarget[NotificationT],
        notification_type: Type[NotificationT],
        encoder: Callable[[NotificationT], Mapping[str, Any]],
        decoder: Callable[[Mapping[str, Any]], NotificationT],
        max_record_bytes: int = DEFAULT_MAX_NOTIFICATION_OUTBOX_RECORD_BYTES,
        max_records: int = DEFAULT_MAX_NOTIFICATION_OUTBOX_RECORDS,
        max_queue_bytes: int = DEFAULT_MAX_NOTIFICATION_OUTBOX_BYTES,
    ) -> None:
        if not callable(getattr(target, "notify", None)):
            raise TypeError("notification outbox target must implement notify")
        if not isinstance(notification_type, type):
            raise TypeError("notification_type must be a type")
        if not callable(encoder) or not callable(decoder):
            raise TypeError("notification encoder and decoder must be callable")
        for value, name, maximum in (
            (
                max_record_bytes,
                "max_record_bytes",
                DEFAULT_MAX_NOTIFICATION_OUTBOX_RECORD_BYTES,
            ),
            (max_records, "max_records", DEFAULT_MAX_NOTIFICATION_OUTBOX_RECORDS),
            (
                max_queue_bytes,
                "max_queue_bytes",
                DEFAULT_MAX_NOTIFICATION_OUTBOX_BYTES,
            ),
        ):
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or not 0 < value <= maximum
            ):
                raise ValueError(f"{name} must be between 1 and {maximum}")
        self.directory = Path(directory).expanduser().resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.target = target
        self.notification_type = notification_type
        self._encoder = encoder
        self._decoder = decoder
        self.max_record_bytes = max_record_bytes
        self.max_records = max_records
        self.max_queue_bytes = max_queue_bytes
        self._lock = threading.RLock()
        self._drain_lock = threading.Lock()

    def notify(self, notification: NotificationT) -> Result[None, Error]:
        """Atomically enqueue one notification, deduplicating its payload."""
        if not isinstance(notification, self.notification_type):
            return Result.err(
                _error(
                    "NOTIFICATION_OUTBOX_INVALID",
                    "notification has the wrong type for this outbox.",
                )
            )
        try:
            encoded_notification = self._encode_notification(notification)
            notification_id = hashlib.sha256(encoded_notification).hexdigest()
            path = self._path(notification_id)
            with self._lock:
                if path.exists() or path.is_symlink():
                    self._load_record(path)
                    return Result.ok(None)
                records = self._scan_records_locked()
                if len(records) >= self.max_records:
                    return Result.err(
                        _error(
                            "NOTIFICATION_OUTBOX_FULL",
                            "notification outbox record limit has been reached.",
                            max_records=self.max_records,
                        )
                    )
                now = time.time()
                record = {
                    "schema_version": _SCHEMA_VERSION,
                    "notification_id": notification_id,
                    "notification": json.loads(encoded_notification.decode("utf-8")),
                    "state": "pending",
                    "attempts": 0,
                    "created_at": now,
                    "updated_at": now,
                    "last_error": None,
                }
                try:
                    encoded_record = self._encode_record(record)
                except ValueError as exc:
                    if "exceeds configured size" in str(exc):
                        return Result.err(
                            _error(
                                "NOTIFICATION_OUTBOX_RECORD_TOO_LARGE",
                                "notification outbox record exceeds the configured byte limit.",
                                max_bytes=self.max_record_bytes,
                            )
                        )
                    raise
                queue_bytes = sum(item.path.stat().st_size for item in records)
                if queue_bytes + len(encoded_record) > self.max_queue_bytes:
                    return Result.err(
                        _error(
                            "NOTIFICATION_OUTBOX_FULL",
                            "notification outbox byte limit has been reached.",
                            max_queue_bytes=self.max_queue_bytes,
                        )
                    )
                self._write_record_locked(path, encoded_record)
            return Result.ok(None)
        except _RecordInvalid:
            return Result.err(
                _error(
                    "NOTIFICATION_OUTBOX_RECORD_INVALID",
                    "notification outbox contains an invalid record.",
                )
            )
        except (OSError, TypeError, ValueError, UnicodeError, json.JSONDecodeError):
            return Result.err(
                _error(
                    "NOTIFICATION_OUTBOX_SAVE_ERROR",
                    "notification could not be durably enqueued.",
                )
            )

    def list_pending(self, limit: int = 100) -> Result[List[NotificationT], Error]:
        """Return pending typed notifications in deterministic order."""
        limit_error = self._validate_limit(limit, "NOTIFICATION_OUTBOX_LIMIT_INVALID")
        if limit_error:
            return Result.err(limit_error)
        try:
            with self._lock:
                records = self._scan_records_locked()
                return Result.ok(
                    [item.notification for item in records if item.state == "pending"][
                        :limit
                    ]
                )
        except _RecordInvalid:
            return Result.err(
                _error(
                    "NOTIFICATION_OUTBOX_RECORD_INVALID",
                    "notification outbox contains an invalid record.",
                )
            )
        except (OSError, TypeError, ValueError, UnicodeError, json.JSONDecodeError):
            return Result.err(
                _error(
                    "NOTIFICATION_OUTBOX_LOAD_ERROR",
                    "notification outbox could not be loaded.",
                )
            )

    def drain(self, max_items: int = 100) -> Result[NotificationOutboxReport, Error]:
        """Make at most ``max_items`` explicit delivery attempts."""
        limit_error = self._validate_limit(
            max_items, "NOTIFICATION_OUTBOX_DRAIN_LIMIT_INVALID"
        )
        if limit_error:
            return Result.err(limit_error)
        with self._drain_lock:
            try:
                with self._lock:
                    candidates = [
                        item
                        for item in self._scan_records_locked()
                        if item.state == "pending"
                    ][:max_items]
            except _RecordInvalid:
                return Result.err(
                    _error(
                        "NOTIFICATION_OUTBOX_RECORD_INVALID",
                        "notification outbox contains an invalid record.",
                    )
                )
            except (OSError, TypeError, ValueError, UnicodeError, json.JSONDecodeError):
                return Result.err(
                    _error(
                        "NOTIFICATION_OUTBOX_LOAD_ERROR",
                        "notification outbox could not be loaded.",
                    )
                )

            attempted = 0
            delivered = 0
            failures: List[Error] = []
            for candidate in candidates:
                try:
                    with self._lock:
                        current = self._load_record(candidate.path)
                        if current.state != "pending":
                            continue
                    try:
                        target_result = self.target.notify(current.notification)
                    except Exception:
                        target_result = Result.err(
                            _error(
                                "NOTIFICATION_OUTBOX_TARGET_ERROR",
                                "downstream notifier raised an exception.",
                            )
                        )
                    target_error = self._target_error(target_result)
                    attempted += 1
                    if target_error is None:
                        self._mark_delivered(current)
                        delivered += 1
                        continue
                    failure = self._record_failure(current, target_error)
                    failures.append(failure)
                except _RecordInvalid:
                    return Result.err(
                        _error(
                            "NOTIFICATION_OUTBOX_RECORD_INVALID",
                            "notification outbox contains an invalid record.",
                        )
                    )
                except (
                    OSError,
                    TypeError,
                    ValueError,
                    UnicodeError,
                    json.JSONDecodeError,
                ):
                    return Result.err(
                        _error(
                            "NOTIFICATION_OUTBOX_SAVE_ERROR",
                            "notification outbox delivery state could not be saved.",
                        )
                    )

            try:
                with self._lock:
                    pending = sum(
                        item.state == "pending" for item in self._scan_records_locked()
                    )
            except _RecordInvalid:
                return Result.err(
                    _error(
                        "NOTIFICATION_OUTBOX_RECORD_INVALID",
                        "notification outbox contains an invalid record.",
                    )
                )
            except (OSError, TypeError, ValueError, UnicodeError, json.JSONDecodeError):
                return Result.err(
                    _error(
                        "NOTIFICATION_OUTBOX_LOAD_ERROR",
                        "notification outbox could not be loaded.",
                    )
                )
            return Result.ok(
                NotificationOutboxReport(
                    attempted=attempted,
                    delivered=delivered,
                    failed=len(failures),
                    pending=pending,
                    failure_details=tuple(failures),
                )
            )

    def _validate_limit(self, value: int, error_type: str) -> Optional[Error]:
        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or not 0 < value <= DEFAULT_MAX_NOTIFICATION_OUTBOX_DRAIN
        ):
            return _error(
                error_type,
                "notification outbox limit is out of bounds.",
                max_items=DEFAULT_MAX_NOTIFICATION_OUTBOX_DRAIN,
            )
        return None

    def _path(self, notification_id: str) -> Path:
        if not _NOTIFICATION_ID.fullmatch(notification_id):
            raise _RecordInvalid("notification ID is invalid")
        path = (self.directory / f"{notification_id}.json").resolve()
        if self.directory not in path.parents:
            raise _RecordInvalid("notification path escapes configured directory")
        return path

    def _scan_records_locked(self) -> List[_StoredNotification[NotificationT]]:
        paths: List[Path] = []
        for path in self.directory.glob("*.json"):
            if not path.is_file() and not path.is_symlink():
                raise _RecordInvalid("notification outbox contains a non-file record")
            if path.is_symlink():
                raise _RecordInvalid("notification outbox record must not be a symlink")
            if not _NOTIFICATION_ID.fullmatch(path.stem):
                raise _RecordInvalid("notification outbox filename is invalid")
            paths.append(path)
        records = [self._load_record(path) for path in paths]
        return sorted(records, key=lambda item: (item.created_at, item.notification_id))

    def _load_record(self, path: Path) -> _StoredNotification[NotificationT]:
        if path.parent != self.directory or path.is_symlink():
            raise _RecordInvalid("notification outbox record path is unsafe")
        try:
            size = path.stat().st_size
        except OSError as exc:
            raise _RecordInvalid("notification outbox record cannot be read") from exc
        if size > self.max_record_bytes:
            raise _RecordInvalid("notification outbox record is too large")
        try:
            with path.open("r", encoding="utf-8") as handle:
                raw = json.load(handle)
        except (OSError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
            raise _RecordInvalid(
                "notification outbox record is not valid JSON"
            ) from exc
        if not isinstance(raw, dict):
            raise _RecordInvalid("notification outbox record must be an object")
        if raw.get("schema_version") != _SCHEMA_VERSION:
            raise _RecordInvalid("notification outbox schema is unsupported")
        notification_id = raw.get("notification_id")
        if not isinstance(notification_id, str) or not _NOTIFICATION_ID.fullmatch(
            notification_id
        ):
            raise _RecordInvalid("notification outbox ID is invalid")
        if path.stem != notification_id:
            raise _RecordInvalid("notification outbox filename and ID disagree")
        state = raw.get("state")
        if state not in {"pending", "delivered"}:
            raise _RecordInvalid("notification outbox state is invalid")
        attempts = raw.get("attempts")
        if not isinstance(attempts, int) or isinstance(attempts, bool) or attempts < 0:
            raise _RecordInvalid("notification outbox attempts are invalid")
        created_at = self._finite_timestamp(raw.get("created_at"))
        updated_at = self._finite_timestamp(raw.get("updated_at"))
        last_error = raw.get("last_error")
        if last_error is not None:
            if not isinstance(last_error, dict):
                raise _RecordInvalid("notification outbox failure is invalid")
            if set(last_error) - {"errorType", "message"}:
                raise _RecordInvalid("notification outbox failure has unknown fields")
            if not all(
                isinstance(last_error.get(field), str)
                and bool(last_error.get(field))
                and len(last_error[field]) <= 128
                for field in ("errorType", "message")
            ):
                raise _RecordInvalid("notification outbox failure is invalid")
            last_error = {
                "errorType": last_error["errorType"],
                "message": last_error["message"],
            }
        notification_data = raw.get("notification")
        if not isinstance(notification_data, Mapping):
            raise _RecordInvalid("notification outbox payload is invalid")
        try:
            notification = self._decoder(notification_data)
        except Exception as exc:
            raise _RecordInvalid("notification outbox payload is invalid") from exc
        if not isinstance(notification, self.notification_type):
            raise _RecordInvalid("notification outbox payload has the wrong type")
        try:
            encoded_notification = self._encode_notification(notification)
        except Exception as exc:
            raise _RecordInvalid(
                "notification outbox payload is not canonical"
            ) from exc
        if hashlib.sha256(encoded_notification).hexdigest() != notification_id:
            raise _RecordInvalid("notification outbox payload digest is invalid")
        return _StoredNotification(
            path=path,
            notification_id=notification_id,
            notification=notification,
            state=state,
            attempts=attempts,
            created_at=created_at,
            updated_at=updated_at,
            last_error=last_error,
        )

    @staticmethod
    def _finite_timestamp(value: Any) -> float:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise _RecordInvalid("notification outbox timestamp is invalid")
        normalized = float(value)
        if not math.isfinite(normalized):
            raise _RecordInvalid("notification outbox timestamp is invalid")
        return normalized

    def _encode_notification(self, notification: NotificationT) -> bytes:
        payload = self._encoder(notification)
        if not isinstance(payload, Mapping) or any(
            not isinstance(key, str) for key in payload
        ):
            raise ValueError("notification encoder must return a string-keyed object")
        return json.dumps(
            dict(payload),
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")

    def _encode_record(self, record: Mapping[str, Any]) -> bytes:
        encoded = json.dumps(
            dict(record),
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        if len(encoded) > self.max_record_bytes:
            raise ValueError("notification outbox record exceeds configured size")
        return encoded

    def _write_record_locked(self, path: Path, encoded: bytes) -> None:
        if path.parent != self.directory or path.is_symlink():
            raise _RecordInvalid("notification outbox record path is unsafe")
        temporary_path: Optional[Path] = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=str(self.directory),
                prefix=f".{path.stem}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary_path = Path(handle.name)
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(str(temporary_path), str(path))
            temporary_path = None
            self._fsync_directory(self.directory)
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink()
                except OSError:
                    pass

    def _mark_delivered(self, current: _StoredNotification[NotificationT]) -> None:
        with self._lock:
            latest = self._load_record(current.path)
            if latest.state != "pending":
                return
            record = {
                "schema_version": _SCHEMA_VERSION,
                "notification_id": latest.notification_id,
                "notification": json.loads(
                    self._encode_notification(latest.notification).decode("utf-8")
                ),
                "state": "delivered",
                "attempts": latest.attempts + 1,
                "created_at": latest.created_at,
                "updated_at": time.time(),
                "last_error": None,
            }
            self._write_record_locked(latest.path, self._encode_record(record))

    def _record_failure(
        self,
        current: _StoredNotification[NotificationT],
        target_error: Error,
    ) -> Error:
        safe_target_type = target_error.get("errorType")
        if not isinstance(safe_target_type, str) or not safe_target_type:
            safe_target_type = "unknown"
        safe_target_type = safe_target_type[:64]
        failure = {
            "errorType": "NOTIFICATION_OUTBOX_DELIVERY_ERROR",
            "message": "downstream notifier rejected notification.",
            "notification_id": current.notification_id,
            "target_error_type": safe_target_type,
        }
        with self._lock:
            latest = self._load_record(current.path)
            if latest.state != "pending":
                return failure
            record = {
                "schema_version": _SCHEMA_VERSION,
                "notification_id": latest.notification_id,
                "notification": json.loads(
                    self._encode_notification(latest.notification).decode("utf-8")
                ),
                "state": "pending",
                "attempts": latest.attempts + 1,
                "created_at": latest.created_at,
                "updated_at": time.time(),
                "last_error": {
                    "errorType": "NOTIFICATION_OUTBOX_DELIVERY_ERROR",
                    "message": "downstream notifier rejected notification.",
                },
            }
            self._write_record_locked(latest.path, self._encode_record(record))
        return failure

    @staticmethod
    def _target_error(target_result: Any) -> Optional[Error]:
        if not isinstance(target_result, Result):
            return _error(
                "NOTIFICATION_OUTBOX_TARGET_ERROR",
                "downstream notifier returned an invalid result.",
            )
        if target_result.is_ok():
            return None
        return _error(
            "NOTIFICATION_OUTBOX_TARGET_ERROR",
            "downstream notifier rejected notification.",
        )

    @staticmethod
    def _fsync_directory(directory: Path) -> None:
        try:
            descriptor = os.open(str(directory), os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        except (AttributeError, OSError):
            pass


__all__ = [
    "DEFAULT_MAX_NOTIFICATION_OUTBOX_BYTES",
    "DEFAULT_MAX_NOTIFICATION_OUTBOX_DRAIN",
    "DEFAULT_MAX_NOTIFICATION_OUTBOX_RECORD_BYTES",
    "DEFAULT_MAX_NOTIFICATION_OUTBOX_RECORDS",
    "FileNotificationOutbox",
    "NotificationOutboxReport",
    "NotificationOutboxTarget",
]
