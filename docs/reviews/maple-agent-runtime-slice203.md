# Code Review — Slice 203 native run-ID validation

**Reviewer role:** Code Reviewer · **Date:** 2026-08-29
**Reviewed commits:** `742661a`, `d7834d1`
**Design:** [Slice 203 brief](../briefs/maple-agent-runtime-slice203.md),
[ADR-147](../adr/147-native-run-id-validation.md), and
[Slice 203 plan](../plans/maple-agent-runtime-slice203.md)

## Review limitation

The repository requires fresh independent verifier sessions, but this
environment cannot create them. This is a same-context review and is not
represented as independent approval.

## Executed evidence

```text
focused native regressions: 3 passed in 0.53s
workflow/run suites: 77 passed in 0.67s
full dirty workspace: 1810 passed, 1 skipped in 362.28s (0:06:02)
Black: 101 files would be left unchanged.
isort: exit 0
Ruff: All checks passed!
mypy: Success: no issues found in 101 source files
compileall: ok
pip-audit --strict: No known vulnerabilities found
equivalent-secret-scan: no high-confidence token matches in HEAD
dangerous-construct-scan: no matches in changed runtime modules
```

## Findings

| # | Severity | Finding | Resolution |
|---|---|---|---|
| — | — | Truthiness fallback silently converted explicit empty native run IDs into generated IDs. | Fixed by using `None` as the only generation sentinel in `Workflow.run` and durable agent starts; regressions cover sync, async, and workflow paths. |
| — | — | Adjacent server fallbacks were audited. | Unchanged because request normalization already rejects explicit empty values; transport remains outside this bounded slice. |

## Scope and safety

No signature, route, scope, dependency, storage format, provider, tool, or
execution contract changed. Invalid native IDs fail before checkpoint creation,
provider work, session preparation, and tool execution. No new subprocess,
network call, credential, or external service was introduced.

Bandit, Gitleaks, and fresh independent verifier sessions were unavailable in
this environment and are not claimed as passed.

## Verdict

Pass for this same-context review: 0 blocker, major, minor, or nit findings.
Independent verifier approval remains unavailable by environment constraint.
