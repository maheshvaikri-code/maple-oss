# MAPLE Agent Runtime Slice 140 QA

Date: 2026-08-27

Scope: add bounded guardrail lifecycle events and local trace linkage. The
contract reports ordered `started`, `passed`, `rejected`, and `failed`
transitions without copying guarded values or callback error payloads; agent
event streams correlate input/output transitions with the local run and active
model span where available.

Implementation commit: `28ee94e`

## Acceptance evidence

- Focused contracts/agent suite: `51 passed in 6.00s`
- Exact tracked committed-HEAD suite: `1378 passed, 1 skipped in 286.75s` from `1379` collected tests
- Whole-package mypy: `Success: no issues found in 97 source files`
- Black on changed Python files: `6 files would be left unchanged.`
- isort on changed Python files: passed
- Ruff: `All checks passed!`
- `python -m compileall -q maple tests`: passed
- `git diff --check`: passed
- Project dependency audit: `No known vulnerabilities found`
- Source-only secret scan: `source_secret_high_confidence_matches=0`
- Source-only dangerous-construct scan: `source_dangerous_construct_matches=0`

## Behavioral coverage

- Direct observers receive ordered lifecycle transitions for successful and
  rejected guardrails, including `Result.ok(...)` callbacks.
- Observer exceptions are isolated and do not alter the fail-closed policy
  decision.
- Event metadata validates bounded stage, index, status, trace, and span fields.
- Sync and async agent runs publish the same `guardrail.*` event vocabulary;
  output events include the local model span when available.
- Lifecycle events contain no guarded values, prompts, raw callback errors, or
  rejection payloads, and event-stream publication remains best effort.

## Package evidence

The clean ZIP-extracted archive from documentation commit `3e12052` built
successfully. Wheel and source distribution both passed Twine checks; the
wheel contained `104` entries and the source distribution contained `605`
entries. No-dependency wheel-target installation and import smoke both exited
`0` and reported:
`clean_archive_guardrail_exports=GuardrailEvent,Callable`.

SHA-256: wheel
`92E5F99CC6BFDDFA4C5F375734DDA80AFB225CB951646340D562448CAC1153A4`;
source distribution
`55AC86C2EA8B32D64580DD818F4D54783C54C25A9744A98ABF91BBBD5507CD16`.

## Disposition

Local behavioral, static, and security checks pass for this implementation.
Environment-wide dependency governance remains a release veto from the prior
audit: `384` known vulnerabilities across `77` installed packages. No
publication, deployment, cloud action, or website update was performed.
