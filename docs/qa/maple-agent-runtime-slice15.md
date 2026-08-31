# QA + Security - MAPLE Agent Runtime Slice 15 @ working tree

**QA Engineer · Security Reviewer · Date:** 2026-08-24
**Build under test:** working tree after Slice 15 implementation; package
version `1.1.3`

## Acceptance criteria verification

| # | Criterion | How executed | Evidence | Pass |
|---|---|---|---|---|
| 1 | Independent branches execute concurrently | Barrier-backed branch handlers in regression test | `13 passed` workflow suite | PASS |
| 2 | Branch count and workers are bounded | Configured `max_parallel_branches=2`; limit+1 rejection test; hard ceiling validation in constructor | `13 passed` workflow suite; changed Ruff/Flake8 clean | PASS |
| 3 | State merge is deterministic and fail-closed | Declaration-order `completed_nodes`, collision rejection, join-state assertions | `13 passed` workflow suite | PASS |
| 4 | Fan-in state is checkpointed and resumes safely | File-backed pause/resume test plus existing checkpoint persistence tests | `13 passed` workflow suite | PASS |
| 5 | Public surface and release metadata are documented | ADR-013, API reference, README, changelog, implementation plan | Diff inspection and package build | PASS |

## Adversarial & edge matrix

| Input/scenario | Expected | Observed | Pass |
|---|---|---|---|
| Concurrent branches | Both handlers overlap; join sees both outputs | Barrier released; workflow completed with both branch values | PASS |
| Duplicate output key | Fail rather than last-write-wins | `PARALLEL_STATE_CONFLICT`; checkpoint remains at pre-group boundary | PASS |
| Limit+1 branches | Reject before execution | `PARALLELISM_EXCEEDED` | PASS |
| Interrupted branch | Persist interruption without partial group commit | `interrupted`, empty `completed_nodes`, resume repeats group and completes | PASS |
| Malformed/non-JSON state | Reject or persist a typed failure | Existing workflow boundary regressions pass | PASS |
| File-backed restart | Preserve checkpoint data across store recreation | Existing file checkpoint regression passes | PASS |

## Regression

```text
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/autonomy/test_workflow.py -q -o addopts=
13 passed, 1 warning in 0.06s

$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/llm tests/autonomy tests/test_cli.py -q -o addopts=
187 passed, 1 warning in 0.85s

python -m compileall -q maple
compileall exit code: 0

python -m maple.cli doctor --json
{"checks": {"core": true, "evaluation": true, "events": true, "execution": true, "interop": true, "retrieval": true}, "network": false, "ready": true, "status": "SUCCESS", "version": "1.1.3"}

python -m twine check '.tmp-maple-fanout-release\*'
Checking .tmp-maple-fanout-release\maple_oss-1.1.3-py3-none-any.whl: PASSED
Checking .tmp-maple-fanout-release\maple_oss-1.1.3.tar.gz: PASSED
```

The pytest warning is the existing `asyncio_mode` configuration warning when
plugin autoload is disabled. The temporary package directory was removed
after the check.

## Bugs found

| # | Repro steps | Severity | Fixed @ | Re-verified | Regression test |
|---|---|---|---|---|---|
| 1 | Changed-surface Flake8 initially reported five E501 lines | MINOR | working tree | Flake8 returned `0` after line wrapping | N/A; style gate |

## Security sweep

- **Secrets:** `gitleaks` is unavailable. The bounded fallback scan over the
  changed runtime, tests, and ADR found no token-shaped secret patterns.
- **Injection/deserialization:** branch input is identifier-validated; state
  crosses only the existing bounded JSON validation/copy boundary; no
  `eval`, `exec`, `pickle`, shell, or network path was added.
- **Dependencies:** no dependency changed. Existing isolated dependency gate
  remains the authoritative audit result.
- **Dangerous constructs:** `ThreadPoolExecutor` is bounded and trusted
  in-process only; no sandbox claim is made. Branch exceptions and collisions
  fail the workflow; approval/security boundaries are unchanged.
- **Resource bounds:** branch count, state size/depth, and workflow steps are
  bounded. A pause before the group checkpoint can repeat side effects on
  resume; this is documented as an at-least-once boundary.

**Security verdict:** SIGN-OFF for this changed feature boundary; not a final
publish authorization.
**QA verdict:** CONDITIONAL PASS for Slice 15; full repository regression,
repository-wide lint, independent fresh-context verification, and external
publication remain open release gates.
