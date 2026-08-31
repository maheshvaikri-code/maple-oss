"""
Copyright (C) 2025 Mahesh Vaijainthymala Krishnamoorthy
(Mahesh Vaikri)

This file is part of MAPLE - Multi Agent Protocol Language Engine.

MAPLE - Multi Agent Protocol Language Engine is free software: you can
redistribute it and/or modify it under the terms of the GNU Affero General
Public License as published by the Free Software Foundation, either version 3
of the License, or (at your option) any later version.
MAPLE - Multi Agent Protocol Language Engine is distributed in the hope that
it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty
of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero
General Public License for more details. You should have received a copy of
the GNU Affero General Public License along with MAPLE - Multi Agent Protocol
Language Engine. If not, see <https://www.gnu.org/licenses/>.
"""

# Multi-agent orchestration for MAPLE autonomous agents.

import asyncio
import logging
import math
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Awaitable, Dict, List, Optional, Tuple, TypeVar

from ..core.result import Result
from ..discovery.registry import AgentRegistry
from .execution import CancellationToken

logger = logging.getLogger(__name__)
T = TypeVar("T")


@dataclass
class TeamMember:
    """A member of an agent team."""

    agent: Any  # AutonomousAgent
    role: str = "worker"  # "supervisor", "worker", "specialist"
    capabilities: List[str] = field(default_factory=list)


