# Slice 78 QA — Explicit unsupported capability inventory

**Status:** PASS for the documentation boundary; no runtime behavior changed.

## Scope

This slice makes the remaining intentional `NOT_IMPLEMENTED` paths explicit
in the release brief and public README, then pins the existing fail-closed
contracts with regression assertions. It does not add Redis, mutual-TLS,
OAuth2, subprocess, browser, or hosted-sandbox behavior.

## Evidence

- `rg -n "NOT_IMPLEMENTED" maple` identifies only the documented Redis and
  mutual-TLS/OAuth2 boundaries plus intentional protocol/serialization
  fallback paths.
- `python -m pytest tests/state/test_store.py tests/security/test_authentication.py
  --no-cov -p no:dash -p no:benchmark -q --tb=short` -> `73 passed in 3.44s`.
- The added assertions cover Redis `list_keys` and both deferred authentication
  methods; all existing state/authentication behavior remains green.
- `ruff check tests/state/test_store.py tests/security/test_authentication.py`
  -> `All checks passed!`
- No dependency, network, cloud, publication, or website action occurred.

## Disposition

The release claim is now narrower and auditable: supported local state,
authentication, trusted execution, and code-block extraction are distinguished
from deferred or unsupported integrations. Any future implementation requires
a new scoped brief and security/dependency review.
