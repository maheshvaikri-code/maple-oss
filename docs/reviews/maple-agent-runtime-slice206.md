# Code Review - durable local vector retrieval @ 926e872

**Reviewer role:** Code Reviewer  · **Date:** 2026-08-29
**Reviewed against:** [Slice 206 brief](../briefs/maple-agent-runtime-slice206.md) · [ADR-150](../adr/150-file-vector-retriever.md) · [implementation plan](../plans/maple-agent-runtime-slice206.md)

This is an in-session review. A fresh independent verifier session was not
available in the current tool context, so this report does not claim
independent review.

## Executed

```text
python -m pytest tests/autonomy/test_retrieval.py --no-cov -q
============================= 43 passed in 1.05s ==============================

python -m black --check maple/autonomy/retrieval.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_retrieval.py
4 files would be left unchanged.

python -m ruff check maple/autonomy/retrieval.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_retrieval.py
All checks passed!

python -m mypy maple/ --ignore-missing-imports
Success: no issues found in 102 source files

python -m compileall -q maple tests
(exit 0)
```

## Findings

| # | Sev | Location | Finding | Suggested fix | Resolution |
|---|-----|----------|---------|---------------|------------|
| 1 | [MINOR] | `tests/autonomy/test_retrieval.py` | The first focused test set did not directly demonstrate duplicate-document rejection or malformed persisted vectors. | Add both rejection assertions without weakening existing coverage. | fixed@`484eae0`; reverified in the 43-test focused run above |
| 2 | [MAJOR] | `maple/autonomy/retrieval.py:_validate_vector` | Extremely large integer components could raise `OverflowError` instead of returning the structured vector error. | Catch numeric conversion failures at the shared vector boundary. | fixed@`5366c09`; regression included and reverified |
| 3 | [MINOR] | `maple/autonomy/retrieval.py:FileVectorRetriever._read_records_unlocked` | JSON boolean `true` compares equal to schema version `1` unless its type is checked. | Require an actual integer schema version. | fixed@`926e872`; regression included and reverified |

All findings are resolved; no BLOCKER or open MAJOR remains.

## Scope check

The implementation adds only the planned bounded local vector backend,
exports, focused regressions, and public documentation/bookkeeping. It uses
the existing `InMemoryVectorRetriever`, `TextChunker`, JSON serialization,
atomic replacement, and `DurableRecordLease`. No new dependency, provider,
network call, managed store, distributed coordination, execution path, or
website/publication action was added.

The file backend stores source documents and caller-supplied vectors, rebuilds
derived chunks and cosine lookup state, refreshes every operation, and leaves
the prior state untouched on validation or candidate-write failure. Limits,
UTF-8/JSON parsing, finite vectors, dimensions, duplicate IDs, and generic
storage errors were checked against the brief.

## Verdict

- [x] Pass (0 BLOCKER, MAJORs resolved)
- [ ] Return to build - findings above

The final focused suite and static checks are green. The only review-process
limitation is the unavailable fresh independent verifier, which remains a
release-gate limitation rather than a code finding.
