# MAPLE Agent Runtime Slice 144 Review Record

Date: 2026-08-28

## Review scope

Reviewed the capability declaration and router matching in
`maple/llm/capabilities.py`, its offline regression, and the associated ADR,
API, README, parity, changelog, plan, and QA documentation.

## Findings

No blocking defect found in the reviewed boundary.

The new flag is immutable with the existing frozen dataclasses, defaults to
false for compatibility, participates in provider selection only when
explicitly required, and is validated as a boolean alongside the existing
capability flags. The router remains deterministic and does not introspect
provider methods or turn a synchronous fallback into a non-blocking claim.

## Release risks retained

- Environment-wide dependency governance remains a release veto: the current
  `pip-audit` result is `384` known vulnerabilities in `77` packages, with
  additional non-PyPI local packages skipped.
- Broad Black/isort checks still report pre-existing formatting debt in
  untouched legacy tests; changed-surface checks pass.
- A fresh independent verifier session was unavailable in this tool context;
  this record is not a substitute for that required independent review.

## Decision

Approve the bounded implementation for preview release readiness, subject to
the final package check and the retained overall publish gates. No publication,
deployment, cloud action, or website update was performed.
