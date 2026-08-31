# QA + Security Report — MAPLE 2.0.0 blocker remediation

**QA Engineer · Security Reviewer** · **Date:** 2026-08-30
**Build under test:** committed MAPLE 2.0.0 HEAD; package metadata reports
`2.0.0`.

## Acceptance criteria verification

| # | Criterion | How executed | Evidence | Pass |
|---|---|---|---|---|
| 1 | Python 3.8 imports the package | `py -3.8 -m compileall -q maple` and import probe | `python38_import= 2.0.0` | Yes |
| 2 | JWT has no shared default and revocation is enforced | Focused security tests and live forged-token/revoked-token probes | `253 passed`; forged token returns `JWT_SECRET_NOT_CONFIGURED`; revoked auth returns `TOKEN_REVOKED` | Yes |
| 3 | Release tag handling is validated and shell-safe | Workflow contract tests | `tests/test_release_workflows.py` included in `253 passed` | Yes |
| 4 | README retains the public header and documents the 2.0.0 surface | Header inspection, code-block AST parse, local-link check, smoke examples | Logo/badges present; `README_python_blocks_syntax=12`; `README_local_links=8`; no missing links | Yes |
| 5 | Package artifacts are publishable in shape | `python -m build` and `python -m twine check dist\maple_oss-2.0.0*` | `build_exit=0`, `twine_exit=0`; both artifacts `PASSED` | Yes |

## Adversarial & edge matrix

| Input/scenario | Expected | Observed | Pass |
|---|---|---|---|
| Missing JWT secret | Fail closed | `JWT_SECRET_NOT_CONFIGURED` | Yes |
| 31-byte JWT secret | Fail closed | `JWT_SECRET_NOT_CONFIGURED` | Yes |
| 32-byte Unicode-equivalent secret | Accept | `True` | Yes |
| Forged token signed with the removed shared default | Reject | `JWT_SECRET_NOT_CONFIGURED` | Yes |
| Revoked valid JWT through `authenticate()` | Reject | `TOKEN_REVOKED` | Yes |
| Empty JWT token | Typed validation failure | `MISSING_JWT_TOKEN` | Yes |
| README Python snippets | Parse without syntax errors | `README_python_blocks_syntax=12` | Yes |
| Tracked source secret scan | No leaks | Gitleaks 8.30.1: `no leaks found`, exit `0` | Yes |

## Regression

The final local release-equivalent run completed from committed HEAD:

```text
================ 1912 passed, 1 skipped in 1092.06s (0:18:12) =================
```

The focused security/workflow rerun completed after all implementation changes:

```text
253 passed in 14.53s
```

No flakes were observed. Black, isort, exact Flake8, mypy, Bandit, Python 3.8
compile/import, package build, Twine, offline doctor, and README smoke checks
also passed.

## Security sweep

- **Secrets:** Gitleaks 8.30.1 scanned an isolated copy of exactly the
  tracked working tree: `no leaks found`. A direct forged-default JWT probe
  failed closed. Revocation logs now contain only a short SHA-256 digest, not a
  token prefix.
- **Injection and shell boundaries:** release tags are semver-validated and
  passed to `gh` through quoted environment variables. No new shell, path,
  deserialization, or network input boundary was introduced.
- **Dependencies:** a clean temporary virtual environment installed
  `.[dev,security]`; `pip check` reported no broken requirements and
  `pip-audit` reported `No known vulnerabilities found`. The user-wide
  interpreter was not used as release evidence because it contains unrelated
  packages and 385 unrelated audit findings.
- **Dangerous constructs:** Bandit completed with no findings. MAPLE-produced
  code blocks remain data and are not executed; trusted handlers remain an
  explicitly documented host boundary.
- **Bounds/fail-closed behavior:** existing bounded queues, workflows, event
  streams, retrieval, serialization, and approval contracts remained covered by
  the full suite; new JWT and release-tag boundaries have direct regressions.

**Security verdict:** CONDITIONAL / VETO for publication pending the open
follow-ups in [the remediation plan](../plans/maple-2.0.0-follow-up-remediation.md).
The implemented blocker-remediation slice itself passed its security checks.
**QA verdict:** pass for the local acceptance criteria; publication remains
conditional.

Four fresh independent reviewer sessions were attempted through the reviewer
tool (two code-review attempts, one security attempt, and one QA attempt), but
each timed out before returning a report. No independent-session sign-off is
claimed; protected branch configuration and all external website/cloud/registry
actions remain human/external gates.
