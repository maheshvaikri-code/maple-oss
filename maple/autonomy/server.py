"""Dependency-free loopback HTTP access to registered MAPLE workflows."""

from __future__ import annotations

import hmac
import ipaddress
import json
import math
import re
import threading
import uuid
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Mapping, Optional, Protocol, Sequence, Tuple, cast
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from ..core.result import Result
from .approval import ApprovalRequest, ApprovalStore
from .events import (
    AgentEvent,
    EventCursor,
    EventDeduplicationStore,
    EventStream,
    validate_event_source_id,
)
from .handoffs import HandoffRecord, HandoffStore
from .interactions import HumanInputRequest, HumanInputStore
from .runs import AgentRunCheckpoint, AgentRunStore
from .workflow import Workflow, WorkflowRun

Error = Dict[str, Any]
_MAX_PATH_BYTES = 4_096
_MAX_WORKFLOWS = 64
_DEFAULT_MAX_BODY_BYTES = 1 * 1024 * 1024
_DEFAULT_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_MAX_EARLY_BODY_DISCARD_BYTES = 64 * 1024
_DEFAULT_CLIENT_TIMEOUT_SECONDS = 10.0
_MAX_EVENT_READ_LIMIT = 1_000
_MAX_EVENT_BATCH_ITEMS = 100
_MAX_HUMAN_INPUT_LIMIT = 1_000
_MAX_APPROVAL_LIMIT = 100
_MAX_HANDOFF_LIMIT = 100
_MAX_AGENT_HISTORY_LIMIT = 100
_MAX_AGENTS = 64
_MAX_AGENT_IDENTIFIER_BYTES = 256
_MAX_AGENT_TASK_BYTES = 8 * 1024
_MAX_AGENT_CONTEXT_KEYS = 32
_MAX_AGENT_CONTEXT_ITEMS = 128
_MAX_AGENT_CONTEXT_DEPTH = 8
_MAX_AGENT_CONTEXT_STRING_LENGTH = 8_192
_MAX_AGENT_CONTEXT_BYTES = 32 * 1024
_AGENT_RUN_STATUSES = frozenset({"cancelled", "completed", "paused", "failed"})
_PRINCIPAL_ID_PATTERN = r"^[A-Za-z0-9_.:-]{1,128}$"
_SCOPE_PATTERN = r"^(?:\*|[a-z][a-z0-9_.-]{0,63}:(?:[a-z][a-z0-9_.-]{0,63}|\*))$"
_REQUIRED_SCOPE_PATTERN = r"^[a-z][a-z0-9_.-]{0,63}:[a-z][a-z0-9_.-]{0,63}$"


def _error(error_type: str, message: str, **details: Any) -> Error:
    result: Error = {"errorType": error_type, "message": message}
    if details:
        result["details"] = details
    return result


def _validate_auth_token(auth_token: Optional[str]) -> None:
    if auth_token is None:
        return
    if not isinstance(auth_token, str) or not auth_token.strip():
        raise ValueError("auth_token must be a non-empty string when provided")
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in auth_token):
        raise ValueError("auth_token must not contain control characters")


@dataclass(frozen=True)
class Principal:
    """Host-configured identity and scope set for the local control plane.

    This is an authorization value, not a token issuer or identity provider.
    Hosts may attach it to the single configured bearer-token boundary to
    narrow what that token can do. A scope ending in ``:*`` grants the
    corresponding scope family; ``*`` preserves the legacy all-routes
    behavior when no narrower principal is configured.
    """

    principal_id: str
    scopes: Tuple[str, ...] = ("*",)

    def __post_init__(self) -> None:
        if not isinstance(self.principal_id, str) or not re.fullmatch(
            _PRINCIPAL_ID_PATTERN, self.principal_id
        ):
            raise ValueError("principal_id must be a bounded identifier")
        if (
            not isinstance(self.scopes, tuple)
            or not self.scopes
            or len(self.scopes) > 64
        ):
            raise ValueError("scopes must be a tuple of 1-64 values")
        for scope in self.scopes:
            if not isinstance(scope, str) or not re.fullmatch(_SCOPE_PATTERN, scope):
                raise ValueError("scopes must be bounded lowercase scope names")

    def allows(self, required_scope: str) -> bool:
        """Return whether this principal grants one required scope."""

        if not isinstance(required_scope, str) or not re.fullmatch(
            _REQUIRED_SCOPE_PATTERN, required_scope
        ):
            return False
        if "*" in self.scopes or required_scope in self.scopes:
            return True
        family = required_scope.split(":", 1)[0]
        return f"{family}:*" in self.scopes


def _required_scope(method: str, path: Tuple[str, ...]) -> Optional[str]:
    """Map known control-plane routes to host-owned authorization scopes."""

    if method == "GET" and path == ("healthz",):
        return "health:read"
    if path[0:2] == ("v1", "events"):
        return "event:publish" if method == "POST" else "event:read"
    if path[0:2] == ("v1", "agents"):
        if method == "GET":
            return "agent:read"
        if method == "POST" and len(path) == 4:
            return "agent:invoke"
        if method == "POST" and len(path) == 6 and path[5] == "resume":
            return "agent:resume"
        if method == "POST" and len(path) == 6 and path[5] == "cancel":
            return "agent:cancel"
    if path[0:2] == ("v1", "handoffs"):
        if method == "GET" and len(path) == 4 and path[3] == "result":
            return "handoff:result"
        return "handoff:read" if method == "GET" else "handoff:write"
    if path[0:2] == ("v1", "interactions"):
        if method == "GET":
            return "interaction:read"
        if method == "POST" and len(path) == 4 and path[3] == "consume":
            return "interaction:consume"
        return "interaction:write"
    if path[0:2] == ("v1", "approvals"):
        return "approval:read" if method == "GET" else "approval:decide"
    if path[0:2] == ("v1", "workflows"):
        if method == "GET":
            return "workflow:read"
        if method == "POST":
            return "workflow:invoke"
    return None


def _validate_event_input(event_type: Any, run_id: Optional[Any]) -> Optional[Error]:
    if (
        not isinstance(event_type, str)
        or not event_type
        or len(event_type) > 128
        or any(ord(char) < 32 or ord(char) == 127 for char in event_type)
    ):
        return _error(
            "EVENT_INPUT_INVALID",
            "event_type must be bounded and non-empty.",
        )
    if run_id is not None and (
        not isinstance(run_id, str)
        or not run_id
        or len(run_id) > 256
        or any(ord(char) < 32 or ord(char) == 127 for char in run_id)
    ):
        return _error("EVENT_INPUT_INVALID", "run_id must be bounded when provided.")
    return None


def _validate_agent_identifier(value: Any, field: str) -> Optional[Error]:
    if not isinstance(value, str) or not value.strip():
        return _error(
            "AGENT_IDENTIFIER_INVALID", f"{field} must be a non-empty string."
        )
    if len(value.encode("utf-8")) > _MAX_AGENT_IDENTIFIER_BYTES:
        return _error(
            "AGENT_IDENTIFIER_INVALID",
            f"{field} exceeds the configured byte limit.",
            max_bytes=_MAX_AGENT_IDENTIFIER_BYTES,
        )
    return None


def _copy_bounded_json(
    value: Any,
    *,
    error_type: str,
    path: str = "$",
    depth: int = 0,
) -> Result[Any, Error]:
    if depth > _MAX_AGENT_CONTEXT_DEPTH:
        return Result.err(
            _error(error_type, "JSON value is too deeply nested.", path=path)
        )
    if value is None or isinstance(value, (bool, int)):
        return Result.ok(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            return Result.err(
                _error(error_type, "JSON numbers must be finite.", path=path)
            )
        return Result.ok(value)
    if isinstance(value, str):
        if len(value) > _MAX_AGENT_CONTEXT_STRING_LENGTH:
            return Result.err(
                _error(
                    error_type, "JSON string exceeds the configured limit.", path=path
                )
            )
        return Result.ok(value)
    if isinstance(value, Mapping):
        if len(value) > _MAX_AGENT_CONTEXT_ITEMS:
            return Result.err(
                _error(error_type, "JSON object exceeds the item limit.", path=path)
            )
        copied: Dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str) or not key or len(key) > 128:
                return Result.err(
                    _error(
                        error_type,
                        "JSON object keys must be bounded strings.",
                        path=path,
                    )
                )
            child = _copy_bounded_json(
                item,
                error_type=error_type,
                path=f"{path}.{key}",
                depth=depth + 1,
            )
            if child.is_err():
                return Result.err(child.unwrap_err())
            copied[key] = child.unwrap()
        return Result.ok(copied)
    if isinstance(value, (list, tuple)):
        if len(value) > _MAX_AGENT_CONTEXT_ITEMS:
            return Result.err(
                _error(error_type, "JSON array exceeds the item limit.", path=path)
            )
        copied_list = []
        for index, item in enumerate(value):
            child = _copy_bounded_json(
                item,
                error_type=error_type,
                path=f"{path}[{index}]",
                depth=depth + 1,
            )
            if child.is_err():
                return Result.err(child.unwrap_err())
            copied_list.append(child.unwrap())
        return Result.ok(copied_list)
    return Result.err(
        _error(error_type, "Value must contain only JSON-compatible values.", path=path)
    )


def _normalize_agent_context(
    context: Optional[Mapping[str, Any]],
) -> Result[Dict[str, Any], Error]:
    if context is None:
        return Result.ok({})
    if not isinstance(context, Mapping):
        return Result.err(_error("AGENT_CONTEXT_INVALID", "context must be an object."))
    if len(context) > _MAX_AGENT_CONTEXT_KEYS:
        return Result.err(
            _error(
                "AGENT_CONTEXT_INVALID",
                "context exceeds the key limit.",
                max_keys=_MAX_AGENT_CONTEXT_KEYS,
            )
        )
    copied = _copy_bounded_json(context, error_type="AGENT_CONTEXT_INVALID")
    if copied.is_err():
        return Result.err(copied.unwrap_err())
    normalized = copied.unwrap()
    if not isinstance(normalized, dict):
        return Result.err(_error("AGENT_CONTEXT_INVALID", "context must be an object."))
    try:
        encoded = json.dumps(normalized, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError, OverflowError):
        return Result.err(
            _error("AGENT_CONTEXT_INVALID", "context must be JSON serializable.")
        )
    if len(encoded.encode("utf-8")) > _MAX_AGENT_CONTEXT_BYTES:
        return Result.err(
            _error(
                "AGENT_CONTEXT_INVALID",
                "context exceeds the byte limit.",
                max_bytes=_MAX_AGENT_CONTEXT_BYTES,
            )
        )
    return Result.ok(normalized)


def _normalize_agent_task(task: Any) -> Result[str, Error]:
    if not isinstance(task, str) or not task.strip():
        return Result.err(
            _error("AGENT_TASK_INVALID", "task must be a non-empty string.")
        )
    if len(task.encode("utf-8")) > _MAX_AGENT_TASK_BYTES:
        return Result.err(
            _error(
                "AGENT_TASK_INVALID",
                "task exceeds the configured byte limit.",
                max_bytes=_MAX_AGENT_TASK_BYTES,
            )
        )
    return Result.ok(task)


class AgentRunHandler(Protocol):
    """Host-owned synchronous callback for one bounded agent invocation."""

    def __call__(
        self,
        task: str,
        context: Mapping[str, Any],
        *,
        session_id: Optional[str],
        run_id: str,
    ) -> Result["AgentRun", Error]: ...


class AgentRunResumeHandler(Protocol):
    """Host-owned synchronous callback for one durable agent-run resume."""

    def __call__(self, run_id: str) -> Result["AgentRun", Error]: ...


class AgentRunCancelHandler(Protocol):
    """Host-owned synchronous callback for one cooperative agent-run cancel."""

    def __call__(self, run_id: str) -> Result["AgentRun", Error]: ...


@dataclass(frozen=True)
class AgentRun:
    """JSON-safe result envelope returned by a registered agent handler."""

    agent_id: str
    run_id: str
    status: str
    result: Optional[Any] = None
    error: Optional[Error] = None


