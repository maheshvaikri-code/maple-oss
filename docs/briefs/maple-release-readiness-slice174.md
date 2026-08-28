# Project/Task Brief — MAPLE release-readiness slice 174

**Date:** 2026-08-28 · **Class:** M (workflow supply-chain hardening) ·
**Requested by:** human

## Problem

MAPLE’s GitHub workflows reference third-party actions by mutable major tags.
That leaves a release or verification run dependent on whatever code a tag
resolves to later, weakening reproducibility and supply-chain review.

## Scope

- In: replace every third-party action tag in `.github/workflows/` with the
  verified immutable commit for the currently selected action release, while
  retaining the human-readable release in a comment; add static regression
  coverage.
- **Non-goals:** upgrading action major versions, changing workflow triggers,
  adding dependencies, publishing, or changing website/cloud behavior.
- Deferred: periodic action refresh and automated provenance attestations.

## Acceptance criteria

1. Every `uses:` reference in the workflow directory resolves to a full commit
   SHA, not a branch, tag, or floating major version.
2. The pinned SHAs correspond to the selected current releases documented next
   to each reference.
3. Workflow YAML parsing and static pin regression tests pass.
4. Existing Python tests and package behavior remain unchanged.

## Constraints

No runtime dependencies, credentials, action inputs, workflow triggers, or
external state may change. The pins are verified read-only from the upstream
repositories before editing.

## Assumptions

- A full 40-hex commit SHA is the reproducibility boundary; comments carry the
  human-readable tag for maintenance.
- Refreshing a pin is a new reviewed change, not an automatic update.

## Open questions

- None blocking for this local hardening slice.

**Human confirmed:** no · no workflow execution or external release action
was performed
