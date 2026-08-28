# Implementation Plan — MAPLE release-readiness slice 174

**Brief:** [slice 174 brief](../briefs/maple-release-readiness-slice174.md) ·
**Design/ADRs:** [ADR-119](../adr/119-pin-github-actions.md) · **Class:** M

## Slices

| # | Slice | Role | Files touched | Proven by | Status |
|---|---|---|---|---|---|
| 1 | Pin checkout, Python, artifact, Codecov, and PyPI actions to verified SHAs | DevOps Engineer | `.github/workflows/*.yml` | workflow pin test + YAML parse | done — 4f145b8 |
| 2 | Record review and QA evidence | Code Reviewer / QA Engineer | `docs/reviews/`, `docs/qa/` | focused tests + full suite | done — evidence below |

## Threat sketch

Assets touched: CI execution and release artifact provenance. Entry points:
workflow action resolution on pull requests, pushes, schedules, and tags.
Worst plausible abuse: upstream tag movement causes an unreviewed action
commit to execute with repository contents or release credentials.

## Risks & rollback points

- Risk: a copied SHA is invalid or belongs to the wrong tag → mitigation: keep
  the upstream release comment and verify each selected ref → rollback: revert
  only the pin commit before the next workflow run.
- Risk: action input behavior changes at the selected patch release →
  mitigation: retain the prior major behavior and run YAML/static checks →
  rollback: pin the previously verified compatible commit.

## Status snapshot

Done (with evidence): all `37/37` workflow action references are full SHAs,
the focused/YAML checks pass, and the clean archive suite is green. · Next:
continue the remaining product parity backlog. · Blocked on: none for local
work; publication and cloud actions remain out of scope.
