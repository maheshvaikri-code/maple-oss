# ADR-119: Pin GitHub Actions to reviewed immutable commits

**Date:** 2026-08-28 · **Status:** accepted
**Deciders:** Chief Architect

## Context

All MAPLE workflows currently select third-party GitHub Actions by mutable
major tags such as `@v4` and `@release/v1`. A future tag movement could change
the code executed by CI or the release pipeline without a repository diff.
The repository’s CI doctrine requires pinned action versions, while the
current workflow behavior should remain stable.

## Decision

We will pin every existing third-party action reference to the full commit SHA
verified for its current selected release, retaining a version comment beside
the pin. Pin refreshes require a new reviewed change and an upstream SHA
lookup; no automatic action-upgrade mechanism is introduced by this slice.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Full SHA pins (chosen) | Reproducible workflow code; reviewable updates | Maintenance requires deliberate refreshes | Meets the CI supply-chain requirement without behavior changes |
| Keep major tags | Minimal diff; automatic minor fixes | Tag movement changes executed code | Not reproducible enough for release gates |
| Vendor action code | Maximum local control | Large maintenance and legal/security surface | Excessive for the current workflow scope |

## Consequences

- Positive: later runs execute the reviewed action commits, even if upstream
  tags move.
- Negative / debt accepted: pins become stale and must be refreshed manually;
  comments can drift and require review.
- Invalidation triggers: an action major-version migration or a verified
  organization-wide pinning service may reopen this decision.
