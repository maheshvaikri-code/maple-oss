# QA + Security Report - MAPLE Agent Runtime Slice 6 @ 4ead28d / 3a91c6d

**QA Engineer:** local verification role  · **Security Reviewer:** local
security pass  · **Date:** 2026-08-24
**Build under test:** evaluation/provider capability commits

## Acceptance criteria

| # | Criterion | Evidence | Pass |
|---|---|---|---|
| 1 | Provider selection uses declared capabilities and priority. | Capability and priority selection tests pass. | Yes |
| 2 | Provider initialization has deterministic fallback. | A failing high-priority provider falls back to a working lower-priority provider. | Yes |
| 3 | Evaluation checks output and tool trajectories. | Golden-case tests cover exact output, schema, and ordered tool names. | Yes |
| 4 | Evaluation failures are reportable and bounded. | Per-case failure records, case limits, redaction, and output byte limits are tested. | Yes |
| 5 | Public API is importable. | Top-level `maple` import smoke test passed. | Yes |
| 6 | Existing LLM/autonomy behavior remains green. | `160 passed, 1 warning`. | Yes |

## Security sweep

- No new dependency or network call was added.
- No eval, exec, pickle, subprocess, shell, or YAML-loader path was added.
- Provider fallback returns structured, bounded errors without exception text.
- Capability matching fails closed when a required capability is unknown or
  absent.
- Evaluation actual outputs are recursively redacted and size-bounded before
  entering `EvalResult`.

## Regression evidence

```text
7 passed, 1 warning in 0.02s
160 passed, 1 warning in 0.19s
```

The broader repository run remains unfinished evidence: the previous run
reached `1008 passed` before interruption in an existing slow timing path. It
is not treated as a full-suite release pass.

## Verdict

**Security:** SIGN-OFF for the local evaluation/provider contract; final release
security sign-off remains open.
**QA:** pass for Slice 6; final release QA remains open pending Slice 7 and a
completed repository regression run.
