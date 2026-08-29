# QA + Security Report — Slice 203 native run-ID validation

**QA Engineer · Security Reviewer · Date:** 2026-08-29  
**Build under test:** `d7834d1` (`742661a` implementation)

## Acceptance criteria

| Criterion | Evidence | Pass |
|---|---|---|
| Omitted IDs retain generated-ID behavior | Existing workflow and durable-agent generated-ID coverage | yes |
| Explicit empty workflow IDs fail closed | `test_explicit_empty_run_id_is_rejected_without_creating_a_checkpoint` | yes |
| Sync and async durable agents reject explicit empty IDs | Two Slice 203 agent regressions; provider response remains unconsumed and no checkpoint is created | yes |
| Existing behavior remains green | Dirty suite `1810 passed, 1 skipped in 362.28s`; clean tracked suite `1693 passed, 1 skipped in 252.06s` | yes |
| Static/type/compile/security gates | Black, isort, Ruff, mypy, compileall, strict pip-audit, token-pattern scan, and changed-module dangerous-construct scan | yes |
| Exact package remains installable | Clean archive build/Twine/install/import/doctor smoke | yes |

## Security and failure-path checks

The only behavioral change is ID resolution: `None` generates, while supplied
values reach the existing validator/store boundary. Explicit invalid IDs do not
consume provider responses, create checkpoints, prepare sessions, or execute
tools. The agent retains its stable `RUN_STORE_ERROR` envelope and only exposes
the bounded validator cause.

No dependency, subprocess, network call, credential, or external service was
introduced. Strict dependency audit reported `No known vulnerabilities found`.
Bandit and Gitleaks were unavailable; no result is claimed for either tool.

## Regression output

```text
python -m pytest tests/autonomy/test_workflow.py::test_explicit_empty_run_id_is_rejected_without_creating_a_checkpoint tests/autonomy/test_runs.py::test_sync_agent_rejects_explicit_empty_run_id_before_provider_or_checkpoint tests/autonomy/test_runs.py::test_async_agent_rejects_explicit_empty_run_id_before_provider_or_checkpoint -q --no-cov
3 passed in 0.53s

python -m pytest tests/autonomy/test_workflow.py tests/autonomy/test_runs.py -q --no-cov
77 passed in 0.67s
```

## Clean package smoke

The exact committed tracked archive passed its clean suite and package smoke:

```text
source_archive_entries=886
clean_suite=1693 passed, 1 skipped in 252.06s
wheel_entries=108
sdist_entries=862
sdist_bytes=1372751
wheel_sha256=C5BCFDDCBEC5A3DDEC1F341FF018CFDC659AF41BEABAF8A69A575E80C3D782A9
sdist_sha256=21570E58DCFF7EC77E0745FB743A82949D791256BA93B7734359682CFA90E3BE
build_exit=0
twine_exit=0
install_exit=0
import_exit=0
doctor_exit=0
import_ok 1.1.3 True True
{"checks": {"core": true, "evaluation": true, "events": true, "execution": true, "interop": true, "retrieval": true, "server": true, "sessions": true}, "network": false, "ready": true, "status": "SUCCESS", "version": "1.1.3"}
```

The first archive attempt used a PowerShell text pipeline and was stopped after
`tar` reported damaged headers; the second attempt used a ZIP archive and
passed. The first package-phase attempt passed artifact objects to Twine as
bare names; the rerun used absolute paths and passed. Both failures were in
the temporary harness only; the repository was not modified.

## Status

Slice 203 is verified and closed locally. Publication, registry writes, cloud
actions, and website updates were not performed.
