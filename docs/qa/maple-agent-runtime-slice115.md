# QA + Security Report - MAPLE Agent Runtime Slice 115 @ 338650a

**QA Engineer - Security Reviewer - Date:** 2026-08-26  
**Build under test:** `338650a` (feature, boundary-test, review, and QA commits)

## Acceptance criteria verification

| # | Criterion | How executed | Evidence (real output) | Pass |
|---|---|---|---|---|
| 1 | A parent workflow can compose a child workflow with explicit state filtering. | Focused workflow tests using `input_map` and `output_map`. | `31 passed in 4.62s`; mapped output contains only the requested child key. | Yes |
| 2 | Child interruption and recovery preserve lifecycle ownership. | Nested pause/resume test with a child checkpoint and parent interruption payload. | Child pause is propagated with child run ID/payload; parent resume completes the child; `31 passed`. | Yes |
| 3 | Parent crash-window recovery does not re-execute a completed child when journal output exists. | Parent store fails its second save; parent recovery reads the execution journal. | `test_subworkflow_recovery_reuses_completed_child_after_parent_commit_failure`; child handler called once; `31 passed`. | Yes |
| 4 | Invalid mappings and malformed child stores fail closed with typed errors. | Missing input, duplicate destinations, self-reference, malformed checkpoint, and invalid result tests. | Typed `SUBWORKFLOW_INPUT_MISSING`, `DUPLICATE_SUBWORKFLOW_TARGET`, `INVALID_SUBWORKFLOW`, and `SUBWORKFLOW_CHECKPOINT_INVALID` results; `31 passed`. | Yes |
| 5 | Documented mapping limits are enforced. | Boundary sweep at 255/256/257 entries and 256/257-character keys. | 255 and 256 entries/characters accepted; 257-entry/key cases return typed errors; `31 passed`. | Yes |
| 6 | Existing application behavior remains green. | Exact tracked test manifest; five user-owned untracked Doctrine test files excluded. | `1290 passed, 1 skipped in 234.57s (0:03:54)` across 1291 collected tests. | Yes |
| 7 | Public/runtime surfaces are documented and statically valid. | Black, Ruff, changed-boundary mypy, compile, doctor, and diff checks. | Black: `3 files would be left unchanged`; Ruff: `All checks passed!`; mypy: `Success: no issues found in 1 source file`; doctor `ready=true`, all eight checks true, `network=false`; compile/diff exit `0`. | Yes |
| 8 | Clean package evidence is collected before release promotion. | Clean archive build, package inspection, and isolated wheel smoke test. | Candidate `338650a`: `python -m build --wheel --sdist` exit `0`; Twine wheel/sdist checks `PASSED`; sdist `531` entries; required public files `6/6`; workspace-only audit `0`; wheel `104` entries and fresh no-dependency install/import smoke passed for `Workflow` and `add_subworkflow`. No publication performed. | Yes |

## Adversarial and edge matrix

| Input/scenario | Expected | Observed | Pass |
|---|---|---|---|
| Missing mapped parent key | Fail before child handler execution | `SUBWORKFLOW_INPUT_MISSING`; child call list remains empty | Yes |
| Duplicate mapping destination | Reject registration | `DUPLICATE_SUBWORKFLOW_TARGET` | Yes |
| Self-referential workflow | Reject registration | `INVALID_SUBWORKFLOW` | Yes |
| Malformed child checkpoint object | Fail closed at store boundary | `SUBWORKFLOW_CHECKPOINT_INVALID` | Yes |
| Empty/default state maps | Preserve explicit empty or unchanged-key contract | Default composition and mapped tests complete | Yes |
| Map entries 255 / 256 / 257 | Accept through 256; reject 257 | Boundary test passes with typed overflow | Yes |
| State-map key length 256 / 257 | Accept through 256; reject 257 | Boundary test passes with typed invalid-map error | Yes |
| Unicode/JSON state values | Preserve existing JSON-safe state boundary | Existing workflow state validation and full regression pass | Yes |
| Child interruption / repeated resume | Persist child identity and resume same child | Child pause payload and completion path pass | Yes |
| Parent checkpoint failure after child completion | Reuse journaled child output | Child handler executes once during initial attempt and not during recovery | Yes |
| Child store error or malformed result | Return typed parent failure | Store/result wrappers are bounded and structured | Yes |
| External child side effects | Do not claim exactly-once | ADR/API docs retain at-least-once/idempotent-handler boundary | Yes |

## Regression

Focused workflow/replay suite:

```text
31 passed in 4.62s
```

Final tracked application suite:

```text
1290 passed, 1 skipped in 234.57s (0:03:54)
```

The skip is the existing NATS dependency-gated test. No flaky retry or
retry-until-lucky behavior was used.

## Bugs found

| # | Repro steps (minimal) | Severity | Fixed @ | Re-verified | Regression test |
|---|---|---|---|---|---|
| 1 | Return a non-`WorkflowCheckpoint` object from a child checkpoint store and invoke the parent sub-workflow node. | Major risk at a custom store boundary | `8c08018` | Focused suite at `decbf36`: `31 passed` | `test_subworkflow_malformed_child_checkpoint_fails_closed` |

## Security sweep

- Precise changed-surface secret-pattern scan: `manual secret-pattern scan: no
  matches`.
- Recent-history secret-pattern scan: `recent history secret-pattern scan: no
  matches`.
- Dangerous-construct scan on the changed workflow/test surface:
  `workflow dangerous-construct scan: no matches`.
- `gitleaks`: unavailable in the environment.
- `bandit`: unavailable in the environment.
- Injection review: state maps are validated at registration, JSON state and
  child checkpoints cross existing bounded serialization stores, and no shell,
  SQL, template, `eval`, `exec`, pickle, or network path was added.
- Bounds/fail-closed review: map count and key length are bounded; existing
  state byte/depth/step limits remain active; malformed stores and child
  failures become typed parent failures; child effects remain at-least-once.
- Dependency review: no new runtime dependency; implementation uses existing
  workflow/checkpoint/journal contracts and the standard library.
- Dependency audit command: `python -m pip_audit --progress-spinner off`.
  Real result: `Found 383 known vulnerabilities in 77 packages`; it exited
  `1`, and also listed local packages not auditable from PyPI. This is an
  environment/release-governance finding, not silently accepted as clean.

**Security verdict:** **VETO** for a final repository publication claim until
dependency findings are dispositioned; no new Slice 115 security defect found.
Human override: n/a.  
**QA verdict:** pass for Slice 115 behavior, boundaries, static checks,
regression coverage, and clean package evidence. Release remains conditional
on dependency-governance disposition; no publication was performed.
