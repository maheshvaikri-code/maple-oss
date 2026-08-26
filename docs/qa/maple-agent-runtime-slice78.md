# Slice 78 QA — Explicit unsupported capability inventory

**Status:** PASS for the documentation boundary; no runtime behavior changed.

## Scope

This slice makes the remaining intentional `NOT_IMPLEMENTED` paths explicit
in the release brief and public README. It does not add Redis, mutual-TLS,
OAuth2, subprocess, browser, or hosted-sandbox behavior.

## Evidence

- `rg -n "NOT_IMPLEMENTED" maple` identifies only the documented Redis and
  mutual-TLS/OAuth2 boundaries plus intentional protocol/serialization
  fallback paths.
- Existing state and authentication regressions cover fail-closed behavior;
  no test files were changed in this slice.
- No dependency, network, cloud, publication, or website action occurred.

## Disposition

The release claim is now narrower and auditable: supported local state,
authentication, trusted execution, and code-block extraction are distinguished
from deferred or unsupported integrations. Any future implementation requires
a new scoped brief and security/dependency review.
