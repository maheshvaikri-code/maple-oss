"""
Copyright (C) 2025 Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

This file is part of MAPLE - Multi Agent Protocol Language Engine.

MAPLE - Multi Agent Protocol Language Engine is free software: you can redistribute it and/or
modify it under the terms of the GNU Affero General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later version.
MAPLE - Multi Agent Protocol Language Engine is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE. See the GNU Affero General Public License for more details. You should have
received a copy of the GNU Affero General Public License along with MAPLE - Multi Agent Protocol
Language Engine. If not, see <https://www.gnu.org/licenses/>.
"""

# maple/resources/lease.py
# Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)
#
# Exclusive resource leases -- the "one holder at a time" negotiation semantic that the
# renewable-pool ResourceManager cannot express: a named lock, a physical device (camera,
# robot arm, serial port), a floating license seat, or a singleton "leader"/"writer" role.
#
# A lease is time-boxed (TTL) so a crashed or slow holder cannot deadlock the resource --
# expiry IS the preemption mechanism, no explicit revoke needed. Each grant carries a
# monotonically increasing per-resource FENCING TOKEN: the holder presents it to the guarded
# resource, so a stale holder that resumes after its lease expired and was re-granted to
# someone else is detectably out of date (is_valid() -> False) and will not act on a
# resource another agent now owns. This is the standard fencing-token pattern.

import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, Optional

from ..core.result import Result


@dataclass
class Lease:
    """An exclusive hold on a named resource.

    Attributes:
        resource: The leased resource name.
        holder: The agent id holding it.
        token: Per-resource, monotonically increasing fencing token. The holder passes it
            to the guarded resource; a delayed/stale holder (whose lease has since expired
            and been re-granted) presents an older token and is rejected.
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

    Thread-safe. A lease held by a crashed/slow holder becomes acquirable by another holder
    once its TTL elapses (implicit preemption) -- there is deliberately no force-revoke.
    """

    def __init__(self, clock: Callable[[], float] = time.monotonic):
        # clock is injectable so tests are deterministic (advance a fake clock, no sleeping).
        self._clock = clock
        self._leases: Dict[str, Lease] = {}
        self._counters: Dict[str, int] = {}
        self._lock = threading.RLock()

    def _active(self, resource: str, now: float) -> Optional[Lease]:
        """Return the current non-expired lease for `resource`, pruning it if expired."""
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

        Returns Result.ok(Lease) if granted, or Result.err with the current holder and the
        time remaining if another agent holds a live lease.
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
                        "message": f"Resource '{resource}' is held by '{current.holder}'",
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
        """Extend a lease the caller still holds. Fails if it was lost (expired/preempted)."""
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

        Returns Result.ok(True) if the caller was the current holder, or Result.ok(False)
        if the lease had already expired or been preempted (an idempotent no-op -- a stale
        holder cannot release a resource another agent now holds).
        """
        with self._lock:
            now = self._clock()
            current = self._active(lease.resource, now)
            if current is not None and current.token == lease.token:
                del self._leases[lease.resource]
                return Result.ok(True)
            return Result.ok(False)

    def is_valid(self, lease: Lease) -> bool:
        """True iff this exact lease (by fencing token) is still the active, unexpired hold.

        A holder calls this immediately before acting on the guarded resource -- the fence.
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
