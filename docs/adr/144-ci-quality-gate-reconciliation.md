# ADR-144: Reconcile local and CI quality gates

**Date:** 2026-08-29
**Status:** accepted - source normalization
**Deciders:** Chief Architect / DevOps Engineer

## Context

MAPLE has multiple quality entry points. The checked-in GitHub Actions
workflows invoke Flake8 with a strict 88-column limit and a custom scan
requiring the creator's exact name in every Python module. The initial
workflow-equivalent run reported `610` `E501` findings and `20` missing
notices. These were repository-wide policy mismatches, not runtime defects.

## Decision

Human approval on 2026-08-29 selected source normalization. The existing strict
Flake8 and author-header workflow remains unchanged. All `maple/**/*.py`
modules were normalized to the existing AGPL notice, all overlong source lines
were wrapped, and Protocol stub ellipses were expanded to multiline bodies.
The license was not changed and no lint rule was suppressed.

## Consequences

The existing CI contract is authoritative for source formatting and
provenance. The source-only normalization changes no runtime API or license;
the mechanical quality commit remains reviewable as one logical change.

## Verification

The release plan and checklist must retain the exact commands and real passing
output for formatting, lint, type, compile, security, tests, and package
checks. No external release or website action is part of this ADR.
