# Code Review - MAPLE Agent Runtime Slice 7 @ bf1614b

**Reviewer role:** Code Reviewer  · **Date:** 2026-08-24
**Reviewed against:** [brief](../briefs/maple-agent-runtime-release.md),
[ADR-006](../adr/006-interop-and-doctor-contract.md), and
[implementation plan](../plans/maple-agent-runtime-release.md)

## Scope

This slice adds a strict versioned JSON interop envelope with round-trip helper,
the local `maple doctor --json` readiness command, quickstart documentation,
and regression tests for unknown fields, malformed payloads, and CLI readiness.

## Findings

| # | Sev | Location | Finding | Resolution |
|---|---|---|---|---|
| 1 | MINOR | Interop envelope | Direct mappings with non-string keys could cause sorting/type errors. | Parser now rejects non-string field names before unknown-field processing. |
| 2 | MINOR | Doctor report | A doctor report could be mistaken for a release audit. | CLI/docs explicitly state local-only scope and distinguish it from release gates. |

## Verification evidence

```text
ruff check maple/autonomy/interop.py tests/autonomy/test_interop.py tests/test_cli.py maple/cli.py --output-format concise
All checks passed!

python -m pytest tests/autonomy/test_interop.py tests/test_cli.py -q -o addopts=
5 passed, 1 warning in 0.04s

python -m pytest tests/llm tests/autonomy tests/test_cli.py -q -o addopts=
165 passed, 1 warning in 0.21s

python -m maple.cli doctor --json
{"checks":{"core":true,"evaluation":true,"events":true,"execution":true,"interop":true,"retrieval":true},"network":false,"ready":true,"status":"SUCCESS","version":"1.1.3"}

python -m compileall -q maple
exit code 0
```

The pytest warning is the existing `asyncio_mode` configuration warning when
plugin autoload is disabled. Existing aggregate Ruff debt in the package
initializers remains a separate release-hardening item.

## Verdict

- [x] Slice review pass: no open BLOCKER or MAJOR finding.
- [ ] Final release review: pending release hardening and independent
  fresh-context verifier availability.

The available environment has no separate fresh-agent session facility, so this
artifact records local review evidence and does not claim independent verifier
separation.
