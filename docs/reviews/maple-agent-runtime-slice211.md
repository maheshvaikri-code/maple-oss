# Code Review — asynchronous document ingestion @ 7e2da52

**Reviewer role:** Code Reviewer · **Date:** 2026-08-29
**Reviewed against:** `docs/briefs/maple-agent-runtime-slice211.md`,
`docs/adr/155-async-document-ingestion.md`, and
`docs/plans/maple-agent-runtime-slice211.md`
**Reviewed commits:** `6703e5d..7e2da52`

**Executed:**

```text
python -m pytest tests/autonomy/test_retrieval.py -q
============================= 87 passed in 5.53s ==============================

python -m pytest -q
================= 1895 passed, 1 skipped in 428.08s (0:07:08) ================

python -m mypy maple --ignore-missing-imports
Success: no issues found in 102 source files

python -m black --check maple/autonomy/retrieval.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_retrieval.py
4 files would be left unchanged.

python -m isort --check-only maple/autonomy/retrieval.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_retrieval.py
4 files would be left unchanged.

python -m ruff check maple/autonomy/retrieval.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_retrieval.py
All checks passed!
```

## Findings

| # | Sev | Location | Finding | Suggested fix | Resolution |
|---|-----|----------|---------|---------------|------------|
| — | — | — | No blocker, major, minor, or nit findings. | — | Pass |

## Review checks

- Correctness: the async connector is awaited one page at a time, and the
  existing batch, cursor, duplicate-ID, count, checkpoint, rate-limit, and
  `Result` validation rules are preserved.
- Concurrency: synchronous sink, checkpoint, and rate-limiter callbacks use
  the default executor; no executor lock is held across an await; the focused
  tests assert callbacks run off the event-loop thread.
- Cancellation: ordinary `asyncio.CancelledError` is not converted into a
  typed failure; the public docs and ADR state that an already-started
  executor effect may finish and that recovery is at-least-once.
- Failure posture: connector, sink, checkpoint, and rate-limit exceptions or
  private callback errors are normalized to generic typed errors; malformed
  pages are rejected before sink mutation; incomplete pages do not checkpoint.
- Surface and scope: both new public symbols are exported from `maple` and
  `maple.autonomy`; docs and changelog describe ownership and non-goals; no
  provider, network, managed-store, retry, execution, website, or publication
  behavior was added.
- Repository state: pre-existing user-owned demo, doctrine, packaging, and
  other untracked files were preserved and excluded from the feature commits.

## Scope check

The diff matches Slice 211: one additive async connector protocol, one bounded
async ingestion helper, focused regressions, public exports, and API/parity/
changelog/release-plan documentation. No unrelated source behavior was changed.

Fresh independent verifier sessions were unavailable in this tool context, so
this artifact records the required same-context review and does not claim an
independent verifier sign-off.

## Verdict

- [x] Pass (0 BLOCKER, MAJORs resolved/waived)
- [ ] Return to build — findings above

The implementation is clean against the approved contract and the executed
focused/full/static checks above.
