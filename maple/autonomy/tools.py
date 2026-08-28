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

import asyncio
import hashlib
import inspect
import json
import logging
import math
import re
import uuid
from dataclasses import dataclass, field
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Mapping,
    Optional,
    Sequence,
    Type,
    cast,
)

from ..core.result import Result
from ..llm.types import ToolDefinition
from .contracts import (
    Guardrail,
    run_guardrails,
    structured_model_schema,
    validate_json_schema,
    validate_typed_value,
)
from .execution import CancellationToken, ExecutionExecutor
from .handoffs import HandoffRecord, HandoffStore

if TYPE_CHECKING:
    from .agent import AutonomousAgent

logger = logging.getLogger(__name__)

MAX_HANDOFF_CONTEXT_KEYS = 32
MAX_HANDOFF_CONTEXT_ITEMS = 128
MAX_HANDOFF_CONTEXT_DEPTH = 8
MAX_HANDOFF_CONTEXT_STRING_LENGTH = 8_192
MAX_HANDOFF_CONTEXT_BYTES = 32_768
TOOL_REPLAY_DISABLED = "disabled"
TOOL_REPLAY_REUSE_SUCCESS = "reuse_success"
_CHILD_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")


def _callable_accepts_keyword(handler: Callable[..., Any], keyword: str) -> bool:
    """Return whether a callable accepts one named keyword argument."""
    try:
        signature = inspect.signature(handler)
    except (TypeError, ValueError):
        return False
    parameter = signature.parameters.get(keyword)
    if parameter is not None and parameter.kind in {
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        inspect.Parameter.KEYWORD_ONLY,
    }:
        return True
    return any(
        item.kind is inspect.Parameter.VAR_KEYWORD
        for item in signature.parameters.values()
    )


def _callable_accepts_cancellation(handler: Callable[..., Any]) -> bool:
    """Return whether a callable explicitly accepts the cancellation keyword."""
    return _callable_accepts_keyword(handler, "cancellation")


def _invoke_delegated(
    handler: Callable[..., Any],
    args: Sequence[Any],
    cancellation: Optional[CancellationToken],
    *,
    run_id: Optional[str] = None,
    handoff_id: Optional[str] = None,
) -> Any:
    """Invoke a child method with only signature-compatible control keywords."""
    kwargs: Dict[str, Any] = {}
    if run_id is not None and _callable_accepts_keyword(handler, "run_id"):
        kwargs["run_id"] = run_id
    if handoff_id is not None and _callable_accepts_keyword(handler, "handoff_id"):
        kwargs["handoff_id"] = handoff_id
    if cancellation is not None and _callable_accepts_cancellation(handler):
        kwargs["cancellation"] = cancellation
    return handler(*args, **kwargs)


