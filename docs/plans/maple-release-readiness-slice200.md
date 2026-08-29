# Slice 200 plan — CI quality gate reconciliation

**Brief:** [Slice 200 brief](../briefs/maple-release-readiness-slice200.md)  
**Design/ADR:** [ADR-144](../adr/144-ci-quality-gate-reconciliation.md)  
**Class:** L

## Gates

| # | Gate | Role | Artifact | Status |
|---|---|---|---|---|
| 1 | Reproduce local and CI quality commands | DevOps / QA | command evidence and workflow contract tests | complete |
| 2 | Select authoritative quality/header policy | Human / Chief Architect / DevOps | approved option in ADR-144 | blocked pending human decision |
| 3 | Implement selected workflow/source policy | DevOps | workflows, config/source edits, regression tests | pending |
| 4 | Verify clean-clone and release gates | QA / Security / Release | full/static/security/package evidence | pending |

## Threat and failure sketch

The assets are release trust, CI enforcement, source provenance, and legal
notices. Failure modes include green local checks with a red CI job, an
undocumented blanket lint suppression, unreviewed copyright text, and a
release claim based on a workflow that was never executed successfully.

## Current package smoke

Clean committed candidate `76de1f7` rebuilt and installed without the dirty
workspace files:

```text
source_archive_entries=935
wheel_entries=108
sdist_entries=849
build_exit=0
twine_exit=0
install_exit=0
import_ok
doctor_exit=0
doctor_network=false
doctor_ready=true
wheel_sha256=c1ef5e00c4ff14a00fa4651dddf83be6c89ad4ed287a3d2e3d06667220cc1385
sdist_sha256=56197ed1329eca1caa8277621f6d3d5d9cd0208a1afc23aab147a1fcee9c7b4d
```

## Rollback

The safe rollback is to revert only the follow-up workflow/source policy
commit. Preserve the current fail-closed quality workflow and keep the release
conditional until a replacement policy is verified.

## Exit condition

Gate 1 is complete. Gate 2 requires the human to select a policy; no CI quality
or licensing rule is changed by this design slice.
