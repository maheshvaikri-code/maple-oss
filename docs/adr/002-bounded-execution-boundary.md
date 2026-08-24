# ADR-002: Bounded execution for trusted local handlers

**Status:** Accepted  
**Date:** 2026-08-24  
**Decision owners:** Chief Architect / Security Reviewer

## Context

MAPLE tools currently call Python handlers directly. The framework needs an
execution boundary that can enforce input/output size, concurrency, timeout,
cancellation, approval, and cleanup semantics without implying that an
in-process Python thread can be forcibly killed. Executing model-provided code,
shell commands, or arbitrary untrusted Python is not in scope for this boundary.

## Decision

Add `maple.autonomy.execution.TrustedLocalExecutor` with:

- explicit `ExecutionPolicy` limits for timeout, input/output bytes, and active
  executions;
- a `CancellationToken` that is set on caller cancellation and timeout;
- fail-closed approval callbacks;
- per-call worker cleanup and bounded concurrency;
- JSON serialization for size accounting, with no executable deserialization;
- a clearly named trusted-local contract used by `Tool` only when opted in.

Timeout is a caller deadline plus cooperative cancellation request. It is not a
hard kill for a handler already running in the Python process. Hard isolation
requires a separately reviewed subprocess or hosted sandbox and remains
deferred.

## Alternatives considered

1. **Direct handler calls:** rejected because they provide no common bounds or
   approval/cancellation boundary.
2. **In-process thread kill:** rejected because Python cannot safely terminate a
   running thread.
3. **Implicit subprocess execution:** deferred; arbitrary handler pickling,
   cross-platform process policy, and OS-level resource isolation require a
   separate security design.

## Consequences

Trusted integrations gain predictable failure results and explicit resource
limits. Callers must make long-running handlers cooperative if they need
cancellation. The API does not provide a security boundary for untrusted code;
that limitation is public and test-covered.
