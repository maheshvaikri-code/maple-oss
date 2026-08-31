# QA + Security - MAPLE Agent Runtime Slice 22 @ `a682656`

**QA Engineer · Security Reviewer · Date:** 2026-08-24  
**Build under test:** exact commit `a682656`; package version `1.1.3`

## Acceptance criteria verification

| # | Criterion | How executed | Evidence | Pass |
|---|---|---|---|---|
| 1 | Golden retrieval cases can score source precision, recall, and F1. | Real lexical retriever case and vector-hit case run through `EvaluationHarness.run_retrieval`. | Focused evaluation suite: `10 passed`; perfect case score `1.0`; low-recall case reports F1 `2/3`. | PASS |
| 2 | Both lexical and vector retrieval hit contracts are supported. | Lexical `RetrievalHit` output and `VectorRetrievalHit` output are evaluated. | Both cases execute through the shared public API. | PASS |
| 3 | Invalid/hostile evaluation inputs fail in bounded, isolated ways. | Malformed hit sequence, raising runner, duplicate/unhashable golden URIs, and hit-limit cases. | Typed `RAG_OBSERVATION_INVALID`, `RAG_RUNNER_EXCEPTION`, `RAG_CASE_INVALID`, and `RAG_HIT_LIMIT`; remaining cases continue. | PASS |
| 4 | The feature makes no faithfulness claim and remains dependency-free. | ADR/API review, public imports, compile/doctor, package build, and Twine checks. | Explicit docs scope retrieval coverage only; no new dependency; wheel/sdist Twine `PASSED`. | PASS |

## Adversarial & edge matrix

| Input/scenario | Expected | Observed | Pass |
|---|---|---|---|
| Empty/invalid query or empty golden set | Reject case before runner | `RAG_CASE_INVALID` | PASS |
| Duplicate or unhashable expected URI | Reject without Python exception | `RAG_CASE_INVALID` | PASS |
| Unknown hit type | Isolate malformed observation | `RAG_OBSERVATION_INVALID` | PASS |
| Runner exception | Isolate case and redact exception details | `RAG_RUNNER_EXCEPTION` with exception type only | PASS |
| Hit count over configured cap | Reject before iterating unbounded output | `RAG_HIT_LIMIT` | PASS |
| Duplicate chunks from one source | Score unique source coverage | Source URI deduplication exercised by implementation contract | PASS |
| Missing expected source | Fail recall threshold | `RAG_RECALL_LOW` with bounded metrics | PASS |

## Regression

```text
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/autonomy/test_evaluation.py -q -o addopts=
10 passed, 1 warning in 0.04s

$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/llm tests/autonomy tests/test_cli.py -q -o addopts=
225 passed, 1 warning in 3.00s

python -m compileall -q maple
COMPILE_EXIT=0

python -m maple.cli doctor --json
{"checks": {"core": true, "evaluation": true, "events": true, "execution": true, "interop": true, "retrieval": true, "server": true, "sessions": true}, "network": false, "ready": true, "status": "SUCCESS", "version": "1.1.3"}

python -m twine check .tmp-maple-slice22-final\maple_oss-1.1.3-py3-none-any.whl .tmp-maple-slice22-final\maple_oss-1.1.3.tar.gz
Checking ...maple_oss-1.1.3-py3-none-any.whl: PASSED
Checking ...maple_oss-1.1.3.tar.gz: PASSED
```

The pytest warning is the existing `asyncio_mode` configuration warning when
plugin autoload is disabled.

## Bugs found

| # | Repro steps | Severity | Fixed @ | Re-verified | Regression test |
|---|---|---|---|---|---|
| 1 | Pass an unhashable expected URI or more than the configured hit quota. | MAJOR | `a682656` | `10` focused and `225` combined tests pass. | `test_retrieval_evaluation_rejects_unhashable_golden_uri_without_raising`; `test_retrieval_evaluation_bounds_runner_hit_count` |

## Security sweep

- **Secrets:** `gitleaks` is unavailable. The fallback scan found no
  credential literals in the new evaluator, tests, ADR, or docs; broader
  repository matches are existing placeholders/documentation.
- **Input/deserialization:** evaluation cases, source URIs, hit types, hit
  counts, metadata, and report values are bounded/validated; no persisted
  payload is executed.
- **Dependencies:** no dependency was added. The existing shared-interpreter
  `pip_audit --local` result remains `383` known vulnerabilities across `77`
  packages, with additional local packages unavailable on PyPI; this is a
  pre-existing release gate and not introduced by Slice 22.
- **Dangerous constructs:** no `pickle`, `eval`, `exec`, shell execution,
  network operation, or model call was added.
- **Failure posture:** malformed cases and runner failures are typed and
  isolated per case; report actual values pass through existing redaction and
  byte bounds.

**Security verdict:** SIGN-OFF for this changed feature boundary; shared
dependency remediation and release authorization remain open.  
**QA verdict:** CONDITIONAL PASS for Slice 22; full repository regression,
repository-wide lint, independent fresh-context verification, shared
dependency remediation, and external publication remain open release gates.
