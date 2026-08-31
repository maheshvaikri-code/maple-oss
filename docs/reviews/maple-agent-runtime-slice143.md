# MAPLE Agent Runtime Slice 143 Review Record

Date: 2026-08-28

## Review scope

Reviewed the committed native async completion slice across:

- `maple/llm/openai_provider.py`;
- `maple/llm/anthropic_provider.py`;
- `tests/llm/test_provider.py`;
- ADR, API, README, parity, changelog, plan, and QA evidence.

## Findings

No blocking defect found in the reviewed boundary.

The adapters preserve the existing `Result` contract, use the existing
message/tool formatters, track parsed usage through the existing provider
path, classify provider exceptions, and await native async SDK calls. The
OpenAI async client is optional at construction time, and both providers
delegate explicitly to the base synchronous compatibility path when no async
client is available. That fallback is documented as potentially blocking.

The slice adds no dependency, retry, provider-selection, background-thread,
remote-transport, or concurrency behavior. The test fixtures are offline and
cover both native paths plus the OpenAI missing-async-client fallback.

## Release risks retained

- Environment-wide dependency governance remains a release veto: the current
  `pip-audit` result is `384` known vulnerabilities in `77` packages, with
  additional non-PyPI local packages skipped.
- Broad Black/isort checks still report pre-existing formatting debt in
  untouched legacy tests; changed-surface checks pass.
- A fresh independent verifier session was unavailable in this tool context;
  this record is not a substitute for that required independent review.

## Decision

Approve the implementation for the bounded preview slice and retain the
overall publish hold until dependency governance and independent verification
are resolved. No publication, deployment, cloud action, or website update was
performed.
