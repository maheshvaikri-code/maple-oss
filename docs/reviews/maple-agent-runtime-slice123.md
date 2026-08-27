# MAPLE Agent Runtime Slice 123 Review

**Date:** 2026-08-27
**Implementation commit:** `8ec56bb`
**Review roles:** Code Reviewer / Security Reviewer
**Scope:** authenticated host-owned cooperative agent-run cancellation

## Review findings

1. The public contract is additive: existing invocation and resume callbacks
   remain unchanged, while `cancel_handler` is optional.
2. The operation is fail-closed: agent/run identifiers are validated, callback
   exceptions are redacted, and a callback cannot report cancellation unless
   its normalized envelope is explicitly `cancelled`.
3. Authentication, loopback binding, body draining, response bounds, and
   transport error mapping reuse the existing server boundary.
4. The design does not overclaim hard cancellation or exactly-once behavior;
   token propagation, worker cleanup, checkpoint state, and side-effect
   reconciliation remain host responsibilities.
5. Tests cover success, missing capability, wrong callback status, callback
   exception redaction, and authenticated transport behavior.

## Review result

**Approved for the bounded preview slice.** The implementation is limited to
the transport/control seam and does not introduce dependencies or alter the
existing durable store contract. The environment-wide dependency audit remains
a release-governance veto, independent of this slice's code review.
