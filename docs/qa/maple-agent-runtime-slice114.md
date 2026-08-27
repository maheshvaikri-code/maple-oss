# QA + Security Report — MAPLE Agent Runtime Slice 114 @ 6771fa3

**QA Engineer · Security Reviewer · Date:** 2026-08-26
**Build under test:** implementation commits `8ec8357` and `d41c65a`, plus
release documentation commit `6771fa3`; review artifact follows in `fd28a06`

## Acceptance criteria verification

| # | Criterion | How executed | Evidence (real output) | Pass |
|---|---|---|---|---|
| 1 | Remote operators can list and inspect durable human-input requests. | Authenticated `RunClient` against a loopback `RunServer` configured with `InMemoryHumanInputStore`. | Included in focused result: `19 passed in 5.17s`. | Yes |
| 2 | Remote response, rejection, continuation, and consume operations preserve store semantics. | End-to-end multi-round response/continue/response/consume path; store remains schema and state authority. | Included in focused result: `19 passed in 5.17s`. | Yes |
| 3 | Interaction routes require transport authentication when a store is configured. | Constructor invariant, authenticated round trip, and unauthenticated client regression. | `ValueError` without server token; unauthorized client returns `UNAUTHORIZED`. | Yes |
| 4 | Existing application behavior remains green. | Tracked regression excluding the five user-owned untracked Doctrine tests. | `1283 passed, 1 skipped in 275.08s (0:04:35)` | Yes |
| 5 | Public docs and implementation pass local checks. | Black, Ruff, changed-boundary mypy, compile, and diff checks. | Black: `2 files left unchanged`; Ruff: `All checks passed!`; mypy: `Success: no issues found in 1 source file`; compile and diff checks exit `0`. | Yes |

## Adversarial and edge matrix

| Input/scenario | Expected | Observed | Pass |
|---|---|---|---|
| Human-input store configured without `auth_token` | Fail closed at construction | `ValueError` | Yes |
| Missing or wrong bearer token | Deny before route dispatch | `UNAUTHORIZED` | Yes |
| Pending list limit `0` or `1001` | Reject locally | `HUMAN_INPUT_LIMIT_INVALID` | Yes |
| Missing human-input store | Do not expose an empty or fake surface | `HUMAN_INPUT_STORE_UNAVAILABLE` | Yes |
| Unknown interaction | Typed not-found response | `HUMAN_INPUT_NOT_FOUND` | Yes |
| Invalid response or continuation schema | Store validation remains authoritative | Typed store error; no state bypass | Yes |
| Configured actor authorizer | Propagate `actor_id` to store policy | Store remains mutation authority | Yes |
| Oversized request/response | Existing server bounds apply | Existing bounded body/read/write paths reused | Yes |
| Interaction ID with unsafe path content | URL-encode or reject | `RunClient` uses encoded path segments and existing identifier checks | Yes |
| Automatic run resume or duplicate side effect | No implicit scheduling claim | Transport only mutates/consumes the interaction; resume remains explicit | Yes |

## Regression

Focused server/interaction suite: `19 passed in 5.17s`.

Final tracked suite: `1283 passed, 1 skipped in 275.08s (0:04:35)`.
The skipped test is the existing NATS dependency-gated test. The five ignored
files are user-owned untracked Doctrine tests, not skipped tracked application
coverage. No flaky retry or retry-until-lucky behavior was used.

## Package evidence

Pending the clean archive build after this QA artifact is committed. The
candidate must be built from `git archive`, pass wheel/sdist metadata checks,
contain ADR-060 and the Slice 114 QA/review records, and contain none of the
workspace-only governance files. Publication is not authorized by this task.

## Bugs found

| # | Repro steps (minimal) | Severity | Fixed @ | Re-verified | Regression test |
|---|---|---|---|---|---|
| 1 | Configure `RunServer(..., human_input_store=store)` without a bearer token. | Major risk if misconfigured | `d41c65a` | Focused suite `19 passed` | `test_run_server_requires_authentication_for_human_input_transport` |

## Security sweep

- Secret-pattern scan of the final implementation commit:
  `manual secret-pattern scan: no matches`.
- `gitleaks`: unavailable in the environment.
- `bandit`: unavailable in the environment.
- Authentication review: human-input store configuration now requires a bearer
  token; authorization executes before route dispatch; actor authorization stays
  inside the configured store.
- Injection review: route identifiers are URL-encoded by the client; request
  data uses JSON serialization; no shell, SQL, template, `eval`, `exec`, or
  pickle path was added.
- Bounds/fail-closed review: existing HTTP path/body/response limits apply;
  list limits are capped; missing stores and unsupported multi-round stores
  return typed errors; transport does not schedule run resumption.
- Dependency review: no new runtime dependency; implementation uses the
  standard library and existing store interfaces.
- Dependency audit command: `python -m pip_audit --progress-spinner off`.
  Real result: `Found 383 known vulnerabilities in 77 packages`; the command
  exited `1`. It also reported multiple local packages that could not be
  audited from PyPI. This is an environment/release dependency-governance
  finding, not silently accepted as clean.

**Security verdict:** **VETO** for the repository release gate because the
environment dependency audit is not clean and `gitleaks`/`bandit` are
unavailable. No human override.

**QA verdict:** pass for Slice 114 behavior, static checks, regression
coverage, and security-boundary review; release remains conditional on
dependency-governance disposition and the pending clean package candidate.
