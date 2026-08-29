# Slice 200 brief — CI quality gate reconciliation

**Date:** 2026-08-29  
**Class:** L (repository-wide CI and release policy)  
**Role:** DevOps Engineer

## Problem

The repository's local quality gates and GitHub Actions quality workflows do
not currently agree. Black passes on all `101` MAPLE source files, and the
full isort gate passes after the mechanical import fix in `d1faac3`, but the
workflow's Flake8 invocation reports `608` existing `E501` line-length
findings. The workflow's author-header check also reports `19` MAPLE modules
without the exact author notice it requires. A green local Ruff/mypy suite is
therefore not evidence that the current CI quality job can pass.

## Scope

- In: reproduce the workflow checks, preserve the mechanical import fix, and
  define one authoritative local/CI quality contract.
- Out: silently ignoring a failing quality rule, adding or changing copyright
  notices, changing the project license, adding dependencies, publishing, or
  changing the website.
- Deferred: workflow/source edits until the policy and legal choice below is
  explicitly approved.

## Evidence

```text
python -m black --check --diff maple/
101 files would be left unchanged.

python -m isort --check-only --diff maple/
exit 0 after d1faac3

python -m flake8 maple/ --max-line-length=88 --extend-ignore=E203,W503,W291,W293,E302,E402,F401,F811,F841 --count --statistics
608   E501 line too long (93 > 88 characters)
608

workflow-equivalent author check
license_missing=19

python -m pytest tests/test_ci_workflows.py tests/test_release_workflows.py -q --no-cov
8 passed in 0.30s
```

## Decision required

Choose one policy, then implement and test it in a follow-up slice:

1. **Normalize source to the existing workflow:** fix all Flake8 line-length
   findings and add the existing project-author notice to the 19 modules. This
   changes many files and adds legal/copyright text, so it requires explicit
   human authority.
2. **Authorize a tool-policy update:** make the workflow use the repository's
   accepted Black/isort/mypy/Ruff-style contract, define treatment of long
   strings and generated/header text, and replace or narrow the exact author
   substring check with an approved license/header rule. This changes CI and
   licensing policy and requires explicit human authority.
3. **Keep the current workflow policy:** treat the `608` Flake8 findings and
   `19` missing notices as release blockers and do not claim CI-ready status.

## Acceptance criteria after a decision

- A clean clone runs the same formatter, import sorter, lint, type, security,
  test, and package gates locally and in CI.
- No quality check is hidden with `continue-on-error`, a blanket suppression,
  or an undocumented exception.
- If source headers change, the legal wording and affected file set are
  reviewed and documented.
- Workflow contract tests cover the selected policy and the release checklist
  records real green output.

**Current status:** gated pending human choice. No workflow policy was changed
by this slice.
