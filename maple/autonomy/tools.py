"""Tool framework for MAPLE autonomous agents."""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from ..core.result import Result
from ..llm.types import ToolDefinition

logger = logging.getLogger(__name__)


@dataclass
class Tool:
    """A tool that can be called by an autonomous agent."""
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema
    handler: Callable[..., Result[Any, Dict[str, Any]]]
    requires_approval: bool = False
    tags: List[str] = field(default_factory=list)

    def to_llm_definition(self) -> ToolDefinition:
        """Convert to LLM-compatible tool definition."""
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
        )

    def execute(self, **kwargs) -> Result[Any, Dict[str, Any]]:
        """Execute this tool with the given arguments."""
        try:
            return self.handler(**kwargs)
        except Exception as e:
            return Result.err({
                'errorType': 'TOOL_EXECUTION_ERROR',
                'message': f'Tool "{self.name}" failed: {str(e)}',
                'details': {'tool': self.name, 'args': kwargs}
            })


class ToolRegistry:
    """Registry for discovering and executing tools."""

    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> Result[None, Dict[str, Any]]:
        """Register a tool."""
        self._tools[tool.name] = tool
        logger.debug(f"Registered tool: {tool.name}")
        return Result.ok(None)

    def get(self, name: str) -> Result[Tool, Dict[str, Any]]:
        """Get a tool by name."""
        if name not in self._tools:
            return Result.err({
                'errorType': 'TOOL_NOT_FOUND',
                'message': f'Tool "{name}" not found. Available: {list(self._tools.keys())}'
            })
        return Result.ok(self._tools[name])

    def list_tools(self, tags: Optional[List[str]] = None) -> List[Tool]:
        """List all tools, optionally filtered by tags."""
        tools = list(self._tools.values())
        if tags:
            tools = [t for t in tools if any(tag in t.tags for tag in tags)]
        return tools

    def get_llm_definitions(self, tags: Optional[List[str]] = None) -> List[ToolDefinition]:
        """Get all tool definitions formatted for LLM consumption."""
        return [t.to_llm_definition() for t in self.list_tools(tags)]

    def execute(self, name: str, arguments: Dict[str, Any]) -> Result[Any, Dict[str, Any]]:
        """Execute a tool by name."""
        tool_result = self.get(name)
        if tool_result.is_err():
            return tool_result
        tool = tool_result.unwrap()
        return tool.execute(**arguments)


def create_builtin_tools(agent) -> List[Tool]:
    """Create built-in tools that use existing MAPLE infrastructure."""
    from ..core.message import Message

    tools = []

    def send_message_handler(receiver: str, message_type: str, payload: Optional[dict] = None) -> Result:
        msg = Message(message_type=message_type, receiver=receiver, payload=payload or {})
        return agent.send(msg)

    tools.append(Tool(
        name="send_message",
        description="Send a message to another MAPLE agent",
        parameters={
            "type": "object",
            "properties": {
                "receiver": {"type": "string", "description": "Target agent ID"},
                "message_type": {"type": "string", "description": "Message type"},
                "payload": {"type": "object", "description": "Message payload"},
            },
            "required": ["receiver", "message_type"]
        },
        handler=send_message_handler,
        tags=["communication"]
    ))

    def query_agents_handler(capability: Optional[str] = None) -> Result:
        if agent.registry:
            if capability:
                agents = agent.registry.find_agents_by_capability(capability)
                return Result.ok([{
                    'agent_id': a.agent_id, 'capabilities': a.capabilities,
                    'status': a.status
                } for a in agents])
            else:
                agents = agent.registry.list_agents()
                return Result.ok([{
                    'agent_id': a.agent_id, 'capabilities': a.capabilities,
                    'status': a.status
                } for a in agents])
        return Result.ok([])

    tools.append(Tool(
        name="query_agents",
        description="Query available agents and their capabilities in the MAPLE network",
        parameters={
            "type": "object",
            "properties": {
                "capability": {"type": "string", "description": "Filter by capability (optional)"},
            }
        },
        handler=query_agents_handler,
        tags=["discovery"]
    ))

    def read_state_handler(key: str) -> Result:
        try:
            from ..state.store import StateStore, StorageBackend
            store = StateStore(backend=StorageBackend.MEMORY)
            return store.get(key)
        except Exception as e:
            return Result.err({'errorType': 'STATE_READ_ERROR', 'message': str(e)})

    tools.append(Tool(
        name="read_state",
        description="Read a value from the shared state store",
        parameters={
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "State key to read"},
            },
            "required": ["key"]
        },
        handler=read_state_handler,
        tags=["state"]
    ))

    def write_state_handler(key: str, value: Any) -> Result:
        try:
            from ..state.store import StateStore, StorageBackend
            store = StateStore(backend=StorageBackend.MEMORY)
            return store.set(key, value)
        except Exception as e:
            return Result.err({'errorType': 'STATE_WRITE_ERROR', 'message': str(e)})

    tools.append(Tool(
        name="write_state",
        description="Write a value to the shared state store",
        parameters={
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "State key to write"},
                "value": {"description": "Value to store"},
            },
            "required": ["key", "value"]
        },
        handler=write_state_handler,
        tags=["state"],
        requires_approval=True,
    ))

    return tools
