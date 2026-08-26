# QA + Security Report - local observability sampling and latency metrics @ 9bc3850

**QA Engineer** - **Security Reviewer** - **Date:** 2026-08-26  
**Build under test:** `9bc3850 feat(observability):local-sampling-latency-metrics`

## Acceptance criteria verification

| # | Criterion | How executed | Evidence (real output) | Pass |
|---|---|---|---|---|
| 1 | Validate and apply bounded span sampling | `tests/autonomy/test_observability.py` | `sample_rate` rejects values outside `0.0..1.0`; zero-rate spans return `SPAN_SAMPLED_OUT` and do not enter retention | Yes |
| 2 | Expose local span latency and terminal status metrics | `tests/autonomy/test_observability.py` | `completed_spans=3`, `latency_total_ms=875`, `latency_max_ms=500`, `latency_avg_ms=291`, one error and one cancellation | Yes |
| 3 | Expose event publish/backpressure metrics | `tests/autonomy/test_events.py` | Accepted publishes, subscriber failures, exporter failures, and non-negative publish latency are reported | Yes |
| 4 | Preserve existing behavior and failure isolation | Exact tracked regression manifest | `1265 passed, 1 skipped in 203.80s` across the tracked application tests | Yes |
| 5 | Keep public documentation and API boundaries truthful | ADR/API/README/parity/changelog review | ADR-054 documents stable local sampling, coarse latency, and explicit remote/percentile deferrals | Yes |
| 6 | Produce a clean publishable package candidate | Clean committed-HEAD archive build and audit | Package evidence is pending the final evidence commit | Pending |

## Adversarial & edge matrix

| Input/scenario | Expected | Observed | Pass |
|---|---|---|---|
| Sample rate below zero or above one | Constructor rejects invalid control | `ValueError` with `sample_rate` message | Yes |
| Zero-rate sampling | No span retained; typed drop only | `SPAN_SAMPLED_OUT`, sampled-out count increments | Yes |
| Default sampling | Existing behavior retained | Default basis points reports `10000`; existing recorder tests pass | Yes |
| Finished spans with mixed statuses | Count completion, latency, error, and cancellation | Exact counters match focused regression | Yes |
| Subscriber callback raises | Publish still succeeds and failure is visible | Publish succeeds; `subscriber_failures=1` | Yes |
| Exporter raises | Publish still succeeds and failure is visible | Publish succeeds; `exporter_failures=1` | Yes |
| Retention eviction | Retained ring stays bounded and eviction remains separate | Existing event/span retention tests remain green | Yes |
| Secret-bearing payloads | Metrics expose no payload | Metrics contain scalar counts only; redaction remains active | Yes |
| Remote/percentile request | Remain outside local contract | No transport, persistence, or histogram path added | Yes |

## Regression

Focused suite:

```text
python -m pytest tests/autonomy/test_events.py tests/autonomy/test_observability.py -q --no-cov -p no:dash -p no:benchmark --tb=short --no-header
collected 32 items
============================= 32 passed in 0.27s ==============================
```

Tracked application regression (Doctrine-only untracked tests excluded):

```text
collected 1266 items
================= 1265 passed, 1 skipped in 203.80s (0:03:23) =================
```

Static gates:

```text
Black: 4 files would be left unchanged
Ruff: All checks passed!
mypy changed boundary: Success: no issues found in 2 source files
compileall: exit 0
doctor: {"network": false, "ready": true, "status": "SUCCESS"}
```

## Security sweep

Secret scanner: `gitleaks` is unavailable in the environment. Manual changed-
surface review found no new secret, command, path, deserialization, network,
or credential handling.

Dependency audit: `pip-audit` reported `Found 383 known vulnerabilities in 77
packages` and warned about invalid distribution `~gl`. This slice adds no
dependency; the host-environment finding remains an open release-governance
item and publication veto.

Bounds/fail-closed: sample-rate input is finite and bounded; retained spans
and events remain bounded; metric snapshots contain integer counters only;
subscriber/exporter exceptions do not alter agent outcomes.

**Security verdict:** **VETO** for a final repository publication claim until
dependency findings are dispositioned; no new Slice 108 security defect found.
Human override: n/a.  
**QA verdict:** pass for Slice 108 behavior and local observability boundaries;
package evidence remains to be attached after the final documentation commit.
No publication was performed.
