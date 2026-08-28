# QA + Security Report — bounded durable agent-run history @ f0e09fc

**QA Engineer** · **Security Reviewer** · **Date:** 2026-08-28
**Build under test:** exact commit `f0e09fc`

## Acceptance criteria verification

| # | Criterion | How executed | Evidence (real output) | Pass |
|---|-----------|--------------|------------------------|------|
| 1 | Optional history contract and bounded retention | Focused run-store tests plus constructor/limit probes | `43 passed in 0.46s`; `constructor_1=accepted`; `constructor_10000=accepted`; `constructor_0=ValueError`; `constructor_10001=ValueError`; limits `0/3/True` rejected and `1/2` accepted | Yes |
| 2 | Ordered, detached snapshots and CAS-failure exclusion | `tests/autonomy/test_runs.py` history regressions | In-memory and file histories retain the expected newest versions; mutable returned results do not alter stored snapshots; failed CAS does not append history | Yes |
| 3 | File restart persistence and retention resize | File-store tests and installed clean-archive smoke | `True [2, 3]` for the resize probe; `clean_archive_run_history_smoke=passed` after wheel installation; `sdist_entries=659` | Yes |
| 4 | Fail-closed malformed/corrupt history behavior | Corrupt sidecar regression and invalid-ID probe | `RUN_HISTORY_LOAD_ERROR` on inspection and before save; `invalid_id=RUN_IDENTIFIER_INVALID` | Yes |
| 5 | Repository regression and release checks | Tracked test manifest, mypy, formatting/lint/compile, package archive | `1467 passed, 1 skipped in 223.55s (0:03:43)`; mypy success on 97 files; Black unchanged; Ruff clean; wheel `104` entries; wheel/sdist untracked workspace entries `0`; Twine checks passed | Yes |

## Adversarial & edge matrix

| Input/scenario | Expected | Observed | Pass |
|----------------|----------|----------|------|
| Missing run | Empty successful history | `missing=[]` | Yes |
| Retention `0`, `1`, `10000`, `10001` | Reject outside `1..10000`; accept endpoints | `constructor_0=ValueError`, `constructor_1=accepted`, `constructor_10000=accepted`, `constructor_10001=ValueError` | Yes |
| Read limits `0`, `1`, `2`, `3`, `True` with bound `2` | Reject invalid/boolean; accept in-range | `[(0, False), (1, True), (2, True), (3, False), (True, False)]` | Yes |
| Unicode payload | Preserve JSON-safe data | `unicode_save=True` | Yes |
| Invalid identifier | Typed boundary error | `invalid_id=RUN_IDENTIFIER_INVALID` | Yes |
| CAS conflict | No snapshot for rejected save | Focused regression reports `RUN_CHECKPOINT_CONFLICT`; retained versions remain `[2, 3]` | Yes |
| Corrupt JSON sidecar | Fail closed; do not mutate current checkpoint | `RUN_HISTORY_LOAD_ERROR`; current result remained version 1 | Yes |
| Restart with smaller bound | Read active newest window and allow later save | `True [2, 3]`; regression covers rewrite to `[3, 4]` | Yes |
| Mutable returned snapshot | Store remains unchanged | Regression confirms stored version remains `2` after caller mutation | Yes |
| Concurrent/cross-process fencing | Preserve existing run-store lease boundary | `tests/autonomy/test_run_leases.py` included in focused run suite; no new lease bypass added | Yes |
| Interrupted/partial sidecar write | Atomic replacement; stale temp cleaned | File sidecar uses fsync + `os.replace`; package/restart smoke passed | Yes |

## Regression

Suite:

```text
python -m pytest tests/autonomy/test_runs.py tests/autonomy/test_run_leases.py -q -o addopts=
43 passed in 0.46s

python -m pytest <tracked Python test files> -q -o addopts=
1467 passed, 1 skipped in 223.55s (0:03:43)
```

Flakes: none observed.

## Bugs found

| # | Repro steps (minimal) | Severity | Fixed @ | Re-verified | Regression test |
|---|----------------------|----------|---------|-------------|-----------------|
| 1 | Write three snapshots with the default file-store bound, restart with `max_history=2`, call `history()` | Major | `f0e09fc` | Probe returned `True [2, 3]`; full manifest passed | `test_file_run_store_allows_a_smaller_history_bound_after_restart` |

## Security sweep

- Secrets scan: `targeted_changed_source_secret_scan=clean`.
- Dangerous constructs: `changed_surface_dangerous_construct_scan=clean`.
- Bounds/fail-closed: checkpoint count, sidecar size, JSON parsing, identity,
  ordering, invalid limits, and CAS failure paths are covered above.
- Dependency change: none; implementation uses the standard library and the
  existing `AgentRunStore` boundary.
- Dependency audit: `python -m pip_audit` exited 1 with
  `Found 384 known vulnerabilities in 77 packages`; local non-PyPI packages
  were listed as skipped. This is the existing environment-wide governance
  veto and is not attributable to this slice.
- Bandit: unavailable in the environment; real output was
  `No module named bandit`.

**Security verdict:** **VETO** for publish readiness because the environment-
wide dependency audit remains unresolved and Bandit is unavailable; no
slice-specific secret or dangerous-construct finding was observed.

**QA verdict:** pass for Slice 158 on exact commit `f0e09fc`. Publication,
website changes, cloud actions, and external registry writes were not performed.
