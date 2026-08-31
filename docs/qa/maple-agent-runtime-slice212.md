# Slice 212 QA and security report - restricted host-owned HTTP transports

**QA Engineer:** QA role
**Security Reviewer:** Security role
**Candidate:** `7c62108517f9f13cacfb1a418b2f227e09b3f8a3`
**Date:** 2026-08-29
**Independent verifier:** Unavailable; no fresh-session result is claimed.

## Acceptance criteria

| Criterion | Evidence | Result |
| --- | --- | --- |
| HTTP(S)-only opener with no file/custom handlers | Private opener installed HTTP, HTTPS, proxy, error, and constrained redirect handlers; only legacy MCP adapter retains its separately documented B310 exception | PASS |
| Unsafe redirect and credential targets fail closed | Event exporter regression rejects a `file://` redirect; helper rejects URL credentials, cross-origin redirects, and HTTPS downgrade | PASS |
| Existing transport behavior remains bounded and compatible | Focused event/notification/server suite: `136 passed in 42.40s`; workflow contract tests: `9 passed in 0.38s` | PASS |
| No dependency or Python compatibility regression | Stdlib-only helper; Python >=3.8-compatible `typing.Tuple`; mypy and package import pass | PASS |
| Repository and release evidence are complete | Full suite/static/audit/package smoke below; brief, ADR, plan, review, QA, API, parity, changelog, and release files are present | PASS |

## Regression and adversarial execution

```text
python -m pytest tests/autonomy/test_events.py tests/autonomy/test_remote_notification_delivery.py tests/autonomy/test_remote_approval_notification.py tests/autonomy/test_server.py -q -o addopts=
136 passed in 42.40s

python -m pytest -q
1904 passed, 1 skipped in 409.86s (0:06:49)
```

The focused run exercised normal HTTP delivery, bounded responses, auth
headers, transport failures, notification acknowledgements, server/client
routes, and the unsafe `file://` redirect case. No flaky behavior was
observed.

## Static, security, and dependency gates

```text
python -m black --check --diff maple/
103 files would be left unchanged.

python -m isort --check-only --diff maple/
isort_exit=0

python -m ruff check maple tests
All checks passed!

python -m mypy maple --ignore-missing-imports
Success: no issues found in 103 source files

python -m compileall -q maple
compileall_exit=0

python -m bandit -r maple -ll -q
bandit_exit=0

python -m pip_audit --strict --progress-spinner off --timeout 30 .
No known vulnerabilities found

added-line fallback secret scan from 7dbe8dc..HEAD
added_lines=269
fallback_secret_matches=0
```

Gitleaks is unavailable in this environment, so no Gitleaks pass is claimed.
The legacy MCP adapter's existing `# nosec B310` is outside this slice and
retains its explicit constructor validation comment; the five new findings
are resolved without adding `# nosec`.

## Clean package smoke

The clean ZIP archive was created from the exact candidate and extracted
without the preserved dirty workspace files:

```text
candidate_commit=7c62108517f9f13cacfb1a418b2f227e09b3f8a3
source_archive_files=933
build_exit=0
twine_exit=0
install_exit=0
import_exit=0
import_output=1.1.3 AsyncDocumentConnector ingest_documents_async
doctor_exit=0
doctor_output={"checks": {"core": true, "evaluation": true, "events": true, "execution": true, "interop": true, "retrieval": true, "server": true, "sessions": true}, "network": false, "ready": true, "status": "SUCCESS", "version": "1.1.3"}
wheel_entries=110
sdist_entries=909
sdist_excluded_demo_n8n_entries=0
wheel_maple_entries=104
maple_oss-1.1.3-py3-none-any.whl=BC3DFB7B44DEE2903E75E7BC5A89569F8D83A09E147E1A82BC4D2EC6BF801437
maple_oss-1.1.3.tar.gz=37793076764C70328EFC2CD10441EF3DAF5DB8A7A13A5835714B505BD46F4BF6
```

An earlier `git archive | tar` PowerShell byte-stream attempt failed with
`tar.exe: Damaged tar archive (bad header checksum)` before extraction; the
direct ZIP archive method above was the successful verification and is the
only package result claimed.

## Verdict

**QA:** PASS for Slice 212.  **Security:** SIGN-OFF for the scoped change.

The broader v1.1.4 release remains conditional on the existing CI/header
policy decision, version promotion, clean-main/release process, unavailable
Gitleaks and independent verification, and explicit human tag/publication
approval. No external registry, cloud, or website action occurred.
