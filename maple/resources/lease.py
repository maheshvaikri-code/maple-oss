"""
Copyright (C) 2025 Mahesh Vaijainthymala Krishnamoorthy
(Mahesh Vaikri)

This file is part of MAPLE - Multi Agent Protocol Language Engine.

MAPLE - Multi Agent Protocol Language Engine is free software: you can
redistribute it and/or modify it under the terms of the GNU Affero General
Public License as published by the Free Software Foundation, either version 3
of the License, or (at your option) any later version.
MAPLE - Multi Agent Protocol Language Engine is distributed in the hope that
it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty
of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero
General Public License for more details. You should have received a copy of
the GNU Affero General Public License along with MAPLE - Multi Agent Protocol
Language Engine. If not, see <https://www.gnu.org/licenses/>.
"""

# maple/resources/lease.py
# Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)
#
# Exclusive resource leases -- the "one holder at a time" negotiation semantic
# that the renewable-pool ResourceManager cannot express: a named lock, a
# physical device (camera, robot arm, serial port), a floating license seat, or
# a singleton "leader"/"writer" role.
#
# A lease is time-boxed (TTL) so a crashed or slow holder cannot deadlock the
# resource -- expiry IS the preemption mechanism, no explicit revoke needed.
# Each grant carries a monotonically increasing per-resource FENCING TOKEN: the
# holder presents it to the guarded resource, so a stale holder that resumes
# after its lease expired and was re-granted to someone else is detectably out
# of date (is_valid() -> False) and will not act on a resource another agent now
# owns. This is the standard fencing-token pattern.

import hashlib
import json
import math
import os
import tempfile
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, Callable, Dict, Iterator, Optional, Tuple, Union, cast

from ..core.result import Result

_PROCESS_FILE_LOCKS: Dict[str, Any] = {}
_PROCESS_FILE_LOCKS_GUARD = threading.Lock()


def _process_file_lock(path: Path) -> Any:
    """Return the process-local lock paired with one durable lock file."""
    key = os.path.normcase(os.path.abspath(str(path)))
    with _PROCESS_FILE_LOCKS_GUARD:
        lock = _PROCESS_FILE_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _PROCESS_FILE_LOCKS[key] = lock
        return lock


@dataclass
class Lease:
    """An exclusive hold on a named resource.

    Attributes:
        resource: The leased resource name.
        holder: The agent id holding it.
        token: Per-resource, monotonically increasing fencing token. The holder
            passes it to the guarded resource; a delayed/stale holder (whose
            lease has since expired and been re-granted) presents an older token
            and is rejected.
        expires_at: Absolute deadline on the owning LeaseManager's monotonic clock.
    """

    resource: str
    holder: str
    token: int
    expires_at: float

    def is_expired(self, now: float) -> bool:
        return now >= self.expires_at


