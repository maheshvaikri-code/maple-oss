# QA + Security - MAPLE Agent Runtime Slice 18 @ working tree

**QA Engineer · Security Reviewer · Date:** 2026-08-24
**Build under test:** working tree after Slice 18 implementation; package
version `1.1.3`

## Acceptance criteria verification

| # | Criterion | How executed | Evidence | Pass |
|---|---|---|---|---|
| 1 | Successful saves produce immutable history snapshots | Two-node workflow and state-copy assertions | `16 passed` workflow suite | PASS |
| 2 | History retention and limits are bounded | `max_history=2`, default-bound, explicit over-limit, and missing-run tests | `HISTORY_LIMIT_INVALID` and trimmed versions verified | PASS |
| 3 | Wrapped recovery semantics remain unchanged | Workflow runs through the decorator using the existing in-memory store | Workflow suite and combined gate pass | PASS |
| 4 | No replay or side-effect execution is introduced | API/ADR review and handler-count workflow tests | History only returns data; no handlers run during inspection | PASS |
| 5 | Public surface and release metadata are documented | ADR-016, API reference, README, changelog, exports, and plan | Package build/Twine checks pass | PASS |

## Adversarial & edge matrix

| Input/scenario | Expected | Observed | Pass |
|---|---|---|---|
| Missing run | Empty history, not an exception | `[]` | PASS |
| Limit omitted with small max history | Use configured bound | Returns available bounded snapshots | PASS |
| Limit above max history | Reject | `HISTORY_LIMIT_INVALID` | PASS |
| Mutating returned snapshot | Do not mutate stored history | Fresh JSON-safe copies returned | PASS |
| Failed/paused workflow | Preserve checkpoint transitions | Wrapped store remains source of truth | PASS |
| Replay request | No node execution | History API only reads snapshots | PASS |

## Regression

```text
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/autonomy/test_workflow.py -q -o addopts=
16 passed, 1 warning in 0.10s

$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/llm tests/autonomy tests/test_cli.py -q -o addopts=
199 passed, 1 warning in 0.86s

python -m compileall -q maple
compileall exit code: 0

python -m maple.cli doctor --json
{"checks": {"core": true, "evaluation": true, "events": true, "execution": true, "interop": true, "retrieval": true}, "network": false, "ready": true, "status": "SUCCESS", "version": "1.1.3"}

python -m twine check '.tmp-maple-history-final\*'
Checking .tmp-maple-history-final\maple_oss-1.1.3-py3-none-any.whl: PASSED
Checking .tmp-maple-history-final\maple_oss-1.1.3.tar.gz: PASSED
```

The temporary package directory was removed after the check. The pytest
warning is the existing `asyncio_mode` configuration warning when plugin
autoload is disabled.

## Security sweep

- **Secrets:** `gitleaks` is unavailable. The bounded fallback scan over the
  changed workflow/test/ADR files found no token-shaped secret patterns.
- **Input/deserialization:** run IDs and history limits are validated and
  bounded; snapshots use the existing JSON-safe checkpoint copy boundary.
- **Dependencies:** no dependency changed; the implementation is stdlib-only.
- **Dangerous constructs:** no replay execution, shell, network, `eval`,
  `exec`, or `pickle` was added.
- **Failure posture:** invalid limits fail with typed errors; the wrapped
  store's load/save conflicts propagate without mutating history.

**Security verdict:** SIGN-OFF for this changed feature boundary; not a final
publish authorization.
**QA verdict:** CONDITIONAL PASS for Slice 18; full repository regression,
repository-wide lint, independent fresh-context verification, and external
publication remain open release gates.
