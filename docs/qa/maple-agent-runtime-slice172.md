# QA + Security Report - opt-in remote handoff invocation idempotency

**QA Engineer** / **Security Reviewer** / **Date:** 2026-08-28
**Code candidate:** `21c4f2a` plus final QA/release closure
**Design baseline:** [ADR-117](../adr/117-remote-handoff-idempotency-binding.md)

## Acceptance criteria verification

| # | Criterion | Evidence | Pass |
|---|---|---|---|
| 1 | Default adapter compatibility | Regression uses a `RunClient` whose stub does not accept an idempotency keyword; default invocation succeeds with the legacy argument shape | Yes |
| 2 | Opt-in key/run binding | Regression verifies an explicit handoff ID is passed as both `run_id` and `idempotency_key` | Yes |
| 3 | Fail closed without a handoff ID | Regression verifies `REMOTE_HANDOFF_INPUT_INVALID` and zero client calls when the option is enabled without an ID | Yes |
| 4 | Receiver replay and handler suppression | Real authenticated `RunServer` + `InMemoryAgentInvocationDeduplicationStore` test runs sync then async with one handler call and two matching results | Yes |
| 5 | Sync/async shared behavior | Async adapter delegates through the same `_invoke` implementation; focused sync/async regression and existing server suite pass | Yes |
| 6 | Public contract and release gates | API/README/parity/changelog/release artifacts are filed; full regression and clean archive build, Twine, isolated install, and import pass below | Yes |

## Regression evidence

```text
python -m pytest tests/autonomy/test_remote_handoff_idempotency.py tests/autonomy/test_server.py -q --no-cov
54 passed in 21.77s

python -m pytest -q --no-cov
1674 passed, 1 skipped in 262.74s
```

The full run collected 1,675 tests. The single skip is pre-existing
test-environment coverage; no test was deleted, skipped, weakened, or retried
to obtain this result.

## Static and security gates

```text
black_exit=0
isort_exit=0
ruff_exit=0
mypy_exit=0
compile_exit=0
slice172_secret_scan=passed
slice172_danger_scan=passed
```

`gitleaks` and Bandit are unavailable in this environment. No runtime
dependency was added. The established environment-wide
`python -m pip_audit --local` result of `384 known vulnerabilities in 77
packages` remains a separate pre-existing release-governance veto; this slice
does not change the declared MAPLE dependency set.

## Package gate

The clean committed archive gate produced the following real output:

```text
source_archive_entries=815
Successfully built maple_oss-1.1.3-py3-none-any.whl and maple_oss-1.1.3.tar.gz
build_exit=0
wheel_entries=106
sdist_entries=729
maple_oss-1.1.3-py3-none-any.whl: PASSED
maple_oss-1.1.3.tar.gz: PASSED
twine_exit=0
Successfully installed maple-oss-1.1.3
install_exit=0
isolated_import=passed
version=1.1.3
import_exit=0
```

The package was built from a `git archive HEAD` extraction and no worktree-only
files were included. No publication or upload is authorized by this report.

## Security verdict

Pass for Slice-172-specific behavior under the explicit opt-in boundary. The
adapter validates identity before HTTP, leaves default behavior unchanged,
relies on receiver authentication/scope checks, and forwards no raw error
details. It does not claim distributed coordination, automatic retry, caller
identity binding, or exactly-once external effects.