class LeaseManager:
    """Grants exclusive, time-boxed leases on named resources.

    Thread-safe. A lease held by a crashed/slow holder becomes acquirable by
    another holder once its TTL elapses (implicit preemption) -- there is
    deliberately no force-revoke.
    """

    def __init__(self, clock: Callable[[], float] = time.monotonic):
        # clock is injectable so tests are deterministic (advance a fake clock, no
        # sleeping).
        self._clock = clock
        self._leases: Dict[str, Lease] = {}
        self._counters: Dict[str, int] = {}
        self._lock = threading.RLock()

    def _active(self, resource: str, now: float) -> Optional[Lease]:
        """Return the current non-expired lease for `resource`, pruning it if
        expired."""
        lease = self._leases.get(resource)
        if lease is None:
            return None
        if lease.is_expired(now):
            del self._leases[resource]
            return None
        return lease

    def _next_token(self, resource: str) -> int:
        self._counters[resource] = self._counters.get(resource, 0) + 1
        return self._counters[resource]

    def acquire(self, resource: str, holder: str, ttl_seconds: float) -> Result:
        """Acquire (or, for the same holder, renew) an exclusive lease on `resource`.

        Returns Result.ok(Lease) if granted, or Result.err with the current
        holder and the time remaining if another agent holds a live lease.
        """
        if ttl_seconds <= 0:
            return Result.err(
                {
                    "errorType": "INVALID_TTL",
                    "message": "ttl_seconds must be positive",
                    "details": {"ttl_seconds": ttl_seconds},
                }
            )
        with self._lock:
            now = self._clock()
            current = self._active(resource, now)
            if current is not None and current.holder != holder:
                return Result.err(
                    {
                        "errorType": "RESOURCE_HELD",
                        "message": (
                            f"Resource '{resource}' is held by '{current.holder}'"
                        ),
                        "details": {
                            "holder": current.holder,
                            "expires_in": max(0.0, current.expires_at - now),
                        },
                    }
                )
            # Free, expired, or same-holder renewal -> grant a fresh fencing token.
            token = self._next_token(resource)
            lease = Lease(
                resource=resource,
                holder=holder,
                token=token,
                expires_at=now + ttl_seconds,
            )
            self._leases[resource] = lease
            return Result.ok(lease)

    def renew(self, lease: Lease, ttl_seconds: float) -> Result:
        """Extend a lease the caller still holds. Fails if it was lost
        (expired/preempted)."""
        if ttl_seconds <= 0:
            return Result.err(
                {
                    "errorType": "INVALID_TTL",
                    "message": "ttl_seconds must be positive",
                    "details": {"ttl_seconds": ttl_seconds},
                }
            )
        with self._lock:
            now = self._clock()
            current = self._active(lease.resource, now)
            if current is None or current.token != lease.token:
                return Result.err(
                    {
                        "errorType": "LEASE_LOST",
                        "message": f"Lease on '{lease.resource}' is no longer held",
                        "details": {"resource": lease.resource, "token": lease.token},
                    }
                )
            token = self._next_token(lease.resource)
            renewed = Lease(
                resource=lease.resource,
                holder=current.holder,
                token=token,
                expires_at=now + ttl_seconds,
            )
            self._leases[lease.resource] = renewed
            return Result.ok(renewed)

    def release(self, lease: Lease) -> Result:
        """Release a lease.

        Returns Result.ok(True) if the caller was the current holder, or
        Result.ok(False) if the lease had already expired or been preempted (an
        idempotent no-op -- a stale holder cannot release a resource another
        agent now holds).
        """
        with self._lock:
            now = self._clock()
            current = self._active(lease.resource, now)
            if current is not None and current.token == lease.token:
                del self._leases[lease.resource]
                return Result.ok(True)
            return Result.ok(False)

    def is_valid(self, lease: Lease) -> bool:
        """True iff this exact lease (by fencing token) is still the active,
        unexpired hold.

        A holder calls this immediately before acting on the guarded resource --
        the fence.
        """
        with self._lock:
            current = self._active(lease.resource, self._clock())
            return current is not None and current.token == lease.token

    def holder_of(self, resource: str) -> Optional[str]:
        """Current holder of `resource`, or None if free/expired."""
        with self._lock:
            current = self._active(resource, self._clock())
            return current.holder if current else None

    def is_held(self, resource: str) -> bool:
        """True iff `resource` currently has a live (non-expired) lease."""
        with self._lock:
            return self._active(resource, self._clock()) is not None


_MAX_FILE_LEASE_NAME = 256
_MAX_FILE_LEASE_TTL_SECONDS = 7 * 24 * 60 * 60


def _file_lease_error(
    error_type: str, message: str, details: Optional[Dict[str, object]] = None
) -> Result:
    payload: Dict[str, object] = {"errorType": error_type, "message": message}
    if details is not None:
        payload["details"] = details
    return Result.err(payload)


