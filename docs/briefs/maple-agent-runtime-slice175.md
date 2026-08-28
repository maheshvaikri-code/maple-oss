# MAPLE Agent Runtime Slice 175 Brief

**Title:** Authenticated remote durable checkpoint export and restore
**Class:** L
**Status:** Proposed implementation slice
**Date:** 2026-08-28
**Owner:** Chief Architect

## Objective

Close the P0 remote durable-restore gap in the parity ledger with a bounded,
host-owned transfer contract over the existing authenticated `RunServer` /
`RunClient` control plane. A caller must be able to export a JSON-safe
`AgentRunCheckpoint` from one compatible host and restore it into another
compatible local store before resuming through the existing native callback
boundary.

## In scope

- `GET /v1/agents/{agent_id}/runs/{run_id}/checkpoint` under `agent:restore`.
- `POST /v1/agents/{agent_id}/runs/{run_id}/restore` under `agent:restore`.
- Additive `RunClient.export_agent_run_checkpoint()` and
  `RunClient.restore_agent_run_checkpoint()` methods.
- Strict `AgentRunCheckpoint.from_dict()` parsing, JSON bounds, route/store
  identity binding, resumable-status checks, and existing CAS save semantics.
- Metadata-only restore receipts and regression/static/security evidence.
- API reference, parity ledger, changelog, release plan, review, and QA
  artifacts.

## Explicitly out of scope

- Hosted identity federation, tenancy, TLS termination, or remote store
  discovery.
- Automatic transfer, retries, queues, scheduling, push delivery, or exactly-
  once external effects.
- Pickle or executable-object deserialization.
- Restoring terminal runs or invoking a handler during restore.
- Website changes, publication, cloud deployment, or a version bump.

## Acceptance criteria

1. Export returns the complete validated JSON checkpoint only to a caller with
   `agent:restore`; ordinary `agent:read` remains insufficient.
2. Restore rejects malformed, oversized, terminal, cross-agent, and
   cross-run checkpoints before store mutation.
3. Existing checkpoints require the caller's exact `expected_version`; new
   checkpoints cannot be silently overwritten by a version claim.
4. A restored checkpoint round-trips through a destination store and remains
   detached data; no handler or external side effect runs.
5. Existing inspection, resume, cancellation, and legacy store compatibility
   remain unchanged.
6. Focused regressions, changed-boundary static checks, full tests, and clean
   package evidence are recorded before closure.

## Threat sketch

Checkpoint messages, reasoning steps, tool arguments, pending interaction IDs,
and results are sensitive state. The main risks are unauthorized export,
cross-agent overwrite, malicious deserialization, oversized input, and replay
of stale state. The boundary uses explicit least privilege, bounded JSON
parsing, identity checks, terminal-state rejection, store-owned CAS fencing,
and no executable deserialization or execution during restore. Hosts remain
responsible for transport confidentiality, retention, principal lifecycle,
and side-effect policy.
