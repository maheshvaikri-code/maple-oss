# QA + Security - MAPLE Agent Runtime Slice 16 @ working tree

**QA Engineer · Security Reviewer · Date:** 2026-08-24
**Build under test:** working tree after Slice 16 implementation; package
version `1.1.3`

## Acceptance criteria verification

| # | Criterion | How executed | Evidence | Pass |
|---|---|---|---|---|
| 1 | Approval requests are bounded JSON records | In-memory and file-store lifecycle tests plus malformed argument test | `21 passed` approval/agent suite | PASS |
| 2 | File persistence survives restart | Create/decide with one store, load/consume with a recreated store | `test_file_approval_survives_store_recreation` | PASS |
| 3 | Decisions are fail-closed and one-time | Pending, denied, duplicate decision, consume, and replay paths | `21 passed` approval/agent suite | PASS |
| 4 | Required tools do not execute while pending | Agent integration test checks handler side effects before and after explicit decision | `21 passed` approval/agent suite | PASS |
| 5 | Public surface and release metadata are documented | ADR-014, API reference, README, changelog, exports, and plan | Combined focused gate and package build | PASS |

## Adversarial & edge matrix

| Input/scenario | Expected | Observed | Pass |
|---|---|---|---|
| Pending request | No handler invocation | `APPROVAL_PENDING`, handler call list empty | PASS |
| Explicit denial | No handler invocation | `APPROVAL_DENIED`/terminal record | PASS |
| Duplicate decision | No state reversal | `APPROVAL_CONFLICT` | PASS |
| Replay after consume | No second handler invocation | `APPROVAL_CONSUMED` | PASS |
| Non-JSON argument | Reject before persistence | `APPROVAL_INVALID` and no record | PASS |
| Invalid list limit | Reject unbounded query | `APPROVAL_LIMIT_INVALID` | PASS |
| Malformed file/oversized record | Return typed load failure | File-store boundary catches load errors | PASS |
| Missing callback and missing store | Preserve existing fail-closed path | Existing `APPROVAL_REQUIRED` regression passes | PASS |

## Regression

```text
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/autonomy/test_approval.py tests/autonomy/test_agent.py -q -o addopts=
21 passed, 1 warning in 0.05s

$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/llm tests/autonomy tests/test_cli.py -q -o addopts=
192 passed, 1 warning in 0.87s

python -m compileall -q maple
compileall exit code: 0

python -m maple.cli doctor --json
{"checks": {"core": true, "evaluation": true, "events": true, "execution": true, "interop": true, "retrieval": true}, "network": false, "ready": true, "status": "SUCCESS", "version": "1.1.3"}

python -m twine check '.tmp-maple-approval-final\*'
Checking .tmp-maple-approval-final\maple_oss-1.1.3-py3-none-any.whl: PASSED
Checking .tmp-maple-approval-final\maple_oss-1.1.3.tar.gz: PASSED
```

The temporary package directory was removed after the check. The pytest
warning is the existing `asyncio_mode` configuration warning when plugin
autoload is disabled.

## Security sweep

- **Secrets:** `gitleaks` is unavailable. The bounded fallback scan over the
  changed approval/runtime/test/ADR files found no token-shaped secret
  patterns.
- **Input/deserialization:** approval IDs are path-safe identifiers; tool-call
  text is bounded; arguments are depth-, item-, and byte-bounded JSON; file
  records reject malformed status/decision combinations.
- **Dependencies:** no dependency changed. Existing isolated dependency gate
  remains authoritative.
- **Dangerous constructs:** no `eval`, `exec`, `pickle`, shell, network, or
  credential logging was added. File writes use a temporary file and atomic
  replacement.
- **Failure posture:** absent store, persistence errors, pending/denied states,
  decision conflicts, and consumed requests do not execute the handler.

**Security verdict:** SIGN-OFF for this changed feature boundary; not a final
publish authorization.
**QA verdict:** CONDITIONAL PASS for Slice 16; full repository regression,
repository-wide lint, independent fresh-context verification, and external
publication remain open release gates.