def _agent_run_to_dict(run: AgentRun) -> Dict[str, Any]:
    return {
        "agent_id": run.agent_id,
        "run_id": run.run_id,
        "status": run.status,
        "result": run.result,
        "error": run.error,
    }


def _agent_checkpoint_to_dict(checkpoint: AgentRunCheckpoint) -> Dict[str, Any]:
    """Return a bounded remote summary without messages or reasoning trace."""

    payload = checkpoint.to_dict()
    if not isinstance(payload, dict):
        raise TypeError("agent run checkpoint serialization must return an object")
    payload.pop("messages", None)
    payload.pop("reasoning_steps", None)
    return cast(Dict[str, Any], payload)


def _agent_checkpoint_history_to_dict(
    checkpoint: AgentRunCheckpoint,
) -> Dict[str, Any]:
    """Return metadata-only history data for the remote inspection route."""

    return {
        "run_id": checkpoint.run_id,
        "agent_id": checkpoint.agent_id,
        "status": checkpoint.status,
        "step_count": checkpoint.step_count,
        "output_retries_used": checkpoint.output_retries_used,
        "pending_approval_id": checkpoint.pending_approval_id,
        "pending_input_id": checkpoint.pending_input_id,
        "session_id": checkpoint.session_id,
        "session_version": checkpoint.session_version,
        "token_usage": dict(checkpoint.token_usage),
        "version": checkpoint.version,
        "created_at": checkpoint.created_at,
        "updated_at": checkpoint.updated_at,
    }


def _handoff_to_dict(
    record: HandoffRecord, *, include_result: bool = False
) -> Dict[str, Any]:
    payload = record.to_dict(include_result=include_result)
    if not isinstance(payload, dict):
        raise TypeError("handoff record serialization must return an object")
    return cast(Dict[str, Any], payload)


def _handoff_result_to_dict(record: HandoffRecord) -> Dict[str, Any]:
    """Return the least-privilege envelope for one delivered handoff result."""
    payload = _handoff_to_dict(record, include_result=True)
    return {
        "handoff_id": payload["handoff_id"],
        "status": payload["status"],
        "target_goal_id": payload["target_goal_id"],
        "result": payload["result"],
    }


