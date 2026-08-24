# QA + Security Report - MAPLE Agent Runtime Slice 1 @ d75c58c

**QA Engineer:** local verification role  · **Security Reviewer:** local
security pass  · **Date:** 2026-08-24
**Build under test:** `d75c58c feat(autonomy): add durable workflow runtime`

## Acceptance criteria verification

| # | Criterion | How executed | Evidence | Pass |
|---|-----------|--------------|----------|------|
| 1 | Workflow graph, run ID, checkpoint, interruption, and resume exist as native APIs. | Focused workflow tests and root import. | `33 passed`; `Workflow`, `CheckpointStore`, and `WorkflowPause` import from `maple`. | Yes |
| 2 | Completed nodes are not re-run after an interruption. | `test_workflow_pauses_and_resumes_without_rerunning_completed_nodes`. | Call trace shows `start` once; resume begins at `approval`. | Yes |
| 3 | File checkpoints survive store recreation. | `test_file_checkpoint_survives_store_recreation`. | A new `FileCheckpointStore` resumes the interrupted run to `completed`. | Yes |
| 4 | Malformed or non-JSON checkpoint/state input fails closed. | Malformed checkpoint, non-JSON initial state, and non-JSON node error tests. | All boundary tests passed; no pickle/eval/exec/subprocess path in new workflow code. | Yes |
| 5 | Existing autonomy behavior remains green. | `python -m pytest tests/autonomy -q -o addopts=`. | `96 passed, 1 warning in 0.13s`. | Yes |

## Adversarial and edge matrix

| Input/scenario | Expected | Observed | Pass |
|----------------|----------|----------|------|
| Empty initial state | Valid workflow may run | Completed/paused normally | Yes |
| Non-JSON object in state | Reject before checkpoint write | `INVALID_STATE_VALUE`; store remained empty | Yes |
| Malformed checkpoint JSON | Load error, no execution | `CHECKPOINT_LOAD_ERROR` | Yes |
| Duplicate run ID | Reject without overwriting | `RUN_ID_EXISTS` | Yes |
| Conditional route using node output | Route sees committed candidate state | Correct `right` branch selected | Yes |
| Interruption | Persist current node and payload | `interrupted` checkpoint returned | Yes |
| Resume | Continue from interrupted node | `completed` with prior node preserved | Yes |
| Oversized/too-deep state | Reject at boundary | Enforced by JSON validation and byte limit | Yes |
| Concurrent in-process store access | Serialize access and detect versions | `RLock` + optimistic version checks implemented; stress test deferred to Slice 5 | Partial |

## Regression

Focused command:

```text
33 passed, 1 warning in 0.10s
```

Autonomy suite:

```text
96 passed, 1 warning in 0.13s
```

Broader repository command reached:

```text
1008 passed, 8 warnings in 541.64s (0:09:01)
KeyboardInterrupt
```

The broader run was stopped after a pre-existing timing-heavy path stopped
advancing. It is unfinished evidence, not a full-suite pass.

## Bugs found

| # | Repro steps | Severity | Fixed @ | Re-verified | Regression test |
|---|-------------|----------|---------|-------------|-----------------|
| 1 | Persist a node error containing a non-JSON object. | Major boundary risk | `d75c58c` | Yes | `test_non_json_node_error_is_replaced_with_persistable_failure` |

## Security sweep

- **Secrets:** no credential-like strings found in new workflow code/tests.
- **Injection:** workflow/run/node identifiers are constrained; checkpoint
  paths are resolved and prefix-checked; JSON is parsed as data.
- **Dangerous constructs:** targeted `rg` returned exit code `1` (no matches)
  for `eval`, `exec`, `pickle`, `subprocess`, `shell=True`, or `yaml.load` in
  the new workflow code/tests.
- **Dependencies:** no new dependency was added. `pip-audit` was invoked but
  produced no usable output in this environment; a repository-wide dependency
  audit remains open for the final release gate.
- **Bounds/fail-closed:** state depth, item count, byte size, identifier size,
  checkpoint size, step count, malformed input, and optimistic checkpoint
  conflicts are bounded or rejected.

**Security verdict:** SIGN-OFF for this dependency-free Slice 1 boundary;
final repository release sign-off remains open.
**QA verdict:** pass for Slice 1; full release QA remains open pending the
remaining slices and a completed final regression run.
