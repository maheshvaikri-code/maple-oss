# QA + Security Report — MAPLE Agent Runtime Slice 112 @ 74f8655

**QA Engineer** · **Security Reviewer** · **Date:** 2026-08-26
**Build under test:** feature commit `74f8655`; review artifact follows in
`096a636`

## Acceptance criteria verification

| # | Criterion | How executed | Evidence (real output) | Pass |
|---|-----------|--------------|------------------------|------|
| 1 | `RunClient` covers health, run, inspect, and authenticated transport | `python -m pytest tests/autonomy/test_server.py -q --no-cov -p no:dash -p no:benchmark --tb=short --no-header` | `7 passed in 3.77s` | Yes |
| 2 | Request, path, response, and timeout boundaries return typed failures | Focused tests exercise invalid schemes/userinfo, control characters, oversized request/response, invalid state, and unreachable service | Included in the focused `7 passed` result | Yes |
| 3 | Bearer authentication fails closed and does not weaken loopback defaults | Focused tests exercise missing and wrong tokens; code gate checks constant-time comparison, all-route authorization, `WWW-Authenticate`, and HTTPS for authenticated non-loopback URLs | Included in the focused `7 passed` result | Yes |
| 4 | Existing application behavior remains green | Tracked regression excluding the five user-owned untracked Doctrine tests | `1276 passed, 1 skipped in 255.31s (0:04:15)` | Yes |
| 5 | Public surface and implementation pass local static gates | Black, Ruff, changed-boundary mypy, compile, and diff checks | Black unchanged; `All checks passed!`; `Success: no issues found in 3 source files`; compile and diff exit `0` | Yes |

## Adversarial & edge matrix

| Input/scenario | Expected | Observed | Pass |
|----------------|----------|----------|------|
| Missing bearer token | `401 UNAUTHORIZED` | `401`, structured `UNAUTHORIZED` error | Yes |
| Wrong bearer token | `401 UNAUTHORIZED` | `Result.err` with `UNAUTHORIZED` | Yes |
| Authenticated non-loopback `http` URL | Reject before request | `ValueError` requiring HTTPS | Yes |
| Token or URL control characters | Reject before header/request creation | `ValueError` | Yes |
| Non-HTTP(S), userinfo, query, or fragment URL | Reject | `ValueError` | Yes |
| Oversized serialized request | Typed size error, no network call | `REQUEST_TOO_LARGE` | Yes |
| Oversized response | Typed size error | `RESPONSE_TOO_LARGE` | Yes |
| Unreachable endpoint | Bounded transport error | `TRANSPORT_ERROR` | Yes |
| Invalid workflow state | Typed input error | `INVALID_STATE` | Yes |
| Unicode/unsafe route identifiers | URL-encode or fail closed | `RunClient` encodes segments; invalid segments return `INVALID_IDENTIFIER` | Yes |
| Duplicate/external effects | No implicit retry claim | Client performs no automatic retries; idempotency remains host-owned | Yes |

## Regression

Focused suite: `7 passed in 3.77s`.

Tracked suite: `1276 passed, 1 skipped in 255.31s (0:04:15)`.
The skipped test is the existing NATS dependency-gated test. The five
ignored files are user-owned untracked Doctrine tests, not skipped tracked
application coverage. No flake or retry-until-lucky behavior was used.

## Package evidence

Clean archive source: `git archive HEAD` at candidate `c7fe5bd`.

- `python -m build --wheel --sdist`: exit `0`.
- `python -m twine check dist/maple_oss-1.1.3-py3-none-any.whl dist/maple_oss-1.1.3.tar.gz`:
  both artifacts `PASSED`.
- sdist entries: `522`.
- Required public files: `6/6` present — `README.md`, `LICENSE`,
  `CHANGELOG.md`, ADR-058, this QA report, and the Slice 112 review report.
- Workspace-only audit: `0` entries for `AGENTS.md`, `CLAUDE.md`,
  `COMMERCIAL_LICENSE.md`, `Makefile`, `docs/brief.md`, and `docs/maximus.md`.

The package candidate is locally reproducible and is not published.

## Bugs found

| # | Repro steps (minimal) | Severity | Fixed @ | Re-verified | Regression test |
|---|----------------------|----------|---------|-------------|-----------------|
| 1 | Review client request and authenticated remote URL boundary | Minor | `74f8655` | Focused suite `7 passed` | `test_run_client_bounds_inputs_and_normalizes_transport_errors` |

## Security sweep (per `skills/security.md`)

- Secrets scan: `gitleaks` unavailable; manual pattern scan of feature files:
  `manual secret-pattern scan: no matches`.
- Injection review: path segments are URL-encoded; JSON uses `json.dumps`; no
  shell, SQL, template, `eval`, `exec`, or pickle path was added.
- Authentication: route authorization executes before dispatch; missing and
  wrong tokens are denied; bearer tokens are not placed in URLs; authenticated
  non-loopback HTTP is rejected.
- Bounds/fail-closed: request body, path, response, and timeout boundaries are
  explicit; malformed transport responses become typed errors; server remains
  loopback-only.
- Dangerous constructs: `bandit` unavailable; no new dependency was added and
  this slice uses the Python standard library only.
- Dependency audit command: `python -m pip_audit --progress-spinner off`.
  Real result: `Found 383 known vulnerabilities in 77 packages`; the command
  exited `1`. It also reported multiple local packages that could not be
  audited from PyPI. This is an environment/release dependency-governance
  finding, not silently accepted as clean.

**Security verdict:** **VETO** for the repository release gate because the
environment dependency audit is not clean and `gitleaks`/`bandit` are
unavailable. No human override.

**QA verdict:** pass for Slice 112 behavior, static gates, and package
evidence; release remains conditional on dependency-governance disposition.
