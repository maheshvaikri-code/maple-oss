# Code Review — bounded durable agent-run history @ 44dcc52

**Reviewer role:** Code Reviewer · **Date:** 2026-08-28
**Reviewed against:** [release plan](../plans/maple-agent-runtime-release.md),
[ADR-103](../adr/103-bounded-durable-agent-run-history.md)
**Executed:**

```text
python -m pytest tests/autonomy/test_runs.py tests/autonomy/test_run_leases.py -q -o addopts=
42 passed in 0.50s

python -m pytest <tracked Python test files> -q -o addopts=
1466 passed, 1 skipped in 231.79s (0:03:51)

python -m mypy maple/ --ignore-missing-imports
Success: no issues found in 97 source files

python -m black --check maple/autonomy/runs.py tests/autonomy/test_runs.py
2 files would be left unchanged.

python -m ruff check maple/autonomy/runs.py tests/autonomy/test_runs.py
All checks passed!

smoke: restart FileAgentRunStore with max_history=2 after three saves using
the default max_history
False {'errorType': 'RUN_HISTORY_LOAD_ERROR', 'message': 'Failed to load agent run checkpoint history.', 'details': {'reason': 'invalid run history'}}
```

## Findings

| # | Sev | Location | Finding | Suggested fix | Resolution |
|---|-----|----------|---------|---------------|------------|
| 1 | [MAJOR] | `maple/autonomy/runs.py:608` | A file store configured with a smaller `max_history` cannot read a sidecar written by a store configured with a larger bound. This makes an ordinary retention-policy change fail closed with `invalid run history`, and it also blocks later saves. The behavior is reproduced above. | Treat the current `max_history` as the active retention window: accept a valid sidecar up to the global bounded history cap, return its newest current-window snapshots, and rewrite the trimmed sidecar on the next successful save. Add a restart regression covering a bound decrease (and, if retained, a typed policy-conflict alternative). | fixed@f0e09fc; regression `test_file_run_store_allows_a_smaller_history_bound_after_restart` |

## Scope check

The diff matches Slice 158: an additive optional history protocol, bounded
memory/file snapshots, detached reads, corruption validation, exports, tests,
and release documentation. No dependencies, network calls, replay, restore,
or website/publication behavior was added. The resolved finding was within the
declared configurable-retention contract.

## Re-review

The builder changed history reads to validate against the global bounded cap,
then apply the configured active window. The new regression covers reading and
saving after lowering the bound. The concrete probe now reports:

```text
True [2, 3]
```

The post-fix tracked manifest reports:

```text
1467 passed, 1 skipped in 223.55s (0:03:43)
```

## Verdict

- [x] Pass (0 BLOCKER, MAJORs resolved/waived)
- [ ] Return to build — findings above.

Independent fresh-session verification was not available in this tool context;
this report is the bounded G4 review and records the concrete failure instead
of treating the feature as clean.
