# MAPLE agent-framework parity follow-up plan

**Scope:** functionality and developer surface only; adoption and license are
excluded as requested.
**Baseline:** MAPLE 2.0.0 local release candidate.
**Source:** [agent framework parity matrix](../agent-framework-parity.md)

## Delivery rules

Each phase must add a bounded public contract, tests, documentation, and a
release artifact. Hosted or distributed claims require an emulator and parity
ledger before any real-provider promotion. Security-sensitive execution and
external side effects remain fail-closed by default.

## Prioritized work

| Priority | Capability gap | MAPLE delivery | Exit evidence |
|---|---|---|---|
| P0 | Hosted identity, tenancy, and policy | Define principal/tenant/policy interfaces, request context propagation, authorization decisions, key rotation, audit events, and an in-process reference implementation. | Contract tests prove tenant isolation, deny-by-default, bounded context, and stable error envelopes. |
| P0 | Distributed scheduling and liveness | Add lease-backed worker membership, heartbeats, task claiming, expiry/reassignment, fencing, and a documented at-least-once effect model. | Multi-worker emulator, crash/restart tests, stale-owner rejection, and duplicate-effect ledger. |
| P0 | External side-effect reliability | Standardize idempotency keys, durable intent/outbox records, retry budgets, cancellation, compensation hooks, and operator inspection. | Crash-window matrix, replay tests, bounded retries, and no implicit exactly-once claim. |
| P1 | Managed state and retrieval | Define pluggable state/vector interfaces, consistency and retention contracts, authorization boundaries, migration/versioning, and local adapters. | File/in-memory reference implementations plus compatibility and restart tests. |
| P1 | Sandboxed execution | Define capability-scoped code execution with resource/time/network/filesystem limits, cancellation, artifact capture, and audit. | Deterministic local sandbox emulator, escape-negative tests, and explicit host boundary. |
| P1 | Browser/computer tools | Add provider-neutral tool contracts for navigation, screenshots, input, confirmation, and human approval; keep implementations host-owned. | Mock tool adapter, consent tests, prompt-injection handling, and bounded artifact policy. |
| P1 | Hosted observability and evals | Extend local traces/evals into exportable schemas with correlation, retention, redaction, dataset/version identity, and scorer provenance. | Golden traces, redaction tests, deterministic evaluator fixtures, and export/import checks. |
| P2 | Language and provider breadth | Add capability declarations and conformance suites for additional model/provider clients; preserve explicit async/streaming semantics. | Provider contract matrix, optional-dependency tests, and no-hidden-fallback documentation. |
| P2 | Production hosting and operations | Package health/readiness, configuration, migration, backup/restore, rate-limit, and incident-runbook contracts for an approved provider. | Local deployment emulator first, then provider-specific evidence after cloud approval. |

## Phase sequencing

1. **Foundation:** identity/policy context, idempotency/outbox, and shared
   error/trace contracts.
2. **Distributed runtime:** worker liveness, leases/fencing, reassignment, and
   effect ledger on the local emulator.
3. **Capability plane:** managed state/retrieval interfaces and sandbox/tool
   contracts with host-owned implementations.
4. **Evaluation plane:** exported traces, datasets, scorer provenance, and
   regression suites.
5. **Provider/hosting adapters:** language breadth and approved-cloud work only
   after the provider is recorded and the local parity ledger is complete.

## Definition of complete

A row is complete only when its interface is documented, its security and
failure model is explicit, reference behavior is tested, the parity matrix is
updated, and a release artifact records real output. “Supported” must not mean
“a placeholder exists” or “a provider SDK happens to work.”
