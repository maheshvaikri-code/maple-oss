# QA + Security Report - native autonomous-agent remote transport adapter

**QA Engineer** / **Security Reviewer** / **Date:** 2026-08-28
**Code candidate:** `abf02d6` (`docs(qa): close native agent transport slice`)
**Design baseline:** `c94328e`
**Implementation baseline:** `e1812f6`

## Acceptance criteria verification

| # | Criterion | Evidence (real output) | Pass |
|---|---|---|---|
| 1 | Validate and bind a native agent plus caller-owned run store | `test_native_agent_remote_adapter_binds_store_and_registers_start_and_resume` passes; invalid dependency and identity cases also pass | Yes |
| 2 | Delegate authenticated remote start to native `pursue_goal_with_context` | Authenticated RunServer/RunClient integration passes; task, context, session, and run identity are asserted | Yes |
| 3 | Delegate authenticated remote resume to native `resume_run` | Typed authenticated resume integration passes and preserves the remote run ID | Yes |
| 4 | Sanitize native errors and reject invalid goal state | Error, exception-boundary, run-identity, and unsupported-status regressions pass without private details | Yes |
| 5 | Preserve existing transport and explicit cancellation boundaries | Existing server/tools behavior remains green; cancellation is installed only from an explicit callback | Yes |
| 6 | Synchronize public API and release artifacts | Package exports, README, API reference, parity ledger, changelog, brief, ADR, plans, review, and QA report are filed | Yes |
| 7 | Pass repository regression and release gates | Tracked suite, static/security checks, clean archive, Twine, isolated install/import all pass | Yes |

## Regression

```text
python -m pytest tests/autonomy/test_agent_transport.py -q --no-cov
5 passed in 0.76s

python -m pytest tests/autonomy/test_agent_transport.py tests/autonomy/test_server.py tests/autonomy/test_tools.py -q --no-cov
90 passed in 20.12s

python -m pytest <tracked Python test files> -q --no-cov
1528 passed, 1 skipped in 215.55s
```

The full tracked run collected `1529` tests and completed without failures.
No flaky behavior was observed.

## Static and security gates

```text
python -m ruff check maple tests
All checks passed!

python -m compileall -q maple tests
compile_exit=0

python -m black --check maple/autonomy/agent_transport.py tests/autonomy/test_agent_transport.py maple/autonomy/server.py tests/autonomy/test_server.py
4 files would be left unchanged.

python -m isort --check-only maple/autonomy/agent_transport.py tests/autonomy/test_agent_transport.py maple/autonomy/server.py tests/autonomy/test_server.py
isort_exit=0

python -m mypy --follow-imports=skip maple/autonomy/agent_transport.py maple/autonomy/server.py maple/autonomy/__init__.py maple/__init__.py
Success: no issues found in 4 source files

slice169_secret_scan=passed
slice169_danger_scan=passed
```

- The adapter uses the existing bounded run normalizer after converting native
  goals and maps callback failures to generic `AGENT_RUNTIME_ERROR` values.
- No dependency was added. `gitleaks` is unavailable in this environment.
- Bandit is unavailable: `No module named bandit`.
- `python -m pip_audit --local` reports `384 known vulnerabilities in 77
  packages` and exits `1`; this is the established environment-wide,
  pre-existing dependency-governance veto, not a Slice-169 dependency change.

**Security verdict:** Pass for Slice-169-specific findings. Publication
remains vetoed by the pre-existing dependency-audit/tooling governance
condition and the open fresh-session verifier requirement.

## Package gate

The final package was built from a file-backed clean archive of committed HEAD
`abf02d69c3e64ed2113b2b220c6ee7008885768f`; untracked workspace files were
excluded.

```text
source_archive_entries=733
build_exit=0
twine_exit=0
wheel_entries=104
sdist_entries=708
install_exit=0
isolated_import=passed
version=1.1.3
```

## Release disposition

Slice 169 is ready for staged release review. The dependency-governance veto
and fresh-session verifier follow-up still prevent publication authorization.
No publication, deployment, cloud action, registry write, or website update
was performed.
