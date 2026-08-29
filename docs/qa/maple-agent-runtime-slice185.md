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
Created wheel for maple-oss: filename=maple_oss-1.1.3-py3-none-any.whl size=500076
sha256=d40e35721102cd4ef30590aa529926f676087789e16a4e20321fc3997e526f4c

python -m twine check <wheel>
PASSED

python -m pip install --no-deps --target <isolated-target> <wheel>
Successfully installed maple-oss-1.1.3

python -c "import maple; from maple.task_management import FileTaskQueue"
version=1.1.3
FileTaskQueue=FileTaskQueue
```

Clean Git archive/package evidence is intentionally pending the evidence
commit. The repository is not publish-ready: user-owned dirty/untracked files
remain, package metadata is still `1.1.3` pending the eventual release, the
environment-wide pip-audit reports 385 vulnerabilities in 78 packages, and
Bandit/Gitleaks/fresh independent verifier sessions are unavailable here. No
external state was changed.

**Slice 185 QA status:** PASS for the local implementation and current-source
package smoke; clean archive and final human release gates remain open.
