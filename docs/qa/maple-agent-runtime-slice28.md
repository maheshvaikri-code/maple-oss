# QA + Security Report - MAPLE agent runtime slice 28 @ `76b619a`

**QA Engineer** · **Security Reviewer** · **Date:** 2026-08-25  
**Build under test:** commit `76b619a` (`chore(quality): normalize repository formatting`)

## Acceptance criteria verification

| # | Criterion | How executed | Evidence | Pass |
|---|-----------|--------------|----------|------|
| 1 | Black formatting is deterministic and clean. | Ran the configured Black API idempotence scan and check mode. | `BLACK_NEEDS_FORMAT=0`, `BLACK_PARSE_FAILURES=0`, `BLACK_CHECK=0`. | PASS |
| 2 | isort is deterministic and clean. | Ran configured isort check mode. | `ISORT_CHECK=0`. | PASS |
| 3 | Source remains syntactically valid. | Ran compileall over `maple/`. | `COMPILE_CHECK=0`. | PASS |
| 4 | Runtime behavior remains green on the maintained feature surface. | Ran LLM, autonomy, and CLI focused suites. | `240 passed in 3.23s`. | PASS |
| 5 | Release artifacts remain buildable and metadata-valid. | Built wheel and sdist, then ran Twine validation. | Both artifacts built; both Twine checks `PASSED`. | PASS |

## Regression boundary

The full `tests/` run reached 86% with no reported assertion failure before a
manual interrupt in the historically slow Doctrine-gold tail. Exit code 1 is
therefore an intentional interruption, not a passing result. The full suite
must still complete before publication clearance.

## Security sweep

- No secrets, credentials, dependencies, subprocesses, or trust boundaries
  changed.
- Formatting changes were applied by Black and isort only; no `--unsafe-fixes`
  or behavior-oriented lint rewrites were used.
- The full-tree Ruff audit remains at 338 legacy findings, mypy remains at 459
  errors across 66 files, and Bandit is not installed locally. These are
  visible strict-gate blockers, not waived findings.
- The fail-closed pip-audit workflow remains unchanged by this slice; its
  disposition is still open.

## Verdict

**QA verdict:** pass for formatter-only behavior and artifact checks; full
repository verification remains incomplete.  
**Security verdict:** no new risk in this slice; existing strict-gate debt
remains open.  
**Publication verdict:** not cleared.
