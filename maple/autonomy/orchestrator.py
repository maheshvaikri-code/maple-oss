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

"""Multi-agent orchestration for MAPLE autonomous agents."""

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..core.result import Result
from ..discovery.registry import AgentRegistry

logger = logging.getLogger(__name__)


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

    def __init__(self, registry: Optional[AgentRegistry] = None):
        self.registry = registry or AgentRegistry()
        self._teams: Dict[str, Dict[str, Any]] = {}

    def form_team(
        self,
        team_name: str,
        members: List[TeamMember],
    ) -> Result[str, Dict[str, Any]]:
        """Form a team from explicitly provided members."""
        if not members:
            return Result.err({
                'errorType': 'INVALID_TEAM',
                'message': 'Team must have at least one member',
            })

        supervisors = [m for m in members if m.role == "supervisor"]
        if len(supervisors) > 1:
            return Result.err({
                'errorType': 'INVALID_TEAM',
                'message': 'Team can have at most one supervisor',
            })

        team_id = str(uuid.uuid4())
        self._teams[team_id] = {
            "name": team_name,
            "members": members,
            "supervisor": supervisors[0] if supervisors else None,
            "workers": [m for m in members if m.role != "supervisor"],
        }
        logger.info(f"Formed team '{team_name}' ({team_id}) with {len(members)} members")
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
            members.append(TeamMember(
                agent=supervisor,
                role="supervisor",
                capabilities=getattr(supervisor, "capabilities", []),
            ))

        # Match agents to capabilities
        for agent in available_agents:
            agent_caps = getattr(agent, "capabilities", [])
            matched = [c for c in required_capabilities if c in agent_caps]
            if matched:
                members.append(TeamMember(
                    agent=agent,
                    role="specialist" if len(matched) == 1 else "worker",
                    capabilities=agent_caps,
                ))

        if not members:
            return Result.err({
                'errorType': 'NO_MATCHING_AGENTS',
                'message': f'No agents match required capabilities: {required_capabilities}',
            })

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
            return Result.err({
                'errorType': 'TEAM_NOT_FOUND',
                'message': f'Team {team_id} not found',
            })

        supervisor = team["supervisor"]
        workers = team["workers"]

        if not supervisor:
            return Result.err({
                'errorType': 'NO_SUPERVISOR',
                'message': 'Supervised execution requires a supervisor agent',
            })

        if not workers:
            return Result.err({
                'errorType': 'NO_WORKERS',
                'message': 'Supervised execution requires at least one worker',
            })

        # Step 1: Supervisor decomposes the goal
        from .agent import Goal
        goal = Goal(goal_id=str(uuid.uuid4()), description=goal_description)
        decompose_result = supervisor.agent.decompose_goal(goal)

        if decompose_result.is_err():
            # If decomposition fails, supervisor handles the whole goal
            result = supervisor.agent.pursue_goal(goal_description)
            if result.is_ok():
                goal_obj = result.unwrap()
                return Result.ok({
                    "strategy": "supervisor_solo",
                    "result": goal_obj.result,
                    "status": goal_obj.status,
                })
            return result

        sub_goals = decompose_result.unwrap()

        # Step 2: Assign sub-goals to workers (round-robin)
        assignments: Dict[str, Dict] = {}
        for i, sub_goal in enumerate(sub_goals):
            worker = workers[i % len(workers)]
            assignments[sub_goal.goal_id] = {
                "sub_goal": sub_goal,
                "worker": worker,
            }

        # Step 3: Workers pursue sub-goals
        results = {}
        for sg_id, assignment in assignments.items():
            worker_agent = assignment["worker"].agent
            sub_goal = assignment["sub_goal"]
            worker_result = worker_agent.pursue_goal(sub_goal.description)
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

        return Result.ok({
            "strategy": "supervised",
            "goal": goal_description,
            "sub_results": results,
            "completed": sum(1 for r in results.values() if r["status"] == "completed"),
            "failed": sum(1 for r in results.values() if r["status"] == "failed"),
            "total": len(results),
        })

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
            return Result.err({
                'errorType': 'TEAM_NOT_FOUND',
                'message': f'Team {team_id} not found',
            })

        all_members = team["members"]
        if len(all_members) < 2:
            return Result.err({
                'errorType': 'INSUFFICIENT_MEMBERS',
                'message': 'Consensus requires at least 2 members',
            })

        # Step 1: All agents independently pursue the question
        responses = {}
        for member in all_members:
            result = member.agent.pursue_goal(question)
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
            f"Agent {aid} ({r['role']}): {r.get('result', r.get('error', 'no response'))}"
            for aid, r in responses.items()
        )

        synthesis_goal = (
            f"Multiple agents were asked: \"{question}\"\n"
            f"Their responses:\n{response_summary}\n\n"
            f"Synthesize these into a single best answer."
        )
        synthesis_result = synthesizer.agent.pursue_goal(synthesis_goal)

        synthesis = None
        if synthesis_result.is_ok():
            synthesis = synthesis_result.unwrap().result

        return Result.ok({
            "strategy": "consensus",
            "question": question,
            "individual_responses": responses,
            "synthesis": synthesis,
            "responding_agents": len(responses),
        })

    def share_memory(self, team_id: str, key: str, value: Any) -> Result[int, Dict[str, Any]]:
        """Share a fact across all team members' semantic memory."""
        team = self._teams.get(team_id)
        if not team:
            return Result.err({
                'errorType': 'TEAM_NOT_FOUND',
                'message': f'Team {team_id} not found',
            })

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
            return Result.err({
                'errorType': 'TEAM_NOT_FOUND',
                'message': f'Team {team_id} not found',
            })
        return Result.ok({
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
        })

    def disband_team(self, team_id: str) -> Result[None, Dict[str, Any]]:
        """Disband a team."""
        if team_id not in self._teams:
            return Result.err({
                'errorType': 'TEAM_NOT_FOUND',
                'message': f'Team {team_id} not found',
            })
        del self._teams[team_id]
        return Result.ok(None)
