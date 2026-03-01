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

"""Autonomous agent with LLM-driven reasoning and tool execution."""

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from ..agent.agent import Agent
from ..agent.config import Config
from ..core.result import Result
from ..llm.provider import LLMProvider
from ..llm.registry import LLMProviderRegistry
from ..llm.types import (
    ChatMessage, ChatRole, LLMConfig, LLMResponse, ToolCall, ToolResult,
)
from .memory import MemoryManager
from .tools import Tool, ToolRegistry, create_builtin_tools

logger = logging.getLogger(__name__)


@dataclass
class ReasoningStep:
    """A single step in the ReAct loop."""
    step_number: int
    phase: str
    content: str
    tool_calls: List[ToolCall] = field(default_factory=list)
    tool_results: List[ToolResult] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


@dataclass
class Goal:
    """A goal for the autonomous agent."""
    goal_id: str
    description: str
    status: str = "pending"
    sub_goals: List['Goal'] = field(default_factory=list)
    result: Optional[Any] = None
    reasoning_trace: List[ReasoningStep] = field(default_factory=list)


@dataclass
class AutonomousConfig:
    """Extended configuration for autonomous agents."""
    llm: LLMConfig
    max_reasoning_steps: int = 20
    max_tool_calls_per_step: int = 5
    working_memory_tokens: int = 8000
    require_approval_for: List[str] = field(default_factory=list)
    reflection_frequency: int = 5
    system_prompt: Optional[str] = None


