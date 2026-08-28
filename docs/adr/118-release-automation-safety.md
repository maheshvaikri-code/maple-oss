# ADR-118: Make release automation tag-driven and fail closed

**Date:** 2026-08-28 · **Status:** accepted
**Deciders:** Chief Architect

## Context

The repository already has `v1.1.3`; the next release candidate must therefore
use a new version. The former manual release path could bump files, commit, and
push `main` from a workflow dispatch, and release jobs did not prove that the
tag, package metadata, and changelog described the same version. Registry
publication is an external action and must remain deliberately authorized.

## Decision

We will make the GitHub Release workflow react only to human-created `v*`
tags, validate the tag against `maple.__version__` and a matching changelog
heading before building, and remove automation that commits or pushes version
bumps. Manual registry publication will require an explicit confirmation value
in addition to the existing protected environment. A versioned G6 checklist
will record candidate evidence and every remaining human or governance gate.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Tag-driven, validated release (chosen) | Small authority surface; exact version audit; reversible before tag creation | Human must prepare and tag a release | Matches the doctrine’s deliberate-tag and human-publish rules |
| Keep workflow-dispatch version bump | Convenient one-click release | Workflow can mutate/push `main`; generated commit is harder to review | Unsafe release authority and violates clean release discipline |
| Validate only in documentation | No workflow changes | CI can still create mismatched or stale artifacts | Does not enforce the invariant |

## Consequences

- Positive: release automation cannot create an unreviewed version bump or
  push the wrong branch; mismatched tags fail before artifact creation.
- Negative / debt accepted: action references are still major-version tags and
  require a separate pinning slice; registry security tooling and dependency
  findings remain release gates.
- Invalidation triggers: a supported release service with a reviewed,
  human-approved version-bump flow may reopen the removed dispatch path.
