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

"""Observability for MAPLE autonomous agents."""

import json
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class DecisionTrace:
    """A single decision trace from the ReAct loop."""
    agent_id: str
    goal_id: str
    step_number: int
    timestamp: float
    prompt_summary: str
    response_summary: str
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    token_usage: Dict[str, int] = field(default_factory=dict)
    duration_ms: float = 0.0


class DecisionLogger:
    """Logs and retrieves decision traces for debugging and observability."""

    def __init__(self, max_traces: int = 1000):
        self._traces: deque = deque(maxlen=max_traces)
        self._by_goal: Dict[str, List[DecisionTrace]] = {}

    def log_decision(self, trace: DecisionTrace) -> None:
        """Log a decision trace."""
        self._traces.append(trace)
        if trace.goal_id not in self._by_goal:
            self._by_goal[trace.goal_id] = []
        self._by_goal[trace.goal_id].append(trace)

    def get_traces(self, goal_id: Optional[str] = None) -> List[DecisionTrace]:
        """Retrieve decision traces, optionally filtered by goal."""
        if goal_id:
            return list(self._by_goal.get(goal_id, []))
        return list(self._traces)

    def get_summary(self, goal_id: str) -> Dict[str, Any]:
        """Get a summary of decisions for a goal."""
        traces = self._by_goal.get(goal_id, [])
        if not traces:
            return {"goal_id": goal_id, "steps": 0}

        total_tokens = sum(
            t.token_usage.get("total_tokens", 0) for t in traces
        )
        total_duration = sum(t.duration_ms for t in traces)
        tool_call_count = sum(len(t.tool_calls) for t in traces)

        return {
            "goal_id": goal_id,
            "steps": len(traces),
            "total_tokens": total_tokens,
            "total_duration_ms": total_duration,
            "tool_calls": tool_call_count,
            "first_step": traces[0].timestamp if traces else None,
            "last_step": traces[-1].timestamp if traces else None,
        }

    def export_json(self, goal_id: Optional[str] = None) -> str:
        """Export traces as JSON."""
        traces = self.get_traces(goal_id)
        return json.dumps(
            [
                {
                    "agent_id": t.agent_id,
                    "goal_id": t.goal_id,
                    "step_number": t.step_number,
                    "timestamp": t.timestamp,
                    "prompt_summary": t.prompt_summary,
                    "response_summary": t.response_summary,
                    "tool_calls": t.tool_calls,
                    "tool_results": t.tool_results,
                    "token_usage": t.token_usage,
                    "duration_ms": t.duration_ms,
                }
                for t in traces
            ],
            indent=2,
        )

    @property
    def trace_count(self) -> int:
        return len(self._traces)


class AgentSnapshot:
    """Captures a point-in-time snapshot of an autonomous agent's state."""

    @staticmethod
    def capture(agent) -> Dict[str, Any]:
        """Capture a snapshot of an autonomous agent."""
        snapshot = {
            "agent_id": agent.agent_id,
            "timestamp": time.time(),
            "status": getattr(agent, "status", "unknown"),
        }

        # LLM usage stats
        if hasattr(agent, "llm"):
            snapshot["llm_usage"] = agent.llm.get_usage_stats()

        # Working memory
        if hasattr(agent, "memory"):
            snapshot["working_memory"] = {
                "entries": agent.memory.working.size,
                "token_usage": agent.memory.working.token_usage,
                "max_tokens": agent.memory.working.max_tokens,
            }

        # Active goals
        if hasattr(agent, "_active_goals"):
            snapshot["active_goals"] = {
                gid: {
                    "description": g.description,
                    "status": g.status,
                    "steps": len(g.reasoning_trace),
                }
                for gid, g in agent._active_goals.items()
            }

        # Agent metrics
        for attr in ["messages_sent", "messages_received", "messages_failed"]:
            if hasattr(agent, attr):
                snapshot[attr] = getattr(agent, attr)

        # Tool registry
        if hasattr(agent, "tool_registry"):
            snapshot["registered_tools"] = [
                t.name for t in agent.tool_registry.list_tools()
            ]

        return snapshot