def _file_lease_storage_error(error_type: str, exc: BaseException) -> Result:
    return _file_lease_error(
        error_type,
        "The durable lease store could not complete the operation.",
        {"reason": type(exc).__name__},
    )


def _valid_file_lease_name(value: object) -> bool:
    return isinstance(value, str) and bool(value) and len(value) <= _MAX_FILE_LEASE_NAME


def _valid_file_lease_ttl(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and 0 < float(value) <= _MAX_FILE_LEASE_TTL_SECONDS
    )


class _InterProcessFileLock:
    """Small cross-platform advisory lock used for file-backed lease state."""

    def __init__(self, path: Path, timeout_seconds: float) -> None:
        self._path = path
        self._timeout_seconds = timeout_seconds
        self._handle: Optional[BinaryIO] = None
        self._process_lock = _process_file_lock(path)

    def __enter__(self) -> "_InterProcessFileLock":
        deadline = time.monotonic() + self._timeout_seconds
        remaining = max(0.0, deadline - time.monotonic())
        if not self._process_lock.acquire(timeout=remaining):
            raise TimeoutError("timed out acquiring file lease lock")
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            handle = self._path.open("a+b")
        except BaseException:
            self._process_lock.release()
            raise
        try:
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"0")
                handle.flush()
                os.fsync(handle.fileno())
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                locking = getattr(msvcrt, "locking")
                lock_nonblocking = getattr(msvcrt, "LK_NBLCK")
                while True:
                    try:
                        locking(handle.fileno(), lock_nonblocking, 1)
                        break
                    except OSError:
                        if time.monotonic() >= deadline:
                            raise TimeoutError("timed out acquiring file lease lock")
                        handle.seek(0)
                        time.sleep(0.01)
            else:
                import fcntl

                while True:
                    try:
                        flock = getattr(fcntl, "flock")
                        lock_ex = getattr(fcntl, "LOCK_EX")
                        lock_nb = getattr(fcntl, "LOCK_NB")
                        flock(handle.fileno(), lock_ex | lock_nb)
                        break
                    except OSError:
                        if time.monotonic() >= deadline:
                            raise TimeoutError("timed out acquiring file lease lock")
                        time.sleep(0.01)
            self._handle = handle
            return self
        except BaseException:
            handle.close()
            self._process_lock.release()
            raise

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        handle = self._handle
        self._handle = None
        if handle is None:
            return
        try:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                locking = getattr(msvcrt, "locking")
                lock_unlock = getattr(msvcrt, "LK_UNLCK")
                locking(handle.fileno(), lock_unlock, 1)
            else:
                import fcntl

                flock = getattr(fcntl, "flock")
                lock_un = getattr(fcntl, "LOCK_UN")
                flock(handle.fileno(), lock_un)
        finally:
            handle.close()
            self._process_lock.release()


