# Slice 212 implementation plan - restricted host-owned HTTP transports

**Class:** L
**Status:** G0-G6 complete locally; external publication remains human-gated
**Brief:** `docs/briefs/maple-agent-runtime-slice212.md`
**ADR:** `docs/adr/156-restricted-host-http-transports.md`

## Ordered gates

| Gate | Work | Evidence |
| --- | --- | --- |
| G0 | Define the B310 finding, affected host-owned transports, security scope, and non-goals. | Slice brief and threat sketch. |
| G1 | Choose a private HTTP(S)-only stdlib opener with same-origin redirect controls. | ADR-156 with alternatives and invalidation triggers. |
| G2 | Replace the five `urlopen` call sites and add a redirect regression. | `ecaa7e7`; `tests/autonomy/test_events.py`. |
| G3 | Preserve public transport behavior, documentation, and dependency-free packaging. | `7c62108`; changelog/API/parity updates. |
| G4 | Review handler allowlist, URL credentials, origin matching, downgrade behavior, error mapping, and scope. | `docs/reviews/maple-agent-runtime-slice212.md`; no open findings. |
| G5 | Execute focused/full regressions, static/security/audit gates, and clean package smoke. | `docs/qa/maple-agent-runtime-slice212.md`; all scoped gates pass. |
| G6 | Reconcile release evidence without version promotion, tag, registry write, cloud, or website action. | `docs/releases/v1.1.4.md`; release remains conditional for existing human-gated items. |

## Implementation slices

1. Add the private opener with HTTP, HTTPS, proxy, error, and constrained
   redirect handlers only.
2. Reject malformed/non-HTTP(S)/credentialed request and redirect targets;
   reject cross-origin and HTTPS downgrade redirects.
3. Route event export, event batch forwarding, approval notification,
   human-input notification, and workflow client requests through the helper.
4. Preserve bounds and existing transport error behavior with a regression
   proving unsafe redirects cannot leave the host-owned boundary.

## Rollback and scope boundary

Rollback is a code-only revert of `ecaa7e7`; no state migration exists. This
slice does not select TLS termination, certificate pinning, OAuth/mTLS,
retries, persistence, hosted aggregation, or cross-origin redirect support.

## Gate evidence snapshot

The exact candidate `7c62108517f9f13cacfb1a418b2f227e09b3f8a3` produced:

```text
focused transport/server regression: 136 passed in 42.40s
full suite: 1904 passed, 1 skipped in 409.86s (0:06:49)
black: 103 files would be left unchanged.
isort: exit 0
ruff: All checks passed!
mypy: Success: no issues found in 103 source files
compileall: exit 0
bandit: exit 0
pip-audit: No known vulnerabilities found
workflow contract tests: 9 passed in 0.38s
source archive files: 933
wheel entries: 110
sdist entries: 909
build/twine/install/import/doctor: exit 0
```

Gitleaks and a fresh independent verifier session are unavailable in this
tool context; no pass is claimed for either. Preserved user-owned workspace
changes remain outside the commits.