def _child_run_id_error(value: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(value, str) or not _CHILD_RUN_ID_PATTERN.fullmatch(value):
        return {
            "errorType": "AGENT_TOOL_CHILD_RUN_ID_INVALID",
            "message": (
                "child_run_id must contain 1-128 letters, numbers, '_', '.', ':', "
                "or '-'."
            ),
        }
    return None


def _result_error_type(value: Any) -> Optional[str]:
    if not isinstance(value, Result) or value.is_ok():
        return None
    error = value.unwrap_err()
    if isinstance(error, Mapping) and isinstance(error.get("errorType"), str):
        return cast(str, error["errorType"])
    return None


def _delegation_cancelled(target_id: str) -> Result[Any, Dict[str, Any]]:
    """Return a bounded cancellation result without exposing child data."""
    return Result.err(
        {
            "errorType": "EXECUTION_CANCELLED",
            "message": "Delegated agent cancellation was requested.",
            "details": {"agent_id": target_id},
        }
    )


@dataclass(frozen=True)
class _PersistedHandoffStart:
    """State returned after creating or replaying one persisted handoff."""

    handoff_id: str
    replay_result: Optional[Dict[str, Any]] = None


def _handoff_context_error(message: str, **details: Any) -> Dict[str, Any]:
    error: Dict[str, Any] = {
        "errorType": "HANDOFF_CONTEXT_INVALID",
        "message": message,
    }
    if details:
        error["details"] = details
    return error


def _copy_handoff_value(
    value: Any, *, path: str, depth: int
) -> Result[Any, Dict[str, Any]]:
    if depth > MAX_HANDOFF_CONTEXT_DEPTH:
        return Result.err(
            _handoff_context_error("Handoff context is too deeply nested.", path=path)
        )
    if value is None or isinstance(value, (bool, int, str)):
        if isinstance(value, str) and len(value) > MAX_HANDOFF_CONTEXT_STRING_LENGTH:
            return Result.err(
                _handoff_context_error(
                    "Handoff context string exceeds the limit.", path=path
                )
            )
        return Result.ok(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            return Result.err(
                _handoff_context_error(
                    "Handoff context numbers must be finite.", path=path
                )
            )
        return Result.ok(value)
    if isinstance(value, Mapping):
        if len(value) > MAX_HANDOFF_CONTEXT_ITEMS:
            return Result.err(
                _handoff_context_error(
                    "Handoff context object exceeds the item limit.", path=path
                )
            )
        copied: Dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str) or not key or len(key) > 128:
                return Result.err(
                    _handoff_context_error(
                        "Handoff context keys must be bounded strings.", path=path
                    )
                )
            item_result = _copy_handoff_value(
                item, path=f"{path}.{key}", depth=depth + 1
            )
            if item_result.is_err():
                return Result.err(item_result.unwrap_err())
            copied[key] = item_result.unwrap()
        return Result.ok(copied)
    if isinstance(value, (list, tuple)):
        if len(value) > MAX_HANDOFF_CONTEXT_ITEMS:
            return Result.err(
                _handoff_context_error(
                    "Handoff context array exceeds the item limit.", path=path
                )
            )
        copied_list: List[Any] = []
        for index, item in enumerate(value):
            item_result = _copy_handoff_value(
                item, path=f"{path}[{index}]", depth=depth + 1
            )
            if item_result.is_err():
                return Result.err(item_result.unwrap_err())
            copied_list.append(item_result.unwrap())
        return Result.ok(copied_list)
    return Result.err(
        _handoff_context_error(
            "Handoff context must contain only JSON-compatible values.",
            path=path,
        )
    )


def _normalize_handoff_context(
    context: Optional[Mapping[str, Any]],
) -> Result[Dict[str, Any], Dict[str, Any]]:
    """Copy and bound context before it crosses an agent ownership boundary."""
    if context is None:
        return Result.ok({})
    if not isinstance(context, Mapping):
        return Result.err(_handoff_context_error("Handoff context must be an object."))
    if len(context) > MAX_HANDOFF_CONTEXT_KEYS:
        return Result.err(
            _handoff_context_error(
                "Handoff context exceeds the key limit.",
                max_keys=MAX_HANDOFF_CONTEXT_KEYS,
            )
        )
    copied = _copy_handoff_value(context, path="$", depth=0)
    if copied.is_err():
        return Result.err(copied.unwrap_err())
    normalized = copied.unwrap()
    if not isinstance(normalized, dict):
        return Result.err(_handoff_context_error("Handoff context must be an object."))
    try:
        encoded = json.dumps(normalized, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError, OverflowError):
        return Result.err(
            _handoff_context_error("Handoff context must be JSON serializable.")
        )
    if len(encoded.encode("utf-8")) > MAX_HANDOFF_CONTEXT_BYTES:
        return Result.err(
            _handoff_context_error(
                "Handoff context exceeds the byte limit.",
                max_bytes=MAX_HANDOFF_CONTEXT_BYTES,
            )
        )
    return Result.ok(normalized)


@dataclass
class Tool:
    """A tool that can be called by an autonomous agent.

    ``input_model`` and ``output_model`` optionally provide Pydantic-style
    typed boundaries. When omitted, the existing JSON-Schema contracts and
    handler values are preserved.
    """

    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema
    handler: Callable[..., Result[Any, Dict[str, Any]]]
    requires_approval: bool = False
    tags: List[str] = field(default_factory=list)
    result_schema: Optional[Dict[str, Any]] = None
    input_guardrails: List[Guardrail] = field(default_factory=list)
    output_guardrails: List[Guardrail] = field(default_factory=list)
    executor: Optional[ExecutionExecutor] = None
    input_model: Optional[Type[Any]] = None
    output_model: Optional[Type[Any]] = None
    async_handler: Optional[Callable[..., Awaitable[Result[Any, Dict[str, Any]]]]] = (
        None
    )
    replay_policy: str = TOOL_REPLAY_DISABLED
    accepts_cancellation: bool = False
    _input_model_schema: Optional[Dict[str, Any]] = field(
        default=None, init=False, repr=False
    )

    def __post_init__(self) -> None:
        """Validate typed model configuration once at tool registration time."""
        if not isinstance(self.replay_policy, str) or self.replay_policy not in {
            TOOL_REPLAY_DISABLED,
            TOOL_REPLAY_REUSE_SUCCESS,
        }:
            raise ValueError("replay_policy must be 'disabled' or 'reuse_success'")
        if not isinstance(self.accepts_cancellation, bool):
            raise ValueError("accepts_cancellation must be boolean")
        if self.accepts_cancellation and self.executor is not None:
            raise ValueError("accepts_cancellation cannot be combined with an executor")
        if self.input_model is not None:
            schema = structured_model_schema(self.input_model)
            if schema.is_err():
                raise ValueError(schema.unwrap_err()["message"])
            self._input_model_schema = schema.unwrap()
        if self.output_model is not None:
            schema = structured_model_schema(self.output_model)
            if schema.is_err():
                raise ValueError(schema.unwrap_err()["message"])

    def to_llm_definition(self) -> ToolDefinition:
        """Convert to LLM-compatible tool definition."""
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters=self._input_model_schema or self.parameters,
        )

    def _prepare_arguments(
        self, kwargs: Dict[str, Any]
    ) -> Result[Dict[str, Any], Dict[str, Any]]:
        """Validate and guard tool arguments before either execution path."""
        call_kwargs = kwargs
        if self.input_model is not None:
            input_validation = validate_typed_value(kwargs, self.input_model)
            if input_validation.is_err():
                return Result.err(
                    {
                        "errorType": "TOOL_INPUT_INVALID",
                        "message": f'Tool "{self.name}" received invalid arguments',
                        "details": input_validation.unwrap_err(),
                    }
                )
            model_value = input_validation.unwrap()
            dump = getattr(model_value, "model_dump", None)
            if not callable(dump):
                dump = getattr(model_value, "dict", None)
            if not callable(dump):
                return Result.err(
                    {
                        "errorType": "TOOL_INPUT_INVALID",
                        "message": f'Tool "{self.name}" model cannot produce arguments',
                    }
                )
            try:
                dumped = dump()
            except Exception as exc:
                return Result.err(
                    {
                        "errorType": "TOOL_INPUT_INVALID",
                        "message": f'Tool "{self.name}" model could not produce arguments',
                        "details": {"exception": type(exc).__name__},
                    }
                )
            if not isinstance(dumped, dict):
                return Result.err(
                    {
                        "errorType": "TOOL_INPUT_INVALID",
                        "message": f'Tool "{self.name}" model must produce an object',
                    }
                )
            call_kwargs = dumped
        else:
            input_validation = validate_json_schema(kwargs, self.parameters)
            if input_validation.is_err():
                return Result.err(
                    {
                        "errorType": "TOOL_INPUT_INVALID",
                        "message": f'Tool "{self.name}" received invalid arguments',
                        "details": input_validation.unwrap_err(),
                    }
                )
        input_guardrails = run_guardrails(
            call_kwargs, self.input_guardrails, stage=f"tool:{self.name}:input"
        )
        if input_guardrails.is_err():
            return Result.err(input_guardrails.unwrap_err())
        return Result.ok(call_kwargs)

    def _finish_result(self, result: Any) -> Result[Any, Dict[str, Any]]:
        """Validate and guard a handler result shared by sync/async paths."""
        if not isinstance(result, Result):
            return Result.err(
                {
                    "errorType": "TOOL_EXECUTION_ERROR",
                    "message": f'Tool "{self.name}" returned a non-Result value',
                }
            )
        if result.is_err():
            return result
        output = result.unwrap()
        if self.output_model is not None:
            output_validation = validate_typed_value(output, self.output_model)
        else:
            output_validation = validate_json_schema(output, self.result_schema)
        if output_validation.is_err():
            return Result.err(
                {
                    "errorType": "TOOL_OUTPUT_INVALID",
                    "message": f'Tool "{self.name}" returned invalid output',
                    "details": output_validation.unwrap_err(),
                }
            )
        if self.output_model is not None:
            output = output_validation.unwrap()
            result = Result.ok(output)
        output_guardrails = run_guardrails(
            output, self.output_guardrails, stage=f"tool:{self.name}:output"
        )
        if output_guardrails.is_err():
            return Result.err(output_guardrails.unwrap_err())
        return cast(Result[Any, Dict[str, Any]], result)

    def execute(
        self,
        *,
        cancellation: Optional[CancellationToken] = None,
        **kwargs: Any,
    ) -> Result[Any, Dict[str, Any]]:
        """Execute this tool with the given arguments."""
        if cancellation is not None and not isinstance(cancellation, CancellationToken):
            return Result.err(
                {
                    "errorType": "EXECUTION_CANCELLATION_INVALID",
                    "message": "cancellation must be a CancellationToken or None.",
                }
            )
        if cancellation is not None and cancellation.is_cancelled():
            return Result.err(
                {
                    "errorType": "EXECUTION_CANCELLED",
                    "message": f'Tool "{self.name}" cancellation was requested.',
                }
            )
        call_kwargs = kwargs
        if self.input_model is not None:
            input_validation = validate_typed_value(kwargs, self.input_model)
            if input_validation.is_err():
                return Result.err(
                    {
                        "errorType": "TOOL_INPUT_INVALID",
                        "message": f'Tool "{self.name}" received invalid arguments',
                        "details": input_validation.unwrap_err(),
                    }
                )
            model_value = input_validation.unwrap()
            dump = getattr(model_value, "model_dump", None)
            if not callable(dump):
                dump = getattr(model_value, "dict", None)
            if not callable(dump):
                return Result.err(
                    {
                        "errorType": "TOOL_INPUT_INVALID",
                        "message": f'Tool "{self.name}" model cannot produce arguments',
                    }
                )
            try:
                dumped = dump()
            except Exception as exc:
                return Result.err(
                    {
                        "errorType": "TOOL_INPUT_INVALID",
                        "message": f'Tool "{self.name}" model could not produce arguments',
                        "details": {"exception": type(exc).__name__},
                    }
                )
            if not isinstance(dumped, dict):
                return Result.err(
                    {
                        "errorType": "TOOL_INPUT_INVALID",
                        "message": f'Tool "{self.name}" model must produce an object',
                    }
                )
            call_kwargs = dumped
        else:
            input_validation = validate_json_schema(kwargs, self.parameters)
            if input_validation.is_err():
                return Result.err(
                    {
                        "errorType": "TOOL_INPUT_INVALID",
                        "message": f'Tool "{self.name}" received invalid arguments',
                        "details": input_validation.unwrap_err(),
                    }
                )
        input_guardrails = run_guardrails(
            call_kwargs, self.input_guardrails, stage=f"tool:{self.name}:input"
        )
        if input_guardrails.is_err():
            return Result.err(input_guardrails.unwrap_err())
        try:
            if self.executor is None:
                if self.accepts_cancellation:
                    result = self.handler(cancellation=cancellation, **call_kwargs)
                else:
                    result = self.handler(**call_kwargs)
            else:
                execution = self.executor.execute(
                    self.name,
                    self.handler,
                    kwargs=call_kwargs,
                    cancellation=cancellation,
                )
                if execution.is_err():
                    return Result.err(execution.unwrap_err())
                result = execution.unwrap()
        except Exception as e:
            return Result.err(
                {
                    "errorType": "TOOL_EXECUTION_ERROR",
                    "message": f'Tool "{self.name}" failed: {str(e)}',
                    "details": {"tool": self.name},
                }
            )
        if not isinstance(result, Result):
            return Result.err(
                {
                    "errorType": "TOOL_EXECUTION_ERROR",
                    "message": f'Tool "{self.name}" returned a non-Result value',
                }
            )
        if result.is_err():
            return result
        if cancellation is not None and cancellation.is_cancelled():
            return Result.err(
                {
                    "errorType": "EXECUTION_CANCELLED",
                    "message": f'Tool "{self.name}" cancellation was requested.',
                }
            )
        output = result.unwrap()
        if self.output_model is not None:
            output_validation = validate_typed_value(output, self.output_model)
        else:
            output_validation = validate_json_schema(output, self.result_schema)
        if output_validation.is_err():
            return Result.err(
                {
                    "errorType": "TOOL_OUTPUT_INVALID",
                    "message": f'Tool "{self.name}" returned invalid output',
                    "details": output_validation.unwrap_err(),
                }
            )
        if self.output_model is not None:
            output = output_validation.unwrap()
            result = Result.ok(output)
        output_guardrails = run_guardrails(
            output, self.output_guardrails, stage=f"tool:{self.name}:output"
        )
        if output_guardrails.is_err():
            return Result.err(output_guardrails.unwrap_err())
        return result

    async def execute_async(
        self,
        *,
        cancellation: Optional[CancellationToken] = None,
        **kwargs: Any,
    ) -> Result[Any, Dict[str, Any]]:
        """Execute an async handler without blocking the event loop.

        Tools without an async handler, or tools with an execution policy, use
        the existing synchronous path in a worker so legacy and bounded tools
        remain usable from async agent turns. An execution policy takes
        precedence over an optional async handler because its sync executor is
        the only contract that can enforce those bounds.
        """
        if cancellation is not None and not isinstance(cancellation, CancellationToken):
            return Result.err(
                {
                    "errorType": "EXECUTION_CANCELLATION_INVALID",
                    "message": "cancellation must be a CancellationToken or None.",
                }
            )
        if cancellation is not None and cancellation.is_cancelled():
            return Result.err(
                {
                    "errorType": "EXECUTION_CANCELLED",
                    "message": f'Tool "{self.name}" cancellation was requested.',
                }
            )
        if self.async_handler is None or self.executor is not None:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                None, lambda: self.execute(cancellation=cancellation, **kwargs)
            )
        prepared = self._prepare_arguments(kwargs)
        if prepared.is_err():
            return Result.err(prepared.unwrap_err())
        try:
            if self.accepts_cancellation:
                result = await self.async_handler(
                    cancellation=cancellation, **prepared.unwrap()
                )
            else:
                result = await self.async_handler(**prepared.unwrap())
        except Exception as exc:
            return Result.err(
                {
                    "errorType": "TOOL_EXECUTION_ERROR",
                    "message": f'Tool "{self.name}" failed: {str(exc)}',
                    "details": {"tool": self.name},
                }
            )
        if cancellation is not None and cancellation.is_cancelled():
            return Result.err(
                {
                    "errorType": "EXECUTION_CANCELLED",
                    "message": f'Tool "{self.name}" cancellation was requested.',
                }
            )
        return self._finish_result(result)


