# Code Review - MAPLE Agent Runtime Slice 165

**Review basis:** `3de5e27`
**Brief:** `docs/briefs/maple-agent-runtime-slice165.md`
**ADR:** `docs/adr/110-authenticated-handoff-result-delivery.md`
**Date:** 2026-08-28
**Role:** Code Reviewer

## Decision

Pass after the corrective patch in `d346291`.

## Findings

### [MAJOR] Preserve legacy completion calls without a result — resolved

- **Location:** `maple/autonomy/server.py`, `_RequestHandler._mutate_handoff`
- **Evidence:** The completion branch always passes `result=` to
  `HandoffStore.complete`, including when the request omits the new optional
  field. A custom store that implements the previously accepted
  `complete(handoff_id, target_agent_id, target_goal_id)` signature now raises
  `TypeError`, which the request dispatcher converts into an internal `500`.
- **Impact:** The brief requires existing completion calls without `result` to
  behave as before; this breaks that compatibility boundary for custom stores.
- **Resolution:** `d346291` calls the legacy three-argument form when the
  request omits `result`, passes the keyword only for the explicit new field,
  and adds a regression test using a legacy-signature store.

## Clean checks

- Reviewed the brief, ADR, runtime diff, server/client route mapping, result
  bounds, authorization-before-body-read path, redacted metadata path, and
  least-privilege result envelope.
- Original focused review execution: `99 passed in 17.54s`.
- Post-fix focused execution: `100 passed in 18.55s`.
- No additional blocker was found in the result-scope mapping, bounded result
  submission, invalid-result no-mutation path, or response redaction.

## Review status

The compatibility finding is resolved and G4 passes. No publication,
deployment, cloud action, or website update is part of this review.
