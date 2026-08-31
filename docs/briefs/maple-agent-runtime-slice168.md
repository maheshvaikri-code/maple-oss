# Project Brief - typed remote agent-run lifecycle

**Date:** 2026-08-28
**Class:** M - public client API and transport-boundary normalization
**Requested by:** human

## Problem

The authenticated remote agent transport already supports start, inspect,
history, resume, and cooperative cancel routes. The start/resume/cancel client
methods return raw dictionaries, so every caller must parse the run envelope
independently. `RemoteHandoffTarget` consequently owns a second parser, which
creates inconsistent identity and malformed-response handling at a public
boundary.

## Scope

- In: additive typed `RunClient` methods for agent start, resume, and cancel;
  one shared bounded response normalizer; regression tests and API docs.
- In: preserve the existing raw methods and wire format for compatibility.
- Non-goals: new HTTP routes, remote checkpoint storage, scheduling, retries,
  push notifications, identity federation, or exactly-once side effects.

## Acceptance criteria (numbered, testable)

1. `run_agent_typed(...)` returns a validated public `AgentRun` for a valid
   remote envelope and preserves completed, paused, failed, and cancelled
   statuses.
2. Typed resume and cancel methods use the existing authenticated routes and
   return validated `AgentRun` values; cancel rejects a non-cancelled result.
3. Malformed envelopes, identity mismatches, invalid result/error values, and
   invalid transport responses fail closed with a stable generic error that
   does not expose remote private details.
4. Existing raw `run_agent`, `resume_agent_run`, and `cancel_agent_run` callers
   remain unchanged, and `RemoteHandoffTarget` behavior remains unchanged.
5. Public API documentation, changelog, parity wording, and release evidence
   describe the typed surface and retain the no-retry/no-exactly-once boundary.
6. Focused and tracked tests, static gates, and clean-archive packaging pass.

## Constraints

- Python standard library and existing `Result`, `AgentRun`, and bounded JSON
  validation only; no dependency changes.
- The typed methods must not return unvalidated remote mappings as `AgentRun`.
- Remote error messages and result data are returned only after the existing
  transport and run normalizers accept them.
- No change to authentication, route scopes, or host-owned resume callbacks.

## Threat sketch

Assets touched: bearer-authenticated run identity, remote result/error data, and
caller lifecycle decisions. Untrusted inputs are remote JSON, status codes,
and caller-supplied agent/run IDs. Worst plausible abuse is a malicious or
broken host returning a mismatched run, oversized value, or private error that
causes a caller to act on the wrong lifecycle state. Shared normalization,
identity checks, bounded JSON copying, and generic adapter errors contain the
boundary.

## Open questions

- None. The feature is additive and does not change the external cloud target.

**Human confirmed:** continuation of the direct request on 2026-08-28
