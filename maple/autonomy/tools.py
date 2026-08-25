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

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Type

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

    return tools
