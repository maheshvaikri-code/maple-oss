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
import json
import logging
import math
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
from .execution import ExecutionExecutor

if TYPE_CHECKING:
    from .agent import AutonomousAgent

logger = logging.getLogger(__name__)

MAX_HANDOFF_CONTEXT_KEYS = 32
MAX_HANDOFF_CONTEXT_ITEMS = 128
MAX_HANDOFF_CONTEXT_DEPTH = 8
MAX_HANDOFF_CONTEXT_STRING_LENGTH = 8_192
MAX_HANDOFF_CONTEXT_BYTES = 32_768


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
    _input_model_schema: Optional[Dict[str, Any]] = field(
        default=None, init=False, repr=False
    )

    def __post_init__(self) -> None:
        """Validate typed model configuration once at tool registration time."""
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
        return result

    def execute(self, **kwargs: Any) -> Result[Any, Dict[str, Any]]:
        """Execute this tool with the given arguments."""
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
                result = self.handler(**call_kwargs)
            else:
                execution = self.executor.execute(
                    self.name, self.handler, kwargs=call_kwargs
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

    async def execute_async(self, **kwargs: Any) -> Result[Any, Dict[str, Any]]:
        """Execute an async handler without blocking the event loop.

        Tools without an async handler use the existing synchronous path in a
        worker so legacy tools remain usable from async agent turns.
        """
        if self.async_handler is None:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, lambda: self.execute(**kwargs))
        prepared = self._prepare_arguments(kwargs)
        if prepared.is_err():
            return Result.err(prepared.unwrap_err())
        try:
            result = await self.async_handler(**prepared.unwrap())
        except Exception as exc:
            return Result.err(
                {
                    "errorType": "TOOL_EXECUTION_ERROR",
                    "message": f'Tool "{self.name}" failed: {str(exc)}',
                    "details": {"tool": self.name},
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
        self, name: str, arguments: Dict[str, Any]
    ) -> Result[Any, Dict[str, Any]]:
        """Execute a tool by name."""
        tool_result = self.get(name)
        if tool_result.is_err():
            return Result.err(tool_result.unwrap_err())
        tool = tool_result.unwrap()
        return tool.execute(**arguments)

    async def execute_async(
        self, name: str, arguments: Dict[str, Any]
    ) -> Result[Any, Dict[str, Any]]:
        """Execute a tool through its async handler when one is available."""
        tool_result = self.get(name)
        if tool_result.is_err():
            return Result.err(tool_result.unwrap_err())
        tool = tool_result.unwrap()
        return await tool.execute_async(**arguments)


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


def create_handoff_tool(
    target_agent: "AutonomousAgent",
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    requires_approval: bool = True,
    allowed_context_keys: Optional[Sequence[str]] = None,
) -> Tool:
    """Create a bounded tool that delegates one task to another agent.

    The target is invoked through its synchronous ``pursue_goal`` method. An
    optional context object is copied, bounded, and filtered by an explicit
    ``allowed_context_keys`` list. Non-empty context requires the target to
    expose ``pursue_goal_with_context``; legacy targets remain compatible when
    no context is supplied.
    """
    target_id = getattr(target_agent, "agent_id", None)
    pursue_goal = getattr(target_agent, "pursue_goal", None)
    if not isinstance(target_id, str) or not target_id or len(target_id) > 256:
        raise ValueError("target_agent must expose a bounded non-empty agent_id")
    if not callable(pursue_goal):
        raise ValueError("target_agent must expose a callable pursue_goal method")
    if not isinstance(requires_approval, bool):
        raise ValueError("requires_approval must be boolean")
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
        task: str, context: Optional[Dict[str, Any]] = None
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
        pursue_with_context = getattr(target_agent, "pursue_goal_with_context", None)
        try:
            if handoff_context:
                if not callable(pursue_with_context):
                    return Result.err(
                        {
                            "errorType": "HANDOFF_CONTEXT_UNSUPPORTED",
                            "message": "Target agent does not declare context-aware handoff.",
                            "details": {"agent_id": target_id},
                        }
                    )
                target_result = pursue_with_context(task, handoff_context)
            else:
                target_result = pursue_goal(task)
        except Exception as exc:
            return Result.err(
                {
                    "errorType": "HANDOFF_TARGET_ERROR",
                    "message": "Delegated agent execution failed.",
                    "details": {
                        "agent_id": target_id,
                        "exception": type(exc).__name__,
                    },
                }
            )
        return _format_handoff_result(target_result, target_id)

    async_handler: Optional[Callable[..., Awaitable[Result[Any, Dict[str, Any]]]]] = (
        None
    )
    pursue_goal_async = getattr(target_agent, "pursue_goal_async", None)
    pursue_with_context_async = getattr(
        target_agent, "pursue_goal_with_context_async", None
    )
    if callable(pursue_goal_async):

        async def async_handoff_handler(
            task: str, context: Optional[Dict[str, Any]] = None
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
            try:
                if handoff_context:
                    if not callable(pursue_with_context_async):
                        return Result.err(
                            {
                                "errorType": "HANDOFF_CONTEXT_UNSUPPORTED",
                                "message": "Target agent does not declare async context-aware handoff.",
                                "details": {"agent_id": target_id},
                            }
                        )
                    target_result = await pursue_with_context_async(
                        task, handoff_context
                    )
                else:
                    target_result = await pursue_goal_async(task)
            except Exception as exc:
                return Result.err(
                    {
                        "errorType": "HANDOFF_TARGET_ERROR",
                        "message": "Delegated agent execution failed.",
                        "details": {
                            "agent_id": target_id,
                            "exception": type(exc).__name__,
                        },
                    }
                )
            return _format_handoff_result(target_result, target_id)

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
            },
            "required": ["task"],
            "additionalProperties": False,
        },
        handler=handoff_handler,
        async_handler=async_handler,
        requires_approval=requires_approval,
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
