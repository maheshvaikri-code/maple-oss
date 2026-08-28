# Project/Task Brief — MAPLE release-readiness slice 173

**Date:** 2026-08-28 · **Class:** M (release workflow and release evidence)
· **Requested by:** human

## Problem

MAPLE has working CI and packaging workflows, but the release path still has
unsafe or stale behavior: a manual release dispatch can commit and push to
`main`, the tag and package versions are not checked against each other, the
CI summary advertises an old version, and the repository has no versioned G6
release checklist. These gaps make the next release candidate harder to audit
and leave too much release authority inside automation.

## Scope

- In: tag-driven release workflow safety, exact version/changelog validation,
  explicit manual publish confirmation, stale CI display text, a v1.1.4 G6
  checklist, and static regression checks for those workflow invariants.
- **Non-goals:** creating tags, pushing branches, publishing to PyPI or GitHub,
  changing the website, selecting a cloud provider, or remediating the known
  environment-wide dependency audit findings.
- Deferred: action SHA pinning and hosted identity/notification/sandbox
  capabilities remain separate follow-up work after their exact upstream
  references and security scope are established.

## Acceptance criteria

1. `release.yml` cannot mutate `main` or create a version bump from
   `workflow_dispatch`; release automation accepts only a human-created tag.
2. A tag release fails when the `vX.Y.Z` tag does not equal
   `maple.__version__` or when the matching version section is absent from
   `CHANGELOG.md`.
3. A manually dispatched registry publish requires an explicit confirmation
   value, while the existing protected registry environment remains in force.
4. CI no longer reports the stale `1.1.1` version.
5. `docs/releases/v1.1.4.md` records the candidate state, exact current
   evidence, unresolved gates, and rollback path without claiming publication.
6. Static workflow regression tests and the repository’s applicable local
   checks pass.

## Constraints

Python 3.8+ remains supported. No runtime dependency or credential is added.
The current `v1.1.3` tag must not be reused. Existing user-owned working-tree
changes remain untouched. External release actions remain human-controlled.

## Assumptions

- The next candidate version is `1.1.4` because `v1.1.3` is already tagged.
- A human-created release tag and protected GitHub environment are the release
  approvals; this repository change does not grant approval itself.

## Open questions

- None blocking for the local workflow and evidence changes.

**Human confirmed:** no · external release actions remain deferred by policy
