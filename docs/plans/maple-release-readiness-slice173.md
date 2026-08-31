# Implementation Plan — MAPLE release-readiness slice 173

**Brief:** [slice 173 brief](../briefs/maple-release-readiness-slice173.md) ·
**Design/ADRs:** [ADR-118](../adr/118-release-automation-safety.md) ·
**Class:** M

## Slices

| # | Slice | Role | Files touched | Proven by | Status |
|---|---|---|---|---|---|
| 1 | Remove workflow-dispatch branch mutation and validate tag/package/changelog agreement | Release Manager | `.github/workflows/release.yml` | workflow regression tests | done — 1ac8a72 |
| 2 | Require explicit confirmation for manual registry publication | Release Manager | `.github/workflows/publish.yml` | workflow regression tests | done — 1ac8a72 |
| 3 | Remove stale CI version text and file the v1.1.4 G6 checklist | Release Manager | `.github/workflows/ci.yml`, `docs/releases/v1.1.4.md` | static checks + checklist review | done — 1ac8a72 |
| 4 | Run local verification and record review/QA evidence | Code Reviewer / QA Engineer | `docs/reviews/`, `docs/qa/` | focused tests, full suite, package checks | done — evidence below |

## Threat sketch

Assets touched: release branch history, package artifacts, registry
credentials, and version metadata. Entry points / untrusted inputs: pushed
Git tags and manually supplied workflow inputs. Worst plausible abuse: a
mismatched or unauthorized dispatch publishes an artifact under a misleading
version, or a workflow pushes generated changes to the wrong branch.

## Risks & rollback points

- Risk: a stricter tag check rejects a malformed existing tag workflow run →
  mitigation: release only from a correctly versioned new tag → rollback:
  revert the workflow commit before creating a tag.
- Risk: manual publish confirmation is misspelled by an operator → mitigation:
  document the exact value in the checklist → rollback: no external state is
  changed; rerun with the correct input.
- Risk: current user-owned files are accidentally staged → mitigation: stage
  only the slice files and audit the staged diff → rollback: unstage before
  commit; do not touch unrelated paths.

## Deviation log

- 2026-08-28: candidate target changed from the existing package version
  `1.1.3` to `1.1.4` after confirming the `v1.1.3` tag exists; no version bump
  is made in this slice.

## Status snapshot

Done (with evidence): tag-driven release/publish gates, workflow regression
tests, clean-archive suite, doctor, and package checks. · Next: independent
review and remaining parity slices. · Blocked on: human release
authorization, fresh independent verifier, and unresolved security-gate
findings before any external publication.
