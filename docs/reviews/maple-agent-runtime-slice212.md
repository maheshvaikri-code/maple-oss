# Code Review - restricted host-owned HTTP transports @ 7c62108

**Reviewer role:** Code Reviewer
**Date:** 2026-08-29
**Reviewed against:** `docs/briefs/maple-agent-runtime-slice212.md`,
`docs/adr/156-restricted-host-http-transports.md`, and
`docs/plans/maple-agent-runtime-slice212.md`
**Reviewed commits:** `ecaa7e7`, `7c62108`

## Executed

```text
python -m pytest tests/autonomy/test_events.py tests/autonomy/test_remote_notification_delivery.py tests/autonomy/test_remote_approval_notification.py tests/autonomy/test_server.py -q -o addopts=
136 passed in 42.40s

python -m pytest -q
1904 passed, 1 skipped in 409.86s (0:06:49)

python -m black --check --diff maple/
103 files would be left unchanged.

python -m isort --check-only --diff maple/
isort_exit=0

python -m ruff check maple tests
All checks passed!

python -m mypy maple --ignore-missing-imports
Success: no issues found in 103 source files

python -m bandit -r maple -ll -q
bandit_exit=0
```

## Findings

| # | Sev | Location | Finding | Resolution |
|---|---|---|---|---|
| - | - | - | No blocker, major, minor, or nit findings. | Pass |

## Review checks

- Correctness: all five former `urlopen` call sites use the one private
  opener, and existing HTTP/Result/error handling remains at the caller.
- Boundary: initial requests and redirects accept only absolute HTTP(S),
  reject URL credentials, and install no file/custom-scheme handlers.
- Redirects: hostname and explicit port must remain unchanged; HTTPS cannot
  downgrade to HTTP. Proxy support remains provided by the stdlib handler.
- Security: the fix removes five Bandit B310 findings without adding a
  suppression, network dependency, shell path, deserialization path, or
  credential-bearing URL.
- Scope: no public symbol, wire schema, version, TLS policy, retry behavior,
  persistence, hosted service, cloud action, or website behavior was added.
- Compatibility: focused event, notification, workflow, full regression,
  static, and package gates passed on the reviewed candidate.

Fresh independent verifier sessions were unavailable in this tool context;
this report does not claim an independent verifier sign-off.

## Verdict

- [x] Pass (0 BLOCKER, 0 MAJOR, 0 MINOR, 0 NIT)
- [ ] Return to build
