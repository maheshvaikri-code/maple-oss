"""
MAPLE Autonomous Agent - Hello World Example

Demonstrates:
1. Creating an AutonomousAgent with an LLM provider
2. Registering custom tools
3. Pursuing a goal using the ReAct loop
4. Inspecting reasoning traces and memory

Usage:
    # With OpenAI
    export OPENAI_API_KEY="sk-..."
    python examples/hello_autonomous_agent.py

    # With Anthropic
    export ANTHROPIC_API_KEY="sk-ant-..."
    python examples/hello_autonomous_agent.py --provider anthropic --model claude-3-sonnet-20240229

    # With a local model (vLLM, Ollama, etc.)
    python examples/hello_autonomous_agent.py --provider openai --model local-model --api-base http://localhost:8000/v1
"""

import argparse
import json
import os

from maple import (
    Config,
    AutonomousAgent,
    AutonomousConfig,
    LLMConfig,
    Tool,
    Result,
)


def create_calculator_tool():
    """A simple calculator tool the agent can use."""
    def calculator(expression: str = "") -> Result:
        try:
            # Safe eval for simple math
            allowed = set("0123456789+-*/.() ")
            if not all(c in allowed for c in expression):
                return Result.err({"error": "Only basic math operations allowed"})
            result = eval(expression)  # noqa: S307
            return Result.ok({"expression": expression, "result": result})
        except Exception as e:
            return Result.err({"error": str(e)})

    return Tool(
        name="calculator",
        description="Evaluate a mathematical expression. Input: a math expression like '2 + 3 * 4'",
        parameters={
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Mathematical expression to evaluate",
                },
            },
            "required": ["expression"],
        },
        handler=calculator,
        tags=["math"],
    )


def create_knowledge_tool():
    """A simple knowledge lookup tool."""
    knowledge_base = {
        "maple": "MAPLE is a Multi Agent Protocol Language Engine for autonomous agentic AI.",
        "react": "ReAct is a reasoning pattern: Think -> Act -> Reflect, used by autonomous agents.",
        "python": "Python is a high-level programming language known for its simplicity.",
    }

    def lookup(topic: str = "") -> Result:
        topic_lower = topic.lower()
        for key, value in knowledge_base.items():
            if key in topic_lower:
                return Result.ok({"topic": topic, "answer": value})
        return Result.ok({"topic": topic, "answer": f"No information found about '{topic}'"})

    return Tool(
        name="knowledge_lookup",
        description="Look up information about a topic from the knowledge base",
        parameters={
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Topic to look up"},
            },
            "required": ["topic"],
        },
        handler=lookup,
        tags=["knowledge"],
    )


def main():
    parser = argparse.ArgumentParser(description="MAPLE Autonomous Agent Example")
    parser.add_argument("--provider", default="openai", help="LLM provider (openai, anthropic)")
    parser.add_argument("--model", default="gpt-4", help="Model name")
    parser.add_argument("--api-base", default=None, help="Custom API base URL (for local models)")
    parser.add_argument("--goal", default="What is 15 * 37 + 42? Also, what is MAPLE?",
                        help="Goal for the agent to pursue")
    args = parser.parse_args()

    # Resolve API key
    api_key = os.environ.get(
        "ANTHROPIC_API_KEY" if args.provider == "anthropic" else "OPENAI_API_KEY"
    )
    if not api_key:
        print(f"Warning: No API key found. Set {'ANTHROPIC_API_KEY' if args.provider == 'anthropic' else 'OPENAI_API_KEY'} environment variable.")
        print("Running with a placeholder key (will fail on actual LLM calls).")
        api_key = "sk-placeholder"

    # 1. Create agent config
    agent_config = Config(agent_id="hello-agent", broker_url="memory://local")

    # 2. Create autonomy config with LLM
    llm_config = LLMConfig(
        provider=args.provider,
        model=args.model,
        api_key=api_key,
        api_base=args.api_base,
        temperature=0.3,
        max_tokens=1024,
    )

    autonomy_config = AutonomousConfig(
        llm=llm_config,
        max_reasoning_steps=10,
        reflection_frequency=5,
    )

    # 3. Create the autonomous agent
    agent = AutonomousAgent(agent_config, autonomy_config)

    # 4. Register custom tools
    agent.register_tool(create_calculator_tool())
    agent.register_tool(create_knowledge_tool())

    print(f"Agent '{agent.agent_id}' created with {len(agent.tool_registry.list_tools())} tools:")
    for tool in agent.tool_registry.list_tools():
        print(f"  - {tool.name}: {tool.description[:60]}")
    print()

    # 5. Pursue the goal
    print(f"Goal: {args.goal}")
    print("=" * 60)

    result = agent.pursue_goal(args.goal)

    if result.is_ok():
        goal = result.unwrap()
        print(f"\nStatus: {goal.status}")
        print(f"Result: {goal.result}")
        print(f"\nReasoning trace ({len(goal.reasoning_trace)} steps):")
        for step in goal.reasoning_trace:
            print(f"  Step {step.step_number}: {step.content[:100]}...")
            if step.tool_calls:
                for tc in step.tool_calls:
                    print(f"    -> Tool: {tc.name}({tc.arguments})")
            if step.tool_results:
                for tr in step.tool_results:
                    print(f"    <- Result: {tr.content[:80]}...")
    else:
        print(f"Error: {result.unwrap_err()}")

    # 6. Show memory state
    print(f"\nWorking memory: {agent.memory.working.size} entries, {agent.memory.working.token_usage} tokens")

    # 7. Show LLM usage
    print(f"LLM usage: {agent.llm.get_usage_stats()}")


if __name__ == "__main__":
    main()
