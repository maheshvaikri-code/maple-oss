"""
MAPLE Multi-Agent Team Example

Demonstrates:
1. Creating multiple AutonomousAgents with different capabilities
2. Forming a team with supervisor and workers
3. Executing goals using the Supervisor pattern
4. Shared memory across team members
5. Observability with DecisionLogger and AgentSnapshot

Usage:
    export OPENAI_API_KEY="sk-..."
    python examples/multi_agent_team.py
"""

import os

from maple import (
    Config,
    AutonomousAgent,
    AutonomousConfig,
    LLMConfig,
    Tool,
    Result,
)
from maple.autonomy.orchestrator import AgentOrchestrator, TeamMember
from maple.autonomy.observability import DecisionLogger, AgentSnapshot


def create_agent(agent_id, capabilities, api_key, provider="openai", model="gpt-4"):
    """Helper to create an autonomous agent."""
    config = Config(
        agent_id=agent_id,
        broker_url="memory://local",
        capabilities=capabilities,
    )
    llm_config = LLMConfig(
        provider=provider,
        model=model,
        api_key=api_key,
        temperature=0.3,
        max_tokens=1024,
    )
    autonomy_config = AutonomousConfig(
        llm=llm_config,
        max_reasoning_steps=8,
        reflection_frequency=4,
    )
    return AutonomousAgent(config, autonomy_config)


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-placeholder")

    # 1. Create specialized agents
    print("Creating agents...")
    supervisor = create_agent(
        "supervisor",
        capabilities=["planning", "coordination"],
        api_key=api_key,
    )

    researcher = create_agent(
        "researcher",
        capabilities=["research", "analysis"],
        api_key=api_key,
    )

    coder = create_agent(
        "coder",
        capabilities=["coding", "debugging"],
        api_key=api_key,
    )

    # Add a custom research tool to the researcher
    def web_search(query: str = "") -> Result:
        # Simulated search results
        return Result.ok({
            "query": query,
            "results": [
                {"title": f"Result about {query}", "snippet": f"Key information about {query}..."}
            ]
        })

    researcher.register_tool(Tool(
        name="web_search",
        description="Search the web for information",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
        handler=web_search,
        tags=["research"],
    ))

    print(f"  Supervisor: {supervisor.agent_id} ({len(supervisor.tool_registry.list_tools())} tools)")
    print(f"  Researcher: {researcher.agent_id} ({len(researcher.tool_registry.list_tools())} tools)")
    print(f"  Coder: {coder.agent_id} ({len(coder.tool_registry.list_tools())} tools)")

    # 2. Form a team
    print("\nForming team...")
    orchestrator = AgentOrchestrator()

    team_result = orchestrator.form_team(
        "dev-team",
        members=[
            TeamMember(agent=supervisor, role="supervisor", capabilities=["planning"]),
            TeamMember(agent=researcher, role="worker", capabilities=["research"]),
            TeamMember(agent=coder, role="worker", capabilities=["coding"]),
        ],
    )

    if team_result.is_err():
        print(f"Failed to form team: {team_result.unwrap_err()}")
        return

    team_id = team_result.unwrap()
    team_info = orchestrator.get_team(team_id).unwrap()
    print(f"  Team '{team_info['name']}': {team_info['member_count']} members")
    print(f"  Has supervisor: {team_info['has_supervisor']}")

    # 3. Share context across team
    print("\nSharing context...")
    shared = orchestrator.share_memory(
        team_id,
        "project_context",
        "We are building an autonomous AI system using MAPLE framework."
    )
    print(f"  Shared with {shared.unwrap()} agents")

    # 4. Execute supervised goal
    print("\nExecuting supervised goal...")
    print("=" * 60)

    result = orchestrator.execute_supervised(
        team_id,
        "Research and implement a simple data processing pipeline"
    )

    if result.is_ok():
        outcome = result.unwrap()
        print(f"\nStrategy: {outcome['strategy']}")
        print(f"Sub-tasks completed: {outcome.get('completed', 0)}/{outcome.get('total', 0)}")
        if 'sub_results' in outcome:
            for sg_id, sub_result in outcome['sub_results'].items():
                print(f"  [{sub_result['status']}] {sub_result['description'][:60]}...")
                print(f"    Worker: {sub_result.get('worker', 'N/A')}")
    else:
        print(f"Execution failed: {result.unwrap_err()}")

    # 5. Capture snapshots
    print("\n\nAgent snapshots:")
    print("-" * 40)
    for agent in [supervisor, researcher, coder]:
        snapshot = AgentSnapshot.capture(agent)
        print(f"  {snapshot['agent_id']}:")
        if 'working_memory' in snapshot:
            print(f"    Memory: {snapshot['working_memory']['entries']} entries")
        if 'active_goals' in snapshot:
            print(f"    Goals: {len(snapshot['active_goals'])}")
        if 'llm_usage' in snapshot:
            usage = snapshot['llm_usage']
            print(f"    LLM tokens: {usage.get('total_prompt_tokens', 0)} prompt + {usage.get('total_completion_tokens', 0)} completion")

    # 6. Disband team
    orchestrator.disband_team(team_id)
    print("\nTeam disbanded. Done!")


if __name__ == "__main__":
    main()
