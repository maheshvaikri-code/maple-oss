# QA + Security Report - authenticated remote handoff payload delivery

**QA Engineer** / **Security Reviewer** / **Date:** 2026-08-28
**Code candidate:** `fa16c9f` (`style(autonomy): format remote handoff target`)
**Design baseline:** `599a9f8`
**Implementation baseline:** `aa27498`
**Documentation baseline:** `73af546`

## Acceptance criteria verification

| # | Criterion | Evidence (real output) | Pass |
|---|---|---|---|
| 1 | Validate the target agent, session, and optional handoff identifiers | Focused server/tool tests cover valid values, empty/oversized values, and control-character rejection | Yes |
| 2 | Forward bounded task/context through the authenticated agent route | Focused server/tool suite: `83 passed in 19.39s`; requests use `RunClient.run_agent(...)` and the existing authenticated route | Yes |
| 3 | Bind an explicit local `handoff_id` to the remote `run_id` | Handoff integration tests assert the remote request receives the local ID and the returned result preserves the correlation | Yes |
| 4 | Preserve local pending/accepted/completed and failure semantics | Tool tests cover local state transitions, remote incomplete/error results, generic failure mapping, and no raw remote detail leakage | Yes |
| 5 | Support synchronous and asynchronous callers | Sync and executor-backed async target tests pass in the focused suite | Yes |
| 6 | Preserve legacy local target compatibility and public exports | Existing local-target tests remain green; `maple` and `maple.autonomy` export checks pass in the tracked suite and package smoke | Yes |
| 7 | Keep unsupported distributed guarantees excluded | Brief, ADR, README, API reference, parity ledger, changelog, review, and release plan explicitly exclude retries, remote restore, scheduling, push, and exactly-once effects | Yes |

## Regression

```text
python -m pytest tests/autonomy/test_tools.py tests/autonomy/test_server.py -q --no-cov
83 passed in 19.39s

python -m pytest <tracked Python test files> -q --no-cov
1521 passed, 1 skipped in 207.92s
```

No flaky behavior was observed.

## Static and security gates

```text
python -m ruff check maple tests
All checks passed!

python -m compileall -q maple tests
exit 0

python -m black --check <Slice-167 changed files>
6 files would be left unchanged.

python -m isort --check-only <Slice-167 changed files>
exit 0

python -m mypy --follow-imports=skip maple/autonomy/server.py maple/autonomy/tools.py maple/autonomy/__init__.py maple/__init__.py
Success: no issues found in 4 source files

slice167_secret_scan=passed
```

- The adapter reuses the existing authenticated client and transport bounds,
  validates control-free identifiers, requires a completed remote run, and
  maps remote failures to generic typed errors.
- No dependency was added. `gitleaks` is unavailable in this environment.
- Bandit is unavailable: `No module named bandit`.
- `python -m pip_audit --local` reports `384 known vulnerabilities in 77
  packages` and exits `1`; this is the established environment-wide,
  pre-existing dependency-governance veto, not a Slice-167 dependency change.

**Security verdict:** Pass for Slice-167-specific findings. Publication
remains vetoed by the pre-existing dependency-audit/tooling governance
condition and the open fresh-session verifier requirement.

## Package gate

The package was built from a file-backed clean archive of committed HEAD
`fa16c9f25c5cf87053cbc3942f3568aab522753e`; untracked workspace files were
excluded.

```text
source_archive_entries=721
build_exit=0
twine_exit=0
wheel_entries=103
sdist_entries=696
install_exit=0
isolated_import=passed
version=1.1.3
```

## Release disposition

Slice 167 is ready for staged release review. The dependency-governance veto
and fresh-session verifier follow-up still prevent publication authorization.
No publication, deployment, cloud action, registry write, or website update
was performed.
