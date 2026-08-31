# QA + Security Report — MAPLE agent runtime Slice 197 @ 683b8a9

**QA Engineer** · **Security Reviewer** · **Date:** 2026-08-29
**Build under test:** `683b8a9` implementation/test candidate; documentation-only
closure will retain the same code and be package-tested before release evidence
is closed.

## Acceptance criteria verification

| # | Criterion | How executed | Evidence (real output) | Pass |
|---|-----------|--------------|------------------------|------|
| 1 | OpenAI-compatible sync/async mapping and normalized response | Deterministic fake sync and async clients in `tests/llm/test_provider_contracts.py` | `15` provider-contract tests passed within the focused `39 passed in 0.40s` run | yes |
| 2 | Anthropic sync/async mapping and normalized response | Deterministic fake sync and async clients with system, text, image, tool, stop, and usage fixtures | Focused provider suite: `39 passed in 0.40s` | yes |
| 3 | Malformed tool arguments fail closed before execution | OpenAI malformed JSON/non-object fixtures; Anthropic non-object fixture; non-JSON-native key fixture | Each returns `LLM_PROVIDER_RESPONSE_INVALID`; counters remain zero; focused suite passed | yes |
| 4 | Malformed usage fails closed before accounting | Negative OpenAI usage, string Anthropic usage, and oversized/invalid normalized output fixtures | Each returns `LLM_PROVIDER_RESPONSE_INVALID`; focused suite passed | yes |
| 5 | Existing provider failure classification remains stable | Existing capability/provider regression suites, including transient, rate-limit, timeout, non-transient, raised, and async cases | Final implementation candidate full run: `1790 passed, 1 skipped in 350.47s (0:05:50)` | yes |
| 6 | No network/new dependency; imports and repository remain green | Fake clients only; changed-surface format/lint/type checks; full test suite | `All checks passed!`; `Success: no issues found in 3 source files`; full suite passed | yes |

## Adversarial & edge matrix

| Input/scenario | Expected | Observed | Pass |
|----------------|----------|----------|------|
| Empty message list | Fixture request remains bounded and parser behavior is deterministic | Malformed-response tests use `complete([])` and return typed errors without accounting | yes |
| Oversized completion content | Reject before accounting | `test_provider_rejects_oversized_completion_before_accounting` returns `LLM_PROVIDER_RESPONSE_INVALID` and leaves counters at zero | yes |
| Unicode / unencodable content | Reject invalid UTF-8 boundary data | `test_provider_rejects_unencodable_completion_before_accounting` returns typed invalid response | yes |
| Zero/negative usage | Zero is valid; negative is rejected | Existing `TokenUsage` coverage accepts zero defaults; negative fixture returns typed invalid response | yes |
| Duplicate/concurrent/interrupted provider response | Not part of this local synchronous completion contract; no claim made | Explicitly out of scope in the Slice 197 brief and ADR; no scheduling or side-effect state is introduced | n/a |
| Malformed JSON, non-object, non-JSON-native tool arguments | Reject; expose no arguments | OpenAI/Anthropic fixtures return typed invalid response and do not mutate counters | yes |
| Missing usage object | Preserve unavailable usage compatibility | Existing provider tests and normalized fixtures retain `usage=None` behavior | yes |
| Usage zero / max / above max | Accept bounded integers at zero and the exact cap; reject above it | `test_provider_enforces_completion_usage_boundary` exercises `0`, `100_000_000`, and `100_000_001`; focused `39 passed in 0.40s` | yes |

## Regression

Focused command:

```text
python -m pytest tests/llm/test_provider_contracts.py tests/llm/test_provider.py tests/llm/test_provider_native_streaming.py tests/llm/test_provider_streaming.py -q --no-cov
============================= 39 passed in 0.40s ==============================
```

Full command:

```text
python -m pytest -q --no-cov
================= 1790 passed, 1 skipped in 350.47s (0:05:50) =================
```

Determinism: the focused run was executed after the usage-boundary test
addition, and the full run re-executed all `1791` collected tests at the same
implementation candidate. No flakes observed.

## Bugs found

| # | Repro steps (minimal) | Severity | Fixed @ | Re-verified | Regression test |
|---|----------------------|----------|---------|-------------|-----------------|
| 1 | Return a completion containing an unpaired surrogate string | major | `1c1277d` | focused and full suites | `test_provider_rejects_unencodable_completion_before_accounting` |
| 2 | Return Anthropic tool arguments with a non-string dictionary key | major | `1c1277d` | focused and full suites | `test_provider_rejects_non_json_native_tool_arguments_before_accounting` |

## Security sweep

- Secrets scan: `gitleaks` is unavailable; equivalent token/private-key
  pattern scan over outgoing Slice 197 commits and changed docs found no
  secret. Existing README `sk-...` examples are placeholders, not credentials.
- Injection review: no SQL, shell, path, template, authentication, or network
  path was added. Provider tool arguments are parsed as bounded JSON objects,
  round-trip checked, and rejected before usage accounting.
- Dependency audit:

  ```text
  pip-audit --progress-spinner off --strict .
  No known vulnerabilities found
  ```

- Dangerous constructs: no `eval`, `exec`, `pickle`, unsafe TLS override,
  `shell=True`, or subprocess code introduced. `bandit` is unavailable.
- Bounds/fail-closed: response text, tool-call count, tool-argument bytes,
  metadata lengths, UTF-8 encoding, and usage integers are bounded; typed
  parser errors occur before `_track_usage`.

**Security verdict:** SIGN-OFF for the scoped Slice 197 diff, with unavailable
`gitleaks`/`bandit` recorded above. The project-level audit is clean; the
standing shared-environment vulnerability audit remains a separate release
governance blocker and is not waived here.

**QA verdict:** pass for Slice 197. Local package evidence remains required
for release closure, and the overall release remains conditional until the
standing release gates are resolved. No human override.
