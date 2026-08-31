# Code Review - MAPLE Agent Runtime Slice 17 @ working tree

**Reviewer role:** Code Reviewer · **Date:** 2026-08-24
**Reviewed against:** [brief](../briefs/maple-agent-runtime-release.md),
[ADR-015](../adr/015-dependency-free-vector-retrieval.md), and
[implementation plan](../plans/maple-agent-runtime-release.md)

## Scope

This slice adds a bounded, thread-safe in-memory cosine index over
caller-supplied embeddings. It validates one vector per generated chunk,
finite numeric values, non-zero norms, one index dimension, quotas, atomic
ingestion, deterministic ties, and source-bearing vector hits. It does not
ship an embedding model, hosted vector database, ANN accelerator, persistence,
or production RAG quality claim.

## Findings

| # | Sev | Location | Finding | Suggested fix | Resolution |
|---|---|---|---|---|---|
| 1 | MINOR | `InMemoryVectorRetriever` | Linear scan is not an ANN implementation and will not provide production-scale latency. | Add a separately evaluated persistent/ANN adapter when a deployment target and dependency are approved. | Explicitly documented in ADR-015 and API/README; accepted for the local reference seam. |
| 2 | MINOR | Embedding boundary | Retrieval tests prove ranking and validation, not the quality of any embedding model. | Add versioned recall/groundedness evals when a pinned embedding provider is introduced. | Explicitly documented in ADR-015; no model change is part of this slice. |

## Scope check

The diff matches Slice 17. It adds no dependency, credential, cloud call,
website change, publication action, or embedding-model claim. Invalid vectors,
dimension mismatches, quota overflow, duplicate documents, and malformed
queries fail before index mutation.

## Verification evidence

```text
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/autonomy/test_retrieval.py -q -o addopts=
10 passed, 1 warning in 0.02s

$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/llm tests/autonomy tests/test_cli.py -q -o addopts=
196 passed, 1 warning in 0.88s

ruff check maple/autonomy/retrieval.py tests/autonomy/test_retrieval.py
All checks passed!

python -m flake8 maple/autonomy/retrieval.py tests/autonomy/test_retrieval.py --max-line-length=88 --extend-ignore=E203,W503,W291,W293,E302,E402,F401,F811,F841 --count --statistics
0

python -m compileall -q maple
compileall exit code: 0

python -m maple.cli doctor --json
{"checks": {"core": true, "evaluation": true, "events": true, "execution": true, "interop": true, "retrieval": true}, "network": false, "ready": true, "status": "SUCCESS", "version": "1.1.3"}

python -m twine check '.tmp-maple-vector-final\*'
Checking .tmp-maple-vector-final\maple_oss-1.1.3-py3-none-any.whl: PASSED
Checking .tmp-maple-vector-final\maple_oss-1.1.3.tar.gz: PASSED
```

The pytest warning is the existing `asyncio_mode` configuration warning when
plugin autoload is disabled. Independent fresh-context verifier sessions are
not available in this tool context, so this is local review evidence only.

## Verdict

- [x] Pass: no open BLOCKER or MAJOR finding.
- [ ] Return to build.
