# QA + Security - MAPLE Agent Runtime Slice 17 @ working tree

**QA Engineer · Security Reviewer · Date:** 2026-08-24
**Build under test:** working tree after Slice 17 implementation; package
version `1.1.3`

## Acceptance criteria verification

| # | Criterion | How executed | Evidence | Pass |
|---|---|---|---|---|
| 1 | Supplied embeddings are validated at the boundary | Numeric, finite, non-zero, sequence, count, and dimension tests | `10 passed` retrieval suite | PASS |
| 2 | Ingestion is atomic and bounded | Count mismatch, invalid vector, dimension mismatch, duplicate, and quota tests | Stats remain unchanged on rejected adds | PASS |
| 3 | Vector search is deterministic and source-bearing | Cosine ranking, citation, tie-break, and removal tests | `10 passed` retrieval suite | PASS |
| 4 | No embedding model or vendor dependency is introduced | Dependency/static review and package build | No dependency change; wheel/sdist Twine checks pass | PASS |
| 5 | Public surface is documented and exported | ADR-015, API reference, README, changelog, root/autonomy exports | Combined focused gate and imports pass | PASS |

## Adversarial & edge matrix

| Input/scenario | Expected | Observed | Pass |
|---|---|---|---|
| Empty vector | Reject | `RETRIEVAL_VECTOR_INVALID` | PASS |
| Zero vector | Reject | `RETRIEVAL_VECTOR_INVALID` | PASS |
| NaN vector | Reject | `RETRIEVAL_VECTOR_INVALID` | PASS |
| Wrong vector count | Reject without document mutation | `RETRIEVAL_VECTOR_COUNT_MISMATCH`; stats unchanged | PASS |
| Wrong dimensions | Reject without partial index | `RETRIEVAL_VECTOR_DIMENSION_MISMATCH` | PASS |
| Vector quota+1 | Reject without partial index | `RETRIEVAL_VECTOR_LIMIT` | PASS |
| Similarity tie | Stable result order | Chunk ID ascending tie-break | PASS |
| Removal | Remove vectors and reset empty index dimension | Remaining search/stats reflect removal | PASS |

## Regression

```text
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/autonomy/test_retrieval.py -q -o addopts=
10 passed, 1 warning in 0.02s

$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/llm tests/autonomy tests/test_cli.py -q -o addopts=
196 passed, 1 warning in 0.88s

python -m compileall -q maple
compileall exit code: 0

python -m maple.cli doctor --json
{"checks": {"core": true, "evaluation": true, "events": true, "execution": true, "interop": true, "retrieval": true}, "network": false, "ready": true, "status": "SUCCESS", "version": "1.1.3"}

python -m twine check '.tmp-maple-vector-final\*'
Checking .tmp-maple-vector-final\maple_oss-1.1.3-py3-none-any.whl: PASSED
Checking .tmp-maple-vector-final\maple_oss-1.1.3.tar.gz: PASSED
```

The temporary package directory was removed after the check. The pytest
warning is the existing `asyncio_mode` configuration warning when plugin
autoload is disabled.

## Security sweep

- **Secrets:** `gitleaks` is unavailable. The bounded fallback scan over the
  changed retrieval/test/ADR files found no token-shaped secret patterns.
- **Input/deserialization:** vectors are finite numeric sequences with bounded
  dimensions; document text, metadata, chunk count, result count, and source
  references retain existing bounds. No deserialization or code execution was
  added.
- **Dependencies:** no dependency changed; the implementation is stdlib-only.
- **Dangerous constructs:** no network, shell, `eval`, `exec`, or `pickle` was
  added. Index mutation occurs only after all document/vector validation.
- **Failure posture:** invalid and oversized vector inputs return typed
  `Result` errors and leave the index unchanged; no model fallback is claimed.

**Security verdict:** SIGN-OFF for this changed feature boundary; not a final
publish authorization.
**QA verdict:** CONDITIONAL PASS for Slice 17; full repository regression,
repository-wide lint, independent fresh-context verification, and external
publication remain open release gates.
