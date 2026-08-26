# QA + Security Report - bounded local observability retention metrics @ ec190bc

**QA Engineer** - **Security Reviewer** - **Date:** 2026-08-26  
**Build under test:** `ec190bc fix(observability): keep metrics capacity typed`

## Acceptance criteria verification

| # | Criterion | How executed | Evidence (real output) | Pass |
|---|---|---|---|---|
| 1 | Expose thread-safe event-buffer retention metrics | `tests/autonomy/test_events.py` | `30 passed in 0.25s`; event metrics assert retained count, capacity, evictions, and subscriber count | Yes |
| 2 | Expose thread-safe span-buffer retention and open-span metrics | `tests/autonomy/test_observability.py` | `30 passed in 0.25s`; span metrics assert retained count, capacity, evictions, and open spans | Yes |
| 3 | Keep metrics metadata-only, bounded, and dependency-free | Source review, focused tests, and dependency audit | Metrics contain only integer counts; no new dependency or payload/export path was added | Yes |
| 4 | Preserve existing event/span behavior and failure posture | Exact tracked regression manifest | `1263 passed, 1 skipped in 248.55s` across 108 tracked test files | Yes |
| 5 | Keep public documentation and API boundaries truthful | ADR/API/README/parity/changelog review | ADR-053 and `metrics()` API documentation state local-only scope; sampling and remote aggregation remain deferred | Yes |
| 6 | Produce a clean publishable package candidate | Clean committed-HEAD archive build and audit | Package candidate `beba0f2`: build_exit=0, twine_exit=0, sdist_entries=507, required public files `5/5`, workspace-only audit `0` | Yes |

## Adversarial & edge matrix

| Input/scenario | Expected | Observed | Pass |
|---|---|---|---|
| Empty event buffer | Zero retained/dropped/subscriber counts | Metrics returns integer zero counts for empty fields | Yes |
| Event ring at capacity plus one | Count one eviction and retain configured capacity | `retained_events=2`, `max_events=2`, `dropped_events=1` | Yes |
| Active event subscriber | Include subscriber pressure | `subscriber_count=1` after subscription | Yes |
| Open spans under retention pressure | Report retained/open counts separately | `retained_spans=2`, `open_spans=2`, `dropped_spans=1` | Yes |
| Finished span | Remove from open count but retain record | Existing finish-once tests pass; metrics derives status from retained spans | Yes |
| Concurrent span recording | Snapshot remains thread-safe and bounded | Existing concurrent-start test passes | Yes |
| Invalid lazy EventStream configuration | Metrics remains an integer snapshot | Uses actual deque capacity rather than invalid configured value | Yes |
| Unicode or secret-bearing payloads | Metrics must not expose payload data | Metrics contain counts only; redaction tests remain green | Yes |
| Sampling/remote exporter request | Remain outside this local contract | No sampling or transport behavior was introduced | Yes |

## Regression

Focused suite:

```text
python -m pytest tests/autonomy/test_events.py tests/autonomy/test_observability.py -q --no-cov -p no:dash -p no:benchmark --tb=short --no-header
collected 30 items
tests\\autonomy\\test_events.py ...........                                [ 36%]
tests\\autonomy\\test_observability.py ...................                 [100%]
============================== 30 passed in 0.25s ==============================
```

Exact tracked regression manifest:

```text
collected 1264 items
================= 1263 passed, 1 skipped in 248.55s (0:04:08) =================
```

Flakes: none observed in the final exact run.

## Bugs found

| # | Repro steps (minimal) | Severity | Fixed @ | Re-verified | Regression test |
|---|---|---|---|---|---|
| 1 | Call `EventStream.metrics()` with an invalid lazy configuration | Minor | `ec190bc` | Yes | `test_ring_buffer_tracks_evictions_and_snapshot_order` |

## Security sweep

Secrets scan: `gitleaks` unavailable; changed-pattern scan exit `1` means no
matching secret/dangerous-construction additions.  
Injection review: metrics are read-only integer snapshots and add no input,
command, path, template, deserialization, or authorization surface.  
Dependency audit: `pip-audit` rerun against the host environment reported
`Found 383 known vulnerabilities in 77 packages`; this slice adds no
dependency. The finding remains an open release-governance item and
publication veto.  
Dangerous constructs: no new subprocess, TLS, unsafe, deserialization, or
world-writable-file behavior.  
Bounds/fail-closed: event/span rings remain bounded; metrics use lock-protected
integer snapshots and do not alter retention or error behavior.

**Security verdict:** **VETO** for a final repository publication claim until
the dependency-audit findings are dispositioned; no new Slice 107 security
defect found. Human override: n/a.  
**QA verdict:** pass for Slice 107 behavior and local metrics boundaries;
committed package evidence is attached below. No publication was performed.

**Package audit evidence:**

```text
head=beba0f2
build_exit=0
twine_exit=0
artifact_count=2
sdist_entries=507
required_hits=5/5
workspace_only_hits=0
maple_oss-1.1.3-py3-none-any.whl: PASSED
maple_oss-1.1.3.tar.gz: PASSED
```
