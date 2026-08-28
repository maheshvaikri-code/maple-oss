"""Adapters for exposing native autonomous agents through the run transport."""

from __future__ import annotations

import json
from typing import Any, Mapping, Optional, Protocol

from ..core.result import Result
from .runs import AgentRunStore
from .server import AgentRegistry, AgentRun, AgentRunCancelHandler, Error

_AGENT_RUN_STATUSES = frozenset({"cancelled", "completed", "paused", "failed"})


class _AutonomousAgentLike(Protocol):
    agent_id: str

    def set_run_store(self, store: Optional[AgentRunStore]) -> None: ...

    def pursue_goal_with_context(
        self,
        description: str,
        context: Mapping[str, Any],
        *,
        session_id: Optional[str],
        run_id: Optional[str],
    ) -> Result[Any, Error]: ...

    def resume_run(
        self, run_id: str, *, cancellation: Optional[Any] = None
    ) -> Result[Any, Error]: ...


def _error(error_type: str, message: str, **details: Any) -> Error:
    error: Error = {"errorType": error_type, "message": message}
    if details:
        error["details"] = details
    return error


def _bounded_json(value: Any) -> Result[Any, Error]:
    """Copy one native goal result through a strict JSON boundary."""

    candidate = value
    model_dump = getattr(candidate, "model_dump", None)
    if candidate is not None and callable(model_dump):
        try:
            candidate = model_dump(mode="json")
        except (TypeError, ValueError):
            return Result.err(
                _error(
                    "AGENT_RUNTIME_RESULT_INVALID",
                    "Native agent result is not JSON-compatible.",
                )
            )
    elif candidate is not None:
        dictionary = getattr(candidate, "dict", None)
        if callable(dictionary):
            try:
                candidate = dictionary()
            except (TypeError, ValueError):
                return Result.err(
                    _error(
                        "AGENT_RUNTIME_RESULT_INVALID",
                        "Native agent result is not JSON-compatible.",
                    )
                )
    try:
        return Result.ok(
            json.loads(json.dumps(candidate, ensure_ascii=False, allow_nan=False))
        )
    except (TypeError, ValueError, OverflowError, json.JSONDecodeError):
        return Result.err(
            _error(
                "AGENT_RUNTIME_RESULT_INVALID",
                "Native agent result is not JSON-compatible.",
            )
        )


class AutonomousAgentRemoteAdapter:
    """Bind a native autonomous agent to the authenticated run registry.

    The adapter delegates checkpoint creation and recovery to the native
    agent. The supplied run store must also be passed to ``RunServer`` when
    the host wants remote inspection of the same checkpoints.
    """

    def __init__(
        self, agent: _AutonomousAgentLike, *, run_store: AgentRunStore
    ) -> None:
        agent_id = getattr(agent, "agent_id", None)
        if (
            not isinstance(agent_id, str)
            or not agent_id.strip()
            or len(agent_id.encode("utf-8")) > 256
            or any(ord(char) < 32 or ord(char) == 127 for char in agent_id)
        ):
            raise ValueError("agent must expose a bounded non-empty agent_id")
        if not all(
            callable(getattr(run_store, method, None)) for method in ("load", "save")
        ):
            raise TypeError("run_store must implement load and save")
        if not callable(getattr(agent, "set_run_store", None)):
            raise TypeError("agent must expose set_run_store")
        if not callable(getattr(agent, "pursue_goal_with_context", None)):
            raise TypeError("agent must expose pursue_goal_with_context")
        if not callable(getattr(agent, "resume_run", None)):
            raise TypeError("agent must expose resume_run")
        self.agent = agent
        self.agent_id = agent_id
        self.run_store = run_store
        agent.set_run_store(run_store)

    def _runtime_error(self, operation: str, run_id: str) -> Error:
        return _error(
            "AGENT_RUNTIME_ERROR",
            "Native autonomous agent execution failed.",
            agent_id=self.agent_id,
            operation=operation,
            run_id=run_id,
        )

    def _goal_to_run(
        self, operation_result: Result[Any, Error], *, operation: str, run_id: str
    ) -> Result[AgentRun, Error]:
        if operation_result.is_err():
            return Result.err(self._runtime_error(operation, run_id))
        goal = operation_result.unwrap()
        goal_run_id = getattr(goal, "run_id", None)
        status = getattr(goal, "status", None)
        if goal_run_id != run_id or status not in _AGENT_RUN_STATUSES:
            return Result.err(
                _error(
                    "AGENT_RUNTIME_RESULT_INVALID",
                    "Native autonomous agent returned an invalid run state.",
                    agent_id=self.agent_id,
                    operation=operation,
                )
            )
        if status in {"failed", "cancelled"}:
            error_type = (
                "AGENT_RUN_CANCELLED"
                if status == "cancelled"
                else "AGENT_RUNTIME_FAILED"
            )
            return Result.ok(
                AgentRun(
                    agent_id=self.agent_id,
                    run_id=run_id,
                    status=status,
                    result=None,
                    error=_error(
                        error_type,
                        "Native autonomous agent did not complete successfully.",
                    ),
                )
            )
        result = _bounded_json(getattr(goal, "result", None))
        if result.is_err():
            return Result.err(result.unwrap_err())
        return Result.ok(
            AgentRun(
                agent_id=self.agent_id,
                run_id=run_id,
                status=status,
                result=result.unwrap(),
                error=None,
            )
        )

    def _run(
        self,
        task: str,
        context: Mapping[str, Any],
        *,
        session_id: Optional[str],
        run_id: str,
    ) -> Result[AgentRun, Error]:
        try:
            result = self.agent.pursue_goal_with_context(
                task,
                context,
                session_id=session_id,
                run_id=run_id,
            )
        except Exception:
            return Result.err(self._runtime_error("invoke", run_id))
        return self._goal_to_run(result, operation="invoke", run_id=run_id)

    def _resume(self, run_id: str) -> Result[AgentRun, Error]:
        try:
            result = self.agent.resume_run(run_id)
        except Exception:
            return Result.err(self._runtime_error("resume", run_id))
        return self._goal_to_run(result, operation="resume", run_id=run_id)

    def register(
        self,
        registry: AgentRegistry,
        *,
        cancel_handler: Optional[AgentRunCancelHandler] = None,
    ) -> Result[None, Error]:
        """Register native invocation/resume callbacks with ``registry``."""
        if not isinstance(registry, AgentRegistry):
            raise TypeError("registry must be an AgentRegistry")
        return registry.register(
            self.agent_id,
            self._run,
            resume_handler=self._resume,
            cancel_handler=cancel_handler,
        )


__all__ = ["AutonomousAgentRemoteAdapter"]