class ToolRegistry:
    """Registry for discovering and executing tools."""

    def __init__(self) -> None:
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> Result[None, Dict[str, Any]]:
        """Register a tool."""
        self._tools[tool.name] = tool
        logger.debug(f"Registered tool: {tool.name}")
        return Result.ok(None)

    def get(self, name: str) -> Result[Tool, Dict[str, Any]]:
        """Get a tool by name."""
        if name not in self._tools:
            return Result.err(
                {
                    "errorType": "TOOL_NOT_FOUND",
                    "message": f'Tool "{name}" not found. Available: {list(self._tools.keys())}',
                }
            )
        return Result.ok(self._tools[name])

    def list_tools(self, tags: Optional[List[str]] = None) -> List[Tool]:
        """List all tools, optionally filtered by tags."""
        tools = list(self._tools.values())
        if tags:
            tools = [t for t in tools if any(tag in t.tags for tag in tags)]
        return tools

    def get_llm_definitions(
        self, tags: Optional[List[str]] = None
    ) -> List[ToolDefinition]:
        """Get all tool definitions formatted for LLM consumption."""
        return [t.to_llm_definition() for t in self.list_tools(tags)]

    def execute(
        self,
        name: str,
        arguments: Dict[str, Any],
        *,
        cancellation: Optional[CancellationToken] = None,
    ) -> Result[Any, Dict[str, Any]]:
        """Execute a tool by name."""
        tool_result = self.get(name)
        if tool_result.is_err():
            return Result.err(tool_result.unwrap_err())
        tool = tool_result.unwrap()
        return tool.execute(cancellation=cancellation, **arguments)

    async def execute_async(
        self,
        name: str,
        arguments: Dict[str, Any],
        *,
        cancellation: Optional[CancellationToken] = None,
    ) -> Result[Any, Dict[str, Any]]:
        """Execute a tool through its async handler when one is available."""
        tool_result = self.get(name)
        if tool_result.is_err():
            return Result.err(tool_result.unwrap_err())
        tool = tool_result.unwrap()
        return await tool.execute_async(cancellation=cancellation, **arguments)


