"""
Copyright (C) 2025 Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

This file is part of MAPLE - Multi Agent Protocol Language Engine.

MAPLE - Multi Agent Protocol Language Engine is free software: you can
redistribute it and/or modify it under the terms of the GNU Affero General
Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later version.
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import math
import os
import re
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    Union,
)

from ..core.result import Result
from .replay import ExecutionJournal, ExecutionRecord

# Small, dependency-free workflow runtime for MAPLE agent applications.


END = "__end__"
_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_STATUSES = {"running", "interrupted", "completed", "failed"}
_MAX_PARALLEL_BRANCHES = 64

Error = Dict[str, Any]
NodeOutput = Union[Mapping[str, Any], Result[Optional[Mapping[str, Any]], Error], None]
NodeHandler = Callable[["WorkflowContext"], NodeOutput]
RouteSelector = Callable[[Mapping[str, Any]], str]


def _error(error_type: str, message: str, **details: Any) -> Error:
    """Build the stable error shape used by the workflow boundary."""
    result: Error = {"errorType": error_type, "message": message}
    if details:
        result["details"] = details
    return result


def _valid_identifier(value: str, field_name: str) -> Optional[Error]:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        return _error(
            "INVALID_IDENTIFIER",
            f"{field_name} must contain 1-128 letters, numbers, '_', '.', ':', or '-'.",
            field=field_name,
        )
    return None


def _validate_json_value(
    value: Any,
    *,
    path: str = "$",
    depth: int = 0,
    max_depth: int = 16,
    max_items: int = 10_000,
) -> Optional[Error]:
    """Validate checkpoint data before it crosses a persistence boundary."""
    if depth > max_depth:
        return _error(
            "STATE_DEPTH_EXCEEDED", "Workflow state nesting is too deep.", path=path
        )

    if value is None or isinstance(value, (bool, int, str)):
        return None
    if isinstance(value, float):
        if not math.isfinite(value):
            return _error(
                "INVALID_STATE_VALUE",
                "Workflow state contains a non-finite number.",
                path=path,
            )
        return None
    if isinstance(value, list):
        if len(value) > max_items:
            return _error(
                "STATE_SIZE_EXCEEDED", "Workflow state list is too large.", path=path
            )
        for index, item in enumerate(value):
            error = _validate_json_value(
                item,
                path=f"{path}[{index}]",
                depth=depth + 1,
                max_depth=max_depth,
                max_items=max_items,
            )
            if error:
                return error
        return None
    if isinstance(value, dict):
        if len(value) > max_items:
            return _error(
                "STATE_SIZE_EXCEEDED", "Workflow state object is too large.", path=path
            )
        for key, item in value.items():
            if not isinstance(key, str):
                return _error(
                    "INVALID_STATE_KEY",
                    "Workflow state keys must be strings.",
                    path=path,
                )
            if len(key) > 256:
                return _error(
                    "STATE_KEY_TOO_LONG", "Workflow state key is too long.", path=path
                )
            error = _validate_json_value(
                item,
                path=f"{path}.{key}",
                depth=depth + 1,
                max_depth=max_depth,
                max_items=max_items,
            )
            if error:
                return error
        return None

    return _error(
        "INVALID_STATE_VALUE",
        "Workflow state must contain only JSON-compatible values.",
        path=path,
        value_type=type(value).__name__,
    )


def _copy_json(value: Any, *, max_state_bytes: int) -> Result[Any, Error]:
    error = _validate_json_value(value)
    if error:
        return Result.err(error)
    try:
        encoded = json.dumps(
            value, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        )
        if len(encoded.encode("utf-8")) > max_state_bytes:
            return Result.err(
                _error(
                    "STATE_SIZE_EXCEEDED",
                    "Workflow state exceeds the configured byte limit.",
                    max_state_bytes=max_state_bytes,
                )
            )
        return Result.ok(json.loads(encoded))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        return Result.err(
            _error(
                "INVALID_STATE_VALUE",
                "Workflow state is not JSON serializable.",
                reason=str(exc)[:256],
            )
        )


@dataclass
class WorkflowContext:
    """Read-only workflow invocation context passed to a node handler."""

    state: Mapping[str, Any]
    run_id: str
    node_name: str
    resume_value: Any = None
    execution_key: Optional[str] = None


class WorkflowPause(Exception):
    """Request a durable pause before the current node commits its output."""

    def __init__(self, payload: Any):
        super().__init__("Workflow execution paused for external input.")
        self.payload = payload


@dataclass
class WorkflowCheckpoint:
    """JSON-safe snapshot of a workflow run at a node boundary."""

    run_id: str
    workflow_name: str
    state: Dict[str, Any]
    completed_nodes: List[str]
    next_node: Optional[str]
    status: str
    step_count: int = 0
    version: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    interrupt_payload: Any = None
    error: Optional[Error] = None

    def to_dict(self) -> Dict[str, Any]:
        """Return the persistence representation."""
        return {
            "run_id": self.run_id,
            "workflow_name": self.workflow_name,
            "state": self.state,
            "completed_nodes": self.completed_nodes,
            "next_node": self.next_node,
            "status": self.status,
            "step_count": self.step_count,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "interrupt_payload": self.interrupt_payload,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "WorkflowCheckpoint":
        """Parse a checkpoint without executing or deserializing code."""
        if not isinstance(data, Mapping):
            raise ValueError("checkpoint must be an object")
        required = ("run_id", "workflow_name", "state", "completed_nodes", "status")
        if any(key not in data for key in required):
            raise ValueError("checkpoint is missing a required field")
        if _valid_identifier(data["run_id"], "run_id"):
            raise ValueError("invalid checkpoint run_id")
        if _valid_identifier(data["workflow_name"], "workflow_name"):
            raise ValueError("invalid checkpoint workflow_name")
        if data["status"] not in _STATUSES:
            raise ValueError("invalid checkpoint status")
        if not isinstance(data["state"], dict):
            raise ValueError("checkpoint state must be an object")
        if not isinstance(data["completed_nodes"], list) or not all(
            isinstance(item, str) for item in data["completed_nodes"]
        ):
            raise ValueError("checkpoint completed_nodes must be a list of strings")
        next_node = data.get("next_node")
        if next_node is not None and (
            not isinstance(next_node, str) or next_node == END
        ):
            raise ValueError("invalid checkpoint next_node")
        step_count = data.get("step_count", 0)
        version = data.get("version", 0)
        if not isinstance(step_count, int) or step_count < 0:
            raise ValueError("invalid checkpoint step_count")
        if not isinstance(version, int) or version < 0:
            raise ValueError("invalid checkpoint version")
        error = data.get("error")
        if error is not None and not isinstance(error, dict):
            raise ValueError("checkpoint error must be an object or null")
        state_error = _validate_json_value(data["state"])
        if state_error:
            raise ValueError(state_error["message"])
        payload_error = _validate_json_value(data.get("interrupt_payload"))
        if payload_error:
            raise ValueError(payload_error["message"])
        error_value_error = _validate_json_value(error)
        if error_value_error:
            raise ValueError(error_value_error["message"])
        return cls(
            run_id=data["run_id"],
            workflow_name=data["workflow_name"],
            state=dict(data["state"]),
            completed_nodes=list(data["completed_nodes"]),
            next_node=next_node,
            status=data["status"],
            step_count=step_count,
            version=version,
            created_at=float(data.get("created_at", time.time())),
            updated_at=float(data.get("updated_at", time.time())),
            interrupt_payload=data.get("interrupt_payload"),
            error=error,
        )


@dataclass
class WorkflowRun:
    """Public view of a workflow run."""

    run_id: str
    workflow_name: str
    status: str
    state: Dict[str, Any]
    completed_nodes: List[str]
    next_node: Optional[str]
    checkpoint_version: int
    step_count: int
    interrupt_payload: Any = None
    error: Optional[Error] = None

    @classmethod
    def from_checkpoint(cls, checkpoint: WorkflowCheckpoint) -> "WorkflowRun":
        return cls(
            run_id=checkpoint.run_id,
            workflow_name=checkpoint.workflow_name,
            status=checkpoint.status,
            state=dict(checkpoint.state),
            completed_nodes=list(checkpoint.completed_nodes),
            next_node=checkpoint.next_node,
            checkpoint_version=checkpoint.version,
            step_count=checkpoint.step_count,
            interrupt_payload=checkpoint.interrupt_payload,
            error=checkpoint.error,
        )


class CheckpointStore(Protocol):
    """Persistence contract for workflow checkpoints."""

    def load(self, run_id: str) -> Result[Optional[WorkflowCheckpoint], Error]: ...

    def save(
        self,
        checkpoint: WorkflowCheckpoint,
        expected_version: Optional[int] = None,
    ) -> Result[WorkflowCheckpoint, Error]: ...


class InMemoryCheckpointStore:
    """Thread-safe reference checkpoint store for tests and local runs."""

    def __init__(self) -> None:
        self._checkpoints: Dict[str, WorkflowCheckpoint] = {}
        self._lock = threading.RLock()

    def load(self, run_id: str) -> Result[Optional[WorkflowCheckpoint], Error]:
        with self._lock:
            checkpoint = self._checkpoints.get(run_id)
            if checkpoint is None:
                return Result.ok(None)
            return Result.ok(WorkflowCheckpoint.from_dict(checkpoint.to_dict()))

    def save(
        self,
        checkpoint: WorkflowCheckpoint,
        expected_version: Optional[int] = None,
    ) -> Result[WorkflowCheckpoint, Error]:
        with self._lock:
            existing = self._checkpoints.get(checkpoint.run_id)
            if existing is None:
                if expected_version is not None:
                    return Result.err(
                        _error("CHECKPOINT_CONFLICT", "Checkpoint does not exist.")
                    )
                version = 1
            else:
                if expected_version != existing.version:
                    return Result.err(
                        _error(
                            "CHECKPOINT_CONFLICT",
                            "Checkpoint version does not match.",
                            run_id=checkpoint.run_id,
                            expected_version=expected_version,
                            actual_version=existing.version,
                        )
                    )
                version = existing.version + 1
            candidate = replace(
                WorkflowCheckpoint.from_dict(checkpoint.to_dict()),
                version=version,
                updated_at=time.time(),
            )
            self._checkpoints[checkpoint.run_id] = candidate
            return Result.ok(WorkflowCheckpoint.from_dict(candidate.to_dict()))


class FileCheckpointStore:
    """Atomic JSON-file checkpoint store for local process-restart recovery.

    The store is thread-safe within one process. Cross-process coordination is
    intentionally deferred until a backend with an explicit lease/CAS contract
    is selected.
    """

    def __init__(
        self, directory: Union[str, Path], max_checkpoint_bytes: int = 1_048_576
    ) -> None:
        if max_checkpoint_bytes <= 0:
            raise ValueError("max_checkpoint_bytes must be positive")
        self.directory = Path(directory).expanduser().resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.max_checkpoint_bytes = max_checkpoint_bytes
        self._lock = threading.RLock()

    def _path(self, run_id: str) -> Path:
        identifier_error = _valid_identifier(run_id, "run_id")
        if identifier_error:
            raise ValueError(identifier_error["message"])
        path = (self.directory / f"{run_id}.json").resolve()
        if self.directory not in path.parents:
            raise ValueError("checkpoint path escapes the configured directory")
        return path

    def _read_unlocked(self, run_id: str) -> Optional[WorkflowCheckpoint]:
        path = self._path(run_id)
        if not path.exists():
            return None
        if path.stat().st_size > self.max_checkpoint_bytes:
            raise ValueError("checkpoint exceeds configured size limit")
        with path.open("r", encoding="utf-8") as handle:
            return WorkflowCheckpoint.from_dict(json.load(handle))

    def load(self, run_id: str) -> Result[Optional[WorkflowCheckpoint], Error]:
        try:
            with self._lock:
                return Result.ok(self._read_unlocked(run_id))
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            return Result.err(
                _error(
                    "CHECKPOINT_LOAD_ERROR",
                    "Failed to load workflow checkpoint.",
                    reason=str(exc)[:256],
                )
            )

    def save(
        self,
        checkpoint: WorkflowCheckpoint,
        expected_version: Optional[int] = None,
    ) -> Result[WorkflowCheckpoint, Error]:
        try:
            with self._lock:
                existing = self._read_unlocked(checkpoint.run_id)
                if existing is None:
                    if expected_version is not None:
                        return Result.err(
                            _error("CHECKPOINT_CONFLICT", "Checkpoint does not exist.")
                        )
                    version = 1
                else:
                    if expected_version != existing.version:
                        return Result.err(
                            _error(
                                "CHECKPOINT_CONFLICT",
                                "Checkpoint version does not match.",
                                run_id=checkpoint.run_id,
                                expected_version=expected_version,
                                actual_version=existing.version,
                            )
                        )
                    version = existing.version + 1
                candidate = replace(
                    WorkflowCheckpoint.from_dict(checkpoint.to_dict()),
                    version=version,
                    updated_at=time.time(),
                )
                payload = json.dumps(
                    candidate.to_dict(), ensure_ascii=False, allow_nan=False, indent=2
                )
                if len(payload.encode("utf-8")) > self.max_checkpoint_bytes:
                    return Result.err(
                        _error(
                            "CHECKPOINT_SIZE_EXCEEDED",
                            "Workflow checkpoint exceeds the configured byte limit.",
                            max_checkpoint_bytes=self.max_checkpoint_bytes,
                        )
                    )
                temporary_path: Optional[Path] = None
                try:
                    with tempfile.NamedTemporaryFile(
                        mode="w",
                        encoding="utf-8",
                        dir=str(self.directory),
                        prefix=f".{checkpoint.run_id}.",
                        suffix=".tmp",
                        delete=False,
                    ) as handle:
                        temporary_path = Path(handle.name)
                        handle.write(payload)
                        handle.flush()
                        os.fsync(handle.fileno())
                    os.replace(str(temporary_path), str(self._path(checkpoint.run_id)))
                    temporary_path = None
                finally:
                    if temporary_path is not None:
                        try:
                            temporary_path.unlink()
                        except OSError:
                            pass
                return Result.ok(WorkflowCheckpoint.from_dict(candidate.to_dict()))
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            return Result.err(
                _error(
                    "CHECKPOINT_SAVE_ERROR",
                    "Failed to save workflow checkpoint.",
                    reason=str(exc)[:256],
                )
            )


class HistoryCheckpointStore:
    """Bounded in-process checkpoint history decorator.

    The wrapped store remains the source of truth for recovery. History is an
    immutable inspection log for the current process and does not replay node
    handlers or claim cross-process durability.
    """

    def __init__(self, store: CheckpointStore, *, max_history: int = 100) -> None:
        if not 0 < max_history <= 10_000:
            raise ValueError("max_history must be between 1 and 10000")
        self.store = store
        self.max_history = max_history
        self._history: Dict[str, List[WorkflowCheckpoint]] = {}
        self._lock = threading.RLock()

    def load(self, run_id: str) -> Result[Optional[WorkflowCheckpoint], Error]:
        return self.store.load(run_id)

    def save(
        self,
        checkpoint: WorkflowCheckpoint,
        expected_version: Optional[int] = None,
    ) -> Result[WorkflowCheckpoint, Error]:
        saved_result = self.store.save(checkpoint, expected_version=expected_version)
        if saved_result.is_err():
            return Result.err(saved_result.unwrap_err())
        saved = saved_result.unwrap()
        with self._lock:
            snapshots = self._history.setdefault(saved.run_id, [])
            snapshots.append(WorkflowCheckpoint.from_dict(saved.to_dict()))
            if len(snapshots) > self.max_history:
                del snapshots[: len(snapshots) - self.max_history]
        return Result.ok(saved)

    def history(
        self, run_id: str, *, limit: Optional[int] = None
    ) -> Result[List[WorkflowCheckpoint], Error]:
        identifier_error = _valid_identifier(run_id, "run_id")
        if identifier_error:
            return Result.err(identifier_error)
        effective_limit = self.max_history if limit is None else limit
        if (
            not isinstance(effective_limit, int)
            or isinstance(effective_limit, bool)
            or not 0 < effective_limit <= self.max_history
        ):
            return Result.err(
                _error(
                    "HISTORY_LIMIT_INVALID",
                    "History limit is outside the configured range.",
                    max_history=self.max_history,
                )
            )
        with self._lock:
            snapshots = self._history.get(run_id, [])
            if snapshots:
                selected = snapshots[-effective_limit:]
                return Result.ok(
                    [WorkflowCheckpoint.from_dict(item.to_dict()) for item in selected]
                )
        loaded_result = self.store.load(run_id)
        if loaded_result.is_err():
            return Result.err(loaded_result.unwrap_err())
        current = loaded_result.unwrap()
        if current is None:
            return Result.ok([])
        return Result.ok([WorkflowCheckpoint.from_dict(current.to_dict())])


class Workflow:
    """Validated workflow with durable node-boundary checkpoints.

    Ordinary edges execute sequentially. ``add_fan_out`` adds one bounded
    thread-based fan-out/fan-in group whose branch outputs are merged in the
    declaration order and committed as one checkpoint before the join node.
    """

    def __init__(
        self,
        name: str,
        *,
        max_steps: int = 100,
        max_state_bytes: int = 1_048_576,
        max_parallel_branches: int = 8,
        checkpoint_store: Optional[CheckpointStore] = None,
        execution_journal: Optional[ExecutionJournal] = None,
    ) -> None:
        identifier_error = _valid_identifier(name, "workflow_name")
        if identifier_error:
            raise ValueError(identifier_error["message"])
        if max_steps <= 0 or max_steps > 100_000:
            raise ValueError("max_steps must be between 1 and 100000")
        if max_state_bytes <= 0:
            raise ValueError("max_state_bytes must be positive")
        if not 0 < max_parallel_branches <= _MAX_PARALLEL_BRANCHES:
            raise ValueError(
                f"max_parallel_branches must be between 1 and {_MAX_PARALLEL_BRANCHES}"
            )
        self.name = name
        self.max_steps = max_steps
        self.max_state_bytes = max_state_bytes
        self.max_parallel_branches = max_parallel_branches
        self.checkpoint_store: CheckpointStore = (
            checkpoint_store or InMemoryCheckpointStore()
        )
        self.execution_journal = execution_journal
        self._nodes: Dict[str, NodeHandler] = {}
        self._direct_edges: Dict[str, Optional[str]] = {}
        self._conditional_edges: Dict[str, Dict[str, Optional[str]]] = {}
        self._routers: Dict[str, RouteSelector] = {}
        self._parallel_edges: Dict[str, Tuple[Tuple[str, ...], str]] = {}
        self._entry_point: Optional[str] = None

    def add_node(self, name: str, handler: NodeHandler) -> Result[None, Error]:
        """Register a node handler."""
        identifier_error = _valid_identifier(name, "node_name")
        if identifier_error:
            return Result.err(identifier_error)
        if name == END:
            return Result.err(_error("INVALID_NODE", f"{END} is reserved."))
        if not callable(handler):
            return Result.err(
                _error("INVALID_NODE", "Node handler must be callable.", node=name)
            )
        if name in self._nodes:
            return Result.err(
                _error(
                    "DUPLICATE_NODE", f'Node "{name}" is already registered.', node=name
                )
            )
        self._nodes[name] = handler
        return Result.ok(None)

    def set_entry_point(self, name: str) -> Result[None, Error]:
        """Set the first node executed by the workflow."""
        identifier_error = _valid_identifier(name, "node_name")
        if identifier_error:
            return Result.err(identifier_error)
        self._entry_point = name
        return Result.ok(None)

    def add_edge(
        self, source: str, target: Optional[str] = None
    ) -> Result[None, Error]:
        """Add one unconditional edge; ``None`` marks a terminal node."""
        source_error = _valid_identifier(source, "source_node")
        if source_error:
            return Result.err(source_error)
        target_error = self._validate_target(target)
        if target_error:
            return Result.err(target_error)
        if (
            source in self._direct_edges
            or source in self._conditional_edges
            or source in self._parallel_edges
        ):
            return Result.err(
                _error(
                    "DUPLICATE_EDGE",
                    f'Node "{source}" already has routing.',
                    node=source,
                )
            )
        self._direct_edges[source] = target
        return Result.ok(None)

    def add_conditional_edges(
        self,
        source: str,
        selector: RouteSelector,
        routes: Mapping[str, Optional[str]],
    ) -> Result[None, Error]:
        """Route from a node using a bounded, named selector result."""
        source_error = _valid_identifier(source, "source_node")
        if source_error:
            return Result.err(source_error)
        if not callable(selector) or not routes:
            return Result.err(
                _error(
                    "INVALID_ROUTING", "Selector and routes are required.", node=source
                )
            )
        if (
            source in self._direct_edges
            or source in self._conditional_edges
            or source in self._parallel_edges
        ):
            return Result.err(
                _error(
                    "DUPLICATE_EDGE",
                    f'Node "{source}" already has routing.',
                    node=source,
                )
            )
        normalized_routes: Dict[str, Optional[str]] = {}
        for route, target in routes.items():
            route_error = _valid_identifier(route, "route_name")
            if route_error:
                return Result.err(route_error)
            target_error = self._validate_target(target)
            if target_error:
                return Result.err(target_error)
            normalized_routes[route] = target
        self._conditional_edges[source] = normalized_routes
        self._routers[source] = selector
        return Result.ok(None)

    def add_fan_out(
        self, source: str, branches: Sequence[str], join: str
    ) -> Result[None, Error]:
        """Run branch nodes concurrently, then continue at ``join``.

        Branch handlers receive independent snapshots of the state produced by
        ``source``. Their mapping outputs must use distinct keys; the merged
        output is committed atomically at the fan-in boundary. Branches are
        ordered for deterministic state merging and checkpoint history even
        though their handlers execute concurrently.
        """
        source_error = _valid_identifier(source, "source_node")
        if source_error:
            return Result.err(source_error)
        join_error = _valid_identifier(join, "join_node")
        if join_error:
            return Result.err(join_error)
        if source == join:
            return Result.err(
                _error("INVALID_PARALLEL_GRAPH", "Source and join nodes must differ.")
            )
        if isinstance(branches, (str, bytes)):
            return Result.err(
                _error(
                    "INVALID_PARALLEL_GRAPH",
                    "Branches must be a sequence of nodes.",
                )
            )
        try:
            normalized_branches = tuple(branches)
        except TypeError:
            return Result.err(
                _error(
                    "INVALID_PARALLEL_GRAPH",
                    "Branches must be a sequence of nodes.",
                )
            )
        if not normalized_branches:
            return Result.err(
                _error("INVALID_PARALLEL_GRAPH", "At least one branch is required.")
            )
        if len(normalized_branches) > self.max_parallel_branches:
            return Result.err(
                _error(
                    "PARALLELISM_EXCEEDED",
                    "Fan-out exceeds the configured branch limit.",
                    max_parallel_branches=self.max_parallel_branches,
                )
            )
        for branch in normalized_branches:
            if not isinstance(branch, str):
                return Result.err(
                    _error("INVALID_IDENTIFIER", "branch_node must be a string.")
                )
        if len(set(normalized_branches)) != len(normalized_branches):
            return Result.err(
                _error("DUPLICATE_BRANCH", "Fan-out branches must be unique.")
            )
        for branch in normalized_branches:
            branch_error = _valid_identifier(branch, "branch_node")
            if branch_error:
                return Result.err(branch_error)
            if branch in {source, join}:
                return Result.err(
                    _error(
                        "INVALID_PARALLEL_GRAPH",
                        "Source and join nodes cannot also be fan-out branches.",
                        node=branch,
                    )
                )
        if source in self._direct_edges or source in self._conditional_edges:
            return Result.err(
                _error(
                    "DUPLICATE_EDGE",
                    f'Node "{source}" already has routing.',
                    node=source,
                )
            )
        if source in self._parallel_edges:
            return Result.err(
                _error(
                    "DUPLICATE_EDGE",
                    f'Node "{source}" already has routing.',
                    node=source,
                )
            )
        self._parallel_edges[source] = (normalized_branches, join)
        return Result.ok(None)

    def validate(self) -> Result[None, Error]:
        """Validate graph structure before accepting a run."""
        if not self._nodes:
            return Result.err(
                _error("INVALID_WORKFLOW", "Workflow must contain at least one node.")
            )
        if self._entry_point not in self._nodes:
            return Result.err(
                _error("INVALID_WORKFLOW", "Workflow entry point is not registered.")
            )
        for source, target in self._direct_edges.items():
            if source not in self._nodes:
                return Result.err(
                    _error(
                        "INVALID_WORKFLOW",
                        "Edge source is not registered.",
                        node=source,
                    )
                )
            target_error = self._validate_target(target)
            if target_error:
                return Result.err(target_error)
        for source, routes in self._conditional_edges.items():
            if source not in self._nodes or source not in self._routers:
                return Result.err(
                    _error(
                        "INVALID_WORKFLOW",
                        "Conditional source is not registered.",
                        node=source,
                    )
                )
            for target in routes.values():
                target_error = self._validate_target(target)
                if target_error:
                    return Result.err(target_error)

        parallel_branches: Dict[str, str] = {}
        for source, (branches, join) in self._parallel_edges.items():
            if source not in self._nodes:
                return Result.err(
                    _error(
                        "INVALID_WORKFLOW",
                        "Fan-out source is not registered.",
                        node=source,
                    )
                )
            if source in self._direct_edges or source in self._conditional_edges:
                return Result.err(
                    _error(
                        "INVALID_WORKFLOW",
                        "Fan-out source cannot also have ordinary routing.",
                        node=source,
                    )
                )
            if join not in self._nodes:
                return Result.err(
                    _error(
                        "INVALID_WORKFLOW",
                        "Fan-in join node is not registered.",
                        node=join,
                    )
                )
            for branch in branches:
                if branch not in self._nodes:
                    return Result.err(
                        _error(
                            "INVALID_WORKFLOW",
                            "Fan-out branch node is not registered.",
                            node=branch,
                        )
                    )
                if branch in self._direct_edges or branch in self._conditional_edges:
                    return Result.err(
                        _error(
                            "INVALID_WORKFLOW",
                            "Fan-out branches cannot define ordinary routing.",
                            node=branch,
                        )
                    )
                previous_source = parallel_branches.get(branch)
                if previous_source is not None:
                    return Result.err(
                        _error(
                            "INVALID_WORKFLOW",
                            "A node cannot belong to multiple fan-out groups.",
                            node=branch,
                            first_source=previous_source,
                            second_source=source,
                        )
                    )
                parallel_branches[branch] = source

        ordinary_targets = set(self._direct_edges.values())
        ordinary_targets.discard(None)
        for routes in self._conditional_edges.values():
            ordinary_targets.update(target for target in routes.values() if target)
        ambiguous_branches = sorted(ordinary_targets.intersection(parallel_branches))
        if ambiguous_branches:
            return Result.err(
                _error(
                    "INVALID_WORKFLOW",
                    "Fan-out branches cannot also be ordinary edge targets.",
                    nodes=ambiguous_branches,
                )
            )

        reachable = set()
        pending = [self._entry_point]
        while pending:
            node = pending.pop()
            if node is None or node in reachable:
                continue
            reachable.add(node)
            if node in self._direct_edges and self._direct_edges[node] is not None:
                pending.append(self._direct_edges[node])
            for target in self._conditional_edges.get(node, {}).values():
                if target is not None:
                    pending.append(target)
            if node in self._parallel_edges:
                branches, join = self._parallel_edges[node]
                pending.extend(branches)
                pending.append(join)
        unreachable = sorted(set(self._nodes) - reachable)
        if unreachable:
            return Result.err(
                _error(
                    "UNREACHABLE_NODE",
                    "Workflow contains unreachable nodes.",
                    nodes=unreachable,
                )
            )
        return Result.ok(None)

    def run(
        self,
        initial_state: Mapping[str, Any],
        *,
        run_id: Optional[str] = None,
        checkpoint_store: Optional[CheckpointStore] = None,
    ) -> Result[WorkflowRun, Error]:
        """Start a workflow and return its lifecycle state."""
        validation = self.validate()
        if validation.is_err():
            return Result.err(validation.unwrap_err())
        if not isinstance(initial_state, Mapping):
            return Result.err(
                _error("INVALID_STATE", "Initial workflow state must be an object.")
            )
        state_result = _copy_json(
            dict(initial_state), max_state_bytes=self.max_state_bytes
        )
        if state_result.is_err():
            return Result.err(state_result.unwrap_err())
        resolved_run_id = run_id or str(uuid.uuid4())
        run_error = _valid_identifier(resolved_run_id, "run_id")
        if run_error:
            return Result.err(run_error)
        store = checkpoint_store or self.checkpoint_store
        existing_result = store.load(resolved_run_id)
        if existing_result.is_err():
            return Result.err(existing_result.unwrap_err())
        if existing_result.unwrap() is not None:
            return Result.err(
                _error(
                    "RUN_ID_EXISTS",
                    "A workflow run with this ID already exists.",
                    run_id=resolved_run_id,
                )
            )

        checkpoint = WorkflowCheckpoint(
            run_id=resolved_run_id,
            workflow_name=self.name,
            state=state_result.unwrap(),
            completed_nodes=[],
            next_node=self._entry_point,
            status="running",
        )
        saved_result = store.save(checkpoint)
        if saved_result.is_err():
            return Result.err(saved_result.unwrap_err())
        return self._execute(saved_result.unwrap(), store)

    def resume(
        self,
        run_id: str,
        *,
        resume_value: Any = None,
        checkpoint_store: Optional[CheckpointStore] = None,
    ) -> Result[WorkflowRun, Error]:
        """Resume an interrupted run from its last committed node."""
        validation = self.validate()
        if validation.is_err():
            return Result.err(validation.unwrap_err())
        run_error = _valid_identifier(run_id, "run_id")
        if run_error:
            return Result.err(run_error)
        resume_error = _validate_json_value(resume_value)
        if resume_error:
            return Result.err(resume_error)
        store = checkpoint_store or self.checkpoint_store
        loaded_result = store.load(run_id)
        if loaded_result.is_err():
            return Result.err(loaded_result.unwrap_err())
        checkpoint = loaded_result.unwrap()
        if checkpoint is None:
            return Result.err(
                _error("RUN_NOT_FOUND", "Workflow run was not found.", run_id=run_id)
            )
        if checkpoint.workflow_name != self.name:
            return Result.err(
                _error("WORKFLOW_MISMATCH", "Checkpoint belongs to another workflow.")
            )
        if checkpoint.status != "interrupted" or checkpoint.next_node is None:
            return Result.err(
                _error("INVALID_RESUME", "Only interrupted runs can be resumed.")
            )
        state_error = _validate_json_value(checkpoint.state)
        if state_error:
            return Result.err(state_error)
        resumed = replace(
            checkpoint,
            status="running",
            interrupt_payload=None,
            error=None,
            updated_at=time.time(),
        )
        saved_result = store.save(resumed, expected_version=checkpoint.version)
        if saved_result.is_err():
            return Result.err(saved_result.unwrap_err())
        return self._execute(saved_result.unwrap(), store, resume_value=resume_value)

    def recover(
        self,
        run_id: str,
        *,
        checkpoint_store: Optional[CheckpointStore] = None,
    ) -> Result[WorkflowRun, Error]:
        """Continue a running checkpoint after a crash or storage failure.

        This is intended for hosts that persisted a running checkpoint but did
        not receive the final node-boundary commit. When an execution journal
        is configured, normalized outputs already recorded before that crash
        are reused by :meth:`_execute`.
        """
        validation = self.validate()
        if validation.is_err():
            return Result.err(validation.unwrap_err())
        run_error = _valid_identifier(run_id, "run_id")
        if run_error:
            return Result.err(run_error)
        store = checkpoint_store or self.checkpoint_store
        loaded_result = store.load(run_id)
        if loaded_result.is_err():
            return Result.err(loaded_result.unwrap_err())
        checkpoint = loaded_result.unwrap()
        if checkpoint is None:
            return Result.err(
                _error("RUN_NOT_FOUND", "Workflow run was not found.", run_id=run_id)
            )
        if checkpoint.workflow_name != self.name:
            return Result.err(
                _error("WORKFLOW_MISMATCH", "Checkpoint belongs to another workflow.")
            )
        if checkpoint.status != "running" or checkpoint.next_node is None:
            return Result.err(
                _error(
                    "INVALID_RECOVERY",
                    "Only running workflow checkpoints can be recovered.",
                )
            )
        state_error = _validate_json_value(checkpoint.state)
        if state_error:
            return Result.err(state_error)
        return self._execute(checkpoint, store)

    def _execute(
        self,
        checkpoint: WorkflowCheckpoint,
        store: CheckpointStore,
        *,
        resume_value: Any = None,
    ) -> Result[WorkflowRun, Error]:
        current = checkpoint
        first_node = True
        while current.next_node is not None:
            if current.step_count >= self.max_steps:
                return self._fail(
                    current,
                    store,
                    _error("MAX_STEPS_REACHED", "Workflow step limit reached."),
                )
            node_name = current.next_node
            handler = self._nodes.get(node_name)
            if handler is None:
                return Result.err(
                    _error(
                        "INVALID_WORKFLOW",
                        "Checkpoint references an unknown node.",
                        node=node_name,
                    )
                )
            state_result = _copy_json(
                current.state, max_state_bytes=self.max_state_bytes
            )
            if state_result.is_err():
                return Result.err(state_result.unwrap_err())
            node_resume_value = resume_value if first_node else None
            execution_key = self._execution_key(
                current.run_id, current.step_count, node_name
            )
            context = WorkflowContext(
                state=state_result.unwrap(),
                run_id=current.run_id,
                node_name=node_name,
                resume_value=node_resume_value,
                execution_key=execution_key,
            )
            first_node = False
            replay_result = self._load_replay(
                execution_key,
                current.run_id,
                current.step_count,
                node_name,
                state_result.unwrap(),
                node_resume_value,
            )
            if replay_result.is_err():
                return self._fail(current, store, replay_result.unwrap_err())
            cached_updates = replay_result.unwrap()
            if cached_updates is not None:
                updates = cached_updates
            else:
                try:
                    output = handler(context)
                except WorkflowPause as pause:
                    payload_error = _validate_json_value(pause.payload)
                    if payload_error:
                        return self._fail(current, store, payload_error)
                    paused = replace(
                        current,
                        status="interrupted",
                        interrupt_payload=pause.payload,
                        error=None,
                        updated_at=time.time(),
                    )
                    saved_result = store.save(paused, expected_version=current.version)
                    if saved_result.is_err():
                        return Result.err(saved_result.unwrap_err())
                    return Result.ok(WorkflowRun.from_checkpoint(saved_result.unwrap()))
                except Exception as exc:
                    return self._fail(
                        current,
                        store,
                        _error(
                            "NODE_EXECUTION_ERROR",
                            "Workflow node execution failed.",
                            node=node_name,
                            reason=str(exc)[:256],
                        ),
                    )

                output_result = self._normalize_output(output)
                if output_result.is_err():
                    return self._fail(current, store, output_result.unwrap_err())
                updates = output_result.unwrap()
                journal_result = self._save_replay(
                    execution_key,
                    current.run_id,
                    current.step_count,
                    node_name,
                    updates,
                    state_result.unwrap(),
                    node_resume_value,
                )
                if journal_result.is_err():
                    return self._fail(current, store, journal_result.unwrap_err())
            prospective_state = dict(current.state)
            prospective_state.update(updates)
            parallel_route = self._parallel_edges.get(node_name)
            if parallel_route is not None:
                branches, join = parallel_route
                try:
                    parallel_result = self._run_parallel_branches(
                        branches,
                        prospective_state,
                        current.run_id,
                        current.step_count,
                        resume_value=node_resume_value,
                    )
                except WorkflowPause as pause:
                    payload_error = _validate_json_value(pause.payload)
                    if payload_error:
                        return self._fail(current, store, payload_error)
                    paused = replace(
                        current,
                        status="interrupted",
                        interrupt_payload=pause.payload,
                        error=None,
                        updated_at=time.time(),
                    )
                    saved_result = store.save(paused, expected_version=current.version)
                    if saved_result.is_err():
                        return Result.err(saved_result.unwrap_err())
                    return Result.ok(WorkflowRun.from_checkpoint(saved_result.unwrap()))
                if parallel_result.is_err():
                    return self._fail(current, store, parallel_result.unwrap_err())
                branch_updates = parallel_result.unwrap()
                conflicting_keys = [key for key in updates if key in branch_updates]
                if conflicting_keys:
                    return self._fail(
                        current,
                        store,
                        _error(
                            "PARALLEL_STATE_CONFLICT",
                            "Source and branch outputs cannot update the same "
                            "state keys.",
                            node=node_name,
                            keys=conflicting_keys,
                        ),
                    )
                updates.update(branch_updates)
                prospective_state.update(branch_updates)
                next_node = join
                completed_nodes = [node_name, *branches]
            else:
                next_result = self._next_node(node_name, prospective_state)
                if next_result.is_err():
                    return self._fail(current, store, next_result.unwrap_err())
                next_node = next_result.unwrap()
                completed_nodes = [node_name]
            state_result = _copy_json(
                prospective_state, max_state_bytes=self.max_state_bytes
            )
            if state_result.is_err():
                return self._fail(current, store, state_result.unwrap_err())
            completed = list(current.completed_nodes)
            completed.extend(completed_nodes)
            updated = replace(
                current,
                state=state_result.unwrap(),
                completed_nodes=completed,
                next_node=next_node,
                status="completed" if next_node is None else "running",
                step_count=current.step_count + 1,
                error=None,
                interrupt_payload=None,
                updated_at=time.time(),
            )
            saved_result = store.save(updated, expected_version=current.version)
            if saved_result.is_err():
                return Result.err(saved_result.unwrap_err())
            current = saved_result.unwrap()
        return Result.ok(WorkflowRun.from_checkpoint(current))

    def _run_parallel_branches(
        self,
        branches: Tuple[str, ...],
        state: Mapping[str, Any],
        run_id: str,
        step_count: int,
        *,
        resume_value: Any = None,
    ) -> Result[Dict[str, Any], Error]:
        """Execute one fan-out group and merge its results deterministically."""

        def execute_branch(branch: str) -> Tuple[str, Any]:
            handler = self._nodes.get(branch)
            if handler is None:
                return (
                    "error",
                    _error(
                        "INVALID_WORKFLOW",
                        "Checkpoint references an unknown parallel branch.",
                        node=branch,
                    ),
                )
            branch_state = _copy_json(state, max_state_bytes=self.max_state_bytes)
            if branch_state.is_err():
                return ("error", branch_state.unwrap_err())
            execution_key = self._execution_key(run_id, step_count, branch)
            context = WorkflowContext(
                state=branch_state.unwrap(),
                run_id=run_id,
                node_name=branch,
                resume_value=resume_value,
                execution_key=execution_key,
            )
            replay_result = self._load_replay(
                execution_key,
                run_id,
                step_count,
                branch,
                branch_state.unwrap(),
                resume_value,
            )
            if replay_result.is_err():
                return ("error", replay_result.unwrap_err())
            cached_updates = replay_result.unwrap()
            if cached_updates is not None:
                return ("ok", cached_updates)
            try:
                output = handler(context)
            except WorkflowPause as pause:
                return ("pause", pause.payload)
            except Exception as exc:
                return (
                    "error",
                    _error(
                        "NODE_EXECUTION_ERROR",
                        "Parallel workflow node execution failed.",
                        node=branch,
                        reason=str(exc)[:256],
                    ),
                )
            output_result = self._normalize_output(output)
            if output_result.is_err():
                return ("error", output_result.unwrap_err())
            updates = output_result.unwrap()
            journal_result = self._save_replay(
                execution_key,
                run_id,
                step_count,
                branch,
                updates,
                branch_state.unwrap(),
                resume_value,
            )
            if journal_result.is_err():
                return ("error", journal_result.unwrap_err())
            return ("ok", updates)

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(len(branches), self.max_parallel_branches),
            thread_name_prefix="maple-workflow",
        ) as executor:
            futures = [executor.submit(execute_branch, branch) for branch in branches]
            results = [future.result() for future in futures]

        for branch, (status, value) in zip(branches, results):
            if status == "pause":
                raise WorkflowPause(
                    {"branch": branch, "payload": value, "fan_out": list(branches)}
                )
            if status == "error":
                if isinstance(value, dict) and value.get("errorType"):
                    return Result.err(value)
                return Result.err(
                    _error(
                        "PARALLEL_BRANCH_ERROR",
                        "Parallel branch returned an invalid error.",
                        node=branch,
                    )
                )

        merged: Dict[str, Any] = {}
        for branch, (status, value) in zip(branches, results):
            if status != "ok":
                continue
            for key, item in value.items():
                if key in merged:
                    return Result.err(
                        _error(
                            "PARALLEL_STATE_CONFLICT",
                            "Parallel branch outputs cannot update the same "
                            "state keys.",
                            node=branch,
                            key=key,
                        )
                    )
                merged[key] = item
        return Result.ok(merged)

    def _fail(
        self,
        checkpoint: WorkflowCheckpoint,
        store: CheckpointStore,
        error: Error,
    ) -> Result[WorkflowRun, Error]:
        error_result = _copy_json(error, max_state_bytes=self.max_state_bytes)
        persisted_error = error_result.unwrap_or(
            _error(
                "WORKFLOW_FAILURE_NOT_SERIALIZABLE",
                "Workflow failure could not be persisted.",
            )
        )
        failed = replace(
            checkpoint, status="failed", error=persisted_error, updated_at=time.time()
        )
        saved_result = store.save(failed, expected_version=checkpoint.version)
        if saved_result.is_err():
            return Result.err(saved_result.unwrap_err())
        return Result.ok(WorkflowRun.from_checkpoint(saved_result.unwrap()))

    def _normalize_output(self, output: NodeOutput) -> Result[Dict[str, Any], Error]:
        if isinstance(output, Result):
            if output.is_err():
                error = output.unwrap_err()
                if isinstance(error, dict):
                    return Result.err(error)
                return Result.err(
                    _error("NODE_ERROR", "Workflow node returned an invalid error.")
                )
            output = output.unwrap()
        if output is None:
            return Result.ok({})
        if not isinstance(output, Mapping):
            return Result.err(
                _error(
                    "INVALID_NODE_OUTPUT",
                    "Workflow nodes must return a mapping or Result.",
                )
            )
        return Result.ok(dict(output))

    @staticmethod
    def _execution_key(run_id: str, step_count: int, node_name: str) -> str:
        return f"{run_id}:{step_count}:{node_name}"

    def _execution_input_digest(
        self, state: Mapping[str, Any], resume_value: Any
    ) -> Result[str, Error]:
        input_error = _validate_json_value(resume_value)
        if input_error:
            return Result.err(
                _error(
                    "REPLAY_INPUT_INVALID",
                    "Workflow resume value is not JSON-compatible.",
                    cause=input_error,
                )
            )
        try:
            encoded = json.dumps(
                {"state": dict(state), "resume_value": resume_value},
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            return Result.err(
                _error(
                    "REPLAY_INPUT_INVALID",
                    "Workflow execution input is not JSON-serializable.",
                    reason=str(exc)[:256],
                )
            )
        if len(encoded) > self.max_state_bytes:
            return Result.err(
                _error(
                    "REPLAY_INPUT_SIZE",
                    "Workflow execution input exceeds the state byte limit.",
                    max_state_bytes=self.max_state_bytes,
                )
            )
        return Result.ok(hashlib.sha256(encoded).hexdigest())

    def _load_replay(
        self,
        execution_key: str,
        run_id: str,
        step_count: int,
        node_name: str,
        state: Mapping[str, Any],
        resume_value: Any,
    ) -> Result[Optional[Dict[str, Any]], Error]:
        if self.execution_journal is None:
            return Result.ok(None)
        digest_result = self._execution_input_digest(state, resume_value)
        if digest_result.is_err():
            return Result.err(digest_result.unwrap_err())
        loaded = self.execution_journal.load(execution_key, digest_result.unwrap())
        if loaded.is_err():
            return Result.err(loaded.unwrap_err())
        record = loaded.unwrap()
        if record is None:
            return Result.ok(None)
        if (
            record.run_id != run_id
            or record.workflow_name != self.name
            or record.node_name != node_name
            or record.step_count != step_count
        ):
            return Result.err(
                _error(
                    "REPLAY_RECORD_INVALID",
                    "Replay record metadata does not match the workflow invocation.",
                    execution_key=execution_key,
                )
            )
        return Result.ok(dict(record.output))

    def _save_replay(
        self,
        execution_key: str,
        run_id: str,
        step_count: int,
        node_name: str,
        output: Mapping[str, Any],
        state: Mapping[str, Any],
        resume_value: Any,
    ) -> Result[None, Error]:
        if self.execution_journal is None:
            return Result.ok(None)
        digest_result = self._execution_input_digest(state, resume_value)
        if digest_result.is_err():
            return Result.err(digest_result.unwrap_err())
        record = ExecutionRecord(
            execution_key=execution_key,
            run_id=run_id,
            workflow_name=self.name,
            node_name=node_name,
            step_count=step_count,
            input_digest=digest_result.unwrap(),
            output=dict(output),
        )
        saved = self.execution_journal.save(record)
        if saved.is_err():
            return Result.err(saved.unwrap_err())
        return Result.ok(None)

    def _next_node(
        self, source: str, state: Mapping[str, Any]
    ) -> Result[Optional[str], Error]:
        if source in self._conditional_edges:
            try:
                route = self._routers[source](state)
            except Exception as exc:
                return Result.err(
                    _error(
                        "ROUTING_ERROR",
                        "Conditional workflow routing failed.",
                        node=source,
                        reason=str(exc)[:256],
                    )
                )
            if route not in self._conditional_edges[source]:
                return Result.err(
                    _error(
                        "UNKNOWN_ROUTE",
                        "Conditional selector returned an unknown route.",
                        node=source,
                    )
                )
            return Result.ok(self._conditional_edges[source][route])
        return Result.ok(self._direct_edges.get(source))

    def _validate_target(self, target: Optional[str]) -> Optional[Error]:
        if target is None:
            return None
        if target == END:
            return _error(
                "INVALID_TARGET", f"Use None for a terminal edge; {END} is reserved."
            )
        identifier_error = _valid_identifier(target, "target_node")
        return identifier_error
