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

# mapl/resources/manager.py

from __future__ import annotations

import logging
import threading
from copy import deepcopy
from typing import Any, Dict, Optional, Union

from ..core.result import Result
from .specification import ResourceRequest

# NOTE: a LIBRARY must not configure the root logger (that hijacks the host's logging
# and emits INFO noise). Use a module logger; the host owns logging config.
logger = logging.getLogger(__name__)


class ResourceLifecycle:
    """How a resource behaves over its life -- decides whether release() refunds it.

    RENEWABLE  -- a reusable pool: an allocation is carved off and RETURNED to
    the pool on
                  release (compute, memory, bandwidth, tokens, gpu, disk).
    CONSUMABLE -- a depletable budget: an allocation is SPENT and never returned
    on release
                  (money/cost, api_calls, energy). Expressing this is the whole point --
                  the previous release() hard-coded a renewable-only refund list, so a
                  consumable budget modelled as an allocation could silently
                  refund itself.
    """

    RENEWABLE = "renewable"
    CONSUMABLE = "consumable"


# Default lifecycle for well-known resource types. Unknown types default to
# RENEWABLE (the
# historical behaviour for the built-in pools). Override per-manager with
# register_resource(resource_type, amount, lifecycle=...).
DEFAULT_LIFECYCLES: Dict[str, str] = {
    "compute": ResourceLifecycle.RENEWABLE,
    "memory": ResourceLifecycle.RENEWABLE,
    "bandwidth": ResourceLifecycle.RENEWABLE,
    "tokens": ResourceLifecycle.RENEWABLE,
    "gpu": ResourceLifecycle.RENEWABLE,
    "disk": ResourceLifecycle.RENEWABLE,
    "money": ResourceLifecycle.CONSUMABLE,
    "cost": ResourceLifecycle.CONSUMABLE,
    "api_calls": ResourceLifecycle.CONSUMABLE,
    "energy": ResourceLifecycle.CONSUMABLE,
}


