# Code Review - MAPLE Agent Runtime Slice 4 @ 953f601

**Reviewer role:** Code Reviewer  · **Date:** 2026-08-24
**Reviewed against:** [brief](../briefs/maple-agent-runtime-release.md),
[ADR-003](../adr/003-retrieval-data-contract.md), and
[implementation plan](../plans/maple-agent-runtime-release.md)

## Scope

This slice adds source-bearing document contracts, deterministic bounded text
chunking, and `InMemoryLexicalRetriever` behind a `RetrievalBackend` protocol.
It is dependency-free and deliberately lexical; vector stores, embedding
models, document loaders, and hosted retrieval remain adapters or later scope.

## Findings

| # | Sev | Location | Finding | Resolution |
|---|---|---|---|---|
| 1 | MINOR | In-memory backend | A lexical reference backend is not production vector retrieval. | Public docs and ADR call this out; the backend protocol allows later adapters. |
| 2 | MINOR | Chunk/query input | Unbounded text or metadata could cause memory pressure. | Document bytes, metadata, chunk count, retriever counts, query bytes, and `top_k` are bounded. |
| 3 | MINOR | Grounding | Raw result text without source identity would be hard to cite. | Every `DocumentChunk` and `RetrievalHit` carries `SourceRef` and character offsets. |

## Verification evidence

```text
ruff check maple/autonomy/retrieval.py maple/autonomy/execution.py maple/autonomy/tools.py tests/autonomy/test_retrieval.py tests/autonomy/test_execution.py --output-format concise
All checks passed!

python -m pytest tests/autonomy/test_retrieval.py tests/autonomy/test_execution.py tests/autonomy/test_contracts.py -q -o addopts=
20 passed, 1 warning in 0.08s

python -m pytest tests/autonomy -q -o addopts=
120 passed, 1 warning in 0.20s

python -c "from maple import Document, InMemoryLexicalRetriever, SourceRef; print(Document, InMemoryLexicalRetriever, SourceRef)"
<class 'maple.autonomy.retrieval.Document'> <class 'maple.autonomy.retrieval.InMemoryLexicalRetriever'> <class 'maple.autonomy.retrieval.SourceRef'>

python -m compileall -q maple
exit code 0
```

The pytest warning is the existing `asyncio_mode` configuration warning when
plugin autoload is disabled. Existing aggregate Ruff debt in the two package
initializers remains a separate release-hardening item.

## Verdict

- [x] Slice review pass: no open BLOCKER or MAJOR finding.
- [ ] Final release review: pending slices 5-8 and independent fresh-context
  verifier availability.

The available environment has no separate fresh-agent session facility, so this
artifact records local review evidence and does not claim independent verifier
separation.
