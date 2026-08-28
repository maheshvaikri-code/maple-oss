# MAPLE Agent Runtime Slice 141 QA

Date: 2026-08-27

Scope: bounded multimodal image content and explicit provider capability
routing. `ChatMessage` preserves its string form and now accepts ordered text
and `ImageContent` parts. Sources are HTTPS URLs or validated base64 data URIs;
OpenAI-compatible and Anthropic formatting is provider-specific and fail
closed where unsupported. Session and durable run representations remain
JSON-safe and MAPLE performs no media fetch or execution.

Implementation commit: `8f521e4`
Documentation commit: `d708416`

## Acceptance evidence

- Focused LLM/session/provider suite: `49 passed in 0.54s`
- Exact tracked committed-HEAD suite: `1384 passed, 1 skipped in 253.22s`
  from `1385` collected tests
- Whole-package mypy: `Success: no issues found in 97 source files`
- Black on changed Python files: `11 files would be left unchanged.`
- isort on changed Python files: passed
- Ruff: `All checks passed!`
- `python -m compileall -q maple tests`: passed
- `git diff --check 8075d76..HEAD`: passed
- Project dependency audit: `No known vulnerabilities found`
- Source-only secret scan: `source_secret_high_confidence_matches=0`
- Source-only dangerous-construct scan: `source_dangerous_construct_matches=0`

## Behavioral coverage

- `ImageContent` accepts bounded HTTPS URLs and validated JPEG, PNG, WebP, or
  GIF base64 data URIs, with bounded detail values and no URL credentials.
- `ChatMessage` accepts ordered text/image parts while retaining the existing
  string contract; invalid, empty, oversized, or unsupported parts fail at
  construction.
- OpenAI-compatible formatting emits text and `image_url` items for HTTPS and
  data URI sources.
- Anthropic formatting emits base64 image items and returns
  `LLM_UNSUPPORTED_CONTENT` for remote image URLs; neither adapter fetches
  media through MAPLE.
- Session message round trips preserve typed image parts, and
  `ProviderRouter` filters on explicit `image_input=True` capability.

## Package evidence

The clean file-backed `git archive HEAD` package built successfully. Wheel and
source distribution both passed Twine checks; the wheel contained `104`
entries and the source distribution contained `606` entries. No-dependency
wheel-target installation and import/persistence smoke exited `0` and
reported:
`clean_archive_multimodal_smoke=passed`.

## Disposition

Local behavioral, static, package, and source-security checks pass for this
slice. Environment-wide dependency governance remains a release veto from
the prior audit: `384` known vulnerabilities across `77` installed packages.
No publication, deployment, cloud action, or website update was performed.
