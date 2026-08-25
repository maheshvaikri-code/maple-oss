# ADR-017: Bounded conversation session store

**Date:** 2026-08-24  Â· **Status:** accepted  Â· **Deciders:** Chief Architect

## Context

MAPLE has working/episodic memory and workflow checkpoints, but it does not
yet expose a small persistence contract for conversation turns. Agent
frameworks and the future local run server need a stable session identifier,
bounded message history, and restart-safe reads without forcing a model or
database dependency into the core runtime.

## Decision

We will add a dependency-free `SessionStore` contract with bounded immutable
`SessionSnapshot` and `SessionMessage` values, plus thread-safe in-memory and
atomic JSON-file implementations.

- Session IDs and message roles are validated at the boundary.
- Message content, metadata, message count, and serialized session size are
  bounded before mutation.
- Appends use optimistic version checks; returned snapshots are fresh JSON-safe
  copies, so callers cannot mutate stored state through an alias.
- File persistence is atomic and safe within one process. Cross-process leases,
  encryption, retention policies, model/provider coupling, and automatic
  conversation replay remain separate decisions.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| In-memory and atomic JSON stores (chosen) | Zero new dependency; testable; useful for local hosts and a future server | File store is single-process coordinated; no query index | Fits the current local-first release scope and keeps the contract replaceable |
| Reuse `StateStore` directly | Existing storage abstraction; less code | Untyped values, no message/version/session bounds, weaker public contract | It would move validation into every caller and make session invariants implicit |
| Add a database/vector-store dependency | Durable queries and multi-process coordination | Adds deployment, migration, audit, and dependency scope | Production backend choice is not yet specified and needs a separate ADR/human decision |

## Consequences

- Positive: hosts can persist bounded turn history now and later attach it to
  an agent or local run server without changing the message contract.
- Negative / debt accepted: the slice stores conversation data but does not
  automatically feed it into `AutonomousAgent`, summarize it, encrypt it, or
  replay tool/LLM execution.
- Invalidation triggers: reopen this ADR when cross-process writers,
  multi-tenant authorization, encrypted-at-rest requirements, or replay-safe
  execution semantics become release requirements.
