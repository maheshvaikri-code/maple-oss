# QA + Security Report - MAPLE Agent Runtime Slice 116 @ 6224003

**QA Engineer · Security Reviewer · Date:** 2026-08-26  
**Build under test:** `6224003` (Slice 116 implementation and public docs;
review/QA artifacts are filed in the following release-evidence commit)

## Acceptance criteria verification

| # | Criterion | How executed | Evidence (real output) | Pass |
|---|---|---|---|---|
| 1 | Replay is explicit and disabled by default. | Tool policy validation and top-level import tests. | `47 passed in 3.11s`; isolated wheel smoke printed `disabled reuse_success disabled`. | Yes |
| 2 | A successful sync tool result is reused after a saved crash window. | Run-store failure after the tool result is produced, followed by resume with the same deterministic invocation. | Handler executes once; recovery returns the journaled result; `47 passed`. | Yes |
| 3 | Async replay reuses a result even when the provider call ID changes. | Async durable run with a changed regenerated provider call ID. | Handler executes once and the resumed result uses the current call ID; `47 passed`. | Yes |
| 4 | Journal corruption and persistence failures fail closed with typed results. | Malformed record regression plus existing journal failure boundary tests. | Malformed data does not invoke the handler; typed replay errors are returned; `47 passed`. | Yes |
| 5 | Approval-required and human-input tools remain outside this replay contract. | Reviewed sync/async execution branches and existing approval/input tests. | Approval/HITL paths do not enter the replay context; autonomy suite remains green. | Yes |
| 6 | Existing application behavior remains green. | Exact tracked test manifest; five user-owned untracked Doctrine test files excluded. | `1294 passed, 1 skipped in 226.93s (0:03:46)` across 1295 collected tests. | Yes |
| 7 | Public/runtime surfaces are documented and statically valid. | Black, Ruff, changed-boundary mypy, compile, doctor, and diff checks. | Black: `6 files would be left unchanged`; Ruff: `All checks passed!`; mypy: `Success: no issues found in 3 source files`; doctor reports `ready: true`, all eight checks true, `network: false`; compile/diff exit `0`. | Yes |
| 8 | Clean package evidence is collected before release promotion. | Clean archive build from `6224003`, package inspection, Twine checks, and isolated wheel smoke test. | `python -m build --wheel --sdist` exit `0`; Twine wheel/sdist `PASSED`; sdist `532` entries with required public files `6/6`; wheel `104` members; fresh no-dependency install/import smoke passed. Wheel SHA-256 `d48637f9f011caf8186ffd603f9b1b3fe1926bc060dbef9e46ff3f70b2452f83`; sdist SHA-256 `d9c0f55e18dd7108b08724123fc2a96ca4e00b86620852e09a0d42ec810deb78`. No publication performed. | Yes |

## Adversarial and edge matrix

| Input/scenario | Expected | Observed | Pass |
|---|---|---|---|
| Default `Tool` policy | Preserve existing direct execution | Policy prints `disabled`; no journal replay is enabled | Yes |
| Invalid replay policy | Reject registration | Tool validation returns the existing typed/value boundary; focused tests pass | Yes |
| Regenerated provider tool-call ID | Reuse only the matching deterministic invocation | ID is excluded from the journal identity; current ID is returned on replay | Yes |
| Different tool ordinal, run, step, name, or authorized args | Do not reuse another result | Invocation digest binds all fields; malformed/mismatched records fail closed | Yes |
| Malformed journal record | Do not invoke the handler | Typed replay error; handler call count remains zero | Yes |
| Journal read/write failure | Return typed failure and preserve effect caveat | Failure is surfaced; write failure warns that the external effect may have occurred | Yes |
| Approval-required/HITL tool | Keep existing one-time ownership contract | Replay context is excluded | Yes |
| Async execution | Avoid blocking the event loop | Journal I/O uses the executor only when replay is enabled | Yes |
| External side effect after handler, before journal save | Do not claim exactly-once | ADR/API retain the at-least-once/idempotency boundary | Yes |
| Sensitive successful result | Host controls persistence exposure | API/ADR require protected journal access and explicit retention/clearance | Yes |

## Regression

Focused Slice 116 run:

```text
47 passed in 3.11s
```

Final tracked application suite:

```text
1294 passed, 1 skipped in 226.93s (0:03:46)
```

The skip is the existing NATS dependency-gated test. No flaky retry or
retry-until-lucky behavior was used.

## Security sweep

- Precise changed-surface secret-pattern scan: `manual secret-pattern scan: no
  matches`.
- Dangerous-construct scan on the changed source/test surface: no matches for
  `eval(`, `exec(`, `pickle`, `subprocess`, `os.system`, `shell=True`, or
  `yaml.load(`.
- `gitleaks`: unavailable in the environment.
- `bandit`: unavailable in the environment.
- Injection review: replay identities use canonical JSON and SHA-256; the
  implementation adds no shell, SQL, template, dynamic evaluation, pickle, or
  network execution path.
- Bounds/fail-closed review: existing journal quotas remain active; identity
  mismatches, malformed output, and persistence failures do not invoke a
  replayed handler; approvals/HITL remain separate.
- Dependency review: no new runtime dependency; implementation uses existing
  journal contracts and the standard library.
- Dependency audit command: `python -m pip_audit --progress-spinner off`.
  Real result: `Found 383 known vulnerabilities in 77 packages`; it exited
  `1`, and also listed local packages not auditable from PyPI. This is an
  environment/release-governance finding, not silently accepted as clean.

**Security verdict:** **VETO** for a final repository publication claim until
dependency findings are dispositioned; no new Slice 116 security defect was
found.

**QA verdict:** pass for Slice 116 behavior, boundaries, static checks,
regression coverage, and clean package evidence. Release remains conditional
on dependency-governance disposition; no publication or website change was
performed.
