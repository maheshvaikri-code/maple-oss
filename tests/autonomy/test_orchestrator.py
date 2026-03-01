"""Tests for the multi-agent orchestrator."""

import pytest
from unittest.mock import MagicMock
from maple.autonomy.orchestrator import AgentOrchestrator, TeamMember
from maple.autonomy.agent import Goal
from maple.core.result import Result


class FakeAgent:
    """Minimal fake agent for orchestrator tests."""

    def __init__(self, agent_id="agent-1", capabilities=None):
        self.agent_id = agent_id
        self.capabilities = capabilities or []
        self._pursue_result = "completed"

    def pursue_goal(self, description):
        goal = Goal(
            goal_id=f"g-{self.agent_id}",
            description=description,
            status=self._pursue_result,
            result=f"Result from {self.agent_id}: {description[:50]}",
        )
        return Result.ok(goal)

    def decompose_goal(self, goal):
        sub1 = Goal(goal_id="sub-1", description=f"Sub-task 1 of: {goal.description}")
        sub2 = Goal(goal_id="sub-2", description=f"Sub-task 2 of: {goal.description}")
        return Result.ok([sub1, sub2])


class FakeAgentWithMemory(FakeAgent):
    """Fake agent with a memory system."""

    def __init__(self, agent_id="agent-1", capabilities=None):
        super().__init__(agent_id, capabilities)
        from maple.autonomy.memory import MemoryManager
        self.memory = MemoryManager()


class TestTeamFormation:
    def test_form_team(self):
        orch = AgentOrchestrator()
        members = [
            TeamMember(agent=FakeAgent("supervisor"), role="supervisor"),
            TeamMember(agent=FakeAgent("worker-1"), role="worker"),
            TeamMember(agent=FakeAgent("worker-2"), role="worker"),
        ]
        result = orch.form_team("test-team", members)
        assert result.is_ok()
        team_id = result.unwrap()
        assert isinstance(team_id, str)

    def test_form_team_empty(self):
        orch = AgentOrchestrator()
        result = orch.form_team("empty", [])
        assert result.is_err()
        assert result.unwrap_err()["errorType"] == "INVALID_TEAM"

    def test_form_team_multiple_supervisors(self):
        orch = AgentOrchestrator()
        members = [
            TeamMember(agent=FakeAgent("s1"), role="supervisor"),
            TeamMember(agent=FakeAgent("s2"), role="supervisor"),
        ]
        result = orch.form_team("bad-team", members)
        assert result.is_err()

    def test_form_team_by_capability(self):
        orch = AgentOrchestrator()
        agents = [
            FakeAgent("a1", capabilities=["search", "analysis"]),
            FakeAgent("a2", capabilities=["coding"]),
            FakeAgent("a3", capabilities=["search"]),
        ]
        supervisor = FakeAgent("sup")

        result = orch.form_team_by_capability(
            "search-team",
            required_capabilities=["search"],
            available_agents=agents,
            supervisor=supervisor,
        )
        assert result.is_ok()

    def test_form_team_no_matching_agents(self):
        orch = AgentOrchestrator()
        agents = [FakeAgent("a1", capabilities=["coding"])]
        result = orch.form_team_by_capability(
            "impossible",
            required_capabilities=["quantum_computing"],
            available_agents=agents,
        )
        assert result.is_err()
        assert result.unwrap_err()["errorType"] == "NO_MATCHING_AGENTS"


class TestSupervisedExecution:
    def test_execute_supervised(self):
        orch = AgentOrchestrator()
        members = [
            TeamMember(agent=FakeAgent("supervisor"), role="supervisor"),
            TeamMember(agent=FakeAgent("worker-1"), role="worker"),
        ]
        team_result = orch.form_team("team", members)
        team_id = team_result.unwrap()

        result = orch.execute_supervised(team_id, "Build a feature")
        assert result.is_ok()
        data = result.unwrap()
        assert data["strategy"] == "supervised"
        assert data["total"] == 2  # 2 sub-goals from decompose_goal

    def test_execute_supervised_no_supervisor(self):
        orch = AgentOrchestrator()
        members = [TeamMember(agent=FakeAgent("w1"), role="worker")]
        team_id = orch.form_team("no-sup", members).unwrap()
        result = orch.execute_supervised(team_id, "Do something")
        assert result.is_err()
        assert result.unwrap_err()["errorType"] == "NO_SUPERVISOR"

    def test_execute_supervised_no_workers(self):
        orch = AgentOrchestrator()
        members = [TeamMember(agent=FakeAgent("s1"), role="supervisor")]
        team_id = orch.form_team("sup-only", members).unwrap()
        result = orch.execute_supervised(team_id, "Do something")
        assert result.is_err()
        assert result.unwrap_err()["errorType"] == "NO_WORKERS"

    def test_execute_supervised_team_not_found(self):
        orch = AgentOrchestrator()
        result = orch.execute_supervised("nonexistent", "Goal")
        assert result.is_err()


class TestConsensusExecution:
    def test_execute_consensus(self):
        orch = AgentOrchestrator()
        members = [
            TeamMember(agent=FakeAgent("a1"), role="supervisor"),
            TeamMember(agent=FakeAgent("a2"), role="worker"),
            TeamMember(agent=FakeAgent("a3"), role="worker"),
        ]
        team_id = orch.form_team("consensus-team", members).unwrap()

        result = orch.execute_consensus(team_id, "What is the best approach?")
        assert result.is_ok()
        data = result.unwrap()
        assert data["strategy"] == "consensus"
        assert data["responding_agents"] == 3

    def test_consensus_insufficient_members(self):
        orch = AgentOrchestrator()
        members = [TeamMember(agent=FakeAgent("a1"), role="worker")]
        team_id = orch.form_team("small", members).unwrap()
        result = orch.execute_consensus(team_id, "Question?")
        assert result.is_err()
        assert result.unwrap_err()["errorType"] == "INSUFFICIENT_MEMBERS"


class TestSharedMemory:
    def test_share_memory(self):
        orch = AgentOrchestrator()
        members = [
            TeamMember(agent=FakeAgentWithMemory("a1")),
            TeamMember(agent=FakeAgentWithMemory("a2")),
        ]
        team_id = orch.form_team("mem-team", members).unwrap()

        result = orch.share_memory(team_id, "project_goal", "Build the best framework")
        assert result.is_ok()
        assert result.unwrap() == 2  # Shared with 2 agents

    def test_share_memory_team_not_found(self):
        orch = AgentOrchestrator()
        result = orch.share_memory("nonexistent", "key", "value")
        assert result.is_err()


class TestTeamManagement:
    def test_get_team(self):
        orch = AgentOrchestrator()
        members = [
            TeamMember(agent=FakeAgent("s1"), role="supervisor"),
            TeamMember(agent=FakeAgent("w1"), role="worker"),
        ]
        team_id = orch.form_team("info-team", members).unwrap()

        result = orch.get_team(team_id)
        assert result.is_ok()
        info = result.unwrap()
        assert info["name"] == "info-team"
        assert info["member_count"] == 2
        assert info["has_supervisor"] is True

    def test_disband_team(self):
        orch = AgentOrchestrator()
        members = [TeamMember(agent=FakeAgent("w1"), role="worker")]
        team_id = orch.form_team("temp", members).unwrap()

        result = orch.disband_team(team_id)
        assert result.is_ok()

        # Team should be gone now
        assert orch.get_team(team_id).is_err()

    def test_disband_nonexistent(self):
        orch = AgentOrchestrator()
        result = orch.disband_team("nonexistent")
        assert result.is_err()