def _format_handoff_result(
    target_result: Any, target_id: str
) -> Result[Dict[str, Any], Dict[str, Any]]:
    """Normalize a target goal result without forwarding raw target errors."""
    if not isinstance(target_result, Result):
        return Result.err(
            {
                "errorType": "HANDOFF_TARGET_INVALID",
                "message": "Delegated agent returned an invalid result.",
                "details": {"agent_id": target_id},
            }
        )
    if target_result.is_err():
        target_error = target_result.unwrap_err()
        error_type = (
            target_error.get("errorType") if isinstance(target_error, dict) else None
        )
        return Result.err(
            {
                "errorType": "HANDOFF_TARGET_FAILED",
                "message": "Delegated agent reported a failure.",
                "details": {
                    "agent_id": target_id,
                    "target_error_type": error_type or "UNKNOWN",
                },
            }
        )
    goal = target_result.unwrap()
    goal_id = getattr(goal, "goal_id", None)
    status = getattr(goal, "status", None)
    if not isinstance(goal_id, str) or not isinstance(status, str):
        return Result.err(
            {
                "errorType": "HANDOFF_TARGET_INVALID",
                "message": "Delegated agent returned an invalid goal.",
                "details": {"agent_id": target_id},
            }
        )
    return Result.ok(
        {
            "agent_id": target_id,
            "goal_id": goal_id,
            "status": status,
            "result": getattr(goal, "result", None),
        }
    )


def _handoff_digest(value: Any) -> Optional[str]:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError):
        return None
    return hashlib.sha256(encoded).hexdigest()


def _handoff_store_error(
    operation: str, result: Optional[Result[Any, Dict[str, Any]]] = None
) -> Result[Any, Dict[str, Any]]:
    reason = "UNKNOWN"
    if result is not None and result.is_err():
        error = result.unwrap_err()
        if isinstance(error, dict) and isinstance(error.get("errorType"), str):
            reason = error["errorType"][:128]
    return Result.err(
        {
            "errorType": "HANDOFF_STORE_ERROR",
            "message": "Handoff ownership state could not be persisted.",
            "details": {"operation": operation, "reason": reason},
        }
    )


def _handoff_identifier_error(value: Any) -> Optional[Dict[str, Any]]:
    if value is None:
        return None
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 256
        or any(ord(char) < 32 for char in value)
    ):
        return {
            "errorType": "HANDOFF_INPUT_INVALID",
            "message": "handoff_id must be bounded text.",
        }
    return None


def _handoff_store_accepts_result(store: HandoffStore) -> bool:
    try:
        signature = inspect.signature(store.complete)
    except (TypeError, ValueError):
        return False
    result_parameter = signature.parameters.get("result")
    if (
        result_parameter is not None
        and result_parameter.kind is not inspect.Parameter.POSITIONAL_ONLY
    ):
        return True
    return any(
        item.kind is inspect.Parameter.VAR_KEYWORD
        for item in signature.parameters.values()
    )


def _start_persisted_handoff(
    store: HandoffStore,
    source_agent_id: str,
    target_agent_id: str,
    task: str,
    context: Mapping[str, Any],
    *,
    handoff_id: Optional[str] = None,
    persist_result: bool = False,
) -> Result[_PersistedHandoffStart, Dict[str, Any]]:
    identifier_error = _handoff_identifier_error(handoff_id)
    if identifier_error is not None:
        return Result.err(identifier_error)
    task_digest = _handoff_digest(task)
    context_digest = _handoff_digest(context) if context else None
    if task_digest is None or (context and context_digest is None):
        return _handoff_store_error("create")
    chosen_handoff_id = handoff_id or uuid.uuid4().hex
    try:
        created = store.create(
            HandoffRecord.pending(
                chosen_handoff_id,
                source_agent_id,
                target_agent_id,
                task_digest,
                context_digest,
            )
        )
        if created.is_err():
            return _handoff_store_error("create", created)
        record = created.unwrap()
        if record.status == "completed":
            if persist_result and record.result is not None:
                replay_result = record.result
                if (
                    replay_result.get("agent_id") != target_agent_id
                    or replay_result.get("status") != "completed"
                    or not isinstance(replay_result.get("goal_id"), str)
                    or replay_result.get("goal_id") != record.target_goal_id
                ):
                    return Result.err(
                        {
                            "errorType": "HANDOFF_RESULT_INVALID",
                            "message": "Stored handoff result cannot be replayed safely.",
                            "details": {"handoff_id": chosen_handoff_id},
                        }
                    )
                return Result.ok(
                    _PersistedHandoffStart(
                        chosen_handoff_id, replay_result=dict(replay_result)
                    )
                )
            return Result.err(
                {
                    "errorType": "HANDOFF_REPLAY_UNAVAILABLE",
                    "message": "The handoff is already completed without a replayable result.",
                    "details": {"handoff_id": chosen_handoff_id},
                }
            )
        if record.status == "accepted":
            return Result.err(
                {
                    "errorType": "HANDOFF_IN_PROGRESS",
                    "message": "The handoff is already accepted by the target.",
                    "details": {"handoff_id": chosen_handoff_id},
                }
            )
        if record.status == "failed":
            return Result.err(
                {
                    "errorType": "HANDOFF_ALREADY_FAILED",
                    "message": "The handoff already has a terminal failure.",
                    "details": {"handoff_id": chosen_handoff_id},
                }
            )
        accepted = store.accept(chosen_handoff_id, target_agent_id)
        if accepted.is_err():
            return _handoff_store_error("accept", accepted)
    except Exception:
        return _handoff_store_error("create")
    return Result.ok(_PersistedHandoffStart(chosen_handoff_id))


def _finish_persisted_handoff(
    store: HandoffStore,
    handoff_id: str,
    target_agent_id: str,
    formatted: Result[Dict[str, Any], Dict[str, Any]],
    *,
    persist_result: bool = False,
) -> Result[Dict[str, Any], Dict[str, Any]]:
    try:
        if formatted.is_ok():
            target_goal_id = formatted.unwrap().get("goal_id")
            if not isinstance(target_goal_id, str):
                finalized = store.fail(
                    handoff_id, target_agent_id, "HANDOFF_TARGET_INVALID"
                )
            elif persist_result and formatted.unwrap().get("status") == "completed":
                finalized = store.complete(
                    handoff_id,
                    target_agent_id,
                    target_goal_id,
                    result=formatted.unwrap(),
                )
            else:
                finalized = store.complete(handoff_id, target_agent_id, target_goal_id)
        else:
            error = formatted.unwrap_err()
            error_type = (
                error.get("errorType")
                if isinstance(error, dict)
                else "HANDOFF_TARGET_FAILED"
            )
            finalized = store.fail(
                handoff_id,
                target_agent_id,
                error_type if isinstance(error_type, str) else "HANDOFF_TARGET_FAILED",
            )
    except Exception:
        return _handoff_store_error("finalize")
    if finalized.is_err():
        return _handoff_store_error("finalize", finalized)
    if formatted.is_ok():
        payload = dict(formatted.unwrap())
        payload["handoff_id"] = handoff_id
        return Result.ok(payload)
    error = dict(formatted.unwrap_err())
    details = error.get("details")
    merged_details = dict(details) if isinstance(details, dict) else {}
    merged_details["handoff_id"] = handoff_id
    error["details"] = merged_details
    return Result.err(error)


async def _run_handoff_store_async(
    callback: Callable[[], Result[Any, Dict[str, Any]]],
) -> Result[Any, Dict[str, Any]]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, callback)


