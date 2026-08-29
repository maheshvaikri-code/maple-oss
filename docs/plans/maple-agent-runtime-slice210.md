# Slice 210 implementation plan - strict structured-output JSON parsing

**Class:** M
**Status:** Design complete; implementation pending
**Brief:** `docs/briefs/maple-agent-runtime-slice210.md`
**ADR:** `docs/adr/154-strict-structured-output-json.md`

## Gate plan

| Gate | Work | Evidence |
| --- | --- | --- |
| G2 | Confirm the existing parser boundary, strict finite-JSON decision, and rollback. | Brief, ADR, and this plan. |
| G3 | Add the decoder hook and recursion normalization without changing public signatures. | `maple/autonomy/contracts.py` plus regression tests. |
| G4 | Inspect the diff for bounds, error disclosure, compatibility, and absence of unrelated changes. | Self-review report with severity-ranked findings. |
| G5 | Run focused contract tests, the full suite, static checks, dependency audit, and package smoke. | QA/security evidence with real command output. |
| G6 | Reconcile release readiness only; do not bump, tag, publish, deploy, or update the website. | Release-plan entry and changelog note. |

## Implementation units

1. Configure `json.loads()` to reject non-standard numeric constants and catch
   parser recursion failures.
2. Add failure-path regressions for all three constants and deep nesting, plus
   a valid finite-number control case.
3. Update API/release documentation and changelog with the trust-boundary
   correction.
4. Run the prescribed validation and file review/QA evidence.

## Loop journal

- Iteration 1: audit existing contracts and parity ledger; identified default
  JSON constant acceptance and uncaught parser recursion as the next local
  release-safe gap.
