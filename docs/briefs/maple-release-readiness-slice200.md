# Slice 200 brief - CI quality gate reconciliation

**Date:** 2026-08-29
**Class:** L (repository-wide CI and release policy)
**Role:** DevOps Engineer

## Problem

The repository's local quality gates and GitHub Actions quality workflows did
not initially agree. The workflow-equivalent Flake8 invocation reported `610`
`E501` line-length findings, and the author-header check reported `20` MAPLE
modules without the exact author notice it requires.

## Scope

- In: reproduce the workflow checks and normalize the MAPLE source tree to the
  existing CI quality contract.
- Out: silently ignoring a failing quality rule, changing the project license,
  adding dependencies, publishing, or changing the website.
- Deferred: external publication, cloud actions, registry writes, and website
  deployment remain separately gated.

## Decision

Human approval on 2026-08-29 selected Option 1: normalize source to the
existing workflow. The existing AGPL notice was reformatted to fit the
configured 88-column limit; the license itself was not changed.

## Evidence

```text
python -m black maple --check --quiet
exit 0

python -m isort maple --check-only --diff
exit 0

python -m flake8 maple/ --max-line-length=88 --extend-ignore=E203,W503,W291,W293,E302,E402,F401,F811,F841 --count --statistics
0

workflow-equivalent author check
license_missing=0

python -m compileall -q maple
exit 0
```

The strict workflow remains unchanged. All `103` `maple/**/*.py` modules now
contain the required author notice. Protocol stubs were expanded to multiline
bodies so the full configured Flake8 invocation is also clean, with no blanket
suppression.

## Acceptance criteria

- A clean clone runs the same formatter, import sorter, lint, type, security,
  test, and package gates locally and in CI.
- No quality check is hidden with `continue-on-error`, a blanket suppression, or
  an undocumented exception.
- The legal wording and affected source file set are documented.
- Workflow contract tests and the release checklist retain real green output.

**Current status:** implemented. Release validation continues under MAPLE
2.0.0; external publication, cloud, registry, and website actions remain
separate gates.