def _format_agent_tool_result(
    target_result: Any, target_id: str
) -> Result[Dict[str, Any], Dict[str, Any]]:
    """Normalize a nested agent result without forwarding child errors."""
    if not isinstance(target_result, Result):
        return Result.err(
            {
                "errorType": "AGENT_TOOL_TARGET_INVALID",
                "message": "Nested agent returned an invalid result.",
                "details": {"agent_id": target_id},
            }
        )
    if target_result.is_err():
        target_error = target_result.unwrap_err()
        error_type = (
            target_error.get("errorType") if isinstance(target_error, dict) else None
        )
        return Result.err(
            {
                "errorType": "AGENT_TOOL_TARGET_FAILED",
                "message": "Nested agent reported a failure.",
                "details": {
                    "agent_id": target_id,
                    "target_error_type": error_type or "UNKNOWN",
                },
            }
        )
    goal = target_result.unwrap()
    goal_id = getattr(goal, "goal_id", None)
    status = getattr(goal, "status", None)
    if (
        not isinstance(goal_id, str)
        or not goal_id
        or len(goal_id) > 256
        or any(ord(char) < 32 for char in goal_id)
        or not isinstance(status, str)
        or not status
        or len(status) > 64
        or any(ord(char) < 32 for char in status)
    ):
        return Result.err(
            {
                "errorType": "AGENT_TOOL_TARGET_INVALID",
                "message": "Nested agent returned an invalid goal.",
                "details": {"agent_id": target_id},
            }
        )
    copied_result = _copy_handoff_value(
        getattr(goal, "result", None), path="$.result", depth=0
    )
    if copied_result.is_err():
        return Result.err(
            {
                "errorType": "AGENT_TOOL_TARGET_INVALID",
                "message": "Nested agent returned an unbounded result.",
                "details": {"agent_id": target_id},
            }
        )
    return Result.ok(
        {
            "agent_id": target_id,
            "goal_id": goal_id,
            "status": status,
            "result": copied_result.unwrap(),
        }
    )


