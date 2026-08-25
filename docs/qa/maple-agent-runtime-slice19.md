# QA + Security - MAPLE Agent Runtime Slice 19 @ `0648efa`

**QA Engineer · Security Reviewer · Date:** 2026-08-24
**Build under test:** exact commit `0648efa`; package version `1.1.3`

## Acceptance criteria verification

| # | Criterion | How executed | Evidence | Pass |
|---|---|---|---|---|
| 1 | Session IDs, roles, metadata, messages, and snapshots are bounded and JSON-safe | Invalid role/metadata, oversized message, typed round-trip, and serialization tests | `9 passed` session suite | PASS |
| 2 | Appends and clears expose optimistic version conflicts without mutation | Stale append and successful clear tests | `SESSION_CONFLICT`; stored version/state unchanged on failure | PASS |
| 3 | In-memory and file stores are usable under their stated concurrency/restart contract | Threaded in-memory append test and file-store recreation test | Version `8` after concurrent appends; file session reloads after recreation | PASS |
| 4 | Malformed or path-sensitive persistence input fails closed | Malformed JSON snapshot and constrained session-ID paths | `SESSION_LOAD_ERROR`; IDs reject traversal characters | PASS |
| 5 | Public surface and release evidence are updated | Imports, doctor, focused tests, build, and Twine checks | `sessions: true`; `208 passed`; wheel/sdist Twine `PASSED` | PASS |

## Adversarial & edge matrix

| Input/scenario | Expected | Observed | Pass |
|---|---|---|---|
| Empty message content | Accepted as a typed message | Stored and returned as `content == ""` | PASS |
| Oversized message | Reject before mutation | `SESSION_MESSAGE_SIZE`; session remains empty | PASS |
| Invalid role | Reject before mutation | `SESSION_MESSAGE_INVALID` | PASS |
| Invalid metadata object | Reject before session creation | `SESSION_METADATA_VALUE`; no file/state created | PASS |
| Duplicate message ID | Reject | `SESSION_MESSAGE_DUPLICATE` path is guarded by store | PASS |
| Concurrent appends | Serialize under one in-process owner | Eight appends produce version `8` | PASS |
| Malformed file | Fail closed | `SESSION_LOAD_ERROR` | PASS |
| Message-count limit | Reject at max+1 | `SESSION_MESSAGE_LIMIT`; prior message retained | PASS |
| Unicode/metadata depth | JSON boundary is bounded | Validation path is covered by recursive JSON checks; no separate Unicode fixture in this slice | CONDITIONAL |

## Regression

```text
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/autonomy/test_sessions.py -q -o addopts=
9 passed, 1 warning in 0.06s

$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/llm tests/autonomy tests/test_cli.py -q -o addopts=
208 passed, 1 warning in 0.84s

python -m compileall -q maple
compileall exit code: 0

python -m twine check .tmp-maple-session-final\maple_oss-1.1.3-py3-none-any.whl .tmp-maple-session-final\maple_oss-1.1.3.tar.gz
Checking .tmp-maple-session-final\maple_oss-1.1.3-py3-none-any.whl: PASSED
Checking .tmp-maple-session-final\maple_oss-1.1.3.tar.gz: PASSED
```

The pytest warning is the existing `asyncio_mode` configuration warning when
plugin autoload is disabled.

## Bugs found

| # | Repro steps | Severity | Fixed @ | Re-verified | Regression test |
|---|---|---|---|---|---|
| 1 | Load a file containing only `session_id` | MAJOR boundary gap | `0648efa` | `9 passed` | `test_file_session_malformed_payload_fails_closed` |

The parser was tightened to require the complete persisted snapshot shape;
malformed files now fail closed without creating state.

## Security sweep

- **Secrets:** `gitleaks` is unavailable; fallback scan of the changed
  implementation, tests, ADR, and docs found no token-shaped secret.
- **Input/path/deserialization:** IDs are character-constrained and resolved
  paths are prefix-checked; JSON values have depth/item/byte limits; no
  `pickle`, `eval`, `exec`, shell, or network path was added.
- **Dependencies:** no dependency changed. `python -m pip_audit --local`
  reported `383` findings across `77` packages in the shared interpreter,
  including private/non-PyPI packages; these are pre-existing environment
  findings and are not attributable to this stdlib-only slice. The isolated
  package dependency gate remains the release-authoritative check.
- **Failure posture:** validation and optimistic conflicts happen before
  mutation; file writes use same-directory atomic replacement; cross-process
  coordination and encryption remain explicitly unsupported.

**Security verdict:** SIGN-OFF for this changed feature boundary; repository
release authorization remains open.
**QA verdict:** CONDITIONAL PASS for Slice 19; full repository regression,
repository-wide lint, independent fresh-context verification, and external
publication remain open release gates.
