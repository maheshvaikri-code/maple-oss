# ADR-014: Durable approval requests for autonomous tools

## Status

Accepted — 2026-08-24

## Context

MAPLE's approval-required tools previously supported a synchronous callback and
failed closed when no callback was configured. That protects the immediate
execution boundary, but it does not let a host persist a pending action,
restart, present a request to an operator, record a decision, and execute the
approved action exactly once.

## Decision

Add a dependency-free `ApprovalStore` contract with in-memory and atomic JSON
file implementations, plus `AutonomousAgent.set_approval_store(...)` and
host-facing decision/consume methods.

- A pending record stores only bounded JSON data: approval ID, tool-call ID,
  tool name, arguments, timestamps, and optional operator decision.
- `InMemoryApprovalStore` is thread-safe for local runs. `FileApprovalStore`
  uses one canonical JSON record per approval ID and atomic replacement; it is
  thread-safe within one process.
- `decide(id, approved)` is a compare-and-set transition from `pending` to
  `approved` or `denied`. Repeated decisions fail with `APPROVAL_CONFLICT`.
- `consume(id)` is a compare-and-set transition from `approved` to
  `consumed` under the store's lock. The agent claims before invoking the
  tool, preventing accidental replay of the same approval within the store's
  process. A failed tool execution requires a new approval request.
- When a required tool has no callback but a store is configured, the agent
  creates a request and returns `APPROVAL_PENDING` without invoking the
  handler. The host records a decision and calls `execute_approved_tool(id)`.
- Existing approval callbacks retain precedence and behavior for backward
  compatibility. If neither a callback nor a store is configured, the agent
  continues to return `APPROVAL_REQUIRED`.
- The store does not persist the complete ReAct conversation or goal
  checkpoint. Full agent-run pause/resume and session replay remain separate
  capabilities.

## Alternatives considered

### Persist only a boolean callback result

Rejected because it loses the action identity, arguments, operator-visible
request, and process-restart handoff needed for durable approval.

### Execute immediately after `decide` in the store

Rejected because the store must not own tool registries or side effects. The
agent claims the record and executes through the existing tool validation,
guardrail, executor, and result boundary.

### Mark consumed after handler success

Rejected for the default safety posture: a crash after a side effect but
before persistence could allow replay. Claim-before-execute provides
at-most-once approval consumption; callers create a fresh approval for retry.

### Add a database or queue dependency

Deferred. Atomic local JSON is sufficient for the current library contract;
multi-process leases, notifications, retention, and hosted approval queues
belong in a deployment adapter with a separate dependency review.

## Consequences

Hosts can persist and inspect pending approval actions without credentials or a
cloud service. Approval arguments may contain sensitive application data, so
hosts own access control and retention for the approval directory. The new
surface is bounded and fail-closed, but it is not a complete durable agent-run
engine: conversation state, model turn replay, and cross-process CAS are
intentionally outside this slice.