def create_agent_tool(
    target_agent: "AutonomousAgent",
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    requires_approval: bool = True,
    replay_policy: str = TOOL_REPLAY_DISABLED,
    persist_child_run: bool = False,
    allowed_context_keys: Optional[Sequence[str]] = None,
) -> Tool:
    """Create a bounded manager-style tool backed by another agent.

    Unlike :func:`create_handoff_tool`, this keeps orchestration ownership with
    the caller. The nested agent is invoked synchronously when the tool is
    executed, and asynchronously when it exposes ``pursue_goal_async``.
    Optional context is copied and must be explicitly allowlisted. Child
    errors are reduced to their type; prompts, traces, and provider details do
    not cross the tool result boundary. ``replay_policy`` is forwarded to the
    returned tool so a parent execution journal can optionally reuse a
    successful bounded child result during local recovery. ``persist_child_run``
    enables an explicit local child lifecycle: callers supply ``child_run_id``
    and an existing child run is resumed through its native resume API.
    """
    target_id = getattr(target_agent, "agent_id", None)
    pursue_goal = getattr(target_agent, "pursue_goal", None)
    if (
        not isinstance(target_id, str)
        or not target_id
        or len(target_id) > 256
        or any(ord(char) < 32 for char in target_id)
    ):
        raise ValueError("target_agent must expose a bounded non-empty agent_id")
    if not callable(pursue_goal):
        raise ValueError("target_agent must expose a callable pursue_goal method")
    if not isinstance(requires_approval, bool):
        raise ValueError("requires_approval must be boolean")
    if not isinstance(persist_child_run, bool):
        raise ValueError("persist_child_run must be boolean")
    pursue_with_context = getattr(target_agent, "pursue_goal_with_context", None)
    resume_run = getattr(target_agent, "resume_run", None)
    resume_run_handler = cast(Callable[..., Any], resume_run)
    if persist_child_run:
        if not _callable_accepts_keyword(pursue_goal, "run_id"):
            raise ValueError(
                "persist_child_run requires a target pursue_goal run_id parameter"
            )
        if not callable(resume_run):
            raise ValueError("persist_child_run requires a target resume_run method")
        if not _callable_accepts_keyword(resume_run, "run_id"):
            raise ValueError(
                "persist_child_run requires a target resume_run run_id parameter"
            )
        if callable(pursue_with_context) and not _callable_accepts_keyword(
            pursue_with_context, "run_id"
        ):
            raise ValueError(
                "persist_child_run requires context-aware target run_id support"
            )
    if allowed_context_keys is None:
        allowed_keys: frozenset[str] = frozenset()
    else:
        if isinstance(allowed_context_keys, (str, bytes)):
            raise ValueError("allowed_context_keys must be a sequence of strings")
        try:
            raw_allowed_keys = tuple(allowed_context_keys)
        except TypeError as exc:
            raise ValueError(
                "allowed_context_keys must be a sequence of strings"
            ) from exc
        if len(raw_allowed_keys) > MAX_HANDOFF_CONTEXT_KEYS:
            raise ValueError(
                f"allowed_context_keys cannot exceed {MAX_HANDOFF_CONTEXT_KEYS} keys"
            )
        if any(
            not isinstance(key, str) or not key or len(key) > 128
            for key in raw_allowed_keys
        ):
            raise ValueError("allowed_context_keys must contain bounded strings")
        if len(set(raw_allowed_keys)) != len(raw_allowed_keys):
            raise ValueError("allowed_context_keys must not contain duplicates")
        allowed_keys = frozenset(raw_allowed_keys)

    tool_name = name or f"ask_{target_id}"
    tool_description = description or (
        f"Ask agent {target_id} to complete one bounded task and return its result"
    )

    def validate_child_run_id(
        child_run_id: Optional[str],
    ) -> Result[Optional[str], Dict[str, Any]]:
        if not persist_child_run:
            return Result.ok(None)
        if child_run_id is None:
            return Result.err(
                {
                    "errorType": "AGENT_TOOL_CHILD_RUN_ID_INVALID",
                    "message": (
                        "child_run_id is required when child-run persistence is "
                        "enabled."
                    ),
                }
            )
        identifier_error = _child_run_id_error(child_run_id)
        if identifier_error is not None:
            return Result.err(identifier_error)
        return Result.ok(child_run_id)

    def resume_existing_child(
        child_run_id: str,
        cancellation: Optional[CancellationToken],
    ) -> Any:
        try:
            return _invoke_delegated(resume_run_handler, (child_run_id,), cancellation)
        except Exception as exc:
            return Result.err(
                {
                    "errorType": "AGENT_TOOL_CHILD_RESUME_ERROR",
                    "message": "Nested agent resume failed.",
                    "details": {
                        "agent_id": target_id,
                        "exception": type(exc).__name__,
                    },
                }
            )

    def prepare_context(
        context: Optional[Dict[str, Any]],
    ) -> Result[Dict[str, Any], Dict[str, Any]]:
        context_result = _normalize_handoff_context(context)
        if context_result.is_err():
            return Result.err(context_result.unwrap_err())
        nested_context = context_result.unwrap()
        denied_keys = sorted(set(nested_context).difference(allowed_keys))
        if denied_keys:
            return Result.err(
                {
                    "errorType": "AGENT_TOOL_CONTEXT_KEY_DENIED",
                    "message": "Agent-tool context contains a key outside the allowlist.",
                    "details": {"keys": denied_keys},
                }
            )
        return Result.ok(nested_context)

    def invoke_sync(
        task: str,
        context: Optional[Dict[str, Any]] = None,
        child_run_id: Optional[str] = None,
        *,
        cancellation: Optional[CancellationToken] = None,
    ) -> Result[Dict[str, Any], Dict[str, Any]]:
        context_result = prepare_context(context)
        if context_result.is_err():
            return Result.err(context_result.unwrap_err())
        nested_context = context_result.unwrap()
        child_id = validate_child_run_id(child_run_id)
        if child_id.is_err():
            return Result.err(child_id.unwrap_err())
        active_child_run_id = child_id.unwrap()
        if cancellation is not None and cancellation.is_cancelled():
            return _delegation_cancelled(target_id)
        try:
            if nested_context:
                if not callable(pursue_with_context):
                    return Result.err(
                        {
                            "errorType": "AGENT_TOOL_CONTEXT_UNSUPPORTED",
                            "message": "Nested agent does not declare context-aware execution.",
                            "details": {"agent_id": target_id},
                        }
                    )
                target_result = _invoke_delegated(
                    pursue_with_context,
                    (task, nested_context),
                    cancellation,
                    run_id=active_child_run_id,
                )
            else:
                target_result = _invoke_delegated(
                    pursue_goal,
                    (task,),
                    cancellation,
                    run_id=active_child_run_id,
                )
        except Exception as exc:
            return Result.err(
                {
                    "errorType": "AGENT_TOOL_TARGET_ERROR",
                    "message": "Nested agent execution failed.",
                    "details": {"agent_id": target_id, "exception": type(exc).__name__},
                }
            )
        if (
            persist_child_run
            and active_child_run_id is not None
            and _result_error_type(target_result) == "RUN_EXISTS"
        ):
            target_result = resume_existing_child(active_child_run_id, cancellation)
        return _format_agent_tool_result(target_result, target_id)

    async_handler: Optional[Callable[..., Awaitable[Result[Any, Dict[str, Any]]]]] = (
        None
    )
    pursue_goal_async = getattr(target_agent, "pursue_goal_async", None)
    pursue_with_context_async = getattr(
        target_agent, "pursue_goal_with_context_async", None
    )
    resume_run_async = getattr(target_agent, "resume_run_async", None)
    resume_run_async_handler = cast(Callable[..., Any], resume_run_async)
    if persist_child_run and callable(pursue_goal_async):
        if not _callable_accepts_keyword(pursue_goal_async, "run_id"):
            raise ValueError(
                "persist_child_run requires an async target pursue_goal run_id parameter"
            )
        if not callable(resume_run_async):
            raise ValueError(
                "persist_child_run requires a target resume_run_async method"
            )
        if not _callable_accepts_keyword(resume_run_async, "run_id"):
            raise ValueError(
                "persist_child_run requires a target resume_run_async run_id parameter"
            )
        if callable(pursue_with_context_async) and not _callable_accepts_keyword(
            pursue_with_context_async, "run_id"
        ):
            raise ValueError(
                "persist_child_run requires async context-aware target run_id support"
            )
    if callable(pursue_goal_async):

        async def invoke_async(
            task: str,
            context: Optional[Dict[str, Any]] = None,
            child_run_id: Optional[str] = None,
            *,
            cancellation: Optional[CancellationToken] = None,
        ) -> Result[Dict[str, Any], Dict[str, Any]]:
            context_result = prepare_context(context)
            if context_result.is_err():
                return Result.err(context_result.unwrap_err())
            nested_context = context_result.unwrap()
            child_id = validate_child_run_id(child_run_id)
            if child_id.is_err():
                return Result.err(child_id.unwrap_err())
            active_child_run_id = child_id.unwrap()
            if cancellation is not None and cancellation.is_cancelled():
                return _delegation_cancelled(target_id)
            try:
                if nested_context:
                    if not callable(pursue_with_context_async):
                        return Result.err(
                            {
                                "errorType": "AGENT_TOOL_CONTEXT_UNSUPPORTED",
                                "message": "Nested agent does not declare async context-aware execution.",
                                "details": {"agent_id": target_id},
                            }
                        )
                    target_result = await _invoke_delegated(
                        pursue_with_context_async,
                        (task, nested_context),
                        cancellation,
                        run_id=active_child_run_id,
                    )
                else:
                    target_result = await _invoke_delegated(
                        pursue_goal_async,
                        (task,),
                        cancellation,
                        run_id=active_child_run_id,
                    )
            except Exception as exc:
                return Result.err(
                    {
                        "errorType": "AGENT_TOOL_TARGET_ERROR",
                        "message": "Nested agent execution failed.",
                        "details": {
                            "agent_id": target_id,
                            "exception": type(exc).__name__,
                        },
                    }
                )
            if (
                persist_child_run
                and active_child_run_id is not None
                and _result_error_type(target_result) == "RUN_EXISTS"
            ):
                try:
                    target_result = await _invoke_delegated(
                        resume_run_async_handler,
                        (active_child_run_id,),
                        cancellation,
                    )
                except Exception as exc:
                    target_result = Result.err(
                        {
                            "errorType": "AGENT_TOOL_CHILD_RESUME_ERROR",
                            "message": "Nested agent resume failed.",
                            "details": {
                                "agent_id": target_id,
                                "exception": type(exc).__name__,
                            },
                        }
                    )
            return _format_agent_tool_result(target_result, target_id)

        async_handler = invoke_async

    properties: Dict[str, Any] = {
        "task": {
            "type": "string",
            "minLength": 1,
            "maxLength": 8192,
            "description": "The bounded task for the nested agent.",
        },
        "context": {
            "type": "object",
            "maxProperties": MAX_HANDOFF_CONTEXT_KEYS,
            "description": (
                "Optional bounded context. Only explicitly allowlisted "
                "keys reach the nested agent."
            ),
        },
    }
    required = ["task"]
    if persist_child_run:
        properties["child_run_id"] = {
            "type": "string",
            "maxLength": 128,
            "description": (
                "Caller-owned durable ID for resuming an in-flight child run."
            ),
        }
        required.append("child_run_id")

    return Tool(
        name=tool_name,
        description=tool_description,
        parameters={
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        },
        handler=invoke_sync,
        async_handler=async_handler,
        requires_approval=requires_approval,
        replay_policy=replay_policy,
        accepts_cancellation=True,
        tags=["delegation", "agent-as-tool"],
    )


