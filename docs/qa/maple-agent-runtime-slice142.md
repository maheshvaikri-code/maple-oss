# MAPLE Agent Runtime Slice 142 QA

Date: 2026-08-28

Scope: bounded principal scopes for the authenticated local `RunServer`
control plane. A host may configure one immutable `Principal` with exact or
family scopes. Known health, workflow, agent, approval, interaction, handoff,
and event routes authorize before body reads; identity issuance, TLS, tenancy,
and delegated remote identity remain outside the contract.

Implementation commit: `dae1ebd`
Documentation commit: `685110d`

## Acceptance evidence

- Focused server suite: `33 passed in 14.21s`
- Exact tracked committed-HEAD suite: `1386 passed, 1 skipped in 234.74s`
  from `1387` collected tests
- Whole-package mypy: `Success: no issues found in 97 source files`
- Black on changed Python files: `4 files would be left unchanged.`
- isort on changed Python files: passed
- Ruff: `All checks passed!`
- `python -m compileall -q maple tests`: passed
- `git diff --check b955a68..HEAD`: passed
- Documentation fence marker check: `204`, even
- Project dependency audit: `No known vulnerabilities found`
- Source-only secret scan: `source_secret_high_confidence_matches=0`
- Source-only dangerous-construct scan: `source_dangerous_construct_matches=0`

## Behavioral coverage

- `Principal` validates bounded IDs and scope names, supports exact scopes,
  family wildcards, and the legacy all-route wildcard, and rejects malformed
  or empty scope sets.
- `RunServer` requires a bearer token when a principal policy is configured;
  missing route scopes return `403` and discard bounded request bodies before
  route handlers parse them.
- Health and workflow inspection/invocation routes demonstrate separate
  `health:read`, `workflow:read`, and `workflow:invoke` permissions.
- Existing authenticated servers without `auth_principal` retain wildcard
  compatibility, while unauthenticated loopback servers retain their prior
  local behavior.
- The policy does not issue or introspect identities and does not claim TLS,
  tenancy, per-agent delegation identity, notification delivery, scheduling,
  or exactly-once effects.

## Package evidence

The clean file-backed `git archive HEAD` package built successfully. Wheel and
source distribution both passed Twine checks; the wheel contained `104`
entries and the source distribution contained `609` entries. No-dependency
wheel-target installation and principal-scope import smoke exited `0` and
reported:
`clean_archive_principal_scope_smoke=passed`.

## Disposition

Local behavioral, static, package, and source-security checks pass for this
slice. Environment-wide dependency governance remains a release veto from
the prior audit: `384` known vulnerabilities across `77` installed packages.
No publication, deployment, cloud action, or website update was performed.
