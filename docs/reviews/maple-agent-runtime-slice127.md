# MAPLE Agent Runtime Slice 127 Review

**Date:** 2026-08-27
**Implementation commit:** `3b0121c`
**Review roles:** Code Reviewer / Security Reviewer
**Scope:** authenticated bounded remote approval control transport

## Review findings

1. The new route family is optional and requires `auth_token` whenever an
   `ApprovalStore` is configured. Existing loopback binding, bearer validation,
   path limits, body limits, and response limits remain in force.
2. The transport delegates all state transitions to `ApprovalStore`. It does
   not duplicate validation, bypass file leases, or create a second approval
   state machine.
3. Remote callers can list, inspect, and decide approvals, including one
   bounded edited-arguments object. Invalid decisions and non-object edits fail
   before store mutation; the route never consumes or invokes a tool.
4. Inspection returns the store's JSON-safe request envelope, which can include
   tool arguments and a recorded terminal result. Hosts therefore remain
   responsible for bearer-token scope, TLS, retention, and sensitive-data
   handling.
5. The implementation adds no retries, notifications, scheduling, token
   issuance, tenant isolation, remote execution, or exactly-once effect claim.
   Those boundaries remain explicit in ADR-073 and the public docs.

## Review result

**Approved for the bounded authenticated control-plane slice.** The feature
closes remote approval decision transport while preserving local execution and
side-effect ownership. The clean tracked archive package, Twine checks, and
isolated no-dependency transport-export smoke also pass. Hosted identity,
delivery, scheduling, sandboxing, distributed transactions, and exactly-once
effects remain separate work.
