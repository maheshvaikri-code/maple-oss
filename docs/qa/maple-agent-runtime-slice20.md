# QA + Security - MAPLE Agent Runtime Slice 20 @ `7665eaf`

**QA Engineer · Security Reviewer · Date:** 2026-08-24
**Build under test:** exact commit `7665eaf`; package version `1.1.3`

## Acceptance criteria verification

| # | Criterion | How executed | Evidence | Pass |
|---|---|---|---|---|
| 1 | Registered workflows can be started through the local HTTP boundary | Real loopback POST with JSON state and stable run ID | `201`; completed run state returned | PASS |
| 2 | Existing checkpoints can be inspected and interrupted runs resumed | Real GET and POST resume against an in-memory checkpoint store | `200`; paused run resumes to completed | PASS |
| 3 | Server rejects unsafe/oversized boundary inputs | Non-loopback constructor, malformed JSON, unknown workflow, oversized body | `ValueError`, `400`, `404`, `413` | PASS |
| 4 | Lifecycle and public surface are deterministic | Start/close, doctor, compile, focused regression, build artifacts | `212 passed`; doctor ready; Twine checks passed | PASS |

## Adversarial & edge matrix

| Input/scenario | Expected | Observed | Pass |
|---|---|---|---|
| Health request | Local JSON readiness response | `200` with `status=ok` | PASS |
| Unknown workflow | Not found, no execution | `404 WORKFLOW_NOT_FOUND` | PASS |
| Malformed JSON | Typed client error | `400 REQUEST_BODY_INVALID` | PASS |
| Oversized body | Reject before workflow call | `413 REQUEST_TOO_LARGE` | PASS |
| Non-loopback bind | Reject unsafe default expansion | Constructor raises `ValueError` | PASS |
| Interrupted run/resume | Preserve checkpoint semantics | `interrupted` then `completed` | PASS |
| Query string/path traversal | Route IDs remain constrained | Query ignored; workflow/run IDs are validated downstream | PASS |
| Shutdown | No orphan request thread/socket | Context and `close()` tests complete | PASS |

## Regression

```text
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/autonomy/test_server.py -q -o addopts=
4 passed, 1 warning in 2.08s

$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/llm tests/autonomy tests/test_cli.py -q -o addopts=
212 passed, 1 warning in 3.03s

python -m compileall -q maple
compileall exit code: 0

python -m twine check .tmp-maple-server-final\maple_oss-1.1.3-py3-none-any.whl .tmp-maple-server-final\maple_oss-1.1.3.tar.gz
Checking .tmp-maple-server-final\maple_oss-1.1.3-py3-none-any.whl: PASSED
Checking .tmp-maple-server-final\maple_oss-1.1.3.tar.gz: PASSED
```

The pytest warning is the existing `asyncio_mode` configuration warning when
plugin autoload is disabled.

## Bugs found

| # | Repro steps | Severity | Fixed @ | Re-verified | Regression test |
|---|---|---|---|---|---|
| 1 | Send a body over the configured request-byte cap | MAJOR boundary risk | `7665eaf` | `4 passed` and `212 passed` | `test_run_server_rejects_unknown_routes_workflows_and_oversized_bodies` |

The server writes a bounded `413` response and stops request processing before
the workflow registry is called.

## Security sweep

- **Secrets:** `gitleaks` is unavailable; the fallback scan found no secret
  pattern in the new server, tests, ADR, or docs.
- **Input/path/deserialization:** content type and length are required;
  request/response bytes and paths are bounded; workflow/run IDs remain
  validated by the workflow boundary; JSON is parsed as data only.
- **Dependencies:** no dependency changed; the implementation uses only the
  Python standard library. The shared-interpreter `pip_audit --local` findings
  recorded in Slice 19 remain a repository-release gate, not a new dependency
  introduced here.
- **Dangerous constructs:** no `pickle`, `eval`, `exec`, shell, TLS-disable,
  or arbitrary HTTP workflow registration was added. Binding is loopback-only.
- **Failure posture:** malformed requests fail closed, internal errors use a
  generic response, and server shutdown owns its thread and socket.

**Security verdict:** SIGN-OFF for this changed feature boundary; repository
release authorization remains open.
**QA verdict:** CONDITIONAL PASS for Slice 20; full repository regression,
repository-wide lint, independent fresh-context verification, and external
publication remain open release gates.
