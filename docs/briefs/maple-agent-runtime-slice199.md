# Slice 199 brief — execution integration isolation gate

**Date:** 2026-08-29  
**Class:** L (security-sensitive public execution boundary)  
**Requested by:** human continuation request

## Problem

The parity ledger identifies code interpreter, browser, computer-use, and
sandbox execution as unsupported. MAPLE currently exposes
`TrustedLocalExecutor`, which intentionally runs only explicitly trusted local
handlers. Adding a code block materializer or an agent tool is not equivalent
to providing a safe sandbox. An execution surface needs an explicit isolation,
approval, credential, artifact, cleanup, and side-effect contract first.

## Scope

- In: threat model, isolation contract, action taxonomy, approval boundary,
  filesystem/network/device policy, resource limits, artifact exchange,
  cleanup, audit, and release gates for a future local execution adapter.
- Out: shell execution, Python evaluation, browser-driver integration,
  computer-use control, container/VM provisioning, hosted workers, credential
  injection, or changes to `TrustedLocalExecutor`.
- Deferred: any implementation until the human decisions below are recorded
  and the selected isolation mechanism has a security review.

## Required contract decisions

1. **Isolation target:** choose process, OS container, VM, or another reviewed
   boundary, plus supported operating systems and architecture.
2. **Filesystem policy:** define workspace roots, read/write mounts, artifact
   ingress/egress, symlink handling, path traversal rules, and cleanup on
   timeout, cancellation, crash, and normal completion.
3. **Network and device policy:** default-deny or allowlisted egress, proxy/DNS
   behavior, loopback access, browser permissions, display/input devices, and
   outbound secret filtering.
4. **Action and approval policy:** define which code, browser, and computer
   actions require approval; bind approvals to principal, run, action digest,
   resource scope, and expiry; define cancellation and denial semantics.
5. **Resource limits:** set wall-clock, CPU, memory, process, file, output,
   browser-session, and network quotas, including telemetry and enforcement
   behavior when a limit is reached.
6. **Artifacts and results:** define content-addressed inputs/outputs,
   maximum sizes, MIME/type policy, provenance, redaction, retention, and
   whether generated code can be returned without execution.
7. **Side effects and identity:** define identity/tenancy, audit retention,
   replay/idempotency policy, external side-effect authorization, and whether
   execution is inspection-only or can mutate external systems.
8. **Operational target:** if implementation requires a cloud or managed
   service, record one explicit provider target and obtain the cloud-stage
   approval before the first SDK/deploy call.

## Acceptance criteria for this design gate

1. The threat model identifies code, credentials, filesystem, network,
   browser, device, artifact, and external-side-effect assets.
2. The ADR records the fail-closed decision and all required contract inputs;
   no unsupported capability is described as implemented.
3. The implementation plan has explicit gates for the isolation adapter,
   adversarial tests, fresh security/QA review, and package evidence.
4. No code, dependency, subprocess, browser driver, network call, or cloud
   resource is introduced by this design-only slice.

## Current decision

Until the required decisions are supplied and reviewed, MAPLE remains
unsupported for code interpreter, browser, computer-use, and sandbox claims.
`TrustedLocalExecutor` remains a trusted-handler seam and is not promoted to a
sandbox. Existing code-block extraction/materialization remains non-executing.

**Human input required before implementation:** decisions 1–8 above, or an
explicit decision to keep this capability outside MAPLE's release scope.
