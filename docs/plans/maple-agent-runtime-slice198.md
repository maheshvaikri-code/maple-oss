# Slice 198 plan - bounded judge calibration

**Brief:** [maple-agent-runtime-slice198.md](../briefs/maple-agent-runtime-slice198.md)
**Design/ADR:** [ADR-142](../adr/142-bounded-judge-calibration.md)
**Class:** L

## Slices

| # | Slice | Role | Files touched | Proven by (tests) | Status |
|---|---|---|---|---|---|
| 1 | Calibration data/report contracts | Backend / ML | `maple/autonomy/evaluation.py`, autonomy/root exports, evaluation tests | validation, empty set, agreement, optional MAE, bounded JSON report | todo |
| 2 | Sync/async calibration execution | ML / Interop | `maple/autonomy/evaluation.py`, evaluation tests, API docs | sequential sync/async callbacks, redaction, disagreement, judge error isolation | todo |
| 3 | Review, QA, security, package, and parity closure | Code Reviewer / QA / Security / Release | review/QA/release/parity docs, README, changelog | focused/full tests, adversarial bounds, no-network package smoke | todo |

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

- None.

## Status snapshot

G0/G1/G2 accepted for the bounded provider-neutral calibration contract. Next:
implement the typed report and sync/async execution paths. Blocked on: none
for this local slice; provider-owned and hosted calibration remain separate
human-gated work.
