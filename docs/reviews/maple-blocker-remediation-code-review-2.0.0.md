# Code Review — MAPLE 2.0.0 blocker remediation

<!-- G4 artifact. This is a local serial review record; independent session
     approval is not claimed when a fresh verifier session does not return. -->

**Reviewer role:** Code Reviewer · **Date:** 2026-08-30
**Reviewed against:** the MAPLE 2.0.0 release brief, release checklist, and
the final working-tree diff before commit.

## Executed

```text
python -m pytest tests/security tests/test_release_workflows.py -q -o addopts=
253 passed in 14.53s

python -m black --check maple
All done! ✨ 🍰 ✨
103 files would be left unchanged.

python -m flake8 maple/ --max-line-length=88 --extend-ignore=E203,W503,W291,W293,E302,E402,F401,F811,F841 --count --statistics
0

python -m mypy maple/ --ignore-missing-imports
Success: no issues found in 103 source files
```

## Findings

| # | Sev | Location | Finding | Resolution |
|---|---|---|---|---|
| 1 | [BLOCKER] | `maple/security/authentication.py:147-158` | A shared JWT fallback could let installations accept forged tokens. | Fixed by requiring an explicit secret of at least 32 UTF-8 bytes and returning `JWT_SECRET_NOT_CONFIGURED`; regression coverage is in `tests/security/test_authentication.py`. |
| 2 | [BLOCKER] | `maple/security/authentication.py:239-278` | Revoked JWTs were rejected by direct verification but could re-enter through `authenticate()`. | Fixed by checking `revoked_tokens` before JWT decoding; `test_authenticate_rejects_revoked_jwt` covers the path. |
| 3 | [BLOCKER] | `.github/workflows/release.yml:38-48`, `.github/workflows/publish.yml:196-209` | Release tags were passed to shell commands without a validation/data boundary. | Fixed with semver validation and quoted environment variables; static regression checks are in `tests/test_release_workflows.py`. |
| 4 | [BLOCKER] | `maple/core/result.py`, `maple/resources/manager.py`, `maple/autonomy/mcp_tools.py`, `maple/autonomy/tools.py`, `maple/security/authentication.py` | Python 3.8 could evaluate built-in generic annotations during import. | Fixed with future annotations and a Python 3.8 compile/import probe; Python 3.8 is restored to both test matrices. |
| 5 | [MINOR] | `README.md:1-23` and throughout | The prior concise README omitted the historical logo, badges, and practical release guidance. | Restored the logo/badges and reinserted infrastructure, integrations, team, resource, security, state, n8n, testing, and example usage without the removed framework-parity comparison section. |

## Scope check

The implementation matches the requested blocker-remediation slice. No new
dependency, website deployment, cloud call, registry upload, release tag, or
protected-branch mutation was made. README-only additions were validated for
Python syntax and local links.

## Verdict

**Local G4 review: Pass — zero open code blockers.** Four fresh independent
reviewer sessions were attempted through the available reviewer tool (two
code-review attempts, one security attempt, and one QA attempt), but each timed
out without returning a report and was closed. Their absence is an open process
gate, not a fabricated sign-off; this artifact records the limitation
explicitly.
