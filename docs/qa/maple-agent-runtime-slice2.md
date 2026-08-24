# QA + Security Report - MAPLE Agent Runtime Slice 2 @ fed365f

**QA Engineer:** local verification role  · **Security Reviewer:** local
security pass  · **Date:** 2026-08-24
**Build under test:** `fed365f feat(autonomy): add typed agent contracts`

## Acceptance criteria

| # | Criterion | Evidence | Pass |
|---|---|---|---|
| 1 | Tool input schemas are enforced before handlers run. | Invalid required input returned `TOOL_INPUT_INVALID`; handler call list stayed unchanged. | Yes |
| 2 | Tool result schemas and output guardrails are enforced. | Contract tests cover invalid output and guardrail boundaries. | Yes |
| 3 | Model structured output is parsed and validated. | Agent test returned a typed dictionary for a valid response schema. | Yes |
| 4 | Input/output guardrails fail closed. | Rejection, exception, malformed result, and schema guardrail paths are covered. | Yes |
| 5 | Validation is bounded. | Depth, collection-size, byte-size, and unsupported-regex controls are implemented and tested. | Yes |
| 6 | Existing autonomy behavior remains green. | `107 passed, 1 warning`. | Yes |

## Security sweep

- No new dependency was added.
- Structured output is parsed as JSON data; no `eval`, `exec`, `pickle`,
  subprocess, shell, or YAML-loader path was added to the Slice 2 files.
- Tool handler failures no longer return caller arguments in error details.
- Guardrail exception payloads contain the exception type, not exception text.
- `pattern` schemas are rejected because the standard-library regex engine has
  no reliable execution deadline.
- Public API documentation and regression tests were added with the feature.

## Regression evidence

```text
34 passed, 1 warning in 0.04s
107 passed, 1 warning in 0.11s
```

The broader repository run remains unfinished evidence: the previous run
reached `1008 passed` before interruption in an existing slow timing path. It
is not treated as a full-suite release pass.

## Verdict

**Security:** SIGN-OFF for the dependency-free Slice 2 boundary; final release
security sign-off remains open.
**QA:** pass for Slice 2; final release QA remains open pending the remaining
slices and a completed repository regression run.
