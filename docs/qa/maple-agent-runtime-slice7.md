# QA + Security Report - MAPLE Agent Runtime Slice 7 @ bf1614b

**QA Engineer:** local verification role  · **Security Reviewer:** local
security pass  · **Date:** 2026-08-24
**Build under test:** `bf1614b feat(dx): add interop envelope and doctor command`

## Acceptance criteria

| # | Criterion | Evidence | Pass |
|---|---|---|---|
| 1 | Adapter round trips have a strict common envelope. | JSON round trip, unknown field, non-string key, invalid JSON, version, and size tests pass. | Yes |
| 2 | Developer preflight is one command. | `python -m maple.cli doctor --json` returns `SUCCESS`, all checks true, and `network: false`. | Yes |
| 3 | Quickstart docs explain the preflight boundary. | `docs/getting-started.md`, API reference, README, and changelog updated. | Yes |
| 4 | Existing LLM/autonomy/CLI behavior remains green. | `165 passed, 1 warning`. | Yes |

## Security sweep

- No new dependency or network call was added.
- No eval, exec, pickle, subprocess, shell, or YAML-loader path was added.
- Interop parsing rejects unknown fields, unsupported versions, non-string field
  names, non-JSON values, and oversized payloads.
- Doctor is local-only and does not supply credentials to providers.
- Doctor is a readiness signal, not a security audit or publication approval.

## Regression evidence

```text
5 passed, 1 warning in 0.04s
165 passed, 1 warning in 0.21s
```

The broader repository run remains unfinished evidence: the previous run
reached `1008 passed` before interruption in an existing slow timing path. It
is not treated as a full-suite release pass.

## Verdict

**Security:** SIGN-OFF for the local interop/doctor boundary; final release
security sign-off remains open.
**QA:** pass for Slice 7; final release QA remains open pending release
hardening and completed repository regression gates.
