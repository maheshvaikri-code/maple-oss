"""Shared lease orchestration for file-backed autonomy stores."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from ..core.result import Result
from ..resources.lease import FileLeaseManager

Error = Dict[str, Any]


class DurableRecordLease:
    """Run one durable-store operation under a bounded fencing lease.

    The lease manager is caller-owned state when supplied; otherwise a
    ``.maple-leases`` directory is created below the store directory. A
    release failure is deliberately surfaced because the operation may have
    committed before ownership could be relinquished safely.
    """

    def __init__(
        self,
        directory: Path,
        *,
        namespace: str,
        holder_label: str,
        lease_manager: Optional[FileLeaseManager] = None,
        lease_ttl_seconds: float = 30.0,
    ) -> None:
        if not namespace or not holder_label:
            raise ValueError("namespace and holder_label must be non-empty")
        if (
            not isinstance(lease_ttl_seconds, (int, float))
            or isinstance(lease_ttl_seconds, bool)
            or lease_ttl_seconds <= 0
        ):
            raise ValueError("lease_ttl_seconds must be positive")
        self._manager = lease_manager or FileLeaseManager(directory / ".maple-leases")
        self._namespace = namespace
        self._holder = f"{holder_label}-store-{os.getpid()}-{uuid.uuid4().hex}"
        self._ttl_seconds = float(lease_ttl_seconds)

    def _resource(self, record_id: str) -> str:
        return f"{self._namespace}:{record_id}"

    @staticmethod
    def _reason(error: Any) -> str:
        if isinstance(error, dict):
            return str(error.get("errorType", "unknown"))[:64]
        return "unknown"

    def _failure(
        self,
        error_type: str,
        message: str,
        operation: str,
        error: Any,
    ) -> Error:
        return {
            "errorType": error_type,
            "message": message,
            "details": {"operation": operation, "reason": self._reason(error)},
        }

    def run(
        self,
        record_id: str,
        operation: str,
        callback: Callable[[], Result[Any, Error]],
        *,
        acquire_error_type: str,
        acquire_error_message: str,
        release_error_type: str,
        release_error_message: str,
    ) -> Result[Any, Error]:
        try:
            acquired = self._manager.acquire(
                self._resource(record_id), self._holder, self._ttl_seconds
            )
        except (OSError, TypeError, ValueError) as exc:
            return Result.err(
                self._failure(
                    acquire_error_type,
                    acquire_error_message,
                    operation,
                    type(exc).__name__,
                )
            )
        if acquired.is_err():
            return Result.err(
                self._failure(
                    acquire_error_type,
                    acquire_error_message,
                    operation,
                    acquired.unwrap_err(),
                )
            )

        lease = acquired.unwrap()
        result: Optional[Result[Any, Error]] = None
        operation_exception: Optional[Exception] = None
        release_result: Optional[Result[Any, Any]] = None
        release_exception: Optional[Exception] = None
        try:
            try:
                result = callback()
            except Exception as exc:
                operation_exception = exc
        finally:
            try:
                release_result = self._manager.release(lease)
            except Exception as exc:
                release_exception = exc

        if operation_exception is not None:
            if release_exception is not None:
                raise release_exception from operation_exception
            if release_result is not None and (
                release_result.is_err() or release_result.unwrap() is not True
            ):
                raise RuntimeError(
                    "durable record lease release failed"
                ) from operation_exception
            raise operation_exception
        if release_exception is not None:
            raise release_exception
        if result is None:
            raise RuntimeError("durable lease callback returned no result")
        if release_result is not None and (
            release_result.is_err() or release_result.unwrap() is not True
        ):
            release_error = self._failure(
                release_error_type,
                release_error_message,
                operation,
                (
                    release_result.unwrap_err()
                    if release_result.is_err()
                    else {"errorType": "LEASE_NOT_HELD"}
                ),
            )
            if result.is_err():
                existing = dict(result.unwrap_err())
                details = existing.get("details")
                merged_details = dict(details) if isinstance(details, dict) else {}
                merged_details["lease_release_error"] = release_error["errorType"]
                existing["details"] = merged_details
                return Result.err(existing)
            return Result.err(release_error)
        return result
