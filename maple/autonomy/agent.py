# Copyright (C) 2025 Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)
#
# This file is part of MAPLE - Multi Agent Protocol Language Engine.
#
# MAPLE - Multi Agent Protocol Language Engine is free software: you can
# redistribute it and/or modify it under the terms of the GNU Affero General
# Public License as published by the Free Software Foundation, either version 3
# of the License, or (at your option) any later version.
# MAPLE - Multi Agent Protocol Language Engine is distributed in the hope that
# it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty
# of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero
# General Public License for more details. You should have received a copy of
# the GNU Affero General Public License along with MAPLE - Multi Agent Protocol
# Language Engine. If not, see <https://www.gnu.org/licenses/>.

import asyncio
import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Type

from ..agent.agent import Agent
from ..agent.config import Config
from ..broker.broker import MessageBroker
from ..core.result import Result
from ..llm.provider import LLMProvider
from ..llm.registry import LLMProviderRegistry
from ..llm.types import (
    ChatMessage,
    ChatRole,
    LLMConfig,
    LLMResponse,
    ToolCall,
    ToolResult,
)
from .approval import ApprovalRequest, ApprovalStore
from .contracts import (
    Guardrail,
    parse_structured_output,
    parse_typed_output,
    run_guardrails,
    structured_model_schema,
)
from .memory import MemoryManager
from .sessions import SessionMessage, SessionSnapshot, SessionStore
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
    sub_goals: List["Goal"] = field(default_factory=list)
    result: Optional[Any] = None
    reasoning_trace: List[ReasoningStep] = field(default_factory=list)
    session_id: Optional[str] = None
    session_error: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class _SessionTurn:
    """The versioned session state used by one agent turn."""

    session_id: str
    version: int
    messages: Tuple[SessionMessage, ...]


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
    response_schema: Optional[Dict[str, Any]] = None
    output_model: Optional[Type[Any]] = None
    input_guardrails: List[Guardrail] = field(default_factory=list)
    output_guardrails: List[Guardrail] = field(default_factory=list)


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
        broker: Optional[MessageBroker] = None,
    ) -> None:
        super().__init__(config, broker)
        self.autonomy_config = autonomy_config
        self._output_schema: Optional[Dict[str, Any]] = autonomy_config.response_schema
        if autonomy_config.output_model is not None:
            output_schema = structured_model_schema(autonomy_config.output_model)
            if output_schema.is_err():
                error = output_schema.unwrap_err()
                raise ValueError(error.get("message", "Invalid output_model"))
            self._output_schema = output_schema.unwrap()

        # Initialize LLM provider
        provider_result = LLMProviderRegistry.create(autonomy_config.llm)
        if provider_result.is_err():
            raise RuntimeError(
                f"Failed to create LLM provider: {provider_result.unwrap_err()}"
            )
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
        self._approval_store: Optional[ApprovalStore] = None
        self._approval_namespace = uuid.uuid4().hex
        self._session_store: Optional[SessionStore] = None

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

    def set_session_store(self, store: Optional[SessionStore]) -> None:
        """Set the opt-in store used for session-aware agent turns."""
        if store is not None:
            required_methods = ("create", "load", "append", "clear")
            if any(
                not callable(getattr(store, name, None)) for name in required_methods
            ):
                raise TypeError(
                    "session store must implement create, load, append, and clear"
                )
        self._session_store = store

    def set_approval_store(self, store: Optional[ApprovalStore]) -> None:
        """Set a durable store used when approval callbacks are unavailable."""
        if store is not None:
            required_methods = (
                "get",
                "create",
                "decide",
                "consume",
                "list_pending",
            )
            if any(
                not callable(getattr(store, name, None)) for name in required_methods
            ):
                raise TypeError(
                    "approval store must implement get, create, decide, and consume"
                )
        self._approval_store = store

    def decide_approval(
        self, approval_id: str, approved: bool
    ) -> Result[ApprovalRequest, Dict[str, Any]]:
        """Record an operator decision for a pending tool action."""
        if self._approval_store is None:
            return Result.err(
                {
                    "errorType": "APPROVAL_STORE_UNAVAILABLE",
                    "message": "No durable approval store is configured.",
                }
            )
        return self._approval_store.decide(approval_id, approved)

    def execute_approved_tool(self, approval_id: str) -> ToolResult:
        """Consume and execute one approved durable tool request.

        Consuming happens before the handler runs, so a request cannot be
        replayed accidentally. A handler failure is returned as a tool error;
        callers must create a new approval request before retrying the action.
        """
        if self._approval_store is None:
            return self._approval_error(
                approval_id,
                "APPROVAL_STORE_UNAVAILABLE",
                "No durable approval store is configured.",
            )
        request_result = self._approval_store.get(approval_id)
        if request_result.is_err():
            return self._approval_error(
                approval_id,
                "APPROVAL_ERROR",
                "Approval request could not be loaded.",
            )
        request = request_result.unwrap()
        if request is None:
            return self._approval_error(
                approval_id,
                "APPROVAL_NOT_FOUND",
                "Approval request was not found.",
            )
        if request.status != "approved":
            error_type = (
                "APPROVAL_PENDING"
                if request.status == "pending"
                else (
                    "APPROVAL_DENIED"
                    if request.status == "denied"
                    else "APPROVAL_CONSUMED"
                )
            )
            return self._approval_error(
                request.tool_call_id,
                error_type,
                "Approval request is not executable.",
            )
        consumed_result = self._approval_store.consume(approval_id)
        if consumed_result.is_err():
            return self._approval_error(
                request.tool_call_id,
                "APPROVAL_ERROR",
                "Approval request could not be claimed.",
            )
        return self._execute_tool_call(
            ToolCall(
                id=request.tool_call_id,
                name=request.tool_name,
                arguments=request.arguments,
            ),
            skip_approval=True,
        )

    @staticmethod
    def _session_store_failure(
        operation: str, exception: Exception
    ) -> Result[Any, Dict[str, Any]]:
        return Result.err(
            {
                "errorType": "SESSION_STORE_ERROR",
                "message": "Session store operation failed.",
                "details": {
                    "operation": operation,
                    "exception": type(exception).__name__,
                },
            }
        )

    def _prepare_session_turn(
        self, description: str, session_id: Optional[str]
    ) -> Result[Optional[_SessionTurn], Dict[str, Any]]:
        try:
            return self._prepare_session_turn_unchecked(description, session_id)
        except Exception as exc:
            return self._session_store_failure("prepare", exc)

    def _prepare_session_turn_unchecked(
        self, description: str, session_id: Optional[str]
    ) -> Result[Optional[_SessionTurn], Dict[str, Any]]:
        """Create/load a session and CAS-append the current user turn."""
        if session_id is None:
            return Result.ok(None)
        if self._session_store is None:
            return Result.err(
                {
                    "errorType": "SESSION_STORE_UNAVAILABLE",
                    "message": (
                        "A session store is required when session_id is provided."
                    ),
                }
            )

        loaded = self._session_store.load(session_id)
        if loaded.is_err():
            return Result.err(loaded.unwrap_err())
        snapshot = loaded.unwrap()
        if snapshot is None:
            created = self._session_store.create(session_id)
            if created.is_err():
                if created.unwrap_err().get("errorType") != "SESSION_EXISTS":
                    return Result.err(created.unwrap_err())
                loaded = self._session_store.load(session_id)
                if loaded.is_err():
                    return Result.err(loaded.unwrap_err())
                snapshot = loaded.unwrap()
            else:
                snapshot = created.unwrap()
        if not isinstance(snapshot, SessionSnapshot):
            return Result.err(
                {
                    "errorType": "SESSION_STORE_INVALID",
                    "message": "Session store returned an invalid snapshot.",
                }
            )

        appended = self._session_store.append(
            session_id,
            SessionMessage(role=ChatRole.USER.value, content=description),
            expected_version=snapshot.version,
        )
        if appended.is_err():
            return Result.err(appended.unwrap_err())
        updated = appended.unwrap()
        if not isinstance(updated, SessionSnapshot):
            return Result.err(
                {
                    "errorType": "SESSION_STORE_INVALID",
                    "message": "Session store returned an invalid appended snapshot.",
                }
            )
        return Result.ok(
            _SessionTurn(
                session_id=updated.session_id,
                version=updated.version,
                messages=tuple(updated.messages),
            )
        )

    @staticmethod
    def _serialize_session_result(value: Any) -> Result[str, Dict[str, Any]]:
        """Encode a goal result as bounded-store-compatible text."""
        if isinstance(value, str):
            return Result.ok(value)
        try:
            return Result.ok(
                json.dumps(
                    value,
                    ensure_ascii=False,
                    allow_nan=False,
                    separators=(",", ":"),
                )
            )
        except (TypeError, ValueError, OverflowError):
            return Result.err(
                {
                    "errorType": "SESSION_RESULT_INVALID",
                    "message": (
                        "The goal result could not be serialized for the session."
                    ),
                }
            )

    def _record_session_turn(
        self, session_turn: Optional[_SessionTurn], goal: Goal
    ) -> Result[None, Dict[str, Any]]:
        """Append one assistant result after execution, using the prior version."""
        try:
            return self._record_session_turn_unchecked(session_turn, goal)
        except Exception as exc:
            return self._session_store_failure("record", exc)

    def _record_session_turn_unchecked(
        self, session_turn: Optional[_SessionTurn], goal: Goal
    ) -> Result[None, Dict[str, Any]]:
        if session_turn is None:
            return Result.ok(None)
        if self._session_store is None:
            return Result.err(
                {
                    "errorType": "SESSION_STORE_UNAVAILABLE",
                    "message": "The configured session store is no longer available.",
                }
            )
        serialized = self._serialize_session_result(goal.result)
        if serialized.is_err():
            return Result.err(serialized.unwrap_err())
        appended = self._session_store.append(
            session_turn.session_id,
            SessionMessage(
                role=ChatRole.ASSISTANT.value,
                content=serialized.unwrap(),
                metadata={"goal_id": goal.goal_id, "status": goal.status},
            ),
            expected_version=session_turn.version,
        )
        if appended.is_err():
            return Result.err(appended.unwrap_err())
        if not isinstance(appended.unwrap(), SessionSnapshot):
            return Result.err(
                {
                    "errorType": "SESSION_STORE_INVALID",
                    "message": "Session store returned an invalid result snapshot.",
                }
            )
        return Result.ok(None)

    async def _prepare_session_turn_async(
        self, description: str, session_id: Optional[str]
    ) -> Result[Optional[_SessionTurn], Dict[str, Any]]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self._prepare_session_turn, description, session_id
        )

    async def _record_session_turn_async(
        self, session_turn: Optional[_SessionTurn], goal: Goal
    ) -> Result[None, Dict[str, Any]]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self._record_session_turn, session_turn, goal
        )

    def pursue_goal(
        self, description: str, *, session_id: Optional[str] = None
    ) -> Result[Goal, Dict[str, Any]]:
        """
        Main entry point: pursue a high-level goal using the ReAct loop.
        """
        input_guardrails = run_guardrails(
            description,
            self.autonomy_config.input_guardrails,
            stage="agent:input",
        )
        if input_guardrails.is_err():
            return Result.err(input_guardrails.unwrap_err())
        session_result = self._prepare_session_turn(description, session_id)
        if session_result.is_err():
            return Result.err(session_result.unwrap_err())
        session_turn = session_result.unwrap()
        goal = Goal(
            goal_id=str(uuid.uuid4()),
            description=description,
            status="in_progress",
            session_id=session_id,
        )
        self._active_goals[goal.goal_id] = goal

        try:
            result = self._react_loop(
                goal,
                session_messages=(
                    session_turn.messages if session_turn is not None else None
                ),
            )
            if result.is_ok():
                goal.status = "completed"
                goal.result = result.unwrap()
            else:
                goal.status = "failed"
                goal.result = result.unwrap_err()
            session_record = self._record_session_turn(session_turn, goal)
            if session_record.is_err():
                goal.session_error = session_record.unwrap_err()
            return Result.ok(goal)
        except Exception as e:
            goal.status = "failed"
            goal.result = str(e)
            return Result.err(
                {
                    "errorType": "GOAL_PURSUIT_ERROR",
                    "message": str(e),
                    "details": {"goal_id": goal.goal_id},
                }
            )

    def _react_loop(
        self,
        goal: Goal,
        *,
        session_messages: Optional[Sequence[SessionMessage]] = None,
    ) -> Result[Any, Dict[str, Any]]:
        """
        ReAct (Reasoning + Acting) loop.

        1. THINK: Use LLM to reason about what to do next
        2. ACT: Execute tool calls or send messages
        3. REFLECT: Assess progress, update memory, decide if done
        """
        messages = self._build_initial_context(goal, session_messages=session_messages)

        for step_num in range(self.autonomy_config.max_reasoning_steps):
            start_time = time.time()

            # THINK: Get LLM response
            tool_defs = self.tool_registry.get_llm_definitions()
            response_result = self.llm.complete(
                messages, tools=tool_defs if tool_defs else None
            )

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
                return self._finalize_output(response.content)

            # ACT: Execute tool calls
            if response.tool_calls:
                messages.append(
                    ChatMessage(
                        role=ChatRole.ASSISTANT,
                        content=response.content or "",
                        tool_calls=response.tool_calls,
                    )
                )

                for tool_call in response.tool_calls[
                    : self.autonomy_config.max_tool_calls_per_step
                ]:
                    tool_result = self._execute_tool_call(tool_call)
                    step.tool_results.append(tool_result)

                    messages.append(
                        ChatMessage(
                            role=ChatRole.TOOL,
                            content=tool_result.content,
                            tool_call_id=tool_result.tool_call_id,
                            name=tool_call.name,
                        )
                    )

                    # Update working memory
                    self.memory.working.add(
                        key=f"tool:{tool_call.name}:{step_num}",
                        content=tool_result.content[:500],
                    )
            else:
                messages.append(
                    ChatMessage(
                        role=ChatRole.ASSISTANT,
                        content=response.content or "",
                    )
                )

            # REFLECT: Every N steps, assess progress
            if (step_num + 1) % self.autonomy_config.reflection_frequency == 0:
                reflection = self._reflect(goal, messages, step_num)
                if reflection.get("should_stop"):
                    return self._finalize_output(
                        reflection.get("conclusion", response.content)
                    )

        return Result.err(
            {
                "errorType": "MAX_STEPS_REACHED",
                "message": (
                    "Reached maximum reasoning steps "
                    f"({self.autonomy_config.max_reasoning_steps})"
                ),
            }
        )

    def _execute_tool_call(
        self, tool_call: ToolCall, *, skip_approval: bool = False
    ) -> ToolResult:
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
        if not skip_approval and (
            tool.requires_approval
            or tool_call.name in self.autonomy_config.require_approval_for
        ):
            if self._approval_callback is None and self._approval_store is not None:
                approval_id = self._approval_id_for_tool_call(tool_call)
                try:
                    request = ApprovalRequest(
                        approval_id=approval_id,
                        tool_call_id=tool_call.id,
                        tool_name=tool_call.name,
                        arguments=dict(tool_call.arguments),
                    )
                    request_result = self._approval_store.create(request)
                except (TypeError, ValueError):
                    return self._approval_error(
                        tool_call.id,
                        "APPROVAL_ERROR",
                        "Approval request arguments are invalid.",
                    )
                if request_result.is_err():
                    return self._approval_error(
                        tool_call.id,
                        "APPROVAL_ERROR",
                        "Approval request could not be persisted.",
                    )
                request = request_result.unwrap()
                if request.status == "pending":
                    return self._approval_error(
                        tool_call.id,
                        "APPROVAL_PENDING",
                        "Tool execution is waiting for operator approval.",
                        approval_id=request.approval_id,
                    )
                if request.status == "denied":
                    return self._approval_error(
                        tool_call.id,
                        "APPROVAL_DENIED",
                        "Action was not approved by the operator.",
                        approval_id=request.approval_id,
                    )
                if request.status == "consumed":
                    return self._approval_error(
                        tool_call.id,
                        "APPROVAL_CONSUMED",
                        "Approval request was already consumed.",
                        approval_id=request.approval_id,
                    )
                consumed_result = self._approval_store.consume(request.approval_id)
                if consumed_result.is_err():
                    return self._approval_error(
                        tool_call.id,
                        "APPROVAL_ERROR",
                        "Approval request could not be claimed.",
                    )
            elif self._approval_callback is None:
                return ToolResult(
                    tool_call_id=tool_call.id,
                    content=json.dumps(
                        {
                            "errorType": "APPROVAL_REQUIRED",
                            "message": "Tool execution requires approval.",
                            "details": {"tool": tool_call.name},
                        }
                    ),
                    is_error=True,
                )
            approval_callback = self._approval_callback
            if approval_callback is None:
                return self._approval_error(
                    tool_call.id,
                    "APPROVAL_REQUIRED",
                    "Tool execution requires approval.",
                )
            try:
                approved = approval_callback(tool_call.name, tool_call.arguments)
            except Exception as exc:
                return ToolResult(
                    tool_call_id=tool_call.id,
                    content=json.dumps(
                        {
                            "errorType": "APPROVAL_ERROR",
                            "message": "Approval failed closed.",
                            "details": {
                                "tool": tool_call.name,
                                "exception": type(exc).__name__,
                            },
                        }
                    ),
                    is_error=True,
                )
            if not approved:
                return ToolResult(
                    tool_call_id=tool_call.id,
                    content=json.dumps(
                        {
                            "errorType": "APPROVAL_DENIED",
                            "message": "Action was not approved by the operator.",
                            "details": {"tool": tool_call.name},
                        }
                    ),
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

    def _approval_id_for_tool_call(self, tool_call: ToolCall) -> str:
        payload = json.dumps(
            {
                "namespace": self._approval_namespace,
                "tool_call_id": tool_call.id,
                "tool": tool_call.name,
                "arguments": tool_call.arguments,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return f"approval-{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"

    @staticmethod
    def _approval_error(
        tool_call_id: str,
        error_type: str,
        message: str,
        **details: Any,
    ) -> ToolResult:
        payload: Dict[str, Any] = {"errorType": error_type, "message": message}
        if details:
            payload["details"] = details
        return ToolResult(
            tool_call_id=tool_call_id,
            content=json.dumps(payload),
            is_error=True,
        )

    def _build_initial_context(
        self,
        goal: Goal,
        *,
        session_messages: Optional[Sequence[SessionMessage]] = None,
    ) -> List[ChatMessage]:
        """Build the initial message context for the ReAct loop."""
        system_prompt = (
            self.autonomy_config.system_prompt or self._default_system_prompt()
        )

        messages = [
            ChatMessage(role=ChatRole.SYSTEM, content=system_prompt),
        ]

        # Add working memory context
        context = self.memory.working.get_context()
        if context:
            messages.append(
                ChatMessage(
                    role=ChatRole.SYSTEM,
                    content=(
                        "Current working memory:\n"
                        f"{json.dumps(context, default=str)}"
                    ),
                )
            )

        if session_messages is None:
            messages.append(
                ChatMessage(
                    role=ChatRole.USER,
                    content=goal.description,
                )
            )
        else:
            # Stored system/tool messages are data only and are never replayed
            # into a new prompt. The current user turn was already appended by
            # _prepare_session_turn with a compare-and-swap version check.
            messages.extend(
                message.to_chat_message()
                for message in session_messages
                if message.role in {ChatRole.USER.value, ChatRole.ASSISTANT.value}
            )

        return messages

    def _default_system_prompt(self) -> str:
        tools_desc = "\n".join(
            f"- {t.name}: {t.description}" for t in self.tool_registry.list_tools()
        )
        output_instruction = ""
        if self._output_schema is not None:
            output_instruction = (
                "\nReturn the final response as JSON matching this schema:\n"
                f"{json.dumps(self._output_schema, default=str)}\n"
            )
        return (
            f"""You are an autonomous MAPLE agent (ID: {self.agent_id}).
You can reason step by step and use tools to accomplish goals.

Available tools:
{tools_desc}

Instructions:
1. Think carefully before acting.
2. Use tools when you need information or need to take action.
3. If a tool call fails, analyze the error and try a different approach.
"""
            "4. When you have completed the goal, respond with your final "
            "answer without calling any tools.\n"
            f"5. If you cannot complete the goal, explain why.\n{output_instruction}"
        )

    def _finalize_output(self, content: Optional[str]) -> Result[Any, Dict[str, Any]]:
        """Parse structured output and apply output guardrails at the boundary."""
        if self.autonomy_config.output_model is not None:
            parsed = parse_typed_output(content, self.autonomy_config.output_model)
        else:
            parsed = parse_structured_output(
                content, self.autonomy_config.response_schema
            )
        if parsed.is_err():
            return Result.err(parsed.unwrap_err())
        guardrails = run_guardrails(
            parsed.unwrap(),
            self.autonomy_config.output_guardrails,
            stage="agent:output",
        )
        if guardrails.is_err():
            return Result.err(guardrails.unwrap_err())
        return Result.ok(parsed.unwrap())

    def _reflect(
        self, goal: Goal, messages: List[ChatMessage], step_num: int
    ) -> Dict[str, Any]:
        """Ask the LLM to reflect on progress."""
        reflection_prompt = (
            f'Reflect on your progress toward the goal: "{goal.description}"\n'
            f"Step {step_num + 1}/{self.autonomy_config.max_reasoning_steps}.\n"
            "Are you making progress? Should you continue or stop?\n"
            'Respond with JSON: {"should_stop": bool, "conclusion": '
            '"your conclusion if stopping", "reason": "why"}'
        )
        reflection_messages = messages + [
            ChatMessage(
                role=ChatRole.USER,
                content=reflection_prompt,
            )
        ]

        result = self.llm.complete(reflection_messages)
        if result.is_ok():
            try:
                content = result.unwrap().content or ""
                # Try to extract JSON from the response
                if "{" in content:
                    json_str = content[content.index("{") : content.rindex("}") + 1]
                    reflection = json.loads(json_str)
                    if isinstance(reflection, dict):
                        return reflection
            except (json.JSONDecodeError, ValueError):
                pass
        return {"should_stop": False}

    def decompose_goal(self, goal: Goal) -> Result[List[Goal], Dict[str, Any]]:
        """Use LLM to decompose a complex goal into sub-goals."""
        messages = [
            ChatMessage(
                role=ChatRole.SYSTEM,
                content=(
                    "Decompose this goal into 2-5 sub-goals. "
                    "Respond as a JSON array of strings."
                ),
            ),
            ChatMessage(role=ChatRole.USER, content=goal.description),
        ]
        result = self.llm.complete(messages)
        if result.is_err():
            return Result.err(result.unwrap_err())
        try:
            content = result.unwrap().content or "[]"
            if "[" in content:
                json_str = content[content.index("[") : content.rindex("]") + 1]
                sub_descriptions = json.loads(json_str)
            else:
                sub_descriptions = [content]
            sub_goals = [
                Goal(goal_id=str(uuid.uuid4()), description=d)
                for d in sub_descriptions
                if isinstance(d, str)
            ]
            goal.sub_goals = sub_goals
            return Result.ok(sub_goals)
        except Exception as e:
            return Result.err({"errorType": "DECOMPOSITION_ERROR", "message": str(e)})

    def _log_decision(
        self, goal: Goal, step: ReasoningStep, response: LLMResponse, duration_ms: float
    ) -> None:
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
                tool_calls=[
                    {"name": tc.name, "args": tc.arguments}
                    for tc in response.tool_calls
                ],
                tool_results=[],
                token_usage=response.usage.__dict__ if response.usage else {},
                duration_ms=duration_ms,
            )
            self._decision_logger.log_decision(trace)

    def get_active_goals(self) -> Dict[str, Goal]:
        """Get all active goals."""
        return dict(self._active_goals)

    # --- Async support ---

    async def pursue_goal_async(
        self, description: str, *, session_id: Optional[str] = None
    ) -> Result["Goal", Dict[str, Any]]:
        """Async entry point: pursue a high-level goal using the async ReAct loop."""
        input_guardrails = run_guardrails(
            description,
            self.autonomy_config.input_guardrails,
            stage="agent:input",
        )
        if input_guardrails.is_err():
            return Result.err(input_guardrails.unwrap_err())
        session_result = await self._prepare_session_turn_async(description, session_id)
        if session_result.is_err():
            return Result.err(session_result.unwrap_err())
        session_turn = session_result.unwrap()
        goal = Goal(
            goal_id=str(uuid.uuid4()),
            description=description,
            status="in_progress",
            session_id=session_id,
        )
        self._active_goals[goal.goal_id] = goal

        try:
            result = await self._react_loop_async(
                goal,
                session_messages=(
                    session_turn.messages if session_turn is not None else None
                ),
            )
            if result.is_ok():
                goal.status = "completed"
                goal.result = result.unwrap()
            else:
                goal.status = "failed"
                goal.result = result.unwrap_err()
            session_record = await self._record_session_turn_async(session_turn, goal)
            if session_record.is_err():
                goal.session_error = session_record.unwrap_err()
            return Result.ok(goal)
        except Exception as e:
            goal.status = "failed"
            goal.result = str(e)
            return Result.err(
                {
                    "errorType": "GOAL_PURSUIT_ERROR",
                    "message": str(e),
                    "details": {"goal_id": goal.goal_id},
                }
            )

    async def _react_loop_async(
        self,
        goal: Goal,
        *,
        session_messages: Optional[Sequence[SessionMessage]] = None,
    ) -> Result[Any, Dict[str, Any]]:
        """Async ReAct loop — enables parallel tool execution and async LLM calls."""
        messages = self._build_initial_context(goal, session_messages=session_messages)

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
                return self._finalize_output(response.content)

            if response.tool_calls:
                messages.append(
                    ChatMessage(
                        role=ChatRole.ASSISTANT,
                        content=response.content or "",
                        tool_calls=response.tool_calls,
                    )
                )

                tool_calls = response.tool_calls[
                    : self.autonomy_config.max_tool_calls_per_step
                ]
                loop = asyncio.get_running_loop()
                tool_results = await asyncio.gather(
                    *[
                        loop.run_in_executor(None, self._execute_tool_call, tool_call)
                        for tool_call in tool_calls
                    ],
                    return_exceptions=True,
                )
                for tool_call, tool_result in zip(tool_calls, tool_results):
                    if isinstance(tool_result, BaseException):
                        normalized_result = ToolResult(
                            tool_call_id=tool_call.id,
                            content=json.dumps(
                                {
                                    "errorType": "TOOL_EXECUTION_ERROR",
                                    "message": "Tool execution worker failed.",
                                    "details": {
                                        "tool": tool_call.name,
                                        "exception": type(tool_result).__name__,
                                    },
                                }
                            ),
                            is_error=True,
                        )
                    else:
                        normalized_result = tool_result
                    step.tool_results.append(normalized_result)

                    messages.append(
                        ChatMessage(
                            role=ChatRole.TOOL,
                            content=normalized_result.content,
                            tool_call_id=normalized_result.tool_call_id,
                            name=tool_call.name,
                        )
                    )

                    self.memory.working.add(
                        key=f"tool:{tool_call.name}:{step_num}",
                        content=normalized_result.content[:500],
                    )
            else:
                messages.append(
                    ChatMessage(
                        role=ChatRole.ASSISTANT,
                        content=response.content or "",
                    )
                )

            if (step_num + 1) % self.autonomy_config.reflection_frequency == 0:
                reflection = self._reflect(goal, messages, step_num)
                if reflection.get("should_stop"):
                    return self._finalize_output(
                        reflection.get("conclusion", response.content)
                    )

        return Result.err(
            {
                "errorType": "MAX_STEPS_REACHED",
                "message": (
                    "Reached maximum reasoning steps "
                    f"({self.autonomy_config.max_reasoning_steps})"
                ),
            }
        )
