# Slice 198 plan - bounded judge calibration

**Brief:** [maple-agent-runtime-slice198.md](../briefs/maple-agent-runtime-slice198.md)
**Design/ADR:** [ADR-142](../adr/142-bounded-judge-calibration.md)
**Class:** L

## Slices

| # | Slice | Role | Files touched | Proven by (tests) | Status |
|---|---|---|---|---|---|
| 1 | Calibration data/report contracts | Backend / ML | `maple/autonomy/evaluation.py`, autonomy/root exports, evaluation tests | validation, empty set, agreement, optional MAE, bounded JSON report | complete: `35b446e`; focused evaluation suite `35 passed` |
| 2 | Sync/async calibration execution | ML / Interop | `maple/autonomy/evaluation.py`, evaluation tests, API docs | sequential sync/async callbacks, redaction, disagreement, judge error isolation | complete: `35b446e`, `904f48a`; focused evaluation suite `35 passed` |
| 3 | Review, QA, security, package, and parity closure | Code Reviewer / QA / Security / Release | review/QA/release/parity docs, README, changelog | focused/full tests, adversarial bounds, no-network package smoke | complete: review `a3d6e8a`; QA/security `docs/qa/maple-agent-runtime-slice198.md`; clean candidate `1678 passed, 1 skipped`, wheel `108`, sdist `842`, Twine/install/import/doctor pass |
| 4 | Synchronous judge awaitable boundary follow-up | ML / Backend | `maple/autonomy/evaluation.py`, evaluation tests, changelog | disposable awaitable cleanup and typed async-entry-point errors in sync `run`/`calibrate` | complete: `bfe8b43`; focused `37 passed`; full dirty suite `1797 passed, 1 skipped`; clean package smoke, scoped Ruff, mypy, and compileall pass |

## Threat sketch

Assets touched: human labels, model observations, judge rationales, aggregate
metrics, and report serialization. Entry points / untrusted inputs: caller
calibration fixtures, runner observations, host judge callbacks, and judge
results. Worst plausible abuse: sensitive observation data or oversized judge
output crosses the callback/report boundary, or malformed judge results poison
calibration metrics; the design reuses redaction, size bounds, typed result
normalization, and sequential bounded processing.

## Risks and rollback points

- Risk: callers interpret descriptive metrics as semantic truth -> mitigation:
  name/report them as provider-neutral calibration and document non-claims;
  rollback: remove public calibration exports while retaining existing judge
  execution.
- Risk: invalid calibration data hides useful remaining cases -> mitigation:
  reject malformed dataset definitions before callbacks, but isolate judge
  failures per case; rollback: revert only the new calibration methods.
- Risk: sync/async implementations diverge -> mitigation: reuse shared
  normalization/redaction helpers and ordered fixtures; rollback: remove the
  async convenience method without changing sync evaluation.

## Deviation log (append-only)

- `bfe8b43` extends the fail-closed boundary to synchronous `run(..., judge=...)`
  as well as `calibrate(...)` after review identified the same unawaited
  coroutine risk in both public entry points. The behavior is additive for
  invalid callback outputs and preserves valid callback compatibility.

## Status snapshot

G0/G1/G2 accepted; G3 implementation and G4/G5/G6 review, QA, security,
package, and parity closure are complete for the bounded local contract,
including the `bfe8b43` boundary follow-up.
Blocked on: none for this local slice; provider-owned and hosted calibration
remain separate human-gated work.
