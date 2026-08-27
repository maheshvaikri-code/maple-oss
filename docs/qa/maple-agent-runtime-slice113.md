# QA + Security Report — MAPLE Agent Runtime Slice 113 @ d26973f

**QA Engineer · Security Reviewer · Date:** 2026-08-26
**Build under test:** feature commit `d098e3a` plus timeout-validation fix
`d26973f`; review artifact follows in `0261400`

## Acceptance criteria verification

| # | Criterion | How executed | Evidence (real output) | Pass |
|---|---|---|---|---|
| 1 | Optional HTTP export sends the existing redacted event envelope with bearer authentication. | Focused event/server suite with a local HTTP collector. | `22 passed in 4.46s` | Yes |
| 2 | Endpoint, token, request-body, response-body, and timeout boundaries fail closed. | Code review plus focused exporter regressions for remote HTTP, control characters, oversized events, unreachable transport, and non-finite timeouts. | Included in focused `22 passed` result; changed-boundary mypy also passed. | Yes |
| 3 | Export failure cannot fail the local event publication. | Local unreachable endpoint through `EventStream`. | Included in focused `22 passed` result; exporter failure counter remains isolated. | Yes |
| 4 | Existing application behavior remains green. | Tracked regression excluding the five user-owned untracked Doctrine tests. | `1279 passed, 1 skipped in 212.83s (0:03:32)` | Yes |
| 5 | Public exports, docs, and implementation pass local checks. | Black, Ruff, changed-boundary mypy, compile, and diff checks. | Black: `4 files would be left unchanged`; Ruff: `All checks passed!`; mypy: `Success: no issues found in 1 source file`; `compileall exit: 0`; `git diff --check exit: 0`. | Yes |

## Adversarial and edge matrix

| Input/scenario | Expected | Observed | Pass |
|---|---|---|---|
| Event contains nested `secret` data | EventStream redacts before export | Collector receives `[REDACTED]` | Yes |
| Bearer credential | Header-only transport | `Authorization: Bearer local-token`; no URL credential | Yes |
| Remote `http` endpoint | Reject before network call | `ValueError` requiring HTTPS | Yes |
| Loopback `http` endpoint | Permit for local collectors | Local test collector receives the POST | Yes |
| URL userinfo, query, fragment, or control characters | Reject at construction | Validation path returns `ValueError` | Yes |
| Token control characters or blank token | Reject before header construction | Validation path returns `ValueError` | Yes |
| Oversized event JSON | Reject without network call | `ValueError` | Yes |
| Oversized response body | Reject at bounded read | Source-level bounded read is `max_response_bytes + 1` | Yes |
| `NaN`, positive infinity, or negative infinity timeout | Reject as non-finite | `ValueError`, covered by regression | Yes |
| Unreachable collector | Preserve event and count exporter failure | Publish remains successful; `exporter_failures == 1` | Yes |
| Remote retry/persistence behavior | No implicit duplicate or durable side effect | One synchronous POST; no retry, queue, batching, or persistence code | Yes |

## Regression

Focused suite: `22 passed in 4.46s`.

Final tracked suite: `1279 passed, 1 skipped in 212.83s (0:03:32)`.
The skipped test is the existing NATS dependency-gated test. The five ignored
files are user-owned untracked Doctrine tests, not skipped tracked application
coverage. No flaky retry or retry-until-lucky behavior was used.

## Package evidence

Clean archive source: `git archive HEAD` at candidate `b4e7167`.

- `python -m build --wheel --sdist`: exit `0`; built wheel/sdist `1.1.3`.
- `python -m twine check dist/maple_oss-1.1.3-py3-none-any.whl
  dist/maple_oss-1.1.3.tar.gz`: both artifacts `PASSED`.
- Wheel entries: `104`; the wheel contains `maple/autonomy/events.py`.
- sdist entries: `525`.
- Required public files: `6/6` present — `README.md`, `LICENSE`,
  `CHANGELOG.md`, ADR-059, this QA report, and the Slice 113 review report.
- Workspace-only audit: `0` entries for `AGENTS.md`, `CLAUDE.md`,
  `COMMERCIAL_LICENSE.md`, `Makefile`, `docs/brief.md`, and `docs/maximus.md`.

The package candidate is locally reproducible and is not published.

## Bugs found

| # | Repro steps (minimal) | Severity | Fixed @ | Re-verified | Regression test |
|---|---|---|---|---|---|
| 1 | Construct `HttpEventExporter(..., timeout_seconds=math.nan)` or with positive/negative infinity. | Minor | `d26973f` | Focused suite `22 passed` | `test_http_event_exporter_is_bounded_and_requires_secure_remote_transport` |

## Security sweep

- Secret-pattern scan of the exact feature commit:
  `manual secret-pattern scan: no matches`.
- `gitleaks`: unavailable in the environment.
- `bandit`: unavailable in the environment.
- Injection review: payloads use JSON serialization; the exporter adds no
  shell, SQL, template, `eval`, `exec`, or pickle path. Endpoint userinfo,
  query/fragment, and control-character inputs are rejected.
- Authentication review: bearer credentials are validated and sent only in an
  `Authorization` header; non-loopback HTTP is rejected in favor of HTTPS.
- Bounds review: endpoint URL, event body, response body, and timeout are
  explicit finite/bounded controls. Export errors do not include remote body
  contents and are isolated from the run.
- Dependency review: no new runtime dependency; implementation uses the
  standard library only.
- Dependency audit command: `python -m pip_audit --progress-spinner off`.
  Real result: `Found 383 known vulnerabilities in 77 packages`; the command
  exited `1`. It also reported multiple local packages that could not be
  audited from PyPI. This is an environment/release dependency-governance
  finding, not silently accepted as clean.

**Security verdict:** **VETO** for the repository release gate because the
environment dependency audit is not clean and `gitleaks`/`bandit` are
unavailable. No human override.

**QA verdict:** pass for Slice 113 behavior, static checks, regression
coverage, and package evidence; release remains conditional on
dependency-governance disposition.
