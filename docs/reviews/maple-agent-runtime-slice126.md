# MAPLE Agent Runtime Slice 126 Review

**Date:** 2026-08-27
**Implementation commit:** `8ea5b6d`
**Review roles:** Code Reviewer / Security Reviewer
**Scope:** bounded durable approval-outcome replay

## Review findings

1. The approval state transition remains single-use: the request is consumed
   before the handler runs, and the terminal `{content, is_error}` outcome is
   recorded only for the consumed built-in record.
2. Replay is bounded and deterministic. Stored outcomes are validated at the
   request boundary, capped at `131,072` UTF-8 bytes, and returned without
   invoking the tool handler again.
3. The file store keeps its existing lease and atomic-replacement boundary;
   recording is idempotent for the same result and rejects conflicting writes.
4. The handler is not automatically retried when recording fails or when a
   consumed record has no outcome. Those paths expose typed uncertainty rather
   than risking a second external side effect.
5. Custom approval stores are not forced to implement persistence they cannot
   provide. The runtime detects the optional recorder capability and preserves
   the earlier behavior when it is absent.
6. The design stores tool-result content in local approval state. The bound is
   explicit, and hosts remain responsible for choosing an appropriate store,
   access controls, retention policy, and redaction strategy for sensitive
   result content.

## Review result

**Approved for the bounded local replay slice.** The implementation closes the
P0 pending-approval crash-recovery gap for built-in stores while accurately
retaining the at-least-once external-effect model. Distributed transactions,
remote approval transport, sandboxing, scheduling, and exactly-once effects
remain separate capabilities. The environment-wide dependency audit remains
a release-governance veto independent of this code review. The clean tracked
archive wheel and sdist build, Twine checks, workspace-only boundary audit, and
isolated no-dependency approval-export smoke also passed.
