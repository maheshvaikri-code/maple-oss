# Slice 185 QA — bounded durable local task queue

**Date:** 2026-08-28
**QA role:** QA Engineer / Release Manager local pass

## Acceptance coverage

- Restart preserves queued priority order and terminal outcomes.
- Interrupted assignment is redelivered as queued work with its ephemeral
  owner and start time cleared.
- Payload, metadata, result, task count, JSON structure, and state-file sizes
  are bounded; malformed and unknown state fields fail closed.
- Atomic persistence failures roll back in-memory admission and leave the
  previous state file unchanged.
- Competing local holders are fenced before a task mutation.
- The existing `TaskScheduler` can assign through the durable queue.
- The queue is publicly importable from `maple.task_management`.

## Regression evidence

```text
python -m pytest -q --no-cov tests/task_management/test_durable_task_queue.py
11 passed in 0.63s

python -m pytest -q --no-cov tests/task_management
178 passed in 22.75s

python -m pytest -q --no-cov
1743 passed, 1 skipped in 314.00s (0:05:14)
```

## Current-source package smoke

The current dirty source tree was built without dependency resolution using
the installed PEP 517 backend. The wheel passed Twine metadata validation,
installed into an isolated target directory, and imported the new public
class outside the repository working directory:

```text
python -m pip wheel . --no-deps --no-build-isolation --wheel-dir <artifact-dir>
Created wheel for maple-oss: filename=maple_oss-1.1.3-py3-none-any.whl size=500158
sha256=52503329ab49feb103b444c8330dc270583fce98e0b41753d5ce738a7cb5c9e0

python -m twine check <wheel>
PASSED

python -m pip install --no-deps --target <isolated-target> <wheel>
Successfully installed maple-oss-1.1.3

python -c "import maple; from maple import AgentRegistry, RunServer; from maple.task_management import FileTaskQueue"
version=1.1.3
registry=AgentRegistry
server=RunServer
FileTaskQueue=FileTaskQueue
```

The repository is not publish-ready: user-owned dirty/untracked files
remain, package metadata is still `1.1.3` pending the eventual release, the
environment-wide pip-audit reports 385 vulnerabilities in 78 packages, and
Bandit/Gitleaks/fresh independent verifier sessions are unavailable here. No
external state was changed.

## Exact clean archive package gate

The clean Git archive of `2f59090` was tested independently of the dirty
workspace. It contains the durable queue source and regression, and its
artifacts passed metadata, install, import, and local-only doctor checks:

```text
source_archive_entries=866
python -m pytest -q --no-cov
1626 passed, 1 skipped in 253.50s (0:04:13)
build_exit=0
wheel_entries=108
sdist_entries=780
twine check <wheel>, <sdist>
PASSED, PASSED
install_exit=0
version=1.1.3
FileTaskQueue=FileTaskQueue
doctor_exit=0
```

The exact doctor JSON was:

```json
{"checks": {"core": true, "evaluation": true, "events": true, "execution": true, "interop": true, "retrieval": true, "server": true, "sessions": true}, "network": false, "ready": true, "status": "SUCCESS", "version": "1.1.3"}
```

**Slice 185 QA status:** PASS for the implementation and exact clean archive
package gate. Overall release status remains conditional pending the existing
security/verifier gates, final version promotion, clean release tree, and
human publication authorization.
