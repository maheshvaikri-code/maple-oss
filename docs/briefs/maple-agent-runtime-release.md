# Project Brief - MAPLE Agent Runtime and Release Readiness

**Date:** 2026-08-24  · **Class:** L  · **Requested by:** human

## Problem

MAPLE has a strong multi-agent protocol and infrastructure layer, but its
native agent runtime does not yet provide the durable workflows, typed agent
contracts, safe execution, retrieval, streaming, evaluation, and release
automation expected from current agent frameworks. The goal is to close the
highest-value gaps through small, independently tested slices and leave the
repository in a verifiable release-ready state before any website update or
external publication.

## Scope

- **In:** Native workflow execution with checkpoint/resume; typed tool and
  agent I/O; guarded tool execution; retrieval/data primitives; token and
  workflow event streaming; agent observability and evaluation foundations;
  provider/interop improvements; documentation, CI, packaging, changelog,
  security, and release artifacts.
- **Non-goals:** Website changes; external publishing or deployment; paid
  cloud services; replacing MAPLE's broker, security, resource, or protocol
  layers; claiming parity through adapters alone; silently changing the
  license or breaking existing public APIs.
- **Deferred:** Browser/computer-use integrations, hosted sandbox providers,
  managed vector databases, hosted dashboards, and multi-language SDKs until
  the local runtime contracts are stable.

## Explicit unsupported capability boundaries

The following public compatibility surfaces are intentionally fail-closed and
must not be read as completed feature claims:

- **Redis state backend:** `StorageBackend.REDIS` is retained for compatibility,
  but `get`, `set`, `delete`, and `list_keys` return `NOT_IMPLEMENTED` until a
  real Redis dependency, connection/configuration contract, optimistic-version
  semantics, and offline integration test matrix are separately approved.
  Memory, atomic file, and SQLite state backends are the supported local
  implementations.
- **Mutual TLS authentication:** `AuthMethod.MUTUAL_TLS` returns
  `NOT_IMPLEMENTED`. MAPLE does not inspect sockets or certificate chains in
  the in-process authentication manager; transport TLS and peer verification
  require a separately reviewed integration boundary.
- **OAuth2 authentication:** `AuthMethod.OAUTH2` returns `NOT_IMPLEMENTED`.
  Token acquisition, issuer/JWKS validation, audience checks, refresh, and
  revocation semantics require an explicit provider-neutral contract and are
  not represented by a placeholder implementation.
- **Untrusted code execution:** Markdown code blocks are extractable as data,
  while `TrustedLocalExecutor` is only for explicitly trusted local Python
  handlers. MAPLE does not claim an in-process sandbox, subprocess isolation,
  browser/computer-use runtime, or hosted code interpreter.

These boundaries are release documentation, not roadmap promises. A future
implementation requires a new scoped brief, dependency/security review, and
failure-path tests before the corresponding claim can move into the supported
feature list.

## Acceptance criteria

1. Every capability promised by the program has either a documented native
   implementation with tests or an explicit deferred/unsupported status in
   the release documentation.
2. A caller can define a typed workflow with validated nodes and edges, run it
   with a stable run ID, inspect state, and resume from a persisted checkpoint
   after an interruption without re-running completed nodes.
3. Tool arguments and agent outputs can be parsed at the boundary into typed
   contracts, with deterministic errors for malformed input and no unsafe
   deserialization or code execution path.
4. Any code-execution capability is isolated behind an explicit, bounded,
   approval-aware execution boundary; the default path cannot execute
   untrusted code in the MAPLE process.
5. Retrieval/data primitives expose source references and have deterministic
   unit tests plus a versioned evaluation fixture before being presented as a
   production feature.
6. Workflow, model, tool, approval, checkpoint, and failure events expose
   correlation IDs, bounded structured metadata, and a documented redaction
   policy.
7. The repository has one-command setup/test/lint/build checks, a clean
   package build, a changelog entry, public API documentation, and a release
   checklist backed by real local command output.
8. Existing tests remain green, new behavior has failure-path and boundary
   tests, and no external registry, cloud service, or website is modified.

## Constraints

- Python support remains the version range declared by `pyproject.toml`.
- Prefer the standard library and existing dependencies; any new dependency
  requires a dependency-policy review and human approval where required.
- Preserve the existing `Result<T,E>` conventions and backwards-compatible
  protocol behavior.
- Local-first implementation; no cloud target is selected by this brief.
- Security-sensitive features fail closed and are never represented by demo
  placeholders.

## Assumptions

- The comparison set is LangGraph, CrewAI, Microsoft Agent Framework (the
  current AutoGen successor), LlamaIndex, and OpenAI Agents SDK.
- "Ready for publish" means repository release readiness, not publication.
- The first vertical slice is the workflow/checkpoint foundation because it
  is a dependency for human approval, replay, streaming, and evaluation.
- Existing untracked user changes are preserved and are not absorbed into
  this program without review.

## Open questions

- None block the first local workflow slice. A production cloud provider,
  hosted sandbox, and hosted vector store require a later explicit decision.

**Human confirmed:** yes - direct user request on 2026-08-24
