# MAPLE 2.0.0 Blind Security Review

**Review lane:** Security Reviewer
**Review mode:** Serial blind author-run review; no independent reviewer session is callable in this environment
**Target:** `a5182521370ede3e5a157281b2a37ea2e1133198`
**Inputs:** release brief, publication plan, and `origin/main...HEAD`; existing review narratives were not used as review input
**Security disposition:** **VETO / NO-GO** until blocker and major findings are remediated or explicitly accepted by the human release authority.

## Findings

### SEC-001 — BLOCKER — Default JWT signing key permits forged privileged tokens

**Location:** `maple/security/authentication.py:130-132`

`AuthenticationManager` uses a hard-coded default JWT secret when no configuration is supplied. A live probe created a token for `attacker` with `admin` permission using the documented default and `verify_token()` accepted it:

```text
{'accepted': True, 'principal': 'attacker', 'permissions': ['admin']}
```

**Required action:** Fail closed when a production JWT secret is absent; require an explicit high-entropy secret or host-owned key provider. Add a regression test proving the default configuration cannot validate attacker-created tokens.

### SEC-002 — BLOCKER — Release-asset workflow interpolates an untrusted tag into a shell command

**Location:** `.github/workflows/publish.yml:199`

The release-asset step runs `gh release upload ${{ github.ref_name }} dist/*` without quoting or passing the ref through an environment variable. Git accepts a semicolon-bearing `v*` tag (`git check-ref-format` returned exit 0), so a tag can alter the shell command. The job has `contents: write` and exposes `GITHUB_TOKEN`.

**Required action:** Pass the tag through a validated environment variable and quote it, or use an action/API input that does not invoke a shell. Add workflow validation for the tag format and a static workflow-security test.

### SEC-003 — MAJOR — Revoked JWTs can be reauthenticated

**Location:** `maple/security/authentication.py:186-195, 229-270, 505-552`

`revoke_token()` records the token in `revoked_tokens`, but `_authenticate_jwt()` does not consult that set. A revoked token therefore fails `verify_token()` but succeeds when passed back through `authenticate()`:

```text
{'verify_after_revoke': False, 'reauthenticate_after_revoke': True, 'reauthenticated_principal': 'agent'}
```

**Required action:** Check revocation before JWT acceptance and add a regression test covering both verification and authentication entry points.

### SEC-004 — MAJOR — Production PyPI publication remains automatically reachable from a published release

**Locations:** `.github/workflows/release.yml:3-6,95-101`; `.github/workflows/publish.yml:3-5,127-145`

A `v*` tag runs the release workflow, which creates a published GitHub Release. The `release: published` event then enables the PyPI publish job. The workflow has an environment named `pypi`, but its required-reviewer configuration is external and cannot be verified from this repository. The repository-side workflow contains no explicit production authorization input equivalent to the Test PyPI path.

**Required action:** Keep production publication behind a protected environment with required human reviewers and/or a separate manually authorized workflow. Protect release tags. Verify and record the actual GitHub environment/ruleset configuration before publication.

### SEC-005 — MAJOR — Authentication API advertises methods that are explicitly not implemented

**Location:** `maple/security/authentication.py:52-57,402-431`

`AuthMethod` exposes `MUTUAL_TLS` and `OAUTH2`, while both paths return `NOT_IMPLEMENTED`. The class is documented as a production/enterprise authentication manager. Consumers can reasonably treat these enum values as supported security controls.

**Required action:** Remove unsupported methods from the public supported set until implemented, or provide explicit capability reporting and documentation that prevents them from being treated as security boundaries.

### SEC-006 — MAJOR — API keys are retained in plaintext

**Location:** `maple/security/authentication.py:123,343-407,622-636`

API keys are used as raw dictionary keys and stored as raw values. A memory inspection, crash dump, debug instrumentation, or accidental object exposure reveals reusable credentials.

**Required action:** Store a one-way keyed hash/fingerprint and compare using a constant-time method; provide rotation/revocation semantics and tests. Do not serialize or log the raw key.

### SEC-007 — MINOR — Bearer token prefix is written to logs

**Location:** `maple/security/authentication.py:552`

`revoke_token()` logs the first 16 characters of a bearer token. Partial bearer credentials are still sensitive correlation material and violate the repository’s no-token-logging security boundary.

**Required action:** Log only a non-reversible identifier or a separately generated token fingerprint.

### SEC-008 — MINOR — General JSON/MessagePack deserialization lacks a serializer-level byte bound

**Location:** `maple/core/serialization.py:213-220,296-307`

Pickle and protobuf paths enforce a 1 MiB bound, but the public JSON and MessagePack paths do not. A 1.86 MiB MessagePack payload was accepted and materialized 400,000 list entries:

```text
{'payload_bytes': 1868556, 'over_1MiB': True, 'accepted': True}
```

The HTTP server has separate request limits, but callers using `Serializer.deserialize()` directly receive no equivalent protection.

**Required action:** Add configurable byte/depth/object limits or document that callers must enforce an input boundary before invoking these methods. Add oversized and nested-input regression tests.

## Scan evidence

- Isolated clean environment with base/dev/security plus LLM/adapter extras: `No known vulnerabilities found`; exit 0. The local `maple-oss` package was correctly reported as not present on PyPI and was not audited as a third-party package.
- Bandit: exit 0, no findings.
- Exact archived HEAD scan with Gitleaks 8.30.1: `no leaks found`; exit 0.
- Full repository-history Gitleaks scan: 3 heuristic matches in historical test/document fixtures; exit 1. These are known synthetic/placeholder values, not secrets in the archived HEAD, but the historical gate is not zero-finding.

## Disposition

SEC-001 and SEC-002 are release blockers. SEC-003 through SEC-006 are major remediation items. SEC-007 and SEC-008 remain security hardening work. No security sign-off is granted.