def create_handoff_tool(
    target_agent: "AutonomousAgent",
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    requires_approval: bool = True,
    allowed_context_keys: Optional[Sequence[str]] = None,
    handoff_store: Optional[HandoffStore] = None,
    source_agent_id: Optional[str] = None,
    persist_result: bool = False,
) -> Tool:
    """Create a bounded tool that delegates one task to another agent.

    The target is invoked through its synchronous ``pursue_goal`` method. An
    optional context object is copied, bounded, and filtered by an explicit
    ``allowed_context_keys`` list. Non-empty context requires the target to
    expose ``pursue_goal_with_context``; legacy targets remain compatible when
    no context is supplied. When ``handoff_store`` is provided, a bounded
    identity record transfers ownership from ``source_agent_id`` (or ``host``)
    to the target before execution and returns ownership after completion. When
    ``persist_result`` is enabled, an explicit ``handoff_id`` can replay a
    completed bounded result without invoking the target again.
    """
    target_id = getattr(target_agent, "agent_id", None)
    pursue_goal = getattr(target_agent, "pursue_goal", None)
    if (
        not isinstance(target_id, str)
        or not target_id
        or len(target_id) > 256
        or any(ord(char) < 32 for char in target_id)
    ):
        raise ValueError("target_agent must expose a bounded non-empty agent_id")
    if not callable(pursue_goal):
        raise ValueError("target_agent must expose a callable pursue_goal method")
    if not isinstance(requires_approval, bool):
        raise ValueError("requires_approval must be boolean")
    if not isinstance(persist_result, bool):
        raise ValueError("persist_result must be boolean")
    source_id = "host" if source_agent_id is None else source_agent_id
    if (
        not isinstance(source_id, str)
        or not source_id
        or len(source_id) > 256
        or any(ord(char) < 32 for char in source_id)
    ):
        raise ValueError("source_agent_id must be bounded text")
    if handoff_store is not None and any(
        not callable(getattr(handoff_store, method, None))
        for method in ("create", "get", "accept", "complete", "fail", "list_open")
    ):
        raise ValueError("handoff_store does not implement the handoff contract")
    if persist_result and handoff_store is None:
        raise ValueError("persist_result requires a handoff_store")
    if (
        persist_result
        and handoff_store is not None
        and not _handoff_store_accepts_result(handoff_store)
    ):
        raise ValueError(
            "persist_result requires a handoff_store with result completion support"
        )
    if allowed_context_keys is None:
        allowed_keys: frozenset[str] = frozenset()
    else:
        if isinstance(allowed_context_keys, (str, bytes)):
            raise ValueError("allowed_context_keys must be a sequence of strings")
        try:
            raw_allowed_keys = tuple(allowed_context_keys)
        except TypeError as exc:
            raise ValueError(
                "allowed_context_keys must be a sequence of strings"
            ) from exc
        if len(raw_allowed_keys) > MAX_HANDOFF_CONTEXT_KEYS:
            raise ValueError(
                f"allowed_context_keys cannot exceed {MAX_HANDOFF_CONTEXT_KEYS} keys"
            )
        if any(
            not isinstance(key, str) or not key or len(key) > 128
            for key in raw_allowed_keys
        ):
            raise ValueError("allowed_context_keys must contain bounded strings")
        if len(set(raw_allowed_keys)) != len(raw_allowed_keys):
            raise ValueError("allowed_context_keys must not contain duplicates")
        allowed_keys = frozenset(raw_allowed_keys)

    tool_name = name or f"handoff_to_{target_id}"
    tool_description = description or (
        f"Delegate one bounded task to agent {target_id} and receive its result"
    )

    def handoff_handler(
        task: str,
        context: Optional[Dict[str, Any]] = None,
        handoff_id: Optional[str] = None,
        *,
        cancellation: Optional[CancellationToken] = None,
    ) -> Result[Dict[str, Any], Dict[str, Any]]:
        context_result = _normalize_handoff_context(context)
        if context_result.is_err():
            return Result.err(context_result.unwrap_err())
        handoff_context = context_result.unwrap()
        denied_keys = sorted(set(handoff_context).difference(allowed_keys))
        if denied_keys:
            return Result.err(
                {
                    "errorType": "HANDOFF_CONTEXT_KEY_DENIED",
                    "message": "Handoff context contains a key outside the allowlist.",
                    "details": {"keys": denied_keys},
                }
            )
        if handoff_id is not None and handoff_store is None:
            return Result.err(
                {
                    "errorType": "HANDOFF_STORE_UNAVAILABLE",
                    "message": "handoff_id requires a configured handoff store.",
                }
            )
        active_handoff_id: Optional[str] = None
        if handoff_store is not None:
            started = _start_persisted_handoff(
                handoff_store,
                source_id,
                target_id,
                task,
                handoff_context,
                handoff_id=handoff_id,
                persist_result=persist_result,
            )
            if started.is_err():
                return Result.err(started.unwrap_err())
            started_state = started.unwrap()
            active_handoff_id = started_state.handoff_id
            if started_state.replay_result is not None:
                payload = dict(started_state.replay_result)
                payload["handoff_id"] = active_handoff_id
                return Result.ok(payload)
        pursue_with_context = getattr(target_agent, "pursue_goal_with_context", None)
        execution_error: Optional[Result[Dict[str, Any], Dict[str, Any]]] = None
        target_result: Result[Any, Dict[str, Any]]
        if cancellation is not None and cancellation.is_cancelled():
            execution_error = _delegation_cancelled(target_id)
            target_result = execution_error
        else:
            try:
                if handoff_context:
                    if not callable(pursue_with_context):
                        target_result = Result.err(
                            {
                                "errorType": "HANDOFF_CONTEXT_UNSUPPORTED",
                                "message": "Target agent does not declare context-aware handoff.",
                                "details": {"agent_id": target_id},
                            }
                        )
                        execution_error = target_result
                    else:
                        target_result = _invoke_delegated(
                            pursue_with_context,
                            (task, handoff_context),
                            cancellation,
                            handoff_id=active_handoff_id,
                        )
                else:
                    target_result = _invoke_delegated(
                        pursue_goal,
                        (task,),
                        cancellation,
                        handoff_id=active_handoff_id,
                    )
            except Exception as exc:
                target_result = Result.err(
                    {
                        "errorType": "HANDOFF_TARGET_ERROR",
                        "message": "Delegated agent execution failed.",
                        "details": {
                            "agent_id": target_id,
                            "exception": type(exc).__name__,
                        },
                    }
                )
                execution_error = target_result
        formatted = (
            execution_error
            if execution_error is not None
            else _format_handoff_result(target_result, target_id)
        )
        if cancellation is not None and cancellation.is_cancelled():
            formatted = _delegation_cancelled(target_id)
        if handoff_store is not None and active_handoff_id is not None:
            return _finish_persisted_handoff(
                handoff_store,
                active_handoff_id,
                target_id,
                formatted,
                persist_result=persist_result,
            )
        return formatted

    async_handler: Optional[Callable[..., Awaitable[Result[Any, Dict[str, Any]]]]] = (
        None
    )
    pursue_goal_async = getattr(target_agent, "pursue_goal_async", None)
    pursue_with_context_async = getattr(
        target_agent, "pursue_goal_with_context_async", None
    )
    if callable(pursue_goal_async):

        async def async_handoff_handler(
            task: str,
            context: Optional[Dict[str, Any]] = None,
            handoff_id: Optional[str] = None,
            *,
            cancellation: Optional[CancellationToken] = None,
        ) -> Result[Dict[str, Any], Dict[str, Any]]:
            context_result = _normalize_handoff_context(context)
            if context_result.is_err():
                return Result.err(context_result.unwrap_err())
            handoff_context = context_result.unwrap()
            denied_keys = sorted(set(handoff_context).difference(allowed_keys))
            if denied_keys:
                return Result.err(
                    {
                        "errorType": "HANDOFF_CONTEXT_KEY_DENIED",
                        "message": "Handoff context contains a key outside the allowlist.",
                        "details": {"keys": denied_keys},
                    }
                )
            if handoff_id is not None and handoff_store is None:
                return Result.err(
                    {
                        "errorType": "HANDOFF_STORE_UNAVAILABLE",
                        "message": "handoff_id requires a configured handoff store.",
                    }
                )
            active_handoff_id: Optional[str] = None
            if handoff_store is not None:
                started = await _run_handoff_store_async(
                    lambda: _start_persisted_handoff(
                        handoff_store,
                        source_id,
                        target_id,
                        task,
                        handoff_context,
                        handoff_id=handoff_id,
                        persist_result=persist_result,
                    )
                )
                if started.is_err():
                    return Result.err(started.unwrap_err())
                started_state = started.unwrap()
                active_handoff_id = started_state.handoff_id
                if started_state.replay_result is not None:
                    payload = dict(started_state.replay_result)
                    payload["handoff_id"] = active_handoff_id
                    return Result.ok(payload)
            execution_error: Optional[Result[Dict[str, Any], Dict[str, Any]]] = None
            target_result: Result[Any, Dict[str, Any]]
            if cancellation is not None and cancellation.is_cancelled():
                execution_error = _delegation_cancelled(target_id)
                target_result = execution_error
            else:
                try:
                    if handoff_context:
                        if not callable(pursue_with_context_async):
                            target_result = Result.err(
                                {
                                    "errorType": "HANDOFF_CONTEXT_UNSUPPORTED",
                                    "message": "Target agent does not declare async context-aware handoff.",
                                    "details": {"agent_id": target_id},
                                }
                            )
                            execution_error = target_result
                        else:
                            target_result = await _invoke_delegated(
                                pursue_with_context_async,
                                (task, handoff_context),
                                cancellation,
                                handoff_id=active_handoff_id,
                            )
                    else:
                        target_result = await _invoke_delegated(
                            pursue_goal_async,
                            (task,),
                            cancellation,
                            handoff_id=active_handoff_id,
                        )
                except Exception as exc:
                    target_result = Result.err(
                        {
                            "errorType": "HANDOFF_TARGET_ERROR",
                            "message": "Delegated agent execution failed.",
                            "details": {
                                "agent_id": target_id,
                                "exception": type(exc).__name__,
                            },
                        }
                    )
                    execution_error = target_result
            formatted = (
                execution_error
                if execution_error is not None
                else _format_handoff_result(target_result, target_id)
            )
            if cancellation is not None and cancellation.is_cancelled():
                formatted = _delegation_cancelled(target_id)
            if handoff_store is not None and active_handoff_id is not None:
                finalized = await _run_handoff_store_async(
                    lambda: _finish_persisted_handoff(
                        handoff_store,
                        active_handoff_id,
                        target_id,
                        formatted,
                        persist_result=persist_result,
                    )
                )
                return finalized
            return formatted

        async_handler = async_handoff_handler

    return Tool(
        name=tool_name,
        description=tool_description,
        parameters={
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 8192,
                    "description": "The bounded task to delegate.",
                },
                "context": {
                    "type": "object",
                    "maxProperties": MAX_HANDOFF_CONTEXT_KEYS,
                    "description": (
                        "Optional bounded context. Only allowlisted keys cross "
                        "to a context-aware target."
                    ),
                },
                "handoff_id": {
                    "type": "string",
                    "maxLength": 256,
                    "description": (
                        "Optional caller-owned ID for replaying a completed "
                        "persisted handoff."
                    ),
                },
            },
            "required": ["task"],
            "additionalProperties": False,
        },
        handler=handoff_handler,
        async_handler=async_handler,
        requires_approval=requires_approval,
        accepts_cancellation=True,
        tags=["delegation", "handoff"],
    )