class AgentRegistry:
    """Thread-safe registry for host-owned agent run handlers."""

    def __init__(self, *, max_agents: int = _MAX_AGENTS) -> None:
        if (
            not isinstance(max_agents, int)
            or isinstance(max_agents, bool)
            or not 0 < max_agents <= _MAX_AGENTS
        ):
            raise ValueError("max_agents must be between 1 and 64")
        self.max_agents = max_agents
        self._agents: Dict[str, AgentRunHandler] = {}
        self._resume_handlers: Dict[str, AgentRunResumeHandler] = {}
        self._cancel_handlers: Dict[str, AgentRunCancelHandler] = {}
        self._lock = threading.RLock()

    def register(
        self,
        agent_id: str,
        handler: AgentRunHandler,
        *,
        resume_handler: Optional[AgentRunResumeHandler] = None,
        cancel_handler: Optional[AgentRunCancelHandler] = None,
    ) -> Result[None, Error]:
        """Register one host-owned handler before serving requests."""
        identifier_error = _validate_agent_identifier(agent_id, "agent_id")
        if identifier_error is not None:
            return Result.err(identifier_error)
        if not callable(handler):
            return Result.err(
                _error("AGENT_HANDLER_INVALID", "handler must be callable.")
            )
        if resume_handler is not None and not callable(resume_handler):
            return Result.err(
                _error(
                    "AGENT_RESUME_HANDLER_INVALID",
                    "resume_handler must be callable when provided.",
                )
            )
        if cancel_handler is not None and not callable(cancel_handler):
            return Result.err(
                _error(
                    "AGENT_CANCEL_HANDLER_INVALID",
                    "cancel_handler must be callable when provided.",
                )
            )
        with self._lock:
            if agent_id in self._agents:
                return Result.err(
                    _error(
                        "AGENT_EXISTS",
                        "An agent with this ID is already registered.",
                        agent_id=agent_id,
                    )
                )
            if len(self._agents) >= self.max_agents:
                return Result.err(
                    _error(
                        "AGENT_LIMIT",
                        "AgentRegistry has reached its agent limit.",
                        max_agents=self.max_agents,
                    )
                )
            self._agents[agent_id] = handler
            if resume_handler is not None:
                self._resume_handlers[agent_id] = resume_handler
            if cancel_handler is not None:
                self._cancel_handlers[agent_id] = cancel_handler
        return Result.ok(None)

    def _get(self, agent_id: str) -> Result[AgentRunHandler, Error]:
        identifier_error = _validate_agent_identifier(agent_id, "agent_id")
        if identifier_error is not None:
            return Result.err(identifier_error)
        with self._lock:
            handler = self._agents.get(agent_id)
        if handler is None:
            return Result.err(
                _error("AGENT_NOT_FOUND", "Agent was not found.", agent_id=agent_id)
            )
        return Result.ok(handler)

    def _get_resume_handler(
        self, agent_id: str
    ) -> Result[AgentRunResumeHandler, Error]:
        identifier_error = _validate_agent_identifier(agent_id, "agent_id")
        if identifier_error is not None:
            return Result.err(identifier_error)
        with self._lock:
            if agent_id not in self._agents:
                return Result.err(
                    _error("AGENT_NOT_FOUND", "Agent was not found.", agent_id=agent_id)
                )
            handler = self._resume_handlers.get(agent_id)
        if handler is None:
            return Result.err(
                _error(
                    "AGENT_RESUME_UNAVAILABLE",
                    "No durable resume handler is configured for this agent.",
                    agent_id=agent_id,
                )
            )
        return Result.ok(handler)

    def _get_cancel_handler(
        self, agent_id: str
    ) -> Result[AgentRunCancelHandler, Error]:
        identifier_error = _validate_agent_identifier(agent_id, "agent_id")
        if identifier_error is not None:
            return Result.err(identifier_error)
        with self._lock:
            if agent_id not in self._agents:
                return Result.err(
                    _error("AGENT_NOT_FOUND", "Agent was not found.", agent_id=agent_id)
                )
            handler = self._cancel_handlers.get(agent_id)
        if handler is None:
            return Result.err(
                _error(
                    "AGENT_CANCEL_UNAVAILABLE",
                    "No cooperative cancel handler is configured for this agent.",
                    agent_id=agent_id,
                )
            )
        return Result.ok(handler)

    def run(
        self,
        agent_id: str,
        task: str,
        context: Optional[Mapping[str, Any]] = None,
        *,
        session_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> Result[AgentRun, Error]:
        """Invoke one handler with bounded task/context and no transport retry."""
        handler_result = self._get(agent_id)
        if handler_result.is_err():
            return Result.err(handler_result.unwrap_err())
        task_result = _normalize_agent_task(task)
        if task_result.is_err():
            return Result.err(task_result.unwrap_err())
        context_result = _normalize_agent_context(context)
        if context_result.is_err():
            return Result.err(context_result.unwrap_err())
        if session_id is not None:
            session_error = _validate_agent_identifier(session_id, "session_id")
            if session_error is not None:
                return Result.err(session_error)
        if run_id is not None:
            run_error = _validate_agent_identifier(run_id, "run_id")
            if run_error is not None:
                return Result.err(run_error)
        chosen_run_id = run_id or str(uuid.uuid4())
        try:
            result = handler_result.unwrap()(
                task_result.unwrap(),
                context_result.unwrap(),
                session_id=session_id,
                run_id=chosen_run_id,
            )
        except Exception:
            return Result.err(
                _error(
                    "AGENT_HANDLER_ERROR",
                    "Registered agent handler failed.",
                    agent_id=agent_id,
                    run_id=chosen_run_id,
                )
            )
        return _normalize_agent_result(result, agent_id, chosen_run_id)

    def resume(self, agent_id: str, run_id: str) -> Result[AgentRun, Error]:
        """Resume one durable run through an explicitly registered callback."""
        handler_result = self._get_resume_handler(agent_id)
        if handler_result.is_err():
            return Result.err(handler_result.unwrap_err())
        run_error = _validate_agent_identifier(run_id, "run_id")
        if run_error is not None:
            return Result.err(run_error)
        try:
            result = handler_result.unwrap()(run_id)
        except Exception:
            return Result.err(
                _error(
                    "AGENT_RESUME_HANDLER_ERROR",
                    "Registered agent resume handler failed.",
                    agent_id=agent_id,
                    run_id=run_id,
                )
            )
        return _normalize_agent_result(result, agent_id, run_id)

    def cancel(self, agent_id: str, run_id: str) -> Result[AgentRun, Error]:
        """Request cooperative cancellation through an explicit host callback."""
        handler_result = self._get_cancel_handler(agent_id)
        if handler_result.is_err():
            return Result.err(handler_result.unwrap_err())
        run_error = _validate_agent_identifier(run_id, "run_id")
        if run_error is not None:
            return Result.err(run_error)
        try:
            result = handler_result.unwrap()(run_id)
        except Exception:
            return Result.err(
                _error(
                    "AGENT_CANCEL_HANDLER_ERROR",
                    "Registered agent cancel handler failed.",
                    agent_id=agent_id,
                    run_id=run_id,
                )
            )
        normalized = _normalize_agent_result(result, agent_id, run_id)
        if normalized.is_err():
            return Result.err(normalized.unwrap_err())
        if normalized.unwrap().status != "cancelled":
            return Result.err(
                _error(
                    "AGENT_CANCEL_RESULT_INVALID",
                    "Agent cancel handler must return a cancelled AgentRun.",
                )
            )
        return normalized


def _normalize_agent_result(
    result: Any, agent_id: str, chosen_run_id: str
) -> Result[AgentRun, Error]:
    """Validate and copy a host callback's JSON-safe run envelope."""
    if not isinstance(result, Result):
        return Result.err(
            _error("AGENT_RESULT_INVALID", "Agent handler must return a Result.")
        )
    if result.is_err():
        error = result.unwrap_err()
        if not isinstance(error, Mapping):
            return Result.err(
                _error("AGENT_RESULT_INVALID", "Agent handler errors must be objects.")
            )
        if (
            not isinstance(error.get("errorType"), str)
            or not str(error.get("errorType")).strip()
        ):
            return Result.err(
                _error(
                    "AGENT_RESULT_INVALID",
                    "Agent handler errors require a non-empty errorType.",
                )
            )
        if (
            not isinstance(error.get("message"), str)
            or not str(error.get("message")).strip()
        ):
            return Result.err(
                _error(
                    "AGENT_RESULT_INVALID",
                    "Agent handler errors require a non-empty message.",
                )
            )
        copied_error = _copy_bounded_json(error, error_type="AGENT_RESULT_INVALID")
        if copied_error.is_err():
            return Result.err(copied_error.unwrap_err())
        normalized_error = copied_error.unwrap()
        if not isinstance(normalized_error, dict):
            return Result.err(
                _error("AGENT_RESULT_INVALID", "Agent handler errors must be objects.")
            )
        return Result.err(normalized_error)
    run = result.unwrap()
    if not isinstance(run, AgentRun):
        return Result.err(
            _error("AGENT_RESULT_INVALID", "Agent handler must return an AgentRun.")
        )
    if run.agent_id != agent_id or run.run_id != chosen_run_id:
        return Result.err(
            _error(
                "AGENT_RESULT_INVALID",
                "AgentRun identity does not match the request.",
                agent_id=agent_id,
                run_id=chosen_run_id,
            )
        )
    if run.status not in _AGENT_RUN_STATUSES:
        return Result.err(
            _error(
                "AGENT_RESULT_INVALID",
                "AgentRun status is not supported.",
                allowed_statuses=sorted(_AGENT_RUN_STATUSES),
            )
        )
    copied_result = _copy_bounded_json(run.result, error_type="AGENT_RESULT_INVALID")
    if copied_result.is_err():
        return Result.err(copied_result.unwrap_err())
    copied_run_error: Optional[Error] = None
    if run.error is not None:
        if not isinstance(run.error, Mapping):
            return Result.err(
                _error("AGENT_RESULT_INVALID", "AgentRun error must be an object.")
            )
        if (
            not isinstance(run.error.get("errorType"), str)
            or not str(run.error.get("errorType")).strip()
        ):
            return Result.err(
                _error(
                    "AGENT_RESULT_INVALID",
                    "AgentRun errors require a non-empty errorType.",
                )
            )
        if (
            not isinstance(run.error.get("message"), str)
            or not str(run.error.get("message")).strip()
        ):
            return Result.err(
                _error(
                    "AGENT_RESULT_INVALID",
                    "AgentRun errors require a non-empty message.",
                )
            )
        error_result = _copy_bounded_json(run.error, error_type="AGENT_RESULT_INVALID")
        if error_result.is_err():
            return Result.err(error_result.unwrap_err())
        normalized_run_error = error_result.unwrap()
        if not isinstance(normalized_run_error, dict):
            return Result.err(
                _error("AGENT_RESULT_INVALID", "AgentRun error must be an object.")
            )
        copied_run_error = normalized_run_error
    normalized = AgentRun(
        agent_id=agent_id,
        run_id=chosen_run_id,
        status=run.status,
        result=copied_result.unwrap(),
        error=copied_run_error,
    )
    try:
        encoded = json.dumps(
            _agent_run_to_dict(normalized), ensure_ascii=False, allow_nan=False
        )
    except (TypeError, ValueError, OverflowError):
        return Result.err(
            _error("AGENT_RESULT_INVALID", "AgentRun is not JSON serializable.")
        )
    if len(encoded.encode("utf-8")) > _DEFAULT_MAX_RESPONSE_BYTES:
        return Result.err(
            _error(
                "AGENT_RESULT_INVALID",
                "AgentRun exceeds the configured response limit.",
                max_bytes=_DEFAULT_MAX_RESPONSE_BYTES,
            )
        )
    return Result.ok(normalized)


def _run_to_dict(run: WorkflowRun) -> Dict[str, Any]:
    """Convert a workflow result into the stable HTTP response shape."""
    return {
        "run_id": run.run_id,
        "workflow_name": run.workflow_name,
        "status": run.status,
        "state": dict(run.state),
        "completed_nodes": list(run.completed_nodes),
        "next_node": run.next_node,
        "checkpoint_version": run.checkpoint_version,
        "step_count": run.step_count,
        "interrupt_payload": run.interrupt_payload,
        "error": run.error,
    }


def _status_for_error(error: Error) -> int:
    error_type = error.get("errorType")
    if error_type in {
        "RUN_NOT_FOUND",
        "AGENT_RUN_NOT_FOUND",
        "WORKFLOW_NOT_FOUND",
        "AGENT_NOT_FOUND",
        "HANDOFF_NOT_FOUND",
        "APPROVAL_NOT_FOUND",
    }:
        return 404
    if error_type == "HUMAN_INPUT_NOT_FOUND":
        return 404
    if error_type in {
        "RUN_ID_EXISTS",
        "CHECKPOINT_CONFLICT",
        "RUN_CHECKPOINT_CONFLICT",
        "RUN_NOT_RESUMABLE",
        "RUN_WAITING_APPROVAL",
        "RUN_WAITING_INPUT",
    }:
        return 409
    if error_type in {
        "HUMAN_INPUT_CONFLICT",
        "HUMAN_INPUT_NOT_READY",
        "HUMAN_INPUT_ROUND_CONFLICT",
        "HUMAN_INPUT_ROUND_LIMIT",
        "HANDOFF_CONFLICT",
        "HANDOFF_STATE_CONFLICT",
        "HANDOFF_OWNER_ERROR",
        "HANDOFF_RESULT_UNAVAILABLE",
        "APPROVAL_CONFLICT",
        "APPROVAL_LEASE_ERROR",
        "EVENT_CURSOR_EXPIRED",
    }:
        return 409
    if error_type in {
        "INVALID_STATE",
        "INVALID_IDENTIFIER",
        "INVALID_WORKFLOW",
        "RUN_IDENTIFIER_INVALID",
        "AGENT_IDENTIFIER_INVALID",
        "AGENT_TASK_INVALID",
        "AGENT_CONTEXT_INVALID",
        "AGENT_HANDLER_INVALID",
        "AGENT_RESUME_HANDLER_INVALID",
        "INVALID_JSON",
        "REQUEST_BODY_INVALID",
        "WORKFLOW_MISMATCH",
        "HANDOFF_INPUT_INVALID",
        "HANDOFF_LIMIT_INVALID",
        "HANDOFF_RECORD_INVALID",
        "HANDOFF_RESULT_INVALID",
        "APPROVAL_LIMIT_INVALID",
        "APPROVAL_DECISION_INVALID",
        "HUMAN_INPUT_IDENTIFIER_INVALID",
        "HUMAN_INPUT_ACTOR_INVALID",
        "HUMAN_INPUT_LIMIT_INVALID",
        "HUMAN_INPUT_PROMPT_INVALID",
        "HUMAN_INPUT_REASON_INVALID",
        "HUMAN_INPUT_RESPONSE_INVALID",
        "HUMAN_INPUT_ROUND_LIMIT_INVALID",
        "HUMAN_INPUT_VALUE_INVALID",
        "HUMAN_INPUT_VALUE_TOO_DEEP",
        "HUMAN_INPUT_VALUE_TOO_LARGE",
        "EVENT_CONFIG_INVALID",
        "EVENT_INPUT_INVALID",
        "EVENT_QUERY_INVALID",
        "EVENT_CURSOR_INVALID",
        "EVENT_NON_JSON_PAYLOAD",
        "EVENT_PAYLOAD_TOO_DEEP",
        "EVENT_PAYLOAD_TOO_LARGE",
        "EVENT_BATCH_INVALID",
        "AGENT_RUN_HISTORY_LIMIT_INVALID",
    }:
        return 400
    if error_type == "AGENT_REGISTRY_UNAVAILABLE":
        return 503
    if error_type == "EVENT_STREAM_UNAVAILABLE":
        return 503
    if error_type == "AGENT_RUN_STORE_UNAVAILABLE":
        return 503
    if error_type == "AGENT_RESUME_UNAVAILABLE":
        return 501
    if error_type == "AGENT_CANCEL_UNAVAILABLE":
        return 501
    if error_type == "AGENT_RUN_HISTORY_UNAVAILABLE":
        return 501
    if error_type == "HUMAN_INPUT_STORE_UNAVAILABLE":
        return 503
    if error_type == "APPROVAL_STORE_UNAVAILABLE":
        return 503
    if error_type == "HUMAN_INPUT_MULTI_ROUND_UNSUPPORTED":
        return 501
    if error_type in {
        "HUMAN_INPUT_ACTOR_REQUIRED",
        "HUMAN_INPUT_UNAUTHORIZED",
    }:
        return 403
    return 500


class WorkflowRegistry:
    """Thread-safe registry of workflows configured by the host process."""

    def __init__(self, *, max_workflows: int = _MAX_WORKFLOWS) -> None:
        if (
            not isinstance(max_workflows, int)
            or isinstance(max_workflows, bool)
            or not 0 < max_workflows <= _MAX_WORKFLOWS
        ):
            raise ValueError("max_workflows must be between 1 and 64")
        self.max_workflows = max_workflows
        self._workflows: Dict[str, Workflow] = {}
        self._lock = threading.RLock()

    def register(self, workflow: Workflow) -> Result[None, Error]:
        """Register a configured workflow before serving requests."""
        if not isinstance(workflow, Workflow):
            return Result.err(
                _error("INVALID_WORKFLOW", "WorkflowRegistry requires a Workflow.")
            )
        with self._lock:
            if workflow.name in self._workflows:
                return Result.err(
                    _error(
                        "WORKFLOW_EXISTS",
                        "A workflow with this name is already registered.",
                        workflow_name=workflow.name,
                    )
                )
            if len(self._workflows) >= self.max_workflows:
                return Result.err(
                    _error(
                        "WORKFLOW_LIMIT",
                        "WorkflowRegistry has reached its workflow limit.",
                        max_workflows=self.max_workflows,
                    )
                )
            self._workflows[workflow.name] = workflow
        return Result.ok(None)

    def _get(self, workflow_name: str) -> Result[Workflow, Error]:
        with self._lock:
            workflow = self._workflows.get(workflow_name)
        if workflow is None:
            return Result.err(
                _error(
                    "WORKFLOW_NOT_FOUND",
                    "Workflow was not found.",
                    workflow_name=workflow_name,
                )
            )
        return Result.ok(workflow)

    def run(
        self,
        workflow_name: str,
        initial_state: Mapping[str, Any],
        *,
        run_id: Optional[str] = None,
    ) -> Result[WorkflowRun, Error]:
        workflow_result = self._get(workflow_name)
        if workflow_result.is_err():
            return Result.err(workflow_result.unwrap_err())
        return workflow_result.unwrap().run(initial_state, run_id=run_id)

    def resume(
        self,
        workflow_name: str,
        run_id: str,
        *,
        resume_value: Any = None,
    ) -> Result[WorkflowRun, Error]:
        workflow_result = self._get(workflow_name)
        if workflow_result.is_err():
            return Result.err(workflow_result.unwrap_err())
        return workflow_result.unwrap().resume(run_id, resume_value=resume_value)

    def inspect(
        self, workflow_name: str, run_id: str
    ) -> Result[Optional[WorkflowRun], Error]:
        workflow_result = self._get(workflow_name)
        if workflow_result.is_err():
            return Result.err(workflow_result.unwrap_err())
        workflow = workflow_result.unwrap()
        checkpoint_result = workflow.checkpoint_store.load(run_id)
        if checkpoint_result.is_err():
            return Result.err(checkpoint_result.unwrap_err())
        checkpoint = checkpoint_result.unwrap()
        if checkpoint is None:
            return Result.ok(None)
        if checkpoint.workflow_name != workflow.name:
            return Result.err(
                _error(
                    "WORKFLOW_MISMATCH",
                    "Stored run belongs to a different workflow.",
                    run_id=run_id,
                )
            )
        return Result.ok(WorkflowRun.from_checkpoint(checkpoint))


class _MAPLEHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: Any, handler: Any, application: Any) -> None:
        self.application = application
        super().__init__(address, handler)


