# QA + Security Report — MAPLE Agent Runtime Slice 201 @ b2f3809

**QA Engineer · Security Reviewer · Date:** 2026-08-29
**Build under test:** `b2f3809` (`feat/maple-agent-runtime`)

## Acceptance criteria verification

| # | Criterion | How executed | Evidence (real output) | Pass |
|---|-----------|--------------|------------------------|------|
| 1 | Successful mutations retain bounded, ascending history and return detached snapshots | `python -m pytest tests/autonomy/test_sessions.py -q --no-cov` | `============================= 18 passed in 0.61s ==============================` | yes |
| 2 | Forks copy the selected source data into an independent version-zero branch | Same focused session suite; `test_session_fork_copies_selected_version_without_sharing_state` | Included in `18 passed` | yes |
| 3 | Stale, evicted, missing, and existing fork cases fail without mutation | Same focused session suite; `test_session_fork_rejects_stale_existing_and_evicted_versions` | Included in `18 passed` | yes |
| 4 | File restart and legacy direct-snapshot compatibility work without inspection rewrite | Same focused session suite; legacy migration and resize tests | Included in `18 passed` | yes |
| 5 | Invalid bounds, malformed history, oversized records, and partial-write cases fail closed | Same focused session suite; limit, corruption, and byte-budget tests | Included in `18 passed` | yes |
| 6 | Public surface, docs, static checks, and regressions are covered | Full suite plus Ruff, Black, isort, mypy, compileall | `1805 passed, 1 skipped in 368.30s (0:06:08)`; `All checks passed!`; `Success: no issues found in 101 source files`; `compileall: ok` | yes |

## Adversarial & edge matrix

| Input/scenario | Expected | Observed | Pass |
|----------------|----------|----------|------|
| `limit=True`, `limit=3` with `max_history=2` | Typed history-limit error | `SESSION_HISTORY_LIMIT` | yes |
| `max_history=0` and `max_history=10001` | Constructor rejects configuration | `ValueError` identifying `max_history` | yes |
| Stale `expected_version` | No branch created; `SESSION_CONFLICT` | Verified by regression test | yes |
| Evicted `at_version` | No branch created; `SESSION_VERSION_UNAVAILABLE` | Verified by regression test | yes |
| Existing or missing source/target | Typed error and no mutation | `SESSION_EXISTS` / `SESSION_NOT_FOUND` | yes |
| Empty persisted history | Load and mutation fail closed; file unchanged | `SESSION_HISTORY_INVALID`; bytes unchanged | yes |
| Combined retained-history byte overflow | Mutation fails before state/file replacement | `SESSION_SIZE_EXCEEDED`; prior snapshot unchanged | yes |
| Mutable nested metadata/message data returned to caller | Store state remains isolated | Source and history unchanged after caller mutation | yes |
| File history larger than reopened store bound | Newest configured tail is available; successful mutation re-bounds | Versions `[2, 3]`, then `[3, 4]` | yes |

## Regression

Focused suite:

```text
============================= 18 passed in 0.61s ==============================
```

Full repository suite:

```text
================= 1805 passed, 1 skipped in 368.30s (0:06:08) =================
```

No retry or test weakening was used. The existing single skip is the optional
NATS integration test from the repository baseline.

## Bugs found

| # | Repro steps (minimal) | Severity | Fixed @ | Re-verified | Regression test |
|---|----------------------|----------|---------|-------------|-----------------|
| 1 | Initial implementation used the configured default `100` as the explicit history limit for a store configured with `max_history=2`; type narrowing also exposed four file-store diagnostics. | MINOR | `b2f3809` | Focused suite and whole-package mypy passed | bounded-history and file-store tests |
| 2 | Initial review found in-memory history did not apply the combined retained-history byte budget. | MAJOR | `b2f3809` | Focused suite passed with both store implementations | `test_session_history_size_limit_rejects_mutation_without_partial_state` |

## Security sweep

- Secrets scan: `gitleaks` unavailable; equivalent commit scan returned
  `equivalent-secret-scan: no matches in b2f3809`.
- Injection/path review: session and target IDs are charset-constrained before
  use; file paths are resolved and prefix-checked; writes use stdlib atomic
  temporary-file replacement; no SQL or shell input path was added.
- Deserialization/resource bounds: JSON-only parsing, bounded file size,
  message/metadata limits, hard `MAX_HISTORY=10000`, bounded history list, and
  detached copies are enforced before mutation. No `pickle`, `eval`, or
  `exec` was added.
- Dangerous-construct scan: `dangerous-construct-scan: no matches in
  sessions.py`.
- Dependency audit: `pip-audit . --progress-spinner off` returned
  `No known vulnerabilities found`. No dependency files changed in the
  implementation commit.
- `bandit` unavailable in this environment; no new dangerous construct was
  found by the equivalent scan.

**Security verdict:** SIGN-OFF for the bounded local scope; gitleaks and bandit
tool availability limitations are recorded above. No human override.
**QA verdict:** pass for Slice 201.

Fresh independent G4/G5 verifier sessions are unavailable in the current
environment; this report must not be read as independent verifier approval.
