# Slice 193 brief - hosted coordination decision gate

**Date:** 2026-08-29
**Class:** M
**Role:** Chief Architect / Security / Release
**Status:** gated

## Objective

Turn the remaining high-value parity gaps into an explicit contract before
implementation: hosted identity and tenancy, distributed worker scheduling
and liveness, and side-effect/retry semantics for remote coordination.

## Why this is gated

MAPLE currently provides bounded host-owned principals, local policy,
loopback/remote transport contracts, durable local queues, local fencing, and
explicit at-least-once behavior. Those surfaces do not establish tenant
isolation, token issuance or federation, distributed ownership/leases,
worker-failure reconciliation, or exactly-once external effects. Adding a
heartbeat, lease, or hosted-looking route without choosing those semantics
would create a misleading partial contract.

## Decision inputs required before implementation

- identity authority: host-owned tokens, an approved federation, or another
  explicitly selected provider;
- tenant boundary: data, credentials, queues, events, checkpoints, artifacts,
  and audit-log isolation requirements;
- scheduler semantics: ownership, lease renewal/expiry, worker liveness,
  reassignment, fairness, capacity, and durable coordination authority;
- effect semantics: idempotency keys, retry policy, compensation, and the
  exact boundary at which at-least-once behavior is acceptable;
- operational target: local emulator only, or a human-approved cloud/provider
  target with its security and cost constraints.

## Acceptance criteria for opening implementation

1. A human-approved contract names the identity/tenant authority and the
   scheduler/effect consistency model.
2. The contract defines failure, replay, isolation, and audit behavior with
   bounded test fixtures.
3. The implementation is split into reversible slices with no implicit cloud
   or publication action.
4. The parity ledger and release checklist state exactly what is implemented
   and what remains a non-claim.

## Current disposition

No code is changed by Slice193. Local release hardening through Slice192 is
complete. Hosted coordination remains a deliberate gate requiring the inputs
above; publication, cloud services, and website work remain out of scope.