class _RequestHandler(BaseHTTPRequestHandler):
    server: _MAPLEHTTPServer
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: Any) -> None:
        """Do not log request bodies, session content, or credentials."""

    def do_GET(self) -> None:  # noqa: N802
        self._dispatch("GET")

    def do_POST(self) -> None:  # noqa: N802
        self._dispatch("POST")

    def _dispatch(self, method: str) -> None:
        try:
            if not self._authorize():
                return
            path = self._path_segments()
            if path is None:
                return
            if not self._authorize_scope(method, path):
                return
            if method == "GET" and path == ("healthz",):
                self._write_json(200, {"status": "ok", "service": "maple-run-server"})
                return
            if method == "POST" and path == ("v1", "events"):
                self._publish_event()
                return
            if method == "POST" and path == ("v1", "events", "batch"):
                self._publish_event_batch()
                return
            if method == "GET" and path == ("v1", "events"):
                self._read_events()
                return
            if (
                method == "POST"
                and len(path) == 4
                and path[0:2] == ("v1", "agents")
                and path[3] == "runs"
            ):
                self._run_agent(path[2])
                return
            if (
                method == "GET"
                and len(path) == 6
                and path[0:4] == ("v1", "agents", path[2], "runs")
                and path[5] == "history"
            ):
                self._inspect_agent_history(path[2], path[4])
                return
            if (
                method == "GET"
                and len(path) == 5
                and path[0:4] == ("v1", "agents", path[2], "runs")
            ):
                self._inspect_agent(path[2], path[4])
                return
            if (
                method == "POST"
                and len(path) == 6
                and path[0:4] == ("v1", "agents", path[2], "runs")
                and path[5] in {"resume", "cancel"}
            ):
                if path[5] == "resume":
                    self._resume_agent(path[2], path[4])
                else:
                    self._cancel_agent(path[2], path[4])
                return
            if self._handoff_route(method, path):
                return
            if self._interaction_route(method, path):
                return
            if self._approval_route(method, path):
                return
            if (
                method == "GET"
                and len(path) == 5
                and path[0:4]
                == (
                    "v1",
                    "workflows",
                    path[2],
                    "runs",
                )
            ):
                self._inspect(path[2], path[4])
                return
            if (
                method == "POST"
                and len(path) == 4
                and path[0:4]
                == (
                    "v1",
                    "workflows",
                    path[2],
                    "runs",
                )
            ):
                self._run(path[2])
                return
            if (
                method == "POST"
                and len(path) == 6
                and path[0:4]
                == (
                    "v1",
                    "workflows",
                    path[2],
                    "runs",
                )
                and path[5] == "resume"
            ):
                self._resume(path[2], path[4])
                return
            self._write_error(404, _error("NOT_FOUND", "Route was not found."))
        except (TypeError, ValueError, UnicodeError, json.JSONDecodeError):
            self._write_error(
                400, _error("REQUEST_BODY_INVALID", "Request is invalid.")
            )
        except _ResponseWritten:
            return
        except Exception:
            self._write_error(
                500, _error("INTERNAL_ERROR", "Request could not be processed.")
            )

    def _interaction_route(self, method: str, path: Tuple[str, ...]) -> bool:
        store = self.server.application.human_input_store
        if not path or path[0:2] != ("v1", "interactions"):
            return False
        if store is None:
            self._write_error(
                503,
                _error(
                    "HUMAN_INPUT_STORE_UNAVAILABLE",
                    "No human input store is configured.",
                ),
            )
            return True
        if method == "GET" and len(path) == 4 and path[2] == "pending":
            try:
                limit = int(path[3])
            except ValueError:
                self._write_error(
                    400,
                    _error(
                        "HUMAN_INPUT_LIMIT_INVALID",
                        "Human input list limit must be an integer.",
                    ),
                )
                return True
            result = store.list_pending(limit)
            if result.is_err():
                self._write_error(
                    _status_for_error(result.unwrap_err()), result.unwrap_err()
                )
                return True
            self._write_json(
                200,
                {
                    "interactions": [
                        self._interaction_to_dict(item) for item in result.unwrap()
                    ]
                },
            )
            return True
        if method == "GET" and len(path) == 3:
            result = store.get(path[2])
            if result.is_err():
                self._write_error(
                    _status_for_error(result.unwrap_err()), result.unwrap_err()
                )
                return True
            request = result.unwrap()
            if request is None:
                self._write_error(
                    404,
                    _error(
                        "HUMAN_INPUT_NOT_FOUND", "Human input request was not found."
                    ),
                )
                return True
            self._write_json(200, {"interaction": self._interaction_to_dict(request)})
            return True
        if method == "POST" and len(path) == 4:
            self._mutate_interaction(store, path[2], path[3])
            return True
        self._write_error(404, _error("NOT_FOUND", "Interaction route was not found."))
        return True

    def _approval_route(self, method: str, path: Tuple[str, ...]) -> bool:
        store = self.server.application.approval_store
        if not path or path[0:2] != ("v1", "approvals"):
            return False
        if store is None:
            self._write_error(
                503,
                _error(
                    "APPROVAL_STORE_UNAVAILABLE",
                    "No approval store is configured.",
                ),
            )
            return True
        if method == "GET" and len(path) == 4 and path[2] == "pending":
            try:
                limit = int(path[3])
            except ValueError:
                self._write_error(
                    400,
                    _error(
                        "APPROVAL_LIMIT_INVALID",
                        "Approval list limit must be an integer.",
                    ),
                )
                return True
            result = store.list_pending(limit)
            if result.is_err():
                self._write_error(
                    _status_for_error(result.unwrap_err()), result.unwrap_err()
                )
                return True
            self._write_json(
                200,
                {
                    "approvals": [
                        self._approval_to_dict(item) for item in result.unwrap()
                    ]
                },
            )
            return True
        if method == "GET" and len(path) == 3:
            result = store.get(path[2])
            if result.is_err():
                self._write_error(
                    _status_for_error(result.unwrap_err()), result.unwrap_err()
                )
                return True
            request = result.unwrap()
            if request is None:
                self._write_error(
                    404,
                    _error("APPROVAL_NOT_FOUND", "Approval request was not found."),
                )
                return True
            self._write_json(200, {"approval": self._approval_to_dict(request)})
            return True
        if method == "POST" and len(path) == 4 and path[3] == "decide":
            self._mutate_approval(store, path[2])
            return True
        self._write_error(404, _error("NOT_FOUND", "Approval route was not found."))
        return True

    @staticmethod
    def _approval_to_dict(request: ApprovalRequest) -> Dict[str, Any]:
        return cast(Dict[str, Any], request.to_dict())

    def _mutate_approval(self, store: ApprovalStore, approval_id: str) -> None:
        body = self._read_body()
        approved = body.get("approved")
        if type(approved) is not bool:
            self._write_error(
                400,
                _error("APPROVAL_DECISION_INVALID", "approved must be boolean."),
            )
            return
        edited_arguments = body.get("edited_arguments")
        if edited_arguments is not None and not isinstance(edited_arguments, Mapping):
            self._write_error(
                400,
                _error(
                    "APPROVAL_DECISION_INVALID",
                    "edited_arguments must be an object or null.",
                ),
            )
            return
        result = store.decide(
            approval_id,
            approved,
            edited_arguments=(
                dict(edited_arguments) if edited_arguments is not None else None
            ),
        )
        if result.is_err():
            self._write_error(
                _status_for_error(result.unwrap_err()), result.unwrap_err()
            )
            return
        self._write_json(
            200,
            {"approval": self._approval_to_dict(result.unwrap())},
        )

    @staticmethod
    def _interaction_to_dict(request: HumanInputRequest) -> Dict[str, Any]:
        return cast(Dict[str, Any], request.to_dict())

    def _mutate_interaction(
        self, store: HumanInputStore, interaction_id: str, action: str
    ) -> None:
        body = self._read_body()
        actor_id = body.get("actor_id")
        if actor_id is not None and not isinstance(actor_id, str):
            self._write_error(
                400,
                _error("HUMAN_INPUT_IDENTIFIER_INVALID", "actor_id must be a string."),
            )
            return
        if action == "respond":
            if "response" not in body:
                self._write_error(
                    400,
                    _error("HUMAN_INPUT_RESPONSE_INVALID", "response is required."),
                )
                return
            result = store.respond(interaction_id, body["response"], actor_id=actor_id)
        elif action == "reject":
            result = store.reject(
                interaction_id,
                body.get("reason", "Operator rejected the request."),
                actor_id=actor_id,
            )
        elif action == "continue":
            continue_round = getattr(store, "continue_round", None)
            if not callable(continue_round):
                self._write_error(
                    501,
                    _error(
                        "HUMAN_INPUT_MULTI_ROUND_UNSUPPORTED",
                        "The configured human input store does not support multi-round input.",
                    ),
                )
                return
            if "prompt" not in body or "input_schema" not in body:
                self._write_error(
                    400,
                    _error(
                        "REQUEST_BODY_INVALID",
                        "prompt and input_schema are required.",
                    ),
                )
                return
            result = continue_round(
                interaction_id,
                body["prompt"],
                body["input_schema"],
                actor_id=actor_id,
            )
        elif action == "consume":
            result = store.consume(interaction_id)
        else:
            self._write_error(
                404, _error("NOT_FOUND", "Interaction action was not found.")
            )
            return
        if result.is_err():
            self._write_error(
                _status_for_error(result.unwrap_err()), result.unwrap_err()
            )
            return
        self._write_json(
            200, {"interaction": self._interaction_to_dict(result.unwrap())}
        )

    def _authorize(self) -> bool:
        expected_token = self.server.application.auth_token
        if expected_token is None:
            return True
        presented = self.headers.get("Authorization", "")
        expected = f"Bearer {expected_token}"
        if not hmac.compare_digest(presented, expected):
            self._discard_bounded_request_body()
            self._write_json(
                401,
                {"error": _error("UNAUTHORIZED", "A valid bearer token is required.")},
                extra_headers={"WWW-Authenticate": "Bearer"},
            )
            return False
        return True

    def _authorize_scope(self, method: str, path: Tuple[str, ...]) -> bool:
        required_scope = _required_scope(method, path)
        principal = self.server.application.auth_principal
        if required_scope is None or principal is None:
            return True
        if principal.allows(required_scope):
            return True
        self._discard_bounded_request_body()
        self._write_json(
            403,
            {
                "error": _error(
                    "FORBIDDEN",
                    "The authenticated principal lacks the required scope.",
                    principal_id=principal.principal_id,
                    required_scope=required_scope,
                )
            },
        )
        return False

    def _discard_bounded_request_body(self, *, allow_oversized: bool = False) -> None:
        """Drain a bounded rejected body before closing the connection."""
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            return
        try:
            length = int(raw_length)
        except (TypeError, ValueError):
            return
        max_length = self.server.application.max_body_bytes
        if allow_oversized:
            max_length = max(max_length, _MAX_EARLY_BODY_DISCARD_BYTES)
        if length < 0 or length > max_length:
            return
        try:
            self.rfile.read(length)
        except (OSError, TimeoutError):
            return

    def _path_segments(self) -> Optional[Tuple[str, ...]]:
        raw_path = self.path.encode("utf-8", errors="replace")
        if len(raw_path) > _MAX_PATH_BYTES:
            self._write_error(
                414, _error("PATH_TOO_LARGE", "Request path is too large.")
            )
            return None
        parsed = urlsplit(self.path)
        if not parsed.path.startswith("/"):
            self._write_error(400, _error("PATH_INVALID", "Request path is invalid."))
            return None
        parts = tuple(unquote(part) for part in parsed.path.split("/") if part)
        if any(part in {".", ".."} or not part for part in parts):
            self._write_error(400, _error("PATH_INVALID", "Request path is invalid."))
            return None
        return parts

    def _read_body(self) -> Dict[str, Any]:
        content_type = self.headers.get("Content-Type", "")
        if not content_type.lower().split(";", 1)[0].strip() == "application/json":
            raise ValueError("request must use application/json")
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            raise ValueError("content length is required")
        length = int(raw_length)
        if length < 0 or length > self.server.application.max_body_bytes:
            self._discard_bounded_request_body(allow_oversized=True)
            self._write_error(
                413,
                _error(
                    "REQUEST_TOO_LARGE",
                    "Request body exceeds the configured byte limit.",
                    max_bytes=self.server.application.max_body_bytes,
                ),
            )
            raise _ResponseWritten()
        payload = self.rfile.read(length)
        if len(payload) != length:
            raise ValueError("request body is truncated")
        decoded = json.loads(payload.decode("utf-8"))
        if not isinstance(decoded, dict):
            raise ValueError("request body must be an object")
        return decoded

    def _run(self, workflow_name: str) -> None:
        body = self._read_body()
        if "state" not in body or not isinstance(body["state"], Mapping):
            self._write_error(
                400, _error("INVALID_STATE", "Run state must be an object.")
            )
            return
        run_id = body.get("run_id")
        if run_id is not None and not isinstance(run_id, str):
            self._write_error(
                400, _error("INVALID_IDENTIFIER", "run_id must be a string.")
            )
            return
        result = self.server.application.registry.run(
            workflow_name, body["state"], run_id=run_id
        )
        self._write_result(result, success_status=201)

    def _run_agent(self, agent_id: str) -> None:
        registry = self.server.application.agent_registry
        if registry is None:
            self._write_error(
                503,
                _error(
                    "AGENT_REGISTRY_UNAVAILABLE",
                    "No agent registry is configured.",
                ),
            )
            return
        body = self._read_body()
        result = registry.run(
            agent_id,
            body.get("task"),
            body.get("context", {}),
            session_id=body.get("session_id"),
            run_id=body.get("run_id"),
        )
        if result.is_err():
            self._write_error(
                _status_for_error(result.unwrap_err()), result.unwrap_err()
            )
            return
        self._write_json(201, {"run": _agent_run_to_dict(result.unwrap())})

    def _publish_event(self) -> None:
        stream = self.server.application.event_stream
        if stream is None:
            self._discard_bounded_request_body()
            self._write_error(
                503,
                _error(
                    "EVENT_STREAM_UNAVAILABLE",
                    "No event stream is configured.",
                ),
            )
            return
        body = self._read_body()
        if "event_type" not in body or "payload" not in body:
            self._write_error(
                400,
                _error(
                    "EVENT_INPUT_INVALID",
                    "event_type and payload are required.",
                ),
            )
            return
        result = stream.publish(
            body["event_type"],
            body["payload"],
            run_id=body.get("run_id"),
        )
        if result.is_err():
            self._write_error(
                _status_for_error(result.unwrap_err()), result.unwrap_err()
            )
            return
        self._write_json(201, {"event": result.unwrap().as_dict()})

    def _publish_event_batch(self) -> None:
        stream = self.server.application.event_stream
        if stream is None:
            self._discard_bounded_request_body()
            self._write_error(
                503,
                _error(
                    "EVENT_STREAM_UNAVAILABLE",
                    "No event stream is configured.",
                ),
            )
            return
        body = self._read_body()
        raw_events = body.get("events")
        if (
            not isinstance(raw_events, list)
            or not raw_events
            or len(raw_events) > _MAX_EVENT_BATCH_ITEMS
        ):
            self._write_error(
                400,
                _error(
                    "EVENT_BATCH_INVALID",
                    "events must contain between 1 and 100 items.",
                    max_items=_MAX_EVENT_BATCH_ITEMS,
                ),
            )
            return

        dedup_store = self.server.application.event_deduplication_store
        dedup_source_id: Optional[str] = None
        if dedup_store is not None:
            source_error = validate_event_source_id(body.get("source_id"))
            if source_error is not None:
                self._write_error(400, source_error)
                return
            dedup_source_id = cast(str, body.get("source_id"))

        published = []
        failed = []
        for index, item in enumerate(raw_events):
            if not isinstance(item, Mapping):
                failed.append(
                    {
                        "index": index,
                        "error": _error(
                            "EVENT_INPUT_INVALID",
                            "event must be an object.",
                        ),
                    }
                )
                continue
            if "event_type" not in item or "payload" not in item:
                failed.append(
                    {
                        "index": index,
                        "error": _error(
                            "EVENT_INPUT_INVALID",
                            "event_type and payload are required.",
                        ),
                    }
                )
                continue
            source_sequence: Optional[int] = None
            source_event: Optional[AgentEvent] = None
            if dedup_store is not None and dedup_source_id is not None:
                candidate_sequence = item.get("sequence")
                if (
                    not isinstance(candidate_sequence, int)
                    or isinstance(candidate_sequence, bool)
                    or candidate_sequence <= 0
                ):
                    failed.append(
                        {
                            "index": index,
                            "error": _error(
                                "EVENT_SOURCE_SEQUENCE_INVALID",
                                "sequence must be a positive integer when deduplication is enabled.",
                            ),
                        }
                    )
                    continue
                input_error = _validate_event_input(
                    item["event_type"], item.get("run_id")
                )
                if input_error is not None:
                    failed.append({"index": index, "error": input_error})
                    continue
                source_sequence = candidate_sequence
                source_event = AgentEvent(
                    sequence=source_sequence,
                    event_type=item["event_type"],
                    timestamp=0.0,
                    payload=item["payload"],
                    run_id=item.get("run_id"),
                )
                claim = dedup_store.claim(
                    dedup_source_id, source_sequence, source_event
                )
                if claim.is_err():
                    failed.append({"index": index, "error": claim.unwrap_err()})
                    continue
                existing_event = claim.unwrap()
                if existing_event is not None:
                    published.append(
                        {"index": index, "event": existing_event.as_dict()}
                    )
                    continue
            result = stream.publish(
                item["event_type"],
                item["payload"],
                run_id=item.get("run_id"),
            )
            if result.is_err():
                if source_sequence is not None and dedup_source_id is not None:
                    dedup_store.abort(dedup_source_id, source_sequence)
                failed.append({"index": index, "error": result.unwrap_err()})
                continue
            event = result.unwrap()
            if source_sequence is not None and dedup_source_id is not None:
                completed = dedup_store.complete(
                    dedup_source_id, source_sequence, event
                )
                if completed.is_err():
                    dedup_store.abort(dedup_source_id, source_sequence)
                    failed.append({"index": index, "error": completed.unwrap_err()})
                    continue
                event = completed.unwrap()
            published.append({"index": index, "event": event.as_dict()})
        self._write_json(200, {"published": published, "failed": failed})

    def _read_events(self) -> None:
        stream = self.server.application.event_stream
        if stream is None:
            self._write_error(
                503,
                _error(
                    "EVENT_STREAM_UNAVAILABLE",
                    "No event stream is configured.",
                ),
            )
            return
        parsed = urlsplit(self.path)
        try:
            pairs = parse_qsl(
                parsed.query,
                keep_blank_values=True,
                strict_parsing=True,
                max_num_fields=2,
            )
        except ValueError:
            self._write_error(
                400,
                _error("EVENT_QUERY_INVALID", "event query parameters are invalid."),
            )
            return
        if any(key not in {"after", "limit"} for key, _ in pairs) or len(
            {key for key, _ in pairs}
        ) != len(pairs):
            self._write_error(
                400,
                _error(
                    "EVENT_QUERY_INVALID",
                    "event query supports one after and one limit parameter.",
                ),
            )
            return
        query = dict(pairs)
        try:
            after = int(query.get("after", "0"))
            limit = (
                int(query["limit"])
                if "limit" in query
                else min(stream.max_events, _MAX_EVENT_READ_LIMIT)
            )
        except (TypeError, ValueError):
            self._write_error(
                400,
                _error("EVENT_QUERY_INVALID", "after and limit must be integers."),
            )
            return
        if limit > _MAX_EVENT_READ_LIMIT:
            self._write_error(
                400,
                _error(
                    "EVENT_QUERY_INVALID",
                    "limit exceeds the remote event batch bound.",
                    max_limit=_MAX_EVENT_READ_LIMIT,
                ),
            )
            return
        cursor_result = EventCursor.from_dict({"sequence": after})
        if cursor_result.is_err():
            self._write_error(400, cursor_result.unwrap_err())
            return
        result = stream.read(cursor_result.unwrap(), limit=limit)
        if result.is_err():
            self._write_error(
                _status_for_error(result.unwrap_err()), result.unwrap_err()
            )
            return
        self._write_json(200, {"batch": result.unwrap().to_dict()})

    def _inspect_agent(self, agent_id: str, run_id: str) -> None:
        store = self.server.application.agent_run_store
        if store is None:
            self._write_error(
                503,
                _error(
                    "AGENT_RUN_STORE_UNAVAILABLE",
                    "No agent run store is configured.",
                ),
            )
            return
        result = store.load(run_id)
        if result.is_err():
            self._write_error(
                _status_for_error(result.unwrap_err()), result.unwrap_err()
            )
            return
        checkpoint = result.unwrap()
        if checkpoint is None or checkpoint.agent_id != agent_id:
            self._write_error(
                404,
                _error("AGENT_RUN_NOT_FOUND", "Agent run was not found."),
            )
            return
        self._write_json(200, {"run": _agent_checkpoint_to_dict(checkpoint)})

    def _agent_history_limit(self) -> Result[int, Error]:
        parsed = urlsplit(self.path)
        try:
            pairs = parse_qsl(
                parsed.query,
                keep_blank_values=True,
                strict_parsing=True,
                max_num_fields=1,
            )
        except ValueError:
            return Result.err(
                _error(
                    "AGENT_RUN_HISTORY_LIMIT_INVALID",
                    "history query supports one limit parameter.",
                    max_limit=_MAX_AGENT_HISTORY_LIMIT,
                )
            )
        if not pairs:
            return Result.ok(_MAX_AGENT_HISTORY_LIMIT)
        key, raw_limit = pairs[0]
        if key != "limit":
            return Result.err(
                _error(
                    "AGENT_RUN_HISTORY_LIMIT_INVALID",
                    "history query supports only the limit parameter.",
                    max_limit=_MAX_AGENT_HISTORY_LIMIT,
                )
            )
        try:
            limit = int(raw_limit)
        except (TypeError, ValueError):
            return Result.err(
                _error(
                    "AGENT_RUN_HISTORY_LIMIT_INVALID",
                    "history limit must be an integer.",
                    max_limit=_MAX_AGENT_HISTORY_LIMIT,
                )
            )
        if not 0 < limit <= _MAX_AGENT_HISTORY_LIMIT:
            return Result.err(
                _error(
                    "AGENT_RUN_HISTORY_LIMIT_INVALID",
                    "history limit is outside the configured range.",
                    max_limit=_MAX_AGENT_HISTORY_LIMIT,
                )
            )
        return Result.ok(limit)

    def _inspect_agent_history(self, agent_id: str, run_id: str) -> None:
        store = self.server.application.agent_run_store
        if store is None:
            self._write_error(
                503,
                _error(
                    "AGENT_RUN_STORE_UNAVAILABLE",
                    "No agent run store is configured.",
                ),
            )
            return
        limit_result = self._agent_history_limit()
        if limit_result.is_err():
            self._write_error(400, limit_result.unwrap_err())
            return
        history_method = getattr(store, "history", None)
        if not callable(history_method):
            self._write_error(
                501,
                _error(
                    "AGENT_RUN_HISTORY_UNAVAILABLE",
                    "The configured agent run store does not retain history.",
                ),
            )
            return
        current_result = store.load(run_id)
        if current_result.is_err():
            self._write_error(
                _status_for_error(current_result.unwrap_err()),
                current_result.unwrap_err(),
            )
            return
        current = current_result.unwrap()
        if current is None or current.agent_id != agent_id:
            self._write_error(
                404,
                _error("AGENT_RUN_NOT_FOUND", "Agent run was not found."),
            )
            return
        history_result = history_method(run_id)
        if history_result.is_err():
            self._write_error(
                _status_for_error(history_result.unwrap_err()),
                history_result.unwrap_err(),
            )
            return
        snapshots = history_result.unwrap()
        if not isinstance(snapshots, list) or any(
            not isinstance(item, AgentRunCheckpoint)
            or item.run_id != run_id
            or item.agent_id != agent_id
            for item in snapshots
        ):
            self._write_error(
                500,
                _error(
                    "AGENT_RUN_HISTORY_INVALID",
                    "Agent run history failed identity validation.",
                ),
            )
            return
        selected = snapshots[-limit_result.unwrap() :]
        self._write_json(
            200,
            {"history": [_agent_checkpoint_history_to_dict(item) for item in selected]},
        )

    def _resume_agent(self, agent_id: str, run_id: str) -> None:
        self._discard_bounded_request_body()
        registry = self.server.application.agent_registry
        if registry is None:
            self._write_error(
                503,
                _error(
                    "AGENT_REGISTRY_UNAVAILABLE",
                    "No agent registry is configured.",
                ),
            )
            return
        result = registry.resume(agent_id, run_id)
        if result.is_err():
            self._write_error(
                _status_for_error(result.unwrap_err()), result.unwrap_err()
            )
            return
        self._write_json(200, {"run": _agent_run_to_dict(result.unwrap())})

    def _cancel_agent(self, agent_id: str, run_id: str) -> None:
        self._discard_bounded_request_body()
        registry = self.server.application.agent_registry
        if registry is None:
            self._write_error(
                503,
                _error(
                    "AGENT_REGISTRY_UNAVAILABLE",
                    "No agent registry is configured.",
                ),
            )
            return
        result = registry.cancel(agent_id, run_id)
        if result.is_err():
            self._write_error(
                _status_for_error(result.unwrap_err()), result.unwrap_err()
            )
            return
        self._write_json(200, {"run": _agent_run_to_dict(result.unwrap())})

    def _handoff_route(self, method: str, path: Tuple[str, ...]) -> bool:
        store = self.server.application.handoff_store
        if not path or path[0:2] != ("v1", "handoffs"):
            return False
        if store is None:
            self._write_error(
                503,
                _error(
                    "HANDOFF_STORE_UNAVAILABLE",
                    "No handoff store is configured.",
                ),
            )
            return True
        if method == "POST" and path == ("v1", "handoffs"):
            self._create_handoff(store)
            return True
        if method == "GET" and len(path) == 4 and path[3] == "result":
            self._get_handoff_result(store, path[2])
            return True
        if method == "GET" and len(path) == 4 and path[2] == "open":
            try:
                limit = int(path[3])
            except ValueError:
                self._write_error(
                    400,
                    _error("HANDOFF_LIMIT_INVALID", "list limit must be an integer."),
                )
                return True
            result = store.list_open(limit)
            if result.is_err():
                self._write_error(
                    _status_for_error(result.unwrap_err()), result.unwrap_err()
                )
                return True
            self._write_json(
                200,
                {"handoffs": [_handoff_to_dict(record) for record in result.unwrap()]},
            )
            return True
        if method == "GET" and len(path) == 3:
            result = store.get(path[2])
            if result.is_err():
                self._write_error(
                    _status_for_error(result.unwrap_err()), result.unwrap_err()
                )
                return True
            record = result.unwrap()
            if record is None:
                self._write_error(
                    404, _error("HANDOFF_NOT_FOUND", "handoff was not found.")
                )
                return True
            self._write_json(200, {"handoff": _handoff_to_dict(record)})
            return True
        if (
            method == "POST"
            and len(path) == 4
            and path[3]
            in {
                "accept",
                "complete",
                "fail",
            }
        ):
            self._mutate_handoff(store, path[2], path[3])
            return True
        self._write_error(404, _error("NOT_FOUND", "Handoff route was not found."))
        return True

    def _create_handoff(self, store: HandoffStore) -> None:
        body = self._read_body()
        raw_record = body.get("record")
        if not isinstance(raw_record, Mapping):
            self._write_error(
                400,
                _error("HANDOFF_RECORD_INVALID", "record must be an object."),
            )
            return
        try:
            record = HandoffRecord.from_dict(raw_record)
        except (TypeError, ValueError, KeyError):
            self._write_error(
                400,
                _error("HANDOFF_RECORD_INVALID", "record is not a valid handoff."),
            )
            return
        result = store.create(record)
        self._write_handoff_result(result, success_status=201)

    def _mutate_handoff(
        self, store: HandoffStore, handoff_id: str, action: str
    ) -> None:
        body = self._read_body()
        target_agent_id = cast(str, body.get("target_agent_id"))
        if action == "accept":
            result = store.accept(handoff_id, target_agent_id)
        elif action == "complete":
            raw_result = body.get("result")
            if raw_result is not None and not isinstance(raw_result, Mapping):
                self._write_error(
                    400,
                    _error(
                        "HANDOFF_RESULT_INVALID",
                        "result must be an object or null.",
                    ),
                )
                return
            result = store.complete(
                handoff_id,
                target_agent_id,
                cast(str, body.get("target_goal_id")),
                result=cast(Optional[Mapping[str, Any]], raw_result),
            )
        else:
            result = store.fail(
                handoff_id, target_agent_id, cast(str, body.get("error_type"))
            )
        self._write_handoff_result(result, success_status=200)

    def _get_handoff_result(self, store: HandoffStore, handoff_id: str) -> None:
        result = store.get(handoff_id)
        if result.is_err():
            self._write_error(
                _status_for_error(result.unwrap_err()), result.unwrap_err()
            )
            return
        record = result.unwrap()
        if record is None:
            self._write_error(
                404, _error("HANDOFF_NOT_FOUND", "handoff was not found.")
            )
            return
        if record.status != "completed" or record.result is None:
            self._write_error(
                409,
                _error(
                    "HANDOFF_RESULT_UNAVAILABLE",
                    "a completed handoff result is not available.",
                ),
            )
            return
        self._write_json(
            200,
            {"handoff": _handoff_result_to_dict(record)},
        )

    def _write_handoff_result(
        self, result: Result[HandoffRecord, Error], *, success_status: int
    ) -> None:
        if result.is_err():
            error = result.unwrap_err()
            self._write_error(_status_for_error(error), error)
            return
        self._write_json(success_status, {"handoff": _handoff_to_dict(result.unwrap())})

    def _resume(self, workflow_name: str, run_id: str) -> None:
        body = self._read_body()
        result = self.server.application.registry.resume(
            workflow_name, run_id, resume_value=body.get("value")
        )
        self._write_result(result, success_status=200)

    def _inspect(self, workflow_name: str, run_id: str) -> None:
        result = self.server.application.registry.inspect(workflow_name, run_id)
        if result.is_err():
            self._write_error(
                _status_for_error(result.unwrap_err()), result.unwrap_err()
            )
            return
        run = result.unwrap()
        if run is None:
            self._write_error(
                404, _error("RUN_NOT_FOUND", "Workflow run was not found.")
            )
            return
        self._write_json(200, {"run": _run_to_dict(run)})

    def _write_result(
        self, result: Result[WorkflowRun, Error], *, success_status: int
    ) -> None:
        if result.is_err():
            error = result.unwrap_err()
            self._write_error(_status_for_error(error), error)
            return
        self._write_json(success_status, {"run": _run_to_dict(result.unwrap())})

    def _write_error(self, status: int, error: Error) -> None:
        self._write_json(status, {"error": error})

    def _write_json(
        self,
        status: int,
        payload: Dict[str, Any],
        *,
        extra_headers: Optional[Mapping[str, str]] = None,
    ) -> None:
        try:
            encoded = json.dumps(
                payload,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8")
        except (TypeError, ValueError):
            status = 500
            encoded = (
                b'{"error":{"errorType":"INTERNAL_ERROR",'
                b'"message":"Response could not be encoded."}}'
            )
        if len(encoded) > self.server.application.max_response_bytes:
            status = 500
            encoded = (
                b'{"error":{"errorType":"RESPONSE_TOO_LARGE",'
                b'"message":"Response exceeds the configured byte limit."}}'
            )
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Connection", "close")
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.close_connection = True
        self.wfile.write(encoded)
        self.wfile.flush()


class _ResponseWritten(Exception):
    """Internal control flow after a bounded request error was written."""


class RunServer:
    """Loopback-only HTTP server for configured workflow and event runs."""

    def __init__(
        self,
        registry: WorkflowRegistry,
        *,
        host: str = "127.0.0.1",
        port: int = 0,
        max_body_bytes: int = _DEFAULT_MAX_BODY_BYTES,
        max_response_bytes: int = _DEFAULT_MAX_RESPONSE_BYTES,
        auth_token: Optional[str] = None,
        auth_principal: Optional[Principal] = None,
        approval_store: Optional[ApprovalStore] = None,
        human_input_store: Optional[HumanInputStore] = None,
        agent_registry: Optional[AgentRegistry] = None,
        agent_run_store: Optional[AgentRunStore] = None,
        handoff_store: Optional[HandoffStore] = None,
        event_stream: Optional[EventStream] = None,
        event_deduplication_store: Optional[EventDeduplicationStore] = None,
    ) -> None:
        if not isinstance(registry, WorkflowRegistry):
            raise TypeError("registry must be a WorkflowRegistry")
        if not isinstance(host, str) or not host:
            raise ValueError("host must be a non-empty string")
        if host not in {"localhost", "127.0.0.1"}:
            try:
                is_loopback = ipaddress.ip_address(host).is_loopback
            except ValueError as exc:
                raise ValueError("RunServer only binds to loopback hosts") from exc
            if not is_loopback or host != "127.0.0.1":
                raise ValueError("RunServer only binds to loopback hosts")
        if (
            not isinstance(port, int)
            or isinstance(port, bool)
            or not 0 <= port <= 65_535
        ):
            raise ValueError("port must be between 0 and 65535")
        limits = (max_body_bytes, max_response_bytes)
        if any(
            not isinstance(value, int) or isinstance(value, bool) or value <= 0
            for value in limits
        ):
            raise ValueError("server limits must be positive integers")
        _validate_auth_token(auth_token)
        if auth_principal is not None and not isinstance(auth_principal, Principal):
            raise TypeError("auth_principal must be a Principal")
        if auth_principal is not None and auth_token is None:
            raise ValueError("auth_token is required when auth_principal is configured")
        if approval_store is not None:
            if auth_token is None:
                raise ValueError(
                    "auth_token is required when approval_store is configured"
                )
            approval_required_methods = ("get", "list_pending", "decide")
            if any(
                not callable(getattr(approval_store, name, None))
                for name in approval_required_methods
            ):
                raise TypeError(
                    "approval_store must implement get, list_pending, and decide"
                )
        if human_input_store is not None:
            if auth_token is None:
                raise ValueError(
                    "auth_token is required when human_input_store is configured"
                )
            required_methods = ("get", "list_pending", "respond", "reject", "consume")
            if any(
                not callable(getattr(human_input_store, name, None))
                for name in required_methods
            ):
                raise TypeError(
                    "human_input_store must implement get, list_pending, respond, "
                    "reject, and consume"
                )
        if agent_registry is not None:
            if not isinstance(agent_registry, AgentRegistry):
                raise TypeError("agent_registry must be an AgentRegistry")
            if auth_token is None:
                raise ValueError(
                    "auth_token is required when agent_registry is configured"
                )
        if agent_run_store is not None:
            if auth_token is None:
                raise ValueError(
                    "auth_token is required when agent_run_store is configured"
                )
            if not callable(getattr(agent_run_store, "load", None)):
                raise TypeError("agent_run_store must implement load")
        if handoff_store is not None:
            if auth_token is None:
                raise ValueError(
                    "auth_token is required when handoff_store is configured"
                )
            handoff_required_methods = (
                "create",
                "get",
                "accept",
                "complete",
                "fail",
                "list_open",
            )
            if any(
                not callable(getattr(handoff_store, name, None))
                for name in handoff_required_methods
            ):
                raise TypeError(
                    "handoff_store must implement create, get, accept, complete, "
                    "fail, and list_open"
                )
        if event_stream is not None:
            if auth_token is None:
                raise ValueError(
                    "auth_token is required when event_stream is configured"
                )
            if any(
                not callable(getattr(event_stream, name, None))
                for name in ("publish", "read")
            ):
                raise TypeError("event_stream must implement publish and read")
        if event_deduplication_store is not None:
            if event_stream is None:
                raise ValueError(
                    "event_stream is required when event deduplication is configured"
                )
            if auth_token is None:
                raise ValueError(
                    "auth_token is required when event deduplication is configured"
                )
            dedup_required_methods = ("claim", "complete", "abort")
            if any(
                not callable(getattr(event_deduplication_store, name, None))
                for name in dedup_required_methods
            ):
                raise TypeError(
                    "event_deduplication_store must implement claim, complete, and abort"
                )
        self.registry = registry
        self.host = host
        self.port = port
        self.max_body_bytes = max_body_bytes
        self.max_response_bytes = max_response_bytes
        self._auth_token = auth_token
        self._auth_principal = auth_principal
        self.approval_store = approval_store
        self.human_input_store = human_input_store
        self.agent_registry = agent_registry
        self.agent_run_store = agent_run_store
        self.handoff_store = handoff_store
        self.event_stream = event_stream
        self.event_deduplication_store = event_deduplication_store
        self._server: Optional[_MAPLEHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    @property
    def auth_token(self) -> Optional[str]:
        """Return the configured bearer token without exposing a setter."""
        return self._auth_token

    @property
    def principal(self) -> Optional[Principal]:
        """Return the host-configured bearer principal scope policy."""
        return self._auth_principal

    @property
    def auth_principal(self) -> Optional[Principal]:
        """Return the configured principal without exposing a setter."""
        return self._auth_principal

    @property
    def url(self) -> str:
        """Return the bound base URL after `start`; otherwise raise."""
        if self._server is None:
            raise RuntimeError("RunServer has not been started")
        address = self._server.server_address
        return f"http://{self.host}:{address[1]}"

    def start(self) -> str:
        """Start a daemon request thread and return the bound base URL."""
        if self._server is not None:
            raise RuntimeError("RunServer is already started")
        self._server = _MAPLEHTTPServer((self.host, self.port), _RequestHandler, self)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="maple-run-server",
            daemon=True,
        )
        self._thread.start()
        return self.url

    def close(self) -> None:
        """Stop request handling and release the bound socket."""
        server = self._server
        if server is None:
            return
        server.shutdown()
        server.server_close()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=5)
        self._server = None
        self._thread = None

    def __enter__(self) -> "RunServer":
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.close()