class AutonomousAgent(Agent):
    """
    Autonomous agent that extends MAPLE's Agent with LLM reasoning.

    Capabilities:
    - ReAct loop: Observe -> Think -> Act -> Reflect
    - Goal decomposition into sub-tasks
    - Self-correction on errors
    - Multi-step planning with backtracking
    - Tool selection and execution
    - Memory management (working, episodic, semantic)
    - Human-in-the-loop approval for risky actions
    """

    def __init__(
        self,
        config: Config,
        autonomy_config: AutonomousConfig,
        broker=None,
    ):
        super().__init__(config, broker)
        self.autonomy_config = autonomy_config

        # Initialize LLM provider
        provider_result = LLMProviderRegistry.create(autonomy_config.llm)
        if provider_result.is_err():
            raise RuntimeError(f"Failed to create LLM provider: {provider_result.unwrap_err()}")
        self.llm: LLMProvider = provider_result.unwrap()

        # Initialize tool registry with built-in tools
        self.tool_registry = ToolRegistry()
        for tool in create_builtin_tools(self):
            self.tool_registry.register(tool)

        # Initialize memory
        self.memory = MemoryManager(
            working_memory_tokens=autonomy_config.working_memory_tokens
        )

        # Approval callback for human-in-the-loop
        self._approval_callback: Optional[Callable[[str, Dict], bool]] = None

        # Active goals
        self._active_goals: Dict[str, Goal] = {}

        # Decision logger
        self._decision_logger = None

    def register_tool(self, tool: Tool) -> Result[None, Dict]:
        """Register an additional tool."""
        return self.tool_registry.register(tool)

    def set_approval_callback(self, callback: Callable[[str, Dict], bool]) -> None:
        """Set callback for human-in-the-loop approval."""
        self._approval_callback = callback

    def pursue_goal(self, description: str) -> Result[Goal, Dict[str, Any]]:
        """
        Main entry point: pursue a high-level goal using the ReAct loop.
        """
        goal = Goal(
            goal_id=str(uuid.uuid4()),
            description=description,
            status="in_progress",
        )
        self._active_goals[goal.goal_id] = goal

        try:
            result = self._react_loop(goal)
            if result.is_ok():
                goal.status = "completed"
                goal.result = result.unwrap()
            else:
                goal.status = "failed"
                goal.result = result.unwrap_err()
            return Result.ok(goal)
        except Exception as e:
            goal.status = "failed"
            goal.result = str(e)
            return Result.err({
                'errorType': 'GOAL_PURSUIT_ERROR',
                'message': str(e),
                'details': {'goal_id': goal.goal_id}
            })

    def _react_loop(self, goal: Goal) -> Result[Any, Dict[str, Any]]:
        """
        ReAct (Reasoning + Acting) loop.

        1. THINK: Use LLM to reason about what to do next
        2. ACT: Execute tool calls or send messages
        3. REFLECT: Assess progress, update memory, decide if done
        """
        messages = self._build_initial_context(goal)

        for step_num in range(self.autonomy_config.max_reasoning_steps):
            start_time = time.time()

            # THINK: Get LLM response
            tool_defs = self.tool_registry.get_llm_definitions()
            response_result = self.llm.complete(messages, tools=tool_defs if tool_defs else None)

            if response_result.is_err():
                return response_result

            response = response_result.unwrap()
            duration_ms = (time.time() - start_time) * 1000

            # Record reasoning step
            step = ReasoningStep(
                step_number=step_num,
                phase="think",
                content=response.content or "",
                tool_calls=response.tool_calls,
            )
            goal.reasoning_trace.append(step)

            # Log decision
            self._log_decision(goal, step, response, duration_ms)

            # Check if done (no tool calls and finish_reason == "stop")
            if not response.tool_calls and response.finish_reason == "stop":
                return Result.ok(response.content)

            # ACT: Execute tool calls
            if response.tool_calls:
                messages.append(ChatMessage(
                    role=ChatRole.ASSISTANT,
                    content=response.content or "",
                    tool_calls=response.tool_calls,
                ))

                for tool_call in response.tool_calls[:self.autonomy_config.max_tool_calls_per_step]:
                    tool_result = self._execute_tool_call(tool_call)
                    step.tool_results.append(tool_result)

                    messages.append(ChatMessage(
                        role=ChatRole.TOOL,
                        content=tool_result.content,
                        tool_call_id=tool_result.tool_call_id,
                        name=tool_call.name,
                    ))

                    # Update working memory
                    self.memory.working.add(
                        key=f"tool:{tool_call.name}:{step_num}",
                        content=tool_result.content[:500],
                    )
            else:
                messages.append(ChatMessage(
                    role=ChatRole.ASSISTANT,
                    content=response.content or "",
                ))

            # REFLECT: Every N steps, assess progress
            if (step_num + 1) % self.autonomy_config.reflection_frequency == 0:
                reflection = self._reflect(goal, messages, step_num)
                if reflection.get("should_stop"):
                    return Result.ok(reflection.get("conclusion", response.content))

        return Result.err({
            'errorType': 'MAX_STEPS_REACHED',
            'message': f'Reached maximum reasoning steps ({self.autonomy_config.max_reasoning_steps})',
        })

    def _execute_tool_call(self, tool_call: ToolCall) -> ToolResult:
        """Execute a single tool call with approval check."""
        tool_result = self.tool_registry.get(tool_call.name)
        if tool_result.is_err():
            return ToolResult(
                tool_call_id=tool_call.id,
                content=json.dumps(tool_result.unwrap_err()),
                is_error=True,
            )

        tool = tool_result.unwrap()

        # Human-in-the-loop check
        if tool.requires_approval or tool_call.name in self.autonomy_config.require_approval_for:
            if self._approval_callback:
                approved = self._approval_callback(tool_call.name, tool_call.arguments)
                if not approved:
                    return ToolResult(
                        tool_call_id=tool_call.id,
                        content='{"error": "Action not approved by human operator"}',
                        is_error=True,
                    )

        exec_result = tool.execute(**tool_call.arguments)
        if exec_result.is_ok():
            content = json.dumps(exec_result.unwrap(), default=str)
            return ToolResult(tool_call_id=tool_call.id, content=content)
        else:
            return ToolResult(
                tool_call_id=tool_call.id,
                content=json.dumps(exec_result.unwrap_err()),
                is_error=True,
            )

    def _build_initial_context(self, goal: Goal) -> List[ChatMessage]:
        """Build the initial message context for the ReAct loop."""
        system_prompt = self.autonomy_config.system_prompt or self._default_system_prompt()

        messages = [
            ChatMessage(role=ChatRole.SYSTEM, content=system_prompt),
        ]

        # Add working memory context
        context = self.memory.working.get_context()
        if context:
            messages.append(ChatMessage(
                role=ChatRole.SYSTEM,
                content=f"Current working memory:\n{json.dumps(context, default=str)}"
            ))

        messages.append(ChatMessage(
            role=ChatRole.USER,
            content=goal.description,
        ))

        return messages

    def _default_system_prompt(self) -> str:
        tools_desc = "\n".join(
            f"- {t.name}: {t.description}"
            for t in self.tool_registry.list_tools()
        )
        return f"""You are an autonomous MAPLE agent (ID: {self.agent_id}).
You can reason step by step and use tools to accomplish goals.

Available tools:
{tools_desc}

Instructions:
1. Think carefully before acting.
2. Use tools when you need information or need to take action.
3. If a tool call fails, analyze the error and try a different approach.
4. When you have completed the goal, respond with your final answer without calling any tools.
5. If you cannot complete the goal, explain why."""

    def _reflect(self, goal: Goal, messages: List[ChatMessage], step_num: int) -> Dict:
        """Ask the LLM to reflect on progress."""
        reflection_messages = messages + [ChatMessage(
            role=ChatRole.USER,
            content=f"""Reflect on your progress toward the goal: "{goal.description}"
Step {step_num + 1}/{self.autonomy_config.max_reasoning_steps}.
Are you making progress? Should you continue or stop?
Respond with JSON: {{"should_stop": bool, "conclusion": "your conclusion if stopping", "reason": "why"}}"""
        )]

        result = self.llm.complete(reflection_messages)
        if result.is_ok():
            try:
                content = result.unwrap().content or ""
                # Try to extract JSON from the response
                if '{' in content:
                    json_str = content[content.index('{'):content.rindex('}') + 1]
                    return json.loads(json_str)
            except (json.JSONDecodeError, ValueError):
                pass
        return {"should_stop": False}

    def decompose_goal(self, goal: Goal) -> Result[List[Goal], Dict]:
        """Use LLM to decompose a complex goal into sub-goals."""
        messages = [
            ChatMessage(role=ChatRole.SYSTEM, content="Decompose this goal into 2-5 sub-goals. Respond as a JSON array of strings."),
            ChatMessage(role=ChatRole.USER, content=goal.description),
        ]
        result = self.llm.complete(messages)
        if result.is_err():
            return result
        try:
            content = result.unwrap().content or "[]"
            if '[' in content:
                json_str = content[content.index('['):content.rindex(']') + 1]
                sub_descriptions = json.loads(json_str)
            else:
                sub_descriptions = [content]
            sub_goals = [
                Goal(goal_id=str(uuid.uuid4()), description=d)
                for d in sub_descriptions if isinstance(d, str)
            ]
            goal.sub_goals = sub_goals
            return Result.ok(sub_goals)
        except Exception as e:
            return Result.err({'errorType': 'DECOMPOSITION_ERROR', 'message': str(e)})

    def _log_decision(self, goal: Goal, step: ReasoningStep, response: LLMResponse, duration_ms: float) -> None:
        """Log a decision for observability."""
        if self._decision_logger:
            from .observability import DecisionTrace
            trace = DecisionTrace(
                agent_id=self.agent_id,
                goal_id=goal.goal_id,
                step_number=step.step_number,
                timestamp=time.time(),
                prompt_summary=f"Step {step.step_number}",
                response_summary=(response.content or "")[:200],
                tool_calls=[{'name': tc.name, 'args': tc.arguments} for tc in response.tool_calls],
                tool_results=[],
                token_usage=response.usage.__dict__ if response.usage else {},
                duration_ms=duration_ms,
            )
            self._decision_logger.log_decision(trace)

    def get_active_goals(self) -> Dict[str, Goal]:
        """Get all active goals."""
        return dict(self._active_goals)

    # --- Async support ---

    async def pursue_goal_async(self, description: str) -> Result['Goal', Dict[str, Any]]:
        """Async entry point: pursue a high-level goal using the async ReAct loop."""
        goal = Goal(
            goal_id=str(uuid.uuid4()),
            description=description,
            status="in_progress",
        )
        self._active_goals[goal.goal_id] = goal

        try:
            result = await self._react_loop_async(goal)
            if result.is_ok():
                goal.status = "completed"
                goal.result = result.unwrap()
            else:
                goal.status = "failed"
                goal.result = result.unwrap_err()
            return Result.ok(goal)
        except Exception as e:
            goal.status = "failed"
            goal.result = str(e)
            return Result.err({
                'errorType': 'GOAL_PURSUIT_ERROR',
                'message': str(e),
                'details': {'goal_id': goal.goal_id}
            })

    async def _react_loop_async(self, goal: Goal) -> Result[Any, Dict[str, Any]]:
        """Async ReAct loop — enables parallel tool execution and async LLM calls."""
        messages = self._build_initial_context(goal)

        for step_num in range(self.autonomy_config.max_reasoning_steps):
            start_time = time.time()

            # THINK: Get LLM response (async when available)
            tool_defs = self.tool_registry.get_llm_definitions()
            response_result = await self.llm.complete_async(
                messages, tools=tool_defs if tool_defs else None
            )

            if response_result.is_err():
                return response_result

            response = response_result.unwrap()
            duration_ms = (time.time() - start_time) * 1000

            step = ReasoningStep(
                step_number=step_num,
                phase="think",
                content=response.content or "",
                tool_calls=response.tool_calls,
            )
            goal.reasoning_trace.append(step)
            self._log_decision(goal, step, response, duration_ms)

            if not response.tool_calls and response.finish_reason == "stop":
                return Result.ok(response.content)

            if response.tool_calls:
                messages.append(ChatMessage(
                    role=ChatRole.ASSISTANT,
                    content=response.content or "",
                    tool_calls=response.tool_calls,
                ))

                for tool_call in response.tool_calls[:self.autonomy_config.max_tool_calls_per_step]:
                    tool_result = self._execute_tool_call(tool_call)
                    step.tool_results.append(tool_result)

                    messages.append(ChatMessage(
                        role=ChatRole.TOOL,
                        content=tool_result.content,
                        tool_call_id=tool_result.tool_call_id,
                        name=tool_call.name,
                    ))

                    self.memory.working.add(
                        key=f"tool:{tool_call.name}:{step_num}",
                        content=tool_result.content[:500],
                    )
            else:
                messages.append(ChatMessage(
                    role=ChatRole.ASSISTANT,
                    content=response.content or "",
                ))

            if (step_num + 1) % self.autonomy_config.reflection_frequency == 0:
                reflection = self._reflect(goal, messages, step_num)
                if reflection.get("should_stop"):
                    return Result.ok(reflection.get("conclusion", response.content))

        return Result.err({
            'errorType': 'MAX_STEPS_REACHED',
            'message': f'Reached maximum reasoning steps ({self.autonomy_config.max_reasoning_steps})',
        })
