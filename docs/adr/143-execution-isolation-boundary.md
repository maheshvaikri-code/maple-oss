# ADR-143: Gate code, browser, computer-use, and sandbox execution

**Date:** 2026-08-29  
**Status:** proposed — implementation blocked pending explicit contract  
**Deciders:** Chief Architect

## Context

The five-framework parity review exposes execution integrations that MAPLE
does not currently claim: code interpreter, browser automation, computer use,
and sandboxed execution. MAPLE has a `TrustedLocalExecutor` for explicitly
trusted local handlers and a non-executing code-block artifact materializer.
Neither surface establishes isolation from the host, controls network or
credentials, or defines external side effects.

## Decision

Do not add execution code in this slice. Keep the capability explicitly
unsupported and require a reviewed contract before implementation. The future
contract must select an isolation target and define filesystem/network/device
permissions, approval binding, quotas, artifact/result semantics, cleanup,
identity/tenancy, audit, and side-effect policy. Any future implementation must
fail closed on missing isolation, expired approval, quota exhaustion, malformed
artifact, cleanup failure, and ambiguous ownership.

## Boundary

```text
agent request
    |
    v
typed action + principal + run + artifact digests
    |
    +-- missing contract / approval / isolation --> typed refusal
    |
    v
reviewed isolated worker (future, not implemented here)
    |
    +-- quota / cancellation / crash / cleanup failure --> terminal refusal
    |
    v
redacted content-addressed result + audit receipt
```

The current boundary is:

```text
code block extraction/materialization --> artifact bytes only
TrustedLocalExecutor                --> explicitly trusted host handler only
```

Neither current path executes generated code or provides browser/computer
control.

## Required human decisions

- isolation technology and supported host platforms;
- workspace mounts, artifact transfer, symlink/path policy, and cleanup;
- network, DNS, proxy, browser, display, input-device, and secret policy;
- action approval, principal/tenant binding, expiry, cancellation, and denial;
- CPU, memory, process, time, output, browser-session, and network quotas;
- artifact types, provenance, retention, redaction, and result semantics;
- identity, audit, replay/idempotency, and external-side-effect policy;
- explicit cloud target and cloud-stage approval if managed infrastructure is
  selected.

## Alternatives considered

| Option | Decision | Reason |
|---|---|---|
| Add a subprocess or shell helper now | Rejected | A subprocess is not a complete isolation boundary and would create host, credential, filesystem, and cleanup risk without a contract. |
| Rebrand `TrustedLocalExecutor` as a sandbox | Rejected | It would overstate the existing trust model and create a false security claim. |
| Add a provider/browser SDK directly | Deferred | It introduces external dependencies, credentials, network behavior, and provider-specific semantics before policy is defined. |
| Keep the capability gated and design the boundary | Chosen | Preserves fail-closed behavior and makes the missing security decisions explicit. |

## Consequences

Positive: MAPLE's release claims remain accurate, no unsafe execution path is
introduced, and a future implementation has explicit security gates.

Negative: MAPLE remains behind the comparison set for this capability until a
human-approved isolation and side-effect contract exists. This is intentional,
not an implementation-complete claim.

## Invalidation triggers

Any implementation request, cloud/managed-worker selection, credential
injection, browser driver, external side effect, multi-tenant execution, or
exactly-once/replay claim invalidates this design-only decision and requires a
new security review.