class RunClient:
    """Bounded dependency-free client for the MAPLE workflow HTTP contract.

    The client can target a loopback ``RunServer`` or a separately hosted
    implementation of the same contract. It performs no retries and never
    embeds credentials in URLs; callers own transport retry and idempotency
    policy for remote side effects.
    """

    def __init__(
        self,
        base_url: str,
        *,
        auth_token: Optional[str] = None,
        timeout_seconds: float = _DEFAULT_CLIENT_TIMEOUT_SECONDS,
        max_body_bytes: int = _DEFAULT_MAX_BODY_BYTES,
        max_response_bytes: int = _DEFAULT_MAX_RESPONSE_BYTES,
    ) -> None:
        if not isinstance(base_url, str) or not base_url.strip():
            raise ValueError("base_url must be a non-empty URL")
        if any(
            ord(character) < 0x20 or ord(character) == 0x7F for character in base_url
        ):
            raise ValueError("base_url must not contain control characters")
        parsed = urlsplit(base_url.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("base_url must use http or https and include a host")
        if not parsed.hostname:
            raise ValueError("base_url must include a host")
        hostname = parsed.hostname.lower()
        is_loopback = hostname == "localhost"
        if not is_loopback:
            try:
                is_loopback = ipaddress.ip_address(hostname).is_loopback
            except ValueError:
                is_loopback = False
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("base_url must not include user information")
        if parsed.query or parsed.fragment:
            raise ValueError("base_url must not include a query or fragment")
        _validate_auth_token(auth_token)
        if (
            not isinstance(timeout_seconds, (int, float))
            or isinstance(timeout_seconds, bool)
            or timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds must be a positive number")
        if (
            not isinstance(max_body_bytes, int)
            or isinstance(max_body_bytes, bool)
            or max_body_bytes <= 0
        ):
            raise ValueError("max_body_bytes must be a positive integer")
        if (
            not isinstance(max_response_bytes, int)
            or isinstance(max_response_bytes, bool)
            or max_response_bytes <= 0
        ):
            raise ValueError("max_response_bytes must be a positive integer")
        if auth_token is not None and parsed.scheme != "https" and not is_loopback:
            raise ValueError("authenticated non-loopback transport requires https")
        self.base_url = urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", "")
        )
        self.auth_token = auth_token
        self.timeout_seconds = float(timeout_seconds)
        self.max_body_bytes = max_body_bytes
        self.max_response_bytes = max_response_bytes

    def healthz(self) -> Result[Dict[str, Any], Error]:
        """Check the remote workflow service health endpoint."""
        return self._request("GET", ("healthz",))

    def run(
        self,
        workflow_name: str,
        state: Mapping[str, Any],
        *,
        run_id: Optional[str] = None,
    ) -> Result[Dict[str, Any], Error]:
        """Start a workflow run and return the remote response envelope."""
        if not isinstance(state, Mapping):
            return Result.err(_error("INVALID_STATE", "Run state must be an object."))
        if run_id is not None and not isinstance(run_id, str):
            return Result.err(_error("INVALID_IDENTIFIER", "run_id must be a string."))
        body: Dict[str, Any] = {"state": dict(state)}
        if run_id is not None:
            body["run_id"] = run_id
        return self._request("POST", ("v1", "workflows", workflow_name, "runs"), body)

    def run_agent(
        self,
        agent_id: str,
        task: str,
        context: Optional[Mapping[str, Any]] = None,
        *,
        session_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> Result[Dict[str, Any], Error]:
        """Invoke one remote host-owned agent handler without retrying."""
        identifier_error = _validate_agent_identifier(agent_id, "agent_id")
        if identifier_error is not None:
            return Result.err(identifier_error)
        task_result = _normalize_agent_task(task)
        if task_result.is_err():
            return Result.err(task_result.unwrap_err())
        context_result = _normalize_agent_context(context)
        if context_result.is_err():
            return Result.err(context_result.unwrap_err())
        if session_id is not None:
            session_error = _validate_agent_identifier(session_id, "session_id")
            if session_error is not None:
                return Result.err(session_error)
        if run_id is not None:
            run_error = _validate_agent_identifier(run_id, "run_id")
            if run_error is not None:
                return Result.err(run_error)
        body: Dict[str, Any] = {
            "task": task_result.unwrap(),
            "context": context_result.unwrap(),
        }
        if session_id is not None:
            body["session_id"] = session_id
        if run_id is not None:
            body["run_id"] = run_id
        return self._request("POST", ("v1", "agents", agent_id, "runs"), body)

    def publish_event(
        self,
        event_type: str,
        payload: Any,
        *,
        run_id: Optional[str] = None,
    ) -> Result[Dict[str, Any], Error]:
        """Publish one bounded event to a remote host-owned event stream."""
        input_error = _validate_event_input(event_type, run_id)
        if input_error is not None:
            return Result.err(input_error)
        body: Dict[str, Any] = {"event_type": event_type, "payload": payload}
        if run_id is not None:
            body["run_id"] = run_id
        return self._request("POST", ("v1", "events"), body)

    def publish_events(
        self,
        events: Sequence[Mapping[str, Any]],
        *,
        source_id: Optional[str] = None,
    ) -> Result[Dict[str, Any], Error]:
        """Publish up to 100 events and return indexed per-item outcomes.

        When ``source_id`` is supplied, each event must also contain a positive
        source ``sequence`` for an explicitly configured deduplication store.
        """
        if source_id is not None:
            source_error = validate_event_source_id(source_id)
            if source_error is not None:
                return Result.err(source_error)
        if (
            not isinstance(events, (list, tuple))
            or not events
            or len(events) > _MAX_EVENT_BATCH_ITEMS
        ):
            return Result.err(
                _error(
                    "EVENT_BATCH_INVALID",
                    "events must contain between 1 and 100 items.",
                    max_items=_MAX_EVENT_BATCH_ITEMS,
                )
            )
        normalized = []
        for index, item in enumerate(events):
            if not isinstance(item, Mapping):
                return Result.err(
                    _error(
                        "EVENT_BATCH_INVALID",
                        "each event must be an object.",
                        index=index,
                    )
                )
            if "event_type" not in item or "payload" not in item:
                return Result.err(
                    _error(
                        "EVENT_BATCH_INVALID",
                        "event_type and payload are required for each event.",
                        index=index,
                    )
                )
            input_error = _validate_event_input(item["event_type"], item.get("run_id"))
            if input_error is not None:
                input_error["details"] = {
                    **input_error.get("details", {}),
                    "index": index,
                }
                return Result.err(input_error)
            normalized_item: Dict[str, Any] = {
                "event_type": item["event_type"],
                "payload": item["payload"],
            }
            if source_id is not None:
                source_sequence = item.get("sequence")
                if (
                    not isinstance(source_sequence, int)
                    or isinstance(source_sequence, bool)
                    or source_sequence <= 0
                ):
                    return Result.err(
                        _error(
                            "EVENT_SOURCE_SEQUENCE_INVALID",
                            "sequence must be a positive integer when source_id is provided.",
                            index=index,
                        )
                    )
                normalized_item["sequence"] = source_sequence
            if item.get("run_id") is not None:
                normalized_item["run_id"] = item["run_id"]
            normalized.append(normalized_item)
        body: Dict[str, Any] = {"events": normalized}
        if source_id is not None:
            body["source_id"] = source_id
        return self._request("POST", ("v1", "events", "batch"), body)

    def read_events(
        self,
        cursor: Optional[EventCursor] = None,
        *,
        limit: Optional[int] = None,
    ) -> Result[Dict[str, Any], Error]:
        """Read a bounded redacted batch from a remote event stream."""
        if cursor is not None and not isinstance(cursor, EventCursor):
            return Result.err(_error("EVENT_CURSOR_INVALID", "cursor is invalid."))
        if limit is not None and (
            not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0
        ):
            return Result.err(
                _error("EVENT_QUERY_INVALID", "limit must be a positive integer.")
            )
        query: Dict[str, str] = {}
        if cursor is not None:
            query["after"] = str(cursor.sequence)
        if limit is not None:
            query["limit"] = str(limit)
        return self._request("GET", ("v1", "events"), query=query)

    def inspect_agent_run(
        self, agent_id: str, run_id: str
    ) -> Result[Dict[str, Any], Error]:
        """Inspect a redacted durable agent-run checkpoint summary."""
        identifier_error = _validate_agent_identifier(agent_id, "agent_id")
        if identifier_error is not None:
            return Result.err(identifier_error)
        run_error = _validate_agent_identifier(run_id, "run_id")
        if run_error is not None:
            return Result.err(run_error)
        return self._request("GET", ("v1", "agents", agent_id, "runs", run_id))

    def inspect_agent_run_history(
        self,
        agent_id: str,
        run_id: str,
        *,
        limit: int = _MAX_AGENT_HISTORY_LIMIT,
    ) -> Result[Dict[str, Any], Error]:
        """Inspect bounded metadata-only history for one durable agent run."""
        identifier_error = _validate_agent_identifier(agent_id, "agent_id")
        if identifier_error is not None:
            return Result.err(identifier_error)
        run_error = _validate_agent_identifier(run_id, "run_id")
        if run_error is not None:
            return Result.err(run_error)
        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or not 0 < limit <= _MAX_AGENT_HISTORY_LIMIT
        ):
            return Result.err(
                _error(
                    "AGENT_RUN_HISTORY_LIMIT_INVALID",
                    "history limit is outside the configured range.",
                    max_limit=_MAX_AGENT_HISTORY_LIMIT,
                )
            )
        return self._request(
            "GET",
            ("v1", "agents", agent_id, "runs", run_id, "history"),
            query={"limit": str(limit)},
        )

    def resume_agent_run(
        self, agent_id: str, run_id: str
    ) -> Result[Dict[str, Any], Error]:
        """Resume one durable agent run through the host callback seam."""
        identifier_error = _validate_agent_identifier(agent_id, "agent_id")
        if identifier_error is not None:
            return Result.err(identifier_error)
        run_error = _validate_agent_identifier(run_id, "run_id")
        if run_error is not None:
            return Result.err(run_error)
        return self._request(
            "POST", ("v1", "agents", agent_id, "runs", run_id, "resume"), {}
        )

    def cancel_agent_run(
        self, agent_id: str, run_id: str
    ) -> Result[Dict[str, Any], Error]:
        """Request cooperative cancellation through the host callback seam."""
        identifier_error = _validate_agent_identifier(agent_id, "agent_id")
        if identifier_error is not None:
            return Result.err(identifier_error)
        run_error = _validate_agent_identifier(run_id, "run_id")
        if run_error is not None:
            return Result.err(run_error)
        return self._request(
            "POST", ("v1", "agents", agent_id, "runs", run_id, "cancel"), {}
        )

    def list_pending_approvals(
        self, limit: int = _MAX_APPROVAL_LIMIT
    ) -> Result[Dict[str, Any], Error]:
        """List bounded pending approval requests from the remote host."""
        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or not 0 < limit <= _MAX_APPROVAL_LIMIT
        ):
            return Result.err(
                _error(
                    "APPROVAL_LIMIT_INVALID", "Approval list limit is out of bounds."
                )
            )
        return self._request("GET", ("v1", "approvals", "pending", str(limit)))

    def get_approval(self, approval_id: str) -> Result[Dict[str, Any], Error]:
        """Inspect one remote approval request."""
        return self._request("GET", ("v1", "approvals", approval_id))

    def decide_approval(
        self,
        approval_id: str,
        approved: bool,
        *,
        edited_arguments: Optional[Mapping[str, Any]] = None,
    ) -> Result[Dict[str, Any], Error]:
        """Record a bounded remote approval decision without consuming it."""
        if type(approved) is not bool:
            return Result.err(
                _error("APPROVAL_DECISION_INVALID", "approved must be boolean.")
            )
        if edited_arguments is not None and not isinstance(edited_arguments, Mapping):
            return Result.err(
                _error(
                    "APPROVAL_DECISION_INVALID",
                    "edited_arguments must be an object or null.",
                )
            )
        payload: Dict[str, Any] = {"approved": approved}
        if edited_arguments is not None:
            payload["edited_arguments"] = dict(edited_arguments)
        return self._request(
            "POST", ("v1", "approvals", approval_id, "decide"), payload
        )

    def create_handoff(self, record: HandoffRecord) -> Result[Dict[str, Any], Error]:
        """Create or idempotently retrieve a remote digest-only handoff record."""
        if not isinstance(record, HandoffRecord):
            return Result.err(
                _error("HANDOFF_RECORD_INVALID", "record must be a HandoffRecord.")
            )
        return self._request("POST", ("v1", "handoffs"), {"record": record.to_dict()})

    def get_handoff(self, handoff_id: str) -> Result[Dict[str, Any], Error]:
        """Inspect one remote digest-only handoff record."""
        return self._request("GET", ("v1", "handoffs", handoff_id))

    def list_open_handoffs(
        self, limit: int = _MAX_HANDOFF_LIMIT
    ) -> Result[Dict[str, Any], Error]:
        """List bounded pending or accepted remote handoff records."""
        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or not 0 < limit <= _MAX_HANDOFF_LIMIT
        ):
            return Result.err(
                _error("HANDOFF_LIMIT_INVALID", "list limit is out of bounds.")
            )
        return self._request("GET", ("v1", "handoffs", "open", str(limit)))

    def accept_handoff(
        self, handoff_id: str, target_agent_id: str
    ) -> Result[Dict[str, Any], Error]:
        """Transfer a pending handoff to its target owner."""
        return self._request(
            "POST",
            ("v1", "handoffs", handoff_id, "accept"),
            {"target_agent_id": target_agent_id},
        )

    def complete_handoff(
        self,
        handoff_id: str,
        target_agent_id: str,
        target_goal_id: str,
        *,
        result: Optional[Mapping[str, Any]] = None,
    ) -> Result[Dict[str, Any], Error]:
        """Complete an accepted handoff and optionally deliver its result."""
        if result is not None and not isinstance(result, Mapping):
            return Result.err(
                _error(
                    "HANDOFF_RESULT_INVALID",
                    "result must be an object or null.",
                )
            )
        payload: Dict[str, Any] = {
            "target_agent_id": target_agent_id,
            "target_goal_id": target_goal_id,
        }
        if result is not None:
            payload["result"] = dict(result)
        return self._request(
            "POST",
            ("v1", "handoffs", handoff_id, "complete"),
            payload,
        )

    def get_handoff_result(self, handoff_id: str) -> Result[Dict[str, Any], Error]:
        """Retrieve one completed handoff result through its scoped route."""
        if (
            not isinstance(handoff_id, str)
            or not handoff_id
            or len(handoff_id) > 256
            or any(ord(char) < 32 for char in handoff_id)
        ):
            return Result.err(
                _error(
                    "HANDOFF_INPUT_INVALID",
                    "handoff_id must be bounded text.",
                )
            )
        return self._request("GET", ("v1", "handoffs", handoff_id, "result"))

    def fail_handoff(
        self, handoff_id: str, target_agent_id: str, error_type: str
    ) -> Result[Dict[str, Any], Error]:
        """Fail an accepted handoff and return ownership to its source."""
        return self._request(
            "POST",
            ("v1", "handoffs", handoff_id, "fail"),
            {"target_agent_id": target_agent_id, "error_type": error_type},
        )

    def resume(
        self,
        workflow_name: str,
        run_id: str,
        *,
        resume_value: Any = None,
    ) -> Result[Dict[str, Any], Error]:
        """Resume a paused workflow run."""
        return self._request(
            "POST",
            ("v1", "workflows", workflow_name, "runs", run_id, "resume"),
            {"value": resume_value},
        )

    def inspect(self, workflow_name: str, run_id: str) -> Result[Dict[str, Any], Error]:
        """Inspect a persisted workflow run."""
        return self._request("GET", ("v1", "workflows", workflow_name, "runs", run_id))

    def list_pending_human_input(
        self, limit: int = 100
    ) -> Result[Dict[str, Any], Error]:
        """List bounded pending human-input requests from the remote host."""
        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or not 0 < limit <= _MAX_HUMAN_INPUT_LIMIT
        ):
            return Result.err(
                _error(
                    "HUMAN_INPUT_LIMIT_INVALID",
                    "Human input list limit is out of bounds.",
                )
            )
        return self._request("GET", ("v1", "interactions", "pending", str(limit)))

    def get_human_input(self, interaction_id: str) -> Result[Dict[str, Any], Error]:
        """Inspect one remote human-input request."""
        return self._request("GET", ("v1", "interactions", interaction_id))

    def respond_human_input(
        self,
        interaction_id: str,
        response: Any,
        *,
        actor_id: Optional[str] = None,
    ) -> Result[Dict[str, Any], Error]:
        """Submit a schema-validated remote human-input response."""
        payload: Dict[str, Any] = {"response": response}
        if actor_id is not None:
            payload["actor_id"] = actor_id
        return self._request(
            "POST", ("v1", "interactions", interaction_id, "respond"), payload
        )

    def reject_human_input(
        self,
        interaction_id: str,
        reason: str = "Operator rejected the request.",
        *,
        actor_id: Optional[str] = None,
    ) -> Result[Dict[str, Any], Error]:
        """Reject a remote human-input request with a bounded reason."""
        payload: Dict[str, Any] = {"reason": reason}
        if actor_id is not None:
            payload["actor_id"] = actor_id
        return self._request(
            "POST", ("v1", "interactions", interaction_id, "reject"), payload
        )

    def continue_human_input(
        self,
        interaction_id: str,
        prompt: str,
        input_schema: Mapping[str, Any],
        *,
        actor_id: Optional[str] = None,
    ) -> Result[Dict[str, Any], Error]:
        """Open the next bounded round for a remote human-input request."""
        if not isinstance(input_schema, Mapping):
            return Result.err(
                _error(
                    "REQUEST_BODY_INVALID",
                    "input_schema must be an object.",
                )
            )
        if actor_id is not None and not isinstance(actor_id, str):
            return Result.err(
                _error(
                    "HUMAN_INPUT_IDENTIFIER_INVALID",
                    "actor_id must be a string.",
                )
            )
        payload: Dict[str, Any] = {"prompt": prompt, "input_schema": dict(input_schema)}
        if actor_id is not None:
            payload["actor_id"] = actor_id
        return self._request(
            "POST", ("v1", "interactions", interaction_id, "continue"), payload
        )

    def consume_human_input(self, interaction_id: str) -> Result[Dict[str, Any], Error]:
        """Consume a decided remote human-input request exactly once."""
        return self._request(
            "POST", ("v1", "interactions", interaction_id, "consume"), {}
        )

    def _request(
        self,
        method: str,
        segments: Tuple[str, ...],
        payload: Optional[Dict[str, Any]] = None,
        *,
        query: Optional[Mapping[str, str]] = None,
    ) -> Result[Dict[str, Any], Error]:
        if any(
            not isinstance(segment, str) or not segment or segment in {".", ".."}
            for segment in segments
        ):
            return Result.err(
                _error("INVALID_IDENTIFIER", "Path segments are invalid.")
            )
        path = "/".join(quote(segment, safe="") for segment in segments)
        url = f"{self.base_url}/{path}"
        if query is not None:
            if not isinstance(query, Mapping):
                return Result.err(
                    _error("REQUEST_QUERY_INVALID", "Request query is invalid.")
                )
            query_items = []
            for key, value in query.items():
                if not isinstance(key, str) or not key or not isinstance(value, str):
                    return Result.err(
                        _error("REQUEST_QUERY_INVALID", "Request query is invalid.")
                    )
                query_items.append((key, value))
            if query_items:
                url = f"{url}?{urlencode(query_items)}"
        if len(url.encode("utf-8")) > _MAX_PATH_BYTES:
            return Result.err(_error("PATH_TOO_LARGE", "Request path is too large."))
        data: Optional[bytes] = None
        headers = {"Accept": "application/json"}
        if self.auth_token is not None:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        if payload is not None:
            try:
                data = json.dumps(
                    payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")
                ).encode("utf-8")
            except (TypeError, ValueError):
                return Result.err(
                    _error(
                        "REQUEST_BODY_INVALID",
                        "Request payload is not JSON-compatible.",
                    )
                )
            if len(data) > self.max_body_bytes:
                return Result.err(
                    _error(
                        "REQUEST_TOO_LARGE",
                        "Request body exceeds the configured byte limit.",
                        max_bytes=self.max_body_bytes,
                    )
                )
            headers["Content-Type"] = "application/json"
        request = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return self._decode_response(response, int(response.status))
        except HTTPError as exc:
            decoded = self._decode_response(exc, int(exc.code))
            if decoded.is_ok():
                body = decoded.unwrap()
                error = body.get("error")
                if isinstance(error, dict):
                    return Result.err(error)
                return Result.err(
                    _error(
                        "REMOTE_HTTP_ERROR",
                        "Remote service returned an error.",
                        status=exc.code,
                    )
                )
            return Result.err(decoded.unwrap_err())
        except (URLError, TimeoutError, OSError):
            return Result.err(
                _error(
                    "TRANSPORT_ERROR",
                    "The remote workflow service could not be reached.",
                )
            )

    def _decode_response(
        self, response: Any, status: int
    ) -> Result[Dict[str, Any], Error]:
        raw_length = response.headers.get("Content-Length")
        if raw_length is not None:
            try:
                declared_length = int(raw_length)
            except (TypeError, ValueError):
                return Result.err(
                    _error(
                        "REMOTE_RESPONSE_INVALID", "Remote response length is invalid."
                    )
                )
            if declared_length < 0 or declared_length > self.max_response_bytes:
                return Result.err(
                    _error(
                        "RESPONSE_TOO_LARGE",
                        "Remote response exceeds the configured byte limit.",
                    )
                )
        try:
            raw = response.read(self.max_response_bytes + 1)
        except (OSError, TimeoutError):
            return Result.err(
                _error("TRANSPORT_ERROR", "The remote response could not be read.")
            )
        if len(raw) > self.max_response_bytes:
            return Result.err(
                _error(
                    "RESPONSE_TOO_LARGE",
                    "Remote response exceeds the configured byte limit.",
                )
            )
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return Result.err(
                _error("REMOTE_RESPONSE_INVALID", "Remote response is not valid JSON.")
            )
        if not isinstance(decoded, dict):
            return Result.err(
                _error("REMOTE_RESPONSE_INVALID", "Remote response must be an object.")
            )
        if status >= 400 and not isinstance(decoded.get("error"), dict):
            return Result.err(
                _error(
                    "REMOTE_HTTP_ERROR",
                    "Remote service returned an error.",
                    status=status,
                )
            )
        return Result.ok(decoded)


__all__ = [
    "AgentRegistry",
    "AgentRun",
    "AgentRunCancelHandler",
    "AgentRunHandler",
    "RunClient",
    "RunServer",
    "WorkflowRegistry",
]
