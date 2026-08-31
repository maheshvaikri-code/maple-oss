# Code Review — MAPLE agent runtime Slice 197 @ 683b8a9

**Reviewer role:** Code Reviewer · **Date:** 2026-08-29
**Reviewed against:** [Slice 197 brief](../briefs/maple-agent-runtime-slice197.md) · [Slice 197 plan](../plans/maple-agent-runtime-slice197.md) · [ADR-141](../adr/141-offline-provider-contract-fixtures.md)
**Execution note:** This environment has no independent fresh-session facility. The local Code Reviewer gate was run against the committed implementation diff; it is not independent verifier sign-off.

**Executed:**

```text
python -m pytest tests/llm/test_provider_contracts.py tests/llm/test_provider.py tests/llm/test_provider_native_streaming.py tests/llm/test_provider_streaming.py -q --no-cov
============================= 39 passed in 0.40s ==============================

python -m black --check maple/llm/provider.py maple/llm/openai_provider.py maple/llm/anthropic_provider.py tests/llm/test_provider_contracts.py
4 files would be left unchanged.

python -m isort --check-only maple/llm/provider.py maple/llm/openai_provider.py maple/llm/anthropic_provider.py tests/llm/test_provider_contracts.py

python -m ruff check maple/llm/provider.py maple/llm/openai_provider.py maple/llm/anthropic_provider.py tests/llm/test_provider_contracts.py
All checks passed!

python -m mypy maple/llm/provider.py maple/llm/openai_provider.py maple/llm/anthropic_provider.py --ignore-missing-imports
Success: no issues found in 3 source files
```

## Findings

| # | Sev | Location | Finding | Suggested fix | Resolution |
|---|-----|----------|---------|---------------|------------|
| 1 | [MAJOR] | `maple/llm/provider.py` response-content validation | An unencodable provider string could raise `UnicodeEncodeError` and escape as generic `LLM_COMPLETION_ERROR` instead of the typed invalid-response boundary. | Catch the encoding failure while measuring the bounded UTF-8 response and raise `ProviderResponseError`. | fixed@1c1277d; regression fixture `test_provider_rejects_unencodable_completion_before_accounting` passes. |
| 2 | [MAJOR] | `maple/llm/provider.py` tool-argument validation | `json.dumps` can coerce non-string dictionary keys or tuples, allowing a Python value that is not the same JSON-native object to cross the normalized tool boundary. | Round-trip the bounded JSON encoding and reject values that do not remain equal to the original arguments. | fixed@1c1277d; regression fixture `test_provider_rejects_non_json_native_tool_arguments_before_accounting` passes. |

## Scope check

The implementation matches the plan: shared bounded response validation,
provider-specific completion parsing, deterministic sync/async fake-client
fixtures, and no SDK installation, network call, routing, scheduling, or
side-effect execution. Existing streaming behavior is covered by the focused
regressions and was not expanded into streaming failover or live compatibility.
README, API reference, parity ledger, changelog, brief, ADR, and release plan
were updated for the new typed response boundary.

## Verdict

- [x] Pass (0 BLOCKER, MAJORs resolved)
- [ ] Return to build — findings above

The review checked happy paths, sync/async parity, multimodal/tool payload
mapping, malformed JSON/non-object/non-JSON-native tool arguments, malformed
usage, usage boundary values, oversized output, accounting isolation, and the
changed-surface static checks. No open blocker or major remains in the scoped
diff.