class ResourceAllocation:
    """
    Represents allocated resources.
    """

    def __init__(self, allocation_id: str, resources: Dict[str, Any]):
        self.allocation_id = allocation_id
        self.resources = resources

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a dictionary."""
        return {"allocation_id": self.allocation_id, "resources": self.resources}


class ResourceManager:
    """
    Manages resource allocation and tracking.
    """

    def __init__(self) -> None:
        self.available_resources: Dict[str, Any] = {}
        self.allocations: Dict[str, ResourceAllocation] = {}
        self._lifecycles: Dict[str, str] = {}
        self._lock = threading.RLock()
        self._allocation_counter = 0

    def register_resource(
        self, resource_type: str, amount: Any, lifecycle: Optional[str] = None
    ) -> None:
        """
        Register available resources.

        Args:
            resource_type: The type of resource.
            amount: The amount of resource available.
            lifecycle: ResourceLifecycle.RENEWABLE (returned on release) or CONSUMABLE
                (spent, never returned). Defaults to DEFAULT_LIFECYCLES for known types,
                else RENEWABLE (the historical behaviour).
        """
        with self._lock:
            self.available_resources[resource_type] = amount
            self._lifecycles[resource_type] = lifecycle or DEFAULT_LIFECYCLES.get(
                resource_type, ResourceLifecycle.RENEWABLE
            )
            logger.info(
                f"Registered {amount} of {resource_type} "
                f"({self._lifecycles[resource_type]})"
            )

    def lifecycle_of(self, resource_type: str) -> str:
        """Return the lifecycle class for a resource type (defaults to RENEWABLE)."""
        return self._lifecycles.get(
            resource_type,
            DEFAULT_LIFECYCLES.get(resource_type, ResourceLifecycle.RENEWABLE),
        )

    @staticmethod
    def _as_number(value: Any) -> float:
        """Coerce a numeric resource value to float for comparison/arithmetic.

        Accepts int/float and numeric or size strings ('10GB' -> bytes) so a custom
        dimension can carry a size; plain numbers are the expected common case.
        """
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(value)
        except (TypeError, ValueError):
            from ..core.types import Size

            return float(Size.parse(value))

    @staticmethod
    def _as_size_number(value: Any) -> Union[int, float]:
        """Return a numeric size while preserving integer/float inputs."""
        if isinstance(value, (int, float)):
            return value
        from ..core.types import Size

        return Size.parse(value)

    def get_available_resources(self) -> Dict[str, Any]:
        """
        Get the currently available resources.

        Returns:
            A dictionary of available resources.
        """
        with self._lock:
            return deepcopy(self.available_resources)

    def get_allocation(self, allocation_id: str) -> Optional[ResourceAllocation]:
        """Return a tracked allocation by ID, or ``None`` when it is unknown."""
        with self._lock:
            return self.allocations.get(allocation_id)

    def allocate(
        self, request: Union[ResourceRequest, Dict[str, Any]]
    ) -> Result[ResourceAllocation, Dict[str, Any]]:
        """
        Allocate resources based on a request.

        Args:
            request: The resource request.

        Returns:
            A Result containing either the allocation or an error.
        """
        # Convert dictionary to ResourceRequest if needed
        if isinstance(request, dict):
            request = ResourceRequest.from_dict(request)

        with self._lock:
            # Check if we can satisfy the request
            satisfied, shortfall = self._can_satisfy(request)

            if not satisfied:
                return Result.err(
                    {
                        "errorType": "RESOURCE_UNAVAILABLE",
                        "message": "Insufficient resources to satisfy request",
                        "details": {"shortfall": shortfall},
                    }
                )

            # Create an allocation ID
            self._allocation_counter += 1
            allocation_id = f"alloc_{self._allocation_counter}"

            # Allocate the resources
            allocation = self._allocate_resources(allocation_id, request)

            logger.info(f"Allocated resources: {allocation.resources}")
            return Result.ok(allocation)

    def release(self, allocation: ResourceAllocation) -> None:
        """
        Release allocated resources.

        Args:
            allocation: The resource allocation to release.
        """
        with self._lock:
            if allocation.allocation_id in self.allocations:
                # Return each RENEWABLE resource to the pool. CONSUMABLE budgets (money,
                # api_calls, energy) are spent and stay spent -- they are NOT refunded.
                # (Previously this was a hard-coded compute/memory/bandwidth/
                # tokens list,
                # which could not model a consumable budget and could not extend to new
                # renewable dimensions like gpu/disk.)
                for resource_type, amount in self.allocations[
                    allocation.allocation_id
                ].resources.items():
                    if self.lifecycle_of(resource_type) != ResourceLifecycle.RENEWABLE:
                        continue
                    if resource_type in self.available_resources:
                        self.available_resources[resource_type] += amount

                # Remove the allocation
                del self.allocations[allocation.allocation_id]
                logger.info(f"Released allocation {allocation.allocation_id}")

    def _can_satisfy(self, request: ResourceRequest) -> tuple[bool, Dict[str, Any]]:
        """
        Check if a request can be satisfied with available resources.

        Args:
            request: The resource request.

        Returns:
            A tuple of (can_satisfy, shortfall).
        """
        shortfall = {}

        # Check compute
        if request.compute and "compute" in self.available_resources:
            if request.compute.min > self.available_resources["compute"]:
                shortfall["compute"] = {
                    "requested": request.compute.min,
                    "available": self.available_resources["compute"],
                }

        # Check memory
        if request.memory and "memory" in self.available_resources:
            from ..core.types import Size

            requested = (
                Size.parse(request.memory.min)
                if isinstance(request.memory.min, str)
                else request.memory.min
            )
            available = (
                Size.parse(self.available_resources["memory"])
                if isinstance(self.available_resources["memory"], str)
                else self.available_resources["memory"]
            )

            if requested > available:
                shortfall["memory"] = {
                    "requested": request.memory.min,
                    "available": self.available_resources["memory"],
                }

        # Check bandwidth
        if request.bandwidth and "bandwidth" in self.available_resources:
            # Similar to memory, parsing might be needed
            # This is a simplified check
            if request.bandwidth.min > self.available_resources["bandwidth"]:
                shortfall["bandwidth"] = {
                    "requested": request.bandwidth.min,
                    "available": self.available_resources["bandwidth"],
                }

        # Check tokens (LLM budget — plain integer count, like compute)
        if request.tokens and "tokens" in self.available_resources:
            if request.tokens.min > self.available_resources["tokens"]:
                shortfall["tokens"] = {
                    "requested": request.tokens.min,
                    "available": self.available_resources["tokens"],
                }

        # Check custom / arbitrary named numeric resources (gpu, disk, money, ...). Only
        # registered dimensions are enforced; an unregistered custom name is ignored
        # (mirrors the built-in fields, which no-op when their resource type is absent).
        if request.custom:
            for name, rng in request.custom.items():
                if name in self.available_resources:
                    if self._as_number(rng.min) > self._as_number(
                        self.available_resources[name]
                    ):
                        shortfall[name] = {
                            "requested": rng.min,
                            "available": self.available_resources[name],
                        }

        # Return whether there's any shortfall
        return len(shortfall) == 0, shortfall

    def _allocate_resources(
        self, allocation_id: str, request: ResourceRequest
    ) -> ResourceAllocation:
        """
        Allocate resources for a request.

        Args:
            allocation_id: The allocation ID.
            request: The resource request.

        Returns:
            A ResourceAllocation object.
        """
        resources = {}

        # Allocate compute
        if request.compute and "compute" in self.available_resources:
            # Try to allocate preferred, but fall back to minimum
            amount = min(request.compute.preferred, self.available_resources["compute"])
            amount = max(amount, request.compute.min)  # But ensure at least minimum

            self.available_resources["compute"] -= amount
            resources["compute"] = amount

        # Allocate memory
        if request.memory and "memory" in self.available_resources:
            preferred = self._as_size_number(request.memory.preferred)
            available = self._as_size_number(self.available_resources["memory"])
            minimum = self._as_size_number(request.memory.min)

            amount = min(preferred, available)
            amount = max(amount, minimum)  # But ensure at least minimum

            self.available_resources["memory"] = available - amount
            resources["memory"] = amount

        # Allocate bandwidth
        if request.bandwidth and "bandwidth" in self.available_resources:
            # Similar to memory
            amount = min(
                request.bandwidth.preferred, self.available_resources["bandwidth"]
            )
            amount = max(amount, request.bandwidth.min)  # But ensure at least minimum

            self.available_resources["bandwidth"] -= amount
            resources["bandwidth"] = amount

        # Allocate tokens (LLM budget — plain integer count, like compute)
        if request.tokens and "tokens" in self.available_resources:
            amount = min(request.tokens.preferred, self.available_resources["tokens"])
            amount = max(amount, request.tokens.min)  # But ensure at least minimum

            self.available_resources["tokens"] -= amount
            resources["tokens"] = amount

        # Allocate custom / arbitrary named numeric resources. _can_satisfy() has
        # already
        # guaranteed min <= available for every registered custom dimension, so the
        # carved amount stays within [min, available] (never drives the pool negative).
        if request.custom:
            for name, rng in request.custom.items():
                if name in self.available_resources:
                    available = self._as_number(self.available_resources[name])
                    amount = min(self._as_number(rng.preferred), available)
                    amount = max(
                        amount, self._as_number(rng.min)
                    )  # ensure at least minimum
                    self.available_resources[name] = available - amount
                    resources[name] = amount

        # Create and store the allocation
        allocation = ResourceAllocation(allocation_id, resources)
        self.allocations[allocation_id] = allocation

        return allocation
