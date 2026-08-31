# MAPLE 2.0.0 Serial Blind Review Session

**Target:** `a5182521370ede3e5a157281b2a37ea2e1133198`
**Branch:** `feat/maple-agent-runtime`
**Review date:** 2026-08-30
**Mode:** Doctrine G4/G5 role-separated review performed serially in this environment. A callable fresh independent reviewer/session mechanism was unavailable; this is not independent human sign-off.

## Gate verdict

**NO-GO for publication or merge approval.**

The branch is regression-green on Python 3.12 and the exact archived HEAD is leak-free, but the review found two blockers and multiple major issues:

| Gate | Result | Evidence |
|---|---|---|
| Code review | Changes requested | [blind code review](maple-blind-code-review-2.0.0.md) |
| Security review | VETO | [blind security review](../qa/maple-blind-security-review-2.0.0.md) |
| QA | Conditional / no-go | [blind QA review](../qa/maple-blind-qa-review-2.0.0.md) |
| Full tests | Pass | 1906 passed, 1 skipped |
| Package build | Pass | sdist/wheel and `twine check` passed |
| HEAD archive secret scan | Pass | Gitleaks exit 0, no leaks found |
| Full history secret scan | Not clean | 3 known synthetic fixture/document matches, exit 1 |
| Protected branch | Not verified / currently unprotected | GitHub repository check reported `main` protected false and no rulesets |
| Website/cloud/registry | Intentionally untouched | Per publication plan and user instruction |

## Release blockers

1. The hard-coded default JWT signing key permits forged attacker/admin tokens.
2. The PyPI release-asset workflow interpolates an unquoted, attacker-influenced tag into a shell command with write-capable credentials.
3. Python 3.8 is declared supported but cannot import the package.

## Major remediation queue

- Enforce JWT secret provisioning and test fail-closed behavior.
- Make JWT revocation effective through every authentication path.
- Remove plaintext API-key retention and token-prefix logging.
- Separate production publication behind verifiable protected human approval and protected tags.
- Remove or clearly mark unsupported mTLS/OAuth2 methods.
- Add serializer-level input bounds for JSON/MessagePack.
- Reconcile release metadata and executable demo claims with the actual 2.0.0 candidate state.

## Human-controlled next gates

After remediation, the human release authority must still verify fresh independent review sessions, final Gitleaks disposition/history policy, protected-branch and tag configuration, website target/domain, cloud provider target, registry targets, and explicit tag/publication approvals. This review did not perform any external publication or infrastructure action.
