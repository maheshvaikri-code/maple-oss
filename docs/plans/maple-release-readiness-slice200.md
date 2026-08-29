# Slice 200 plan - CI quality gate reconciliation

**Brief:** [Slice 200 brief](../briefs/maple-release-readiness-slice200.md)
**Design/ADR:** [ADR-144](../adr/144-ci-quality-gate-reconciliation.md)
**Class:** L

## Gates

| # | Gate | Role | Artifact | Status |
|---|---|---|---|---|
| 1 | Reproduce local and CI quality commands | DevOps / QA | command evidence and workflow contract tests | complete |
| 2 | Select authoritative quality/header policy | Human / Chief Architect / DevOps | approved Option 1 in ADR-144 | complete - approved 2026-08-29 |
| 3 | Implement selected workflow/source policy | DevOps | source edits and regression checks | complete - workflow unchanged; source normalized |
| 4 | Verify clean-clone and release gates | QA / Security / Release | full/static/security/package evidence | in progress |

## Threat and failure sketch

The assets are release trust, CI enforcement, source provenance, and legal
notices. Failure modes include green local checks with a red CI job, an
undocumented blanket lint suppression, unreviewed copyright text, and a
release claim based on a workflow that was never executed successfully.

## Exit condition

Gates 1-3 are complete. Gate 4 continues with the MAPLE 2.0.0 full-suite,
package, security, and release-candidate evidence. External publication,
registry writes, cloud actions, and website deployment remain human-gated.
