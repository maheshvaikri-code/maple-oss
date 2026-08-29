# ADR-144: Reconcile local and CI quality gates

**Date:** 2026-08-29  
**Status:** proposed — human policy decision required  
**Deciders:** Chief Architect / DevOps Engineer

## Context

MAPLE has multiple quality entry points. Current local checks report Black
clean, isort clean after `d1faac3`, Ruff clean, and mypy clean. The checked-in
GitHub Actions workflows instead invoke Flake8 with a strict 88-column limit,
plus a custom scan requiring the creator's exact name in every Python module.
The workflow-equivalent Flake8 run reports `608` `E501` findings, while the
header scan reports `19` missing notices. These are existing repository-wide
policy mismatches, not evidence of a Slice 198/199 runtime defect.

## Decision

Do not suppress Flake8 findings, add legal notices, or alter the workflow until
the human selects the authoritative policy. The mechanical isort correction in
`d1faac3` is accepted as a behavior-preserving cleanup. The current release
status remains conditional because the checked-in CI quality contract has not
been demonstrated green.

## Options

| Option | Effect | Governance |
|---|---|---|
| Normalize all source to Flake8 and add notices | Makes current workflow authoritative | Broad source edit plus copyright/legal review |
| Update workflow to approved local tools/policy | Makes CI match the maintained style contract | Explicit CI and license/header-policy approval; no silent gate removal |
| Retain current policy | Leaves CI quality failures as blockers | No code/policy change; release remains blocked |

## Consequences

Until selected, developers have two different definitions of quality and a
release cannot honestly claim CI readiness. The gate is intentionally visible
so a future change can be reviewed for security, legal, and reproducibility
impact.

## Required follow-up evidence

The selected policy must update workflow contract tests, provide a clean-clone
run of the same commands, retain failing-on-findings behavior, and document
the decision in the release plan. No external release or website action is
part of this ADR.
