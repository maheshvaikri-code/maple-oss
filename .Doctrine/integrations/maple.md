---
integration: maple
upstream: https://github.com/maheshvaikri-code/maple-oss
license: AGPL-3.0 (see the license verdict below — opt-in, never linked)
pinned_version: 1.1.1
discipline: multi-agent-runtime
verified: 2026-07-13
---

# MAPLE — Integration (opt-in workforce runtime)

MAPLE (Multi Agent Protocol Language Engine, `pip install maple-oss`) is a
multi-agent runtime and protocol: typed messages with `Result<T,E>` error
handling, a broker (in-memory to NATS), pairwise link-identified secure
channels, resource negotiation, task scheduling, and an autonomy layer
with LLM providers (Anthropic included) — three layers: L1 protocol,
L2 runtime, L3 autonomy SDK. Upstream claims (unverified here): 818
tests, 33K msg/sec. Verified here (2026-07-13, Windows, Python 3.12):
package installed and inspected; smoke test ran an orchestrator→worker
`WORK.PACKAGE` dispatch and a typed `GATE.RESULT` reply over the
in-process broker (`memory://localhost`), no external services.

Doctrine remains runtime-agnostic: this integration is OPT-IN. Without
it, the workforce runs on the host agent's native subagents (or serial
role-switching per `04-agent-adapters.md`). With it, roles become
persistent, addressable agents.

## The fit — Doctrine concept → MAPLE primitive

| Doctrine                                | MAPLE                                    |
|-----------------------------------------|------------------------------------------|
| Role / subagent                         | `Agent` (L2) or `AutonomousAgent` (L3, Anthropic provider) |
| Orchestrator (main session)             | `AgentOrchestrator.execute_supervised`   |
| Verifier panel (G4/G5 fan-out)          | `AgentOrchestrator.execute_consensus`    |
| Work package (declared file scope)      | typed `WORK.PACKAGE` message: `package_id`, `role`, `file_scope`, brief hashedref (`{path, sha256}`) |
| Gate verdict                            | typed `GATE.RESULT` message: gate, verdict, evidence, artifact hashedref |
| Honest reporting ("blocked" is valid)   | `Result<T,E>` — errors are values, never fabricated success |
| Separation of duties                    | link identification (`LinkManager`, `strict_link_policy`): a verifier holds links ONLY to the orchestrator, never to builders |
| Permission matrix (enterprise profile)  | `security/` authentication + authorization + audit |
| Loop caps / budgets                     | `ResourceRequest` + `ResourceNegotiator` (see asks: no token resource type yet) |
| doctrineos MCP server                   | `maple.adapters.mcp_adapter` — MAPLE agents read the law over MCP |

Two hard boundaries, non-negotiable:

1. **MAPLE routes; gates decide.** A message reaching a verifier is not a
   review. Verdicts count only as artifacts under `docs/` (content-pinned,
   per `standards/merge-and-promotion.md`). The runtime is transport.
2. **The state plane stays the durable truth.** MAPLE's state store is
   ephemeral runtime state. Checkpoints, distillates, and decisions live
   in `.doctrine-state/` (hash-chained, git-committed) — never in the
   broker.

## Wiring pattern (verified shape)

```python
from maple import Agent, Config, Message, Priority

worker = Agent(Config(agent_id="backend-engineer",
                      broker_url="memory://localhost",
                      capabilities=["build"]))
worker.register_handler("WORK.PACKAGE", on_work_package)  # UPPERCASE key
```

Payload discipline: work packages and verdicts carry **artifact
hashedrefs** (`{path, sha256}`), not prose. A builder's reasoning must
never travel to a verifier — the verifier reads the artifact fresh.
Message types are Doctrine's protocol vocabulary: `WORK.PACKAGE`,
`GATE.RESULT`, plus §5 escalations, which always terminate at the human,
never at another agent.

## Sharp edges found at 1.1.1 (real, reproduced here)

- **Handler-key case trap:** `Message.__init__` uppercases every
  `message_type`, but `register_handler` stores keys verbatim — a
  handler registered as `"work.package"` silently never fires ("No
  handler found for WORK.PACKAGE"). Register handler keys UPPERCASE.
- **`send()` Ok is enqueue, not delivery:** sending to a nonexistent
  agent returned `Ok`. Treat every dispatch as reply-or-timeout at the
  protocol level; never report a work package "dispatched" as evidence
  it was received.

## Enhancement asks for MAPLE (Doctrine's wishlist, upstream work)

1. Normalize `register_handler` keys the same way `Message` normalizes
   `message_type` (kills the case trap).
2. Surface routability in `send()`'s `Result` (or a delivery-receipt
   option) so Ok can mean more than "enqueued".
3. A **fresh-context role preset**: broker-enforced per-agent sender
   allowlist + artifact-ref-only payload policy — separation of duties
   as a runtime guarantee instead of a convention.
4. First-class `WORK.PACKAGE` / `GATE.RESULT` schemas (a "doctrine
   profile" or `maple/adapters/doctrine_adapter.py`) beside A2A/MCP.
5. `tokens` as a resource type in `ResourceRequest` (today: compute,
   memory) so LLM budget negotiation maps to loop-engineering caps.

These change MAPLE, not this repo — they are a work order for the
`maple-oss` repository, executed under its own doctrine when taken up.

## License verdict (dependency-policy §4: AGPL = explicit human decision)

MAPLE is AGPL-3.0 and first-party (same author as this doctrine).
Disposition, recorded 2026-07-13: **never vendored, never imported by
doctrineos** — the wheel, MCP server, and tools stay stdlib-only; this
integration is a document and a protocol contract. Consumer repos that
opt into the MAPLE runtime take the AGPL obligation knowingly (flag it
in their brief: `Workforce runtime: maple`). For the owner's own repos
the copyleft cost is nil.

## Boundaries

The runtime never replaces briefs, gates, artifacts, or the human's §5
authority. If the broker is down, the doctrine still runs — degraded to
native subagents or serial role-switching. Adoption order: prove the
task needs persistent cross-agent messaging first (most Class M work
does not); the runtime earns its keep at fleet scale, not on a bugfix.
