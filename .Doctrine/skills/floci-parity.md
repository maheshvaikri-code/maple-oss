---
name: floci-parity
description: Instrument a demo run and emit parity-ledger.json classifying every exercised cloud API call by emulation fidelity. Use this in FDE phase P5 after `make verify` passes, before any promotion work, and whenever anyone asks "is this cloud-ready", "will this work on AWS/GCP/Azure", or wants to present emulator results to a stakeholder. Promotion without a ledger is prohibited — if floci-promote is requested and no ledger exists, run this first.
version: 0.1.0
inputs: [floci.manifest.yaml, endpoints.lock.json, a passing `make demo`]
outputs: [parity-ledger.json]
---

# floci-parity

The honesty layer. Emulators diverge from real clouds silently — IAM semantics, quotas,
eventual consistency, error shapes. This skill makes the divergence explicit and
machine-readable so "verified on emulator" is never confused with "verified on AWS".

## Fidelity classes

- **high** — emulator behavior matches the real service for this operation, including
  error shapes. Safe to trust.
- **partial** — happy path matches; edge behavior (auth, quotas, consistency, pagination)
  diverges. Trust the demo, checklist the edges.
- **stub** — call is accepted and shaped correctly but semantics are faked. Demo-only.
- **unsupported** — call would fail or misbehave on the emulator. Must not be on the
  critical path.

## Procedure

1. **Capture.** Run `make demo` with Floci call logging enabled (proxy log or
   `floci logs --calls`, per installed CLI). Collect the set of `(service, operation)`
   pairs with counts.
2. **Classify.** Look up each pair in the fidelity table shipped with the pinned Floci
   version. A pair absent from the table classifies as `unsupported` — unknown is not
   assumed safe.
3. **Mark critical path.** An operation is critical-path if the demo scenario's
   observable output depends on it (derive from the scenario trace, not from guessing).
4. **Emit** `parity-ledger.json` conforming to `schemas/parity-ledger.schema.json`,
   canonical JSON. Include the demo run's command, exit code, and output sha256 as
   evidence binding the ledger to a specific verified run.
5. **Verdict.** `summary.gate`: `block` if any critical-path call is `stub` or
   `unsupported`; `warn` if any critical-path call is `partial`; else `pass`.

## Rules

- Never edit a ledger by hand; regenerate from a run.
- Never downgrade a classification to make a gate pass; if the table is wrong, fix the
  table (a human-authored artifact) and note the change.
- One ledger per demo scenario; multiple scenarios → multiple ledgers.

## Failure modes

- **Call capture empty:** the demo bypassed instrumented endpoints — treat as a P4 defect
  (hardcoded hostname somewhere), not a parity result.
- **Fidelity table missing for pinned version:** stop; do not substitute a neighboring
  version's table.