class AgentOrchestrator:
    """
    Orchestrates multiple autonomous agents working together.

    Patterns:
    - Supervisor: One agent decomposes and delegates, workers execute
    - Consensus: All agents independently solve, supervisor synthesizes
    """

    def __init__(
        self,
        registry: Optional[AgentRegistry] = None,
        max_parallel_agents: int = 8,
    ):
        if (
            isinstance(max_parallel_agents, bool)
            or not isinstance(max_parallel_agents, int)
            or not 1 <= max_parallel_agents <= 64
        ):
            raise ValueError("max_parallel_agents must be an integer from 1 to 64")
        self.registry = registry or AgentRegistry()
        self.max_parallel_agents = max_parallel_agents
        self._teams: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def _agent_error(
        agent: TeamMember, error: Exception
    ) -> Result[Any, Dict[str, Any]]:
        """Normalize worker exceptions without aborting sibling agents."""
        return Result.err(
            {
                "errorType": "AGENT_EXECUTION_ERROR",
                "message": "Team member execution failed.",
                "details": {
                    "agent_id": getattr(agent.agent, "agent_id", "unknown"),
                    "exception": type(error).__name__,
                },
            }
        )

    @staticmethod
    def _orchestration_error(error_type: str, message: str) -> Dict[str, Any]:
        """Build a stable public error for orchestration-level interruption."""
        return {"errorType": error_type, "message": message}

    @classmethod
    def _resolve_async_bounds(
        cls,
        cancellation: Optional[CancellationToken],
        timeout_seconds: Optional[float],
    ) -> Result[Tuple[Optional[CancellationToken], Optional[float]], Dict[str, Any]]:
        """Validate caller bounds and convert a relative timeout to a deadline."""
        if timeout_seconds is not None and (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(timeout_seconds)
            or timeout_seconds <= 0
        ):
            return Result.err(
                cls._orchestration_error(
                    "ORCHESTRATION_CONFIG_INVALID",
                    "timeout_seconds must be finite and positive.",
                )
            )
        if cancellation is not None and not isinstance(cancellation, CancellationToken):
            return Result.err(
                cls._orchestration_error(
                    "ORCHESTRATION_CONFIG_INVALID",
                    "cancellation must be a CancellationToken.",
                )
            )
        deadline = (
            None if timeout_seconds is None else time.monotonic() + timeout_seconds
        )
        return Result.ok((cancellation, deadline))

    @staticmethod
    def _bound_error(
        cancellation: Optional[CancellationToken], deadline: Optional[float]
    ) -> Optional[Dict[str, Any]]:
        """Return the first active caller bound, if any."""
        if cancellation is not None and cancellation.is_cancelled():
            return AgentOrchestrator._orchestration_error(
                "ORCHESTRATION_CANCELLED", "Orchestration was cancelled."
            )
        if deadline is not None and time.monotonic() >= deadline:
            return AgentOrchestrator._orchestration_error(
                "ORCHESTRATION_TIMEOUT", "Orchestration exceeded its timeout."
            )
        return None

    @classmethod
    async def _await_with_bounds(
        cls,
        awaitable: Awaitable[T],
        cancellation: Optional[CancellationToken],
        deadline: Optional[float],
    ) -> Result[T, Dict[str, Any]]:
        """Await one operation while observing cancellation and a deadline."""
        task = asyncio.ensure_future(awaitable)
        try:
            while not task.done():
                error = cls._bound_error(cancellation, deadline)
                if error is not None:
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
                    return Result.err(error)
                remaining = (
                    None if deadline is None else max(0.0, deadline - time.monotonic())
                )
                poll_interval = 0.05 if cancellation is not None else remaining
                if poll_interval is not None:
                    poll_interval = min(poll_interval, 0.05)
                await asyncio.wait({task}, timeout=poll_interval)
            return Result.ok(task.result())
        except asyncio.CancelledError:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            raise

    @classmethod
    async def _cancel_pending(
        cls, pending: "set[asyncio.Task[Tuple[str, Result[Any, Dict[str, Any]]]]]"
    ) -> None:
        """Cancel and drain child tasks before returning to the caller."""
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    def _pursue_agents(
        self, assignments: List[Tuple[str, TeamMember, str]]
    ) -> Dict[str, Result[Any, Dict[str, Any]]]:
        """Run independent agent goals with a bounded pool and stable ordering."""
        if not assignments:
            return {}

        results: Dict[str, Result[Any, Dict[str, Any]]] = {}
        with ThreadPoolExecutor(
            max_workers=min(self.max_parallel_agents, len(assignments)),
            thread_name_prefix="maple-agent",
        ) as executor:
            futures = [
                (
                    key,
                    member,
                    executor.submit(member.agent.pursue_goal, description),
                )
                for key, member, description in assignments
            ]
            for key, member, future in futures:
                try:
                    results[key] = future.result()
                except Exception as error:
                    results[key] = self._agent_error(member, error)
        return results

    async def _pursue_agents_async(
        self,
        assignments: List[Tuple[str, TeamMember, str]],
        *,
        cancellation: Optional[CancellationToken] = None,
        deadline: Optional[float] = None,
    ) -> Result[Dict[str, Result[Any, Dict[str, Any]]], Dict[str, Any]]:
        """Run async goals with a cap and scoped cancellation/deadline handling."""
        semaphore = asyncio.Semaphore(self.max_parallel_agents)
        loop = asyncio.get_running_loop()

        async def run_one(
            key: str, member: TeamMember, description: str
        ) -> Tuple[str, Result[Any, Dict[str, Any]]]:
            async with semaphore:
                bound_error = self._bound_error(cancellation, deadline)
                if bound_error is not None:
                    return key, Result.err(bound_error)
                try:
                    pursue_async = getattr(member.agent, "pursue_goal_async", None)
                    if pursue_async is not None:
                        result = await pursue_async(description)
                    else:
                        result = await loop.run_in_executor(
                            None, member.agent.pursue_goal, description
                        )
                    return key, result
                except Exception as error:
                    return key, self._agent_error(member, error)

        tasks = {
            asyncio.create_task(run_one(key, member, description))
            for key, member, description in assignments
        }
        pending = set(tasks)
        results: Dict[str, Result[Any, Dict[str, Any]]] = {}
        try:
            while pending:
                bound_error = self._bound_error(cancellation, deadline)
                if bound_error is not None:
                    await self._cancel_pending(pending)
                    return Result.err(bound_error)
                remaining = (
                    None if deadline is None else max(0.0, deadline - time.monotonic())
                )
                poll_interval = 0.05 if cancellation is not None else remaining
                if poll_interval is not None:
                    poll_interval = min(poll_interval, 0.05)
                done, pending = await asyncio.wait(
                    pending,
                    timeout=poll_interval,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if not done:
                    continue
                for task in done:
                    key, result = task.result()
                    results[key] = result
            return Result.ok(results)
        except asyncio.CancelledError:
            await self._cancel_pending(pending)
            raise

    def form_team(
        self,
        team_name: str,
        members: List[TeamMember],
    ) -> Result[str, Dict[str, Any]]:
        """Form a team from explicitly provided members."""
        if not members:
            return Result.err(
                {
                    "errorType": "INVALID_TEAM",
                    "message": "Team must have at least one member",
                }
            )

        supervisors = [m for m in members if m.role == "supervisor"]
        if len(supervisors) > 1:
            return Result.err(
                {
                    "errorType": "INVALID_TEAM",
                    "message": "Team can have at most one supervisor",
                }
            )

        team_id = str(uuid.uuid4())
        self._teams[team_id] = {
            "name": team_name,
            "members": members,
            "supervisor": supervisors[0] if supervisors else None,
            "workers": [m for m in members if m.role != "supervisor"],
        }
        logger.info(
            f"Formed team '{team_name}' ({team_id}) with {len(members)} members"
        )
        return Result.ok(team_id)

    def form_team_by_capability(
        self,
        team_name: str,
        required_capabilities: List[str],
        available_agents: List[Any],
        supervisor: Optional[Any] = None,
    ) -> Result[str, Dict[str, Any]]:
        """
        Form a team by matching agent capabilities to requirements.
        Uses the registry to find best-fit agents.
        """
        members = []

        if supervisor:
            members.append(
                TeamMember(
                    agent=supervisor,
                    role="supervisor",
                    capabilities=getattr(supervisor, "capabilities", []),
                )
            )

        # Match agents to capabilities
        for agent in available_agents:
            agent_caps = getattr(agent, "capabilities", [])
            matched = [c for c in required_capabilities if c in agent_caps]
            if matched:
                members.append(
                    TeamMember(
                        agent=agent,
                        role="specialist" if len(matched) == 1 else "worker",
                        capabilities=agent_caps,
                    )
                )

        if not members:
            return Result.err(
                {
                    "errorType": "NO_MATCHING_AGENTS",
                    "message": (
                        "No agents match required capabilities: "
                        f"{required_capabilities}"
                    ),
                }
            )

        return self.form_team(team_name, members)

    def execute_supervised(
        self,
        team_id: str,
        goal_description: str,
    ) -> Result[Dict[str, Any], Dict[str, Any]]:
        """
        Execute a goal using the supervisor pattern.

        1. Supervisor decomposes goal into sub-goals
        2. Sub-goals assigned to workers
        3. Workers pursue their sub-goals independently
        4. Results collected and returned
        """
        team = self._teams.get(team_id)
        if not team:
            return Result.err(
                {
                    "errorType": "TEAM_NOT_FOUND",
                    "message": f"Team {team_id} not found",
                }
            )

        supervisor = team["supervisor"]
        workers = team["workers"]

        if not supervisor:
            return Result.err(
                {
                    "errorType": "NO_SUPERVISOR",
                    "message": "Supervised execution requires a supervisor agent",
                }
            )

        if not workers:
            return Result.err(
                {
                    "errorType": "NO_WORKERS",
                    "message": "Supervised execution requires at least one worker",
                }
            )

        # Step 1: Supervisor decomposes the goal
        from .agent import Goal

        goal = Goal(goal_id=str(uuid.uuid4()), description=goal_description)
        decompose_result = supervisor.agent.decompose_goal(goal)

        if decompose_result.is_err():
            # If decomposition fails, supervisor handles the whole goal
            result = supervisor.agent.pursue_goal(goal_description)
            if result.is_ok():
                goal_obj = result.unwrap()
                return Result.ok(
                    {
                        "strategy": "supervisor_solo",
                        "result": goal_obj.result,
                        "status": goal_obj.status,
                    }
                )
            return Result.err(result.unwrap_err())

        sub_goals = decompose_result.unwrap()

        # Step 2: Assign sub-goals to workers (round-robin)
        assignments: Dict[str, Dict] = {}
        for i, sub_goal in enumerate(sub_goals):
            worker = workers[i % len(workers)]
            assignments[sub_goal.goal_id] = {
                "sub_goal": sub_goal,
                "worker": worker,
            }

        # Step 3: Workers pursue sub-goals concurrently, with stable collection order.
        worker_results = self._pursue_agents(
            [
                (sg_id, assignment["worker"], assignment["sub_goal"].description)
                for sg_id, assignment in assignments.items()
            ]
        )
        results = {}
        for sg_id, assignment in assignments.items():
            worker_agent = assignment["worker"].agent
            sub_goal = assignment["sub_goal"]
            worker_result = worker_results[sg_id]
            if worker_result.is_ok():
                goal_obj = worker_result.unwrap()
                results[sg_id] = {
                    "description": sub_goal.description,
                    "status": goal_obj.status,
                    "result": goal_obj.result,
                    "worker": worker_agent.agent_id,
                }
            else:
                results[sg_id] = {
                    "description": sub_goal.description,
                    "status": "failed",
                    "error": worker_result.unwrap_err(),
                    "worker": worker_agent.agent_id,
                }

        return Result.ok(
            {
                "strategy": "supervised",
                "goal": goal_description,
                "sub_results": results,
                "completed": sum(
                    1 for r in results.values() if r["status"] == "completed"
                ),
                "failed": sum(1 for r in results.values() if r["status"] == "failed"),
                "total": len(results),
            }
        )

    def execute_consensus(
        self,
        team_id: str,
        question: str,
    ) -> Result[Dict[str, Any], Dict[str, Any]]:
        """
        Execute using the consensus pattern.

        1. All agents independently answer the question
        2. Supervisor (or first agent) synthesizes responses
        """
        team = self._teams.get(team_id)
        if not team:
            return Result.err(
                {
                    "errorType": "TEAM_NOT_FOUND",
                    "message": f"Team {team_id} not found",
                }
            )

        all_members = team["members"]
        if len(all_members) < 2:
            return Result.err(
                {
                    "errorType": "INSUFFICIENT_MEMBERS",
                    "message": "Consensus requires at least 2 members",
                }
            )

        # Step 1: All agents independently pursue the question concurrently.
        member_assignments = [
            (f"member-{index}", member, question)
            for index, member in enumerate(all_members)
        ]
        member_results = self._pursue_agents(member_assignments)
        responses = {}
        for index, member in enumerate(all_members):
            result = member_results[f"member-{index}"]
            if result.is_ok():
                goal_obj = result.unwrap()
                responses[member.agent.agent_id] = {
                    "role": member.role,
                    "result": goal_obj.result,
                    "status": goal_obj.status,
                }
            else:
                responses[member.agent.agent_id] = {
                    "role": member.role,
                    "error": result.unwrap_err(),
                    "status": "failed",
                }

        # Step 2: Synthesize (use supervisor if available, else first agent)
        synthesizer = team["supervisor"] or all_members[0]
        response_summary = "\n".join(
            f"Agent {aid} ({r['role']}): "
            f"{r.get('result', r.get('error', 'no response'))}"
            for aid, r in responses.items()
        )

        synthesis_goal = (
            f'Multiple agents were asked: "{question}"\n'
            f"Their responses:\n{response_summary}\n\n"
            f"Synthesize these into a single best answer."
        )
        synthesis_result = synthesizer.agent.pursue_goal(synthesis_goal)

        synthesis = None
        if synthesis_result.is_ok():
            synthesis = synthesis_result.unwrap().result

        return Result.ok(
            {
                "strategy": "consensus",
                "question": question,
                "individual_responses": responses,
                "synthesis": synthesis,
                "responding_agents": len(responses),
            }
        )

    async def execute_supervised_async(
        self,
        team_id: str,
        goal_description: str,
        *,
        cancellation: Optional[CancellationToken] = None,
        timeout_seconds: Optional[float] = None,
    ) -> Result[Dict[str, Any], Dict[str, Any]]:
        """Async supervised execution with bounded, cancellable worker goals.

        ``timeout_seconds`` is a total request budget covering decomposition,
        worker fan-out, and result collection. Cancellation is cooperative:
        native async agents are canceled as tasks, while sync-only agents
        running in an executor may continue until their own call returns.
        """
        bounds = self._resolve_async_bounds(cancellation, timeout_seconds)
        if bounds.is_err():
            return Result.err(bounds.unwrap_err())
        cancellation, deadline = bounds.unwrap()
        bound_error = self._bound_error(cancellation, deadline)
        if bound_error is not None:
            return Result.err(bound_error)
        team = self._teams.get(team_id)
        if not team:
            return Result.err(
                {
                    "errorType": "TEAM_NOT_FOUND",
                    "message": f"Team {team_id} not found",
                }
            )

        supervisor = team["supervisor"]
        workers = team["workers"]
        if not supervisor:
            return Result.err(
                {
                    "errorType": "NO_SUPERVISOR",
                    "message": "Supervised execution requires a supervisor agent",
                }
            )
        if not workers:
            return Result.err(
                {
                    "errorType": "NO_WORKERS",
                    "message": "Supervised execution requires at least one worker",
                }
            )

        from .agent import Goal

        goal = Goal(goal_id=str(uuid.uuid4()), description=goal_description)
        loop = asyncio.get_running_loop()
        decompose_call = await self._await_with_bounds(
            loop.run_in_executor(None, supervisor.agent.decompose_goal, goal),
            cancellation,
            deadline,
        )
        if decompose_call.is_err():
            return Result.err(decompose_call.unwrap_err())
        decompose_result = decompose_call.unwrap()
        if decompose_result.is_err():
            fallback = await self._pursue_agents_async(
                [("fallback", supervisor, goal_description)],
                cancellation=cancellation,
                deadline=deadline,
            )
            if fallback.is_err():
                return Result.err(fallback.unwrap_err())
            result = fallback.unwrap()["fallback"]
            if result.is_ok():
                goal_obj = result.unwrap()
                return Result.ok(
                    {
                        "strategy": "supervisor_solo",
                        "result": goal_obj.result,
                        "status": goal_obj.status,
                    }
                )
            return Result.err(result.unwrap_err())

        sub_goals = decompose_result.unwrap()
        assignments = {
            sub_goal.goal_id: {
                "sub_goal": sub_goal,
                "worker": workers[index % len(workers)],
            }
            for index, sub_goal in enumerate(sub_goals)
        }
        worker_results = await self._pursue_agents_async(
            [
                (sg_id, assignment["worker"], assignment["sub_goal"].description)
                for sg_id, assignment in assignments.items()
            ],
            cancellation=cancellation,
            deadline=deadline,
        )
        if worker_results.is_err():
            return Result.err(worker_results.unwrap_err())
        worker_result_map = worker_results.unwrap()
        results = {}
        for sg_id, assignment in assignments.items():
            worker_agent = assignment["worker"].agent
            sub_goal = assignment["sub_goal"]
            worker_result = worker_result_map[sg_id]
            if worker_result.is_ok():
                goal_obj = worker_result.unwrap()
                results[sg_id] = {
                    "description": sub_goal.description,
                    "status": goal_obj.status,
                    "result": goal_obj.result,
                    "worker": worker_agent.agent_id,
                }
            else:
                results[sg_id] = {
                    "description": sub_goal.description,
                    "status": "failed",
                    "error": worker_result.unwrap_err(),
                    "worker": worker_agent.agent_id,
                }

        return Result.ok(
            {
                "strategy": "supervised",
                "goal": goal_description,
                "sub_results": results,
                "completed": sum(
                    1 for result in results.values() if result["status"] == "completed"
                ),
                "failed": sum(
                    1 for result in results.values() if result["status"] == "failed"
                ),
                "total": len(results),
            }
        )

    async def execute_consensus_async(
        self,
        team_id: str,
        question: str,
        *,
        cancellation: Optional[CancellationToken] = None,
        timeout_seconds: Optional[float] = None,
    ) -> Result[Dict[str, Any], Dict[str, Any]]:
        """Async consensus execution with bounded, cancellable member goals."""
        bounds = self._resolve_async_bounds(cancellation, timeout_seconds)
        if bounds.is_err():
            return Result.err(bounds.unwrap_err())
        cancellation, deadline = bounds.unwrap()
        bound_error = self._bound_error(cancellation, deadline)
        if bound_error is not None:
            return Result.err(bound_error)
        team = self._teams.get(team_id)
        if not team:
            return Result.err(
                {
                    "errorType": "TEAM_NOT_FOUND",
                    "message": f"Team {team_id} not found",
                }
            )

        all_members = team["members"]
        if len(all_members) < 2:
            return Result.err(
                {
                    "errorType": "INSUFFICIENT_MEMBERS",
                    "message": "Consensus requires at least 2 members",
                }
            )

        member_assignments = [
            (f"member-{index}", member, question)
            for index, member in enumerate(all_members)
        ]
        member_results = await self._pursue_agents_async(
            member_assignments,
            cancellation=cancellation,
            deadline=deadline,
        )
        if member_results.is_err():
            return Result.err(member_results.unwrap_err())
        member_result_map = member_results.unwrap()
        responses = {}
        for index, member in enumerate(all_members):
            result = member_result_map[f"member-{index}"]
            if result.is_ok():
                goal_obj = result.unwrap()
                responses[member.agent.agent_id] = {
                    "role": member.role,
                    "result": goal_obj.result,
                    "status": goal_obj.status,
                }
            else:
                responses[member.agent.agent_id] = {
                    "role": member.role,
                    "error": result.unwrap_err(),
                    "status": "failed",
                }

        synthesizer = team["supervisor"] or all_members[0]
        response_summary = "\n".join(
            f"Agent {agent_id} ({response['role']}): "
            f"{response.get('result', response.get('error', 'no response'))}"
            for agent_id, response in responses.items()
        )
        synthesis_goal = (
            f'Multiple agents were asked: "{question}"\n'
            f"Their responses:\n{response_summary}\n\n"
            "Synthesize these into a single best answer."
        )
        synthesis_result = await self._pursue_agents_async(
            [("synthesis", synthesizer, synthesis_goal)],
            cancellation=cancellation,
            deadline=deadline,
        )
        if synthesis_result.is_err():
            return Result.err(synthesis_result.unwrap_err())
        synthesis_result_map = synthesis_result.unwrap()
        synthesis = None
        if synthesis_result_map["synthesis"].is_ok():
            synthesis = synthesis_result_map["synthesis"].unwrap().result

        return Result.ok(
            {
                "strategy": "consensus",
                "question": question,
                "individual_responses": responses,
                "synthesis": synthesis,
                "responding_agents": len(responses),
            }
        )

    def share_memory(
        self, team_id: str, key: str, value: Any
    ) -> Result[int, Dict[str, Any]]:
        """Share a fact across all team members' semantic memory."""
        team = self._teams.get(team_id)
        if not team:
            return Result.err(
                {
                    "errorType": "TEAM_NOT_FOUND",
                    "message": f"Team {team_id} not found",
                }
            )

        shared_count = 0
        for member in team["members"]:
            if hasattr(member.agent, "memory"):
                result = member.agent.memory.semantic.store_fact(
                    f"shared:{key}", value, metadata={"team_id": team_id}
                )
                if result.is_ok():
                    shared_count += 1

        return Result.ok(shared_count)

    def get_team(self, team_id: str) -> Result[Dict[str, Any], Dict[str, Any]]:
        """Get team information."""
        team = self._teams.get(team_id)
        if not team:
            return Result.err(
                {
                    "errorType": "TEAM_NOT_FOUND",
                    "message": f"Team {team_id} not found",
                }
            )
        return Result.ok(
            {
                "name": team["name"],
                "member_count": len(team["members"]),
                "has_supervisor": team["supervisor"] is not None,
                "members": [
                    {
                        "agent_id": m.agent.agent_id,
                        "role": m.role,
                        "capabilities": m.capabilities,
                    }
                    for m in team["members"]
                ],
            }
        )

    def disband_team(self, team_id: str) -> Result[None, Dict[str, Any]]:
        """Disband a team."""
        if team_id not in self._teams:
            return Result.err(
                {
                    "errorType": "TEAM_NOT_FOUND",
                    "message": f"Team {team_id} not found",
                }
            )
        del self._teams[team_id]
        return Result.ok(None)
