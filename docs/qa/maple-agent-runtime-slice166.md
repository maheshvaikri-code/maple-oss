# QA + Security Report - durable receiver-side event deduplication

**QA Engineer** / **Security Reviewer** / **Date:** 2026-08-28
**Code candidate:** `81e8dcf` (`test(events): cover dedup completion bounds`)
**Design baseline:** `de56ecc`
**Implementation baseline:** `f5abe63`

## Acceptance criteria verification

| # | Criterion | Evidence (real output) | Pass |
|---|---|---|---|
| 1 | Completed claims replay after a new store instance starts | `tests/autonomy/test_events.py`: `45 passed in 4.30s`; restart test returns the copied destination event | Yes |
| 2 | Pending claims are fenced and explicit abort permits a later claim | Focused event tests verify `EVENT_DEDUPLICATION_IN_PROGRESS` before abort and a new claim after abort | Yes |
| 3 | Invalid, conflicting, expired, capacity, and oversized state fail without partial mutation | Focused tests verify typed errors, unchanged bytes, pending-state preservation, expiry, and completed-only eviction | Yes |
| 4 | Concurrent local instances serialize durable operations | Focused test runs two store instances concurrently; one claims and one receives `EVENT_DEDUPLICATION_IN_PROGRESS` | Yes |
| 5 | Public receiver path survives store recreation | HTTP batch regression creates a fresh `FileEventDeduplicationStore` for each receiver instance and leaves one destination event | Yes |
| 6 | Public exports and documentation are synchronized | `maple` and `maple.autonomy` imports pass; README, API reference, parity ledger, changelog, brief, ADR, review, and release plan are filed | Yes |
| 7 | Exactly-once and hosted claims remain excluded | ADR, API docs, README, parity ledger, and changelog explicitly retain local durable at-least-once wording | Yes |

## Regression

```text
python -m pytest tests/autonomy/test_events.py -q --no-cov
45 passed in 4.30s

python -m pytest tests/autonomy/test_events.py tests/autonomy/test_server.py -q --no-cov
85 passed in 22.45s

python -m pytest <tracked Python test files> -q --no-cov
1516 passed, 1 skipped in 245.98s (0:04:05)
```

No flaky behavior was observed.

## Static and security gates

```text
ruff check maple tests
All checks passed!

compileall maple tests
exit 0

black --check maple/autonomy/events.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_events.py
4 files would be left unchanged.

isort --check-only maple/autonomy/events.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_events.py
exit 0

mypy --follow-imports=skip maple/autonomy/events.py maple/autonomy/__init__.py maple/__init__.py
Success: no issues found in 3 source files

slice166_secret_danger_scan=passed
gitleaks=unavailable
equivalent_targeted_scan=passed
```

- The store validates the complete versioned JSON document before returning
  data, bounds entries/bytes/TTL, retains no source event payload, and uses
  atomic replacement under a durable local lease.
- No new dependency was added. Bandit is unavailable in the environment:
  `No module named bandit`.
- `python -m pip_audit --local` exited `1`. The established environment-wide
  baseline is `384 known vulnerabilities in 77 packages`; the current run
  also lists local packages that cannot be audited from PyPI. This is a
  pre-existing dependency-governance veto, not a Slice166 dependency change.
- No external registry, cloud service, broker, scheduler, or code-execution
  path was added.

**Security verdict:** Pass for Slice166-specific findings; publication remains
vetoed by the pre-existing dependency-audit/tooling governance condition.

## Package gate

Pending final clean-archive validation at the release-evidence commit.

## Release disposition

The implementation is ready for local package validation and staged release
review. No publication, deployment, cloud action, registry write, or website
update was performed.
