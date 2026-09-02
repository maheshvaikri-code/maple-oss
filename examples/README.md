# MAPLE examples

These examples are small starting points for the supported Python runtime.

- [Hello autonomous agent](hello_autonomous_agent.py): configure an
  autonomous agent and its model provider.
- [Multi-agent team](multi_agent_team.py): form a team with a supervisor and
  workers.
- [Core hello world](helloworld.py): basic MAPLE messaging.

Install from the repository root:

~~~bash
python -m pip install -e ".[dev,llm]"
~~~

Provider-backed examples need the host's configured provider credentials.
Keep credentials in environment variables or a secret manager; never put them
in source or example files. Read the [root README](../README.md) and
[getting started guide](../docs/getting-started.md) before adapting an
example for a real system.
