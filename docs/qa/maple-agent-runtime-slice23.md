# QA + Security Report - MAPLE agent runtime slice 23 @ `1af7f3a`

**QA Engineer** · **Security Reviewer** · **Date:** 2026-08-24
**Build under test:** commit `1af7f3a` (`feat(workflow): add bounded execution journal recovery`)

## Acceptance criteria verification

| # | Criterion | How executed | Evidence | Pass |
|---|-----------|--------------|----------|------|
| 1 | The capability is native, documented, and bounded. | Inspected exports, ADR, API reference, README, changelog, and plan; ran journal tests. | `tests/autonomy/test_replay.py`: 7 passed; `tests/autonomy/test_workflow_replay.py`: 3 passed. | PASS |
| 2 | Running workflow checkpoints can be recovered without repeating a journaled node output. | Simulated a checkpoint-save failure after journal persistence, then called `Workflow.recover`. | `26 passed`; `test_recover_reuses_output_written_before_checkpoint_failure` asserts one handler call and stable key `recover-run:0:start`. | PASS |
| 3 | Malformed, conflicting, oversized, and path-mismatched journal data fails closed. | Exercised malformed JSON, input/record conflicts, output byte quota, and hashed filename mismatch. | `26 passed`; typed `REPLAY_*` errors observed by assertions. | PASS |
| 4 | Package/public surface remains usable. | Ran focused CI gate, compile, doctor, wheel/sdist build, Twine, and clean-wheel smoke. | `235 passed in 3.33s`; doctor `ready: true`; both artifacts `PASSED`; fresh wheel doctor exit `0`. | PASS |

## Adversarial & edge matrix

| Input/scenario | Expected | Observed | Pass |
|----------------|----------|----------|------|
| Empty JSON object output | Accepted and round-tripped | In-memory/file journal and workflow tests pass | PASS |
| Oversized output | Reject before journal mutation | `REPLAY_RECORD_SIZE` | PASS |
| Duplicate identical record | Idempotent save | Existing record returned | PASS |
| Duplicate key with different input/output | Reject without overwrite | `REPLAY_INPUT_CONFLICT` / `REPLAY_CONFLICT` | PASS |
| Malformed JSON / missing fields | Fail closed | `REPLAY_LOAD_ERROR` | PASS |
| Key/path mismatch | Fail closed | `REPLAY_LOAD_ERROR` | PASS |
| Global record bound | Reject over-limit save/scan | `REPLAY_RECORD_LIMIT` | PASS |
| Interrupted checkpoint commit | Recover without rerunning journaled handler | Handler called once; recovery completed | PASS |
| Concurrent workflow branches | Preserve existing bounded deterministic behavior | Included in the 235-test focused gate | PASS |

## Regression

```text
python -m pytest tests/llm tests/autonomy tests/test_cli.py -q -o addopts=
235 passed in 3.33s

python -m compileall -q maple
COMPILE_EXIT=0

python -m maple.cli doctor --json
{"checks": {"core": true, "evaluation": true, "events": true, "execution": true, "interop": true, "retrieval": true, "server": true, "sessions": true}, "network": false, "ready": true, "status": "SUCCESS", "version": "1.1.3"}

python -m twine check .tmp-maple-slice23-final\*
Checking C:\Project_WorldLevel\MAPLE\maple-oss\.tmp-maple-slice23-final\maple_oss-1.1.3-py3-none-any.whl: PASSED
Checking C:\Project_WorldLevel\MAPLE\maple-oss\.tmp-maple-slice23-final\maple_oss-1.1.3.tar.gz: PASSED
TWINE_EXIT=0

Fresh-wheel smoke
Successfully installed maple-oss-1.1.3
{"checks": {"core": true, "evaluation": true, "events": true, "execution": true, "interop": true, "retrieval": true, "server": true, "sessions": true}, "network": false, "ready": true, "status": "SUCCESS", "version": "1.1.3"}
WHEEL_DOCTOR_EXIT=0
```

The latest bounded full-repository attempt remains incomplete: it reported
`1049 passed, 8 warnings in 839.17s` before interruption in slow Doctrine gold
cases. No assertion failure was reported, but this is not a full-suite pass.

## Bugs found

| # | Repro steps | Severity | Fixed @ | Re-verified | Regression test |
|---|-------------|----------|---------|-------------|-----------------|
| 1 | Place a valid record in a journal filename whose hash does not match its execution key; inspect/clear the journal. | MINOR | `1af7f3a` | `26 passed` | `test_file_journal_fails_closed_when_record_key_does_not_match_filename` |

## Security sweep

- **Secrets:** `gitleaks` is unavailable. The changed diff emitted no
  token-shaped literal matches in the fallback pattern scan.
- **Injection/path:** execution keys and identifiers are charset-bounded;
  file records use SHA-256-derived filenames; atomic replacement never uses
  caller text as a path component; mismatched filenames fail closed.
- **Deserialization:** JSON only; bounded depth, item count, record bytes,
  and workflow input bytes; no `pickle`, `eval`, or `exec` in the slice.
- **Dependencies:** no new runtime dependency. `python -m pip_audit --local`
  was run and failed against the shared environment with `383 known
  vulnerabilities in 77 packages`; it also reported local packages that are
  unavailable on PyPI. This is an existing environment/repository release
  blocker, not introduced by Slice 23, and must be dispositioned before
  publication.
- **Bounds/failure posture:** global/per-run quotas, atomic writes, typed
  environment errors, conflict checks, and fail-closed malformed data are
  covered by tests.

**Security verdict:** SIGN-OFF for Slice 23 implementation; repository-wide
dependency-audit findings remain an open release gate.
**QA verdict:** pass for Slice 23; publish clearance remains open pending the
full repository regression, repository-wide lint debt, dependency-audit
disposition, and independent fresh-context verification.
