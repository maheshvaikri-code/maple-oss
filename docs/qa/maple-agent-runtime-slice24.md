# QA + Security Report - MAPLE agent runtime slice 24 @ `90203f8`

**QA Engineer** · **Security Reviewer** · **Date:** 2026-08-25
**Build under test:** commit `90203f8` (`feat(evaluation): add groundedness scoring proxy`)

## Acceptance criteria verification

| # | Criterion | How executed | Evidence | Pass |
|---|-----------|--------------|----------|------|
| 1 | The capability is native, documented, and bounded. | Inspected the public exports, ADR, API reference, README, changelog, and plan; ran the evaluation module tests. | `tests/autonomy/test_evaluation.py`: `15 passed in 0.38s`. | PASS |
| 2 | Groundedness scoring is deterministic and reports claim/source coverage. | Ran supported and below-threshold cases through `EvaluationHarness.run_groundedness`. | Focused evaluation tests assert stable claim counts, ratios, supported indexes, and evidence URIs plus typed threshold failure. | PASS |
| 3 | Malformed runners, duplicate sources, non-finite thresholds, runner errors, and case-size limits fail closed per case. | Exercised malformed observations, raising and `Result`-error runners, duplicate source validation, non-finite threshold validation, and a bounded harness case. | The 15-test evaluation suite passes; failures remain typed and isolated. | PASS |
| 4 | Package/public surface remains usable. | Ran the combined feature gate, compile, doctor, wheel/sdist build, Twine, and a fresh-venv wheel smoke on the exact implementation commit. | `240 passed in 3.31s`; compile exit `0`; doctor `ready: true`; wheel/sdist Twine checks `PASSED`; clean-wheel doctor exit `0`. | PASS |

## Adversarial & edge matrix

| Input/scenario | Expected | Observed | Pass |
|----------------|----------|----------|------|
| Unsupported claim ratio below threshold | Typed per-case threshold failure | Groundedness threshold error returned without aborting other cases | PASS |
| Runner raises | Typed runner error and continued evaluation | Runner error isolated in the report | PASS |
| Runner returns malformed observation | Typed observation error | Malformed observation isolated in the report | PASS |
| Runner returns `Result` error | Preserve typed runner failure | Error result surfaced per case | PASS |
| Duplicate source URI | Reject case construction | Validation rejects the case | PASS |
| Non-finite threshold | Reject case construction | Validation rejects `NaN`/infinite threshold | PASS |
| Oversized case under a small harness quota | Reject before runner execution | Case-size bound error returned | PASS |
| Lexical overlap proxy | Deterministic counts and source URI selection | Supported indexes, ratio, and evidence URIs are stable | PASS |

## Regression

```text
python -m pytest tests/llm tests/autonomy tests/test_cli.py -q -o addopts=
240 passed in 3.31s

python -m pytest -q tests/autonomy/test_evaluation.py -o addopts=
15 passed in 0.38s

python -m compileall -q maple
COMPILE_EXIT=0

python -m maple.cli doctor --json
{"checks": {"core": true, "evaluation": true, "events": true, "execution": true, "interop": true, "retrieval": true, "server": true, "sessions": true}, "network": false, "ready": true, "status": "SUCCESS", "version": "1.1.3"}

python -m ruff check maple/autonomy/evaluation.py tests/autonomy/test_evaluation.py
All checks passed!

python -m twine check "$artifactDir\*"
Checking C:\Project_WorldLevel\MAPLE\maple-oss\.tmp-maple-slice24-release\maple_oss-1.1.3-py3-none-any.whl: PASSED
Checking C:\Project_WorldLevel\MAPLE\maple-oss\.tmp-maple-slice24-release\maple_oss-1.1.3.tar.gz: PASSED
TWINE_EXIT=0

Fresh-wheel smoke on the exact implementation commit
{"checks": {"core": true, "evaluation": true, "events": true, "execution": true, "interop": true, "retrieval": true, "server": true, "sessions": true}, "network": false, "ready": true, "status": "SUCCESS", "version": "1.1.3"}
WHEEL_DOCTOR_EXIT=0
CLEANUP_EXIT=0
```

The latest bounded full-repository attempt remains incomplete: it reported
`1049 passed, 8 warnings in 839.17s` before interruption in slow Doctrine gold
cases. No assertion failure was reported, but this is not a full-suite pass.

## Bugs found

| # | Repro steps | Severity | Fixed @ | Re-verified | Regression test |
|---|-------------|----------|----------|-------------|-----------------|
| 1 | QA review found that duplicate-source validation and non-finite-threshold validation shared one test path, which could hide a regression in either constructor check. | MINOR | `90203f8` | `15 passed` | `test_groundedness_rejects_duplicate_sources` and `test_groundedness_rejects_non_finite_threshold` |

## Security sweep

- **Secrets:** `gitleaks` is unavailable. The changed-diff fallback scan found
  only the implementation symbol `_GROUNDING_TOKEN`; it found no credential
  literal.
- **Injection/path:** the slice performs no file, network, shell, or dynamic
  code execution. Query, URI, source, answer, claim, and case collections are
  bounded; source URIs are validated and duplicate IDs are rejected.
- **Deserialization:** the public contract uses typed Python values and
  bounded text; no `pickle`, `eval`, or `exec` was added.
- **Dependencies:** no new runtime dependency. `python -m pip_audit --local`
  remains blocked by the shared environment: it reported `383 known
  vulnerabilities in 77 packages` and local packages unavailable on PyPI.
  This is an existing environment/repository release blocker, not introduced
  by Slice 24.
- **Metric boundary:** documentation and ADR explicitly prevent treating
  lexical overlap as semantic entailment, factuality, citation faithfulness,
  or an LLM-as-judge result.

**Security verdict:** SIGN-OFF for the Slice 24 implementation; repository-wide
dependency-audit findings remain an open release gate.
**QA verdict:** pass for Slice 24; publish clearance remains open pending the
full repository regression, repository-wide lint debt, dependency-audit
disposition, and independent fresh-context verification.