class FileLeaseManager:
    """Cross-process durable lease manager backed by atomic JSON files.

    The in-memory :class:`LeaseManager` remains the zero-I/O option. This class uses an
    advisory OS file lock to serialize read/modify/write operations across processes,
    persists fencing counters so tokens never reset after restart, and fails closed on
    corrupt or unavailable state. Lease expiry uses wall-clock time so persisted leases
    have meaningful semantics after a process restart.
    """

    def __init__(
        self,
        root: Union[str, Path],
        *,
        lock_timeout_seconds: float = 5.0,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if not _valid_file_lease_ttl(lock_timeout_seconds):
            raise ValueError("lock_timeout_seconds must be positive and bounded")
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)
        self._lock_timeout_seconds = float(lock_timeout_seconds)
        self._clock = clock
        self._thread_lock = threading.RLock()

    def _paths(self, resource: str) -> Tuple[Path, Path]:
        digest = hashlib.sha256(resource.encode("utf-8")).hexdigest()
        return self._root / (digest + ".json"), self._root / (digest + ".lock")

    def _read_state(
        self, path: Path, resource: str
    ) -> Tuple[int, Optional[str], float]:
        if not path.exists():
            return 0, None, 0.0
        try:
            raw: object = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("durable lease state is unreadable") from exc
        if not isinstance(raw, dict):
            raise ValueError("durable lease state must be an object")
        state = cast(Dict[str, object], raw)
        stored_resource = state.get("resource")
        token = state.get("token")
        holder = state.get("holder")
        expires_at = state.get("expires_at")
        if (
            stored_resource != resource
            or not isinstance(token, int)
            or isinstance(token, bool)
        ):
            raise ValueError("durable lease state identity is invalid")
        if token < 0 or not _valid_file_lease_name(holder) and holder is not None:
            raise ValueError("durable lease state holder is invalid")
        if not isinstance(expires_at, (int, float)) or isinstance(expires_at, bool):
            raise ValueError("durable lease state expiry is invalid")
        if not math.isfinite(float(expires_at)):
            raise ValueError("durable lease state expiry is not finite")
        if holder is not None and not isinstance(holder, str):
            raise ValueError("durable lease state holder is invalid")
        return token, cast(Optional[str], holder), float(expires_at)

    def _write_state(
        self,
        path: Path,
        resource: str,
        token: int,
        holder: Optional[str],
        expires_at: float,
    ) -> None:
        temporary_path: Optional[Path] = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=str(self._root),
                prefix=".maple-lease-",
                suffix=".tmp-" + uuid.uuid4().hex,
                delete=False,
            ) as handle:
                temporary_path = Path(handle.name)
                json.dump(
                    {
                        "expires_at": expires_at,
                        "holder": holder,
                        "resource": resource,
                        "token": token,
                    },
                    handle,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(str(temporary_path), str(path))
            temporary_path = None
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink()
                except OSError:
                    pass

    @contextmanager
    def _locked_resource(self, resource: str) -> Iterator[Tuple[Path, Path]]:
        state_path, lock_path = self._paths(resource)
        with _InterProcessFileLock(lock_path, self._lock_timeout_seconds):
            yield state_path, lock_path

    def acquire(self, resource: str, holder: str, ttl_seconds: float) -> Result:
        """Acquire or same-holder renew a durable, fencing-token lease."""
        if not _valid_file_lease_name(resource) or not _valid_file_lease_name(holder):
            return _file_lease_error(
                "INVALID_RESOURCE_OR_HOLDER",
                "resource and holder must be non-empty bounded strings",
            )
        if not _valid_file_lease_ttl(ttl_seconds):
            return _file_lease_error(
                "INVALID_TTL",
                "ttl_seconds must be positive and bounded",
                {"max_ttl_seconds": _MAX_FILE_LEASE_TTL_SECONDS},
            )
        try:
            with self._thread_lock:
                with self._locked_resource(resource) as (state_path, _):
                    token, current_holder, expires_at = self._read_state(
                        state_path, resource
                    )
                    now = self._clock()
                    active = current_holder is not None and now < expires_at
                    if active and current_holder != holder:
                        return _file_lease_error(
                            "RESOURCE_HELD",
                            f"Resource '{resource}' is held by '{current_holder}'",
                            {
                                "holder": current_holder,
                                "expires_in": max(0.0, expires_at - now),
                            },
                        )
                    next_token = token + 1
                    lease = Lease(
                        resource=resource,
                        holder=holder,
                        token=next_token,
                        expires_at=now + float(ttl_seconds),
                    )
                    self._write_state(
                        state_path,
                        resource,
                        lease.token,
                        lease.holder,
                        lease.expires_at,
                    )
                    return Result.ok(lease)
        except TimeoutError as exc:
            return _file_lease_storage_error("LEASE_LOCK_TIMEOUT", exc)
        except (OSError, TypeError, ValueError) as exc:
            return _file_lease_storage_error("LEASE_STORAGE_ERROR", exc)

    def renew(self, lease: Lease, ttl_seconds: float) -> Result:
        """Extend a live durable lease and issue a new fencing token."""
        if not isinstance(lease, Lease) or not _valid_file_lease_name(lease.resource):
            return _file_lease_error("INVALID_LEASE", "lease is invalid")
        if not _valid_file_lease_ttl(ttl_seconds):
            return _file_lease_error(
                "INVALID_TTL",
                "ttl_seconds must be positive and bounded",
                {"max_ttl_seconds": _MAX_FILE_LEASE_TTL_SECONDS},
            )
        try:
            with self._thread_lock:
                with self._locked_resource(lease.resource) as (state_path, _):
                    token, holder, expires_at = self._read_state(
                        state_path, lease.resource
                    )
                    now = self._clock()
                    if (
                        holder != lease.holder
                        or token != lease.token
                        or now >= expires_at
                    ):
                        return _file_lease_error(
                            "LEASE_LOST",
                            f"Lease on '{lease.resource}' is no longer held",
                            {"resource": lease.resource, "token": lease.token},
                        )
                    renewed = Lease(
                        resource=lease.resource,
                        holder=lease.holder,
                        token=token + 1,
                        expires_at=now + float(ttl_seconds),
                    )
                    self._write_state(
                        state_path,
                        renewed.resource,
                        renewed.token,
                        renewed.holder,
                        renewed.expires_at,
                    )
                    return Result.ok(renewed)
        except TimeoutError as exc:
            return _file_lease_storage_error("LEASE_LOCK_TIMEOUT", exc)
        except (OSError, TypeError, ValueError) as exc:
            return _file_lease_storage_error("LEASE_STORAGE_ERROR", exc)

    def release(self, lease: Lease) -> Result:
        """Release only the exact current durable lease; stale holders are no-ops."""
        if not isinstance(lease, Lease) or not _valid_file_lease_name(lease.resource):
            return _file_lease_error("INVALID_LEASE", "lease is invalid")
        try:
            with self._thread_lock:
                with self._locked_resource(lease.resource) as (state_path, _):
                    token, holder, expires_at = self._read_state(
                        state_path, lease.resource
                    )
                    now = self._clock()
                    if (
                        holder == lease.holder
                        and token == lease.token
                        and now < expires_at
                    ):
                        self._write_state(state_path, lease.resource, token, None, now)
                        return Result.ok(True)
                    return Result.ok(False)
        except TimeoutError as exc:
            return _file_lease_storage_error("LEASE_LOCK_TIMEOUT", exc)
        except (OSError, TypeError, ValueError) as exc:
            return _file_lease_storage_error("LEASE_STORAGE_ERROR", exc)

    def is_valid(self, lease: Lease) -> bool:
        """Return false on any invalid or unavailable state; stale tokens are fenced."""
        if not isinstance(lease, Lease) or not _valid_file_lease_name(lease.resource):
            return False
        try:
            with self._thread_lock:
                with self._locked_resource(lease.resource) as (state_path, _):
                    token, holder, expires_at = self._read_state(
                        state_path, lease.resource
                    )
                    return (
                        holder == lease.holder
                        and token == lease.token
                        and self._clock() < expires_at
                    )
        except (OSError, TypeError, TimeoutError, ValueError):
            return False

    def holder_of(self, resource: str) -> Optional[str]:
        """Return the current holder, or None for free, expired, or unavailable
        state."""
        if not _valid_file_lease_name(resource):
            return None
        try:
            with self._thread_lock:
                with self._locked_resource(resource) as (state_path, _):
                    _, holder, expires_at = self._read_state(state_path, resource)
                    return (
                        holder
                        if holder is not None and self._clock() < expires_at
                        else None
                    )
        except (OSError, TypeError, TimeoutError, ValueError):
            return None

    def is_held(self, resource: str) -> bool:
        """Return true only when a live durable lease is readable and present."""
        return self.holder_of(resource) is not None
