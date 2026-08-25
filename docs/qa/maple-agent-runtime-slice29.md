# QA evidence — MAPLE agent-runtime slice 29

## Focused regressions

All commands used the repository test configuration with `-o addopts=`.

- Core/autonomy tools, memory, and orchestrator: `72 passed`.
- MCP tools and governance: `16 passed`.
- Observability, run server, workflow, and workflow replay: `36 passed`.
- Memory, replay, sessions, and state-backed paths: `35 passed`.
- Audit logger: `30 passed`.
- Authentication and audit: `51 passed`.
- Authorization and security initialization: `78 passed`.
- Core agent and communication: `81 passed`.
- Task management package: `136 passed`.
- Monitoring package: `20 passed`.
- Cross-module regression after the final static fixes: `132 passed` across
  agent, communication, authentication, and audit tests.

## Static evidence

- Explicit Python 3.10-target mypy checks pass for each changed module slice.
  The command emits the known configuration warning because mypy 2.3 rejects
  the configured Python 3.8 target.
- Black and isort checks pass for each changed slice after formatting.
- Ruff and `compileall` pass on each changed slice.
- `git diff --check` passed before each slice commit.
- Aggregate mypy audit: `Found 313 errors in 46 files (checked 93 source
  files)`; this is an open release blocker, not a pass claim.

## Not run / still open

- The full repository pytest run has not completed; the latest bounded attempt
  reached the historical slow Doctrine-gold tail after 86% progress and was
  manually interrupted without a reported assertion failure.
- Bandit is unavailable in the local interpreter, and dependency-audit
  disposition remains open.
- Fresh-context independent G4/G5 review is unavailable in this environment.
