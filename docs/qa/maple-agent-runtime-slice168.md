# QA + Security Report - typed remote agent-run lifecycle

**QA Engineer** / **Security Reviewer** / **Date:** 2026-08-28
**Code candidate:** `77b2d2b` (`docs(transport): document typed remote lifecycle`)
**Design baseline:** `bfbeef8`
**Implementation baseline:** `2726fab`

## Acceptance criteria verification

| # | Criterion | Evidence (real output) | Pass |
|---|---|---|---|
| 1 | Typed start returns a validated `AgentRun` for supported lifecycle statuses | New typed lifecycle regression covers paused and completed runs; full server/tool suite passed `85` tests | Yes |
| 2 | Typed resume and cancel use existing authenticated routes and return typed runs | New regression covers typed resume and cancellation; cancel requires `cancelled` status | Yes |
| 3 | Malformed and mismatched envelopes fail closed without raw remote details | New regression covers missing fields, identity mismatch, private result suppression, and invalid cancel status | Yes |
| 4 | Existing raw methods and remote handoff behavior remain compatible | Existing server/tool suite passed `85 passed in 19.78s`; no raw method or wire-shape change was made | Yes |
| 5 | Public contract and parity/release records are synchronized | README, API reference, parity ledger, changelog, brief, ADR, slice plan, review, QA, and release plan are filed | Yes |
| 6 | Regression, static, security, and package gates pass | Tracked suite, Ruff, compile, Black, isort, mypy, targeted scans, clean archive, Twine, isolated install/import all pass | Yes |

## Regression

```text
python -m pytest tests/autonomy/test_server.py -k "typed_remote_agent_methods or authenticated_agent_transport_round_trips_bounded_host_handler or authenticated_durable_agent_run_inspection_and_resume" -q --no-cov
4 passed, 43 deselected in 1.34s

python -m pytest tests/autonomy/test_tools.py tests/autonomy/test_server.py -q --no-cov
85 passed in 19.78s

python -m pytest <tracked Python test files> -q --no-cov
1523 passed, 1 skipped in 224.57s
```

No flaky behavior was observed.

## Static and security gates

```text
python -m ruff check maple tests
All checks passed!

python -m compileall -q maple tests
compile_exit=0

python -m black --check maple/autonomy/server.py tests/autonomy/test_server.py
2 files would be left unchanged.

python -m isort --check-only maple/autonomy/server.py tests/autonomy/test_server.py
isort_exit=0

python -m mypy --follow-imports=skip maple/autonomy/server.py
Success: no issues found in 1 source file

slice168_secret_scan=passed
slice168_danger_scan=passed
```

- The new normalizer validates identity, supported status, JSON-safe result and
  error values, and uses generic errors for malformed remote responses.
- No dependency was added. `gitleaks` is unavailable in this environment.
- Bandit is unavailable: `No module named bandit`.
- `python -m pip_audit --local` reports `384 known vulnerabilities in 77
  packages` and exits `1`; this is the established environment-wide,
  pre-existing dependency-governance veto, not a Slice-168 dependency change.

**Security verdict:** Pass for Slice-168-specific findings. Publication
remains vetoed by the pre-existing dependency-audit/tooling governance
condition and the open fresh-session verifier requirement.

## Package gate

The package was built from a file-backed clean archive of committed HEAD
`77b2d2b5b147a26042d5fd5da7f659a56f43ab52`; untracked workspace files were
excluded.

```text
source_archive_entries=726
build_exit=0
twine_exit=0
wheel_entries=103
sdist_entries=701
install_exit=0
isolated_import=passed
version=1.1.3
```

## Release disposition

Slice 168 is ready for staged release review. The dependency-governance veto
and fresh-session verifier follow-up still prevent publication authorization.
No publication, deployment, cloud action, registry write, or website update
was performed.
