# Slice 210 implementation plan - strict structured-output JSON parsing

**Class:** M
**Status:** Complete locally; release-gated
**Brief:** `docs/briefs/maple-agent-runtime-slice210.md`
**ADR:** `docs/adr/154-strict-structured-output-json.md`

## Gate plan

| Gate | Work | Evidence |
| --- | --- | --- |
| G2 | Confirm the existing parser boundary, strict finite-JSON decision, and rollback. | Brief, ADR, and this plan. |
| G3 | Add the decoder hook and recursion normalization without changing public signatures. | Implementation commit `65d3b51`; `maple/autonomy/contracts.py` plus regression tests and aligned docs. |
| G4 | Inspect the diff for bounds, error disclosure, compatibility, and absence of unrelated changes. | `docs/reviews/maple-agent-runtime-slice210.md`; no findings. |
| G5 | Run focused contract tests, the full suite, static checks, dependency audit, and package smoke. | `docs/qa/maple-agent-runtime-slice210.md`; focused `19 passed`, full `1881 passed, 1 skipped`, clean archive smoke. |
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
- Iteration 2: implemented strict constant rejection and typed recursion
  normalization; the first deep-nesting regression assumption was invalid on
  this interpreter, so it was replaced with deterministic decoder-failure
  injection and the corrected focused suite passed.
- Iteration 3: completed static, dependency, package, review, and QA evidence;
  no new dependency or public signature change was introduced.

## Local closure

Implementation and documentation are committed at `65d3b51`. The candidate
passed the focused and full regression suites, changed-boundary formatting,
lint, typing, compilation, project-scoped dependency audit, and isolated
package smoke. Bandit, Gitleaks, and a fresh independent verifier were
unavailable, and the broader release remains conditional on the repository
and human publication gates.
