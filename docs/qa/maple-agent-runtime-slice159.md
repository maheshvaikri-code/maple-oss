# MAPLE agent-runtime slice 159 QA record

**Commit:** `da72c54`

## Behavioral validation

The focused server and run-store suite passed:

```text
77 passed in 15.97s
```

The exact tracked repository manifest passed:

```text
1470 passed, 1 skipped in 206.15s (0:03:26)
```

The added regressions cover:

- bounded newest-history selection and ascending versions;
- metadata-only redaction of descriptions, results, errors, messages, and
  reasoning steps;
- bearer authentication, `agent:read` principal scope, and cross-agent
  ownership masking;
- invalid, unknown, and duplicate history query parameters;
- legacy stores without the optional history capability; and
- fail-closed cross-agent records returned by a malformed history provider.

## Static and security validation

```text
Black (changed files): 2 files would be left unchanged.
Ruff (changed files): All checks passed!
isort (changed files): exit 0, no output.
mypy server (follow-imports=skip): Success: no issues found in 1 source file.
compileall (maple tests): exit 0.
Targeted secret scan: exit 0, no matches.
Targeted dangerous-construct scan: exit 0, no matches.
```

Repository-wide baseline checks remain non-green for reasons outside this
slice:

- Black reports 55 existing files that would be reformatted.
- isort reports existing import-order issues across the repository.
- normal whole-package mypy reports 11 missing/untyped optional-dependency
  imports in 7 untouched files.
- Bandit is not installed (`No module named bandit`).
- `python -m pip_audit` exits 1 with `Found 384 known vulnerabilities in 77
  packages`; this is the existing environment-wide governance veto, not a new
  dependency introduced by this slice.

## QA disposition

**Behavioral QA pass.** Package and archive verification remain required before
calling a release tip publish-ready. No publication, cloud, or website action
was performed.