def create_builtin_tools(agent: "AutonomousAgent") -> List[Tool]:
    """Create built-in tools that use existing MAPLE infrastructure."""
    from ..core.message import Message

    tools = []

    def send_message_handler(
        receiver: str, message_type: str, payload: Optional[dict] = None
    ) -> Result[Any, Dict[str, Any]]:
        msg = Message(
            message_type=message_type, receiver=receiver, payload=payload or {}
        )
        return agent.send(msg)

    tools.append(
        Tool(
            name="send_message",
            description="Send a message to another MAPLE agent",
            parameters={
                "type": "object",
                "properties": {
                    "receiver": {"type": "string", "description": "Target agent ID"},
                    "message_type": {"type": "string", "description": "Message type"},
                    "payload": {"type": "object", "description": "Message payload"},
                },
                "required": ["receiver", "message_type"],
            },
            handler=send_message_handler,
            tags=["communication"],
        )
    )

    def query_agents_handler(
        capability: Optional[str] = None,
    ) -> Result[Any, Dict[str, Any]]:
        if agent.registry:
            if capability:
                agents = agent.registry.find_agents_by_capability(capability)
                return Result.ok(
                    [
                        {
                            "agent_id": a.agent_id,
                            "capabilities": a.capabilities,
                            "status": a.status,
                        }
                        for a in agents
                    ]
                )
            else:
                agents = agent.registry.list_agents()
                return Result.ok(
                    [
                        {
                            "agent_id": a.agent_id,
                            "capabilities": a.capabilities,
                            "status": a.status,
                        }
                        for a in agents
                    ]
                )
        return Result.ok([])

    tools.append(
        Tool(
            name="query_agents",
            description="Query available agents and their capabilities in the MAPLE network",
            parameters={
                "type": "object",
                "properties": {
                    "capability": {
                        "type": "string",
                        "description": "Filter by capability (optional)",
                    },
                },
            },
            handler=query_agents_handler,
            tags=["discovery"],
        )
    )

    def read_state_handler(key: str) -> Result[Any, Dict[str, Any]]:
        try:
            from ..state.store import StateStore, StorageBackend

            store = StateStore(backend=StorageBackend.MEMORY)
            return store.get(key)
        except Exception as e:
            return Result.err({"errorType": "STATE_READ_ERROR", "message": str(e)})

    tools.append(
        Tool(
            name="read_state",
            description="Read a value from the shared state store",
            parameters={
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "State key to read"},
                },
                "required": ["key"],
            },
            handler=read_state_handler,
            tags=["state"],
        )
    )

    def write_state_handler(key: str, value: Any) -> Result[Any, Dict[str, Any]]:
        try:
            from ..state.store import StateStore, StorageBackend

            store = StateStore(backend=StorageBackend.MEMORY)
            return store.set(key, value)
        except Exception as e:
            return Result.err({"errorType": "STATE_WRITE_ERROR", "message": str(e)})

    tools.append(
        Tool(
            name="write_state",
            description="Write a value to the shared state store",
            parameters={
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "State key to write"},
                    "value": {"description": "Value to store"},
                },
                "required": ["key", "value"],
            },
            handler=write_state_handler,
            tags=["state"],
            requires_approval=True,
        )
    )

    def request_human_input_handler(
        prompt: str,
        input_schema: Optional[dict] = None,
        max_rounds: int = 1,
    ) -> Result[Any, Dict[str, Any]]:
        # Durable agent runs intercept this tool before a handler can execute.
        # Direct calls remain fail-closed instead of pretending to collect input.
        return Result.err(
            {
                "errorType": "HUMAN_INPUT_REQUIRES_DURABLE_RUN",
                "message": "Human input requests require a durable agent run.",
            }
        )

    tools.append(
        Tool(
            name="request_human_input",
            description=(
                "Pause the durable agent run and ask the host for a bounded "
                "human response. The host resumes the run after responding."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 4096,
                        "description": "The question shown to the human.",
                    },
                    "input_schema": {
                        "type": "object",
                        "description": "The bounded JSON schema for the response.",
                    },
                    "max_rounds": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 8,
                        "description": "Maximum number of host response rounds for this interaction.",
                    },
                },
                "required": ["prompt"],
                "additionalProperties": False,
            },
            handler=request_human_input_handler,
            tags=["human-input", "interaction"],
        )
    )

    return tools
