# QA + Security Report - MAPLE agent runtime slice 27 @ `6499244`

**QA Engineer** · **Security Reviewer** · **Date:** 2026-08-25  
**Build under test:** commit `6499244` (`ci: fail closed on quality and security checks`)

## Acceptance criteria verification

| # | Criterion | How executed | Evidence | Pass |
|---|-----------|--------------|----------|------|
| 1 | Required CI and quality checks are not configured to pass after failure. | Inspected workflow text through the new contract checks. | `CI_CONTRACTS_OK`; no `continue-on-error: true` in `ci.yml` or `quality.yml`. | PASS |
| 2 | Dependency and security audits return their real status. | Inspected workflow commands and executed the contract checks. | No `pip-audit || true` or Bandit masking; report commands retain explicit exit propagation. | PASS |
| 3 | Security reports remain available after a failing scan. | Parsed the security workflow and inspected upload conditions. | `Upload security reports` retains `if: always()` and both report paths. | PASS |
| 4 | Read-only workflows do not request write permissions. | Parsed and checked CI, quality, and dependency workflows. | `YAML_PARSE_OK`; `contents: read` present and dependency write permissions absent. | PASS |
| 5 | Changed repository test/tool surface remains clean. | Ran Ruff, compilation, and diff checks. | `All checks passed!`; `COMPILE_EXIT=0`; `DIFFCHECK_EXIT=0`. | PASS |

## Regression boundary

The new workflow contract functions were invoked directly and passed. A
complete repository behavioral regression is not claimed: the prior bounded
run stopped before its final summary, and the independent fresh-context
verifier is unavailable in this tool environment.

The fail-closed workflow change intentionally makes the following existing
conditions release-visible: Black and isort formatting drift, 459 mypy errors
across 66 files, and unavailable local Bandit execution. These must be
resolved or explicitly dispositioned before publication.

## Security sweep

- **Secret exposure:** no secrets or credentials were added.
- **Workflow permissions:** CI, quality, and dependency workflows are
  contents-read only; the existing security workflow retains its explicit
  security-events permission for scanning.
- **Failure masking:** removed `continue-on-error` from required checks and
  `|| true` from dependency/security audits. Informational outdated-package
  inventory remains non-gating by design.
- **Action supply chain:** actions remain tag-pinned (`@v4`/`@v5`) rather than
  immutable commit-SHA pinned; this remains an open hardening item.
- **Dependency audit:** the hosted pip-audit gate is now strict; a local
  dependency-audit disposition is still open.

## Verdict

**QA verdict:** pass for the workflow semantics slice.  
**Security verdict:** pass for the changed workflow behavior, with immutable
action pinning and the pre-existing audit/tooling debt open.  
**Publication verdict:** not cleared.
