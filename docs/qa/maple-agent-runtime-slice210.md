# Slice 210 QA and security report - strict structured-output JSON parsing

**QA Engineer:** QA role
**Security Reviewer:** Security role
**Candidate:** `65d3b51`
**Date:** 2026-08-29
**Independent verifier:** Unavailable in this environment; no independent
fresh-session result is claimed.

## Acceptance criteria verification

| Criterion | Evidence | Result |
| --- | --- | --- |
| Reject `NaN`, `Infinity`, and `-Infinity` | `test_structured_output_rejects_non_standard_numeric_constants`; focused contracts suite | PASS |
| Normalize decoder recursion failures | `test_structured_output_normalizes_decoder_recursion_failure`; focused contracts suite | PASS |
| Preserve valid finite JSON and existing validation | `test_structured_output_accepts_finite_json_numbers`, existing contract/model tests, full suite | PASS |
| Keep errors bounded and fail closed | Diff-scoped secret scan `diff_secret_scan_matches=0`; no raw payload or traceback added; implementation review | PASS |
| Keep docs and release records aligned | README, API reference, parity ledger, changelog, brief, ADR, plan, and release-plan entry updated | PASS |
| Preserve repository/package health | Full suite, static checks, dependency audit, and clean package smoke below | PASS |

## Adversarial and edge matrix

| Input/scenario | Expected | Observed | Pass |
| --- | --- | --- | --- |
| `NaN` | Typed invalid-JSON error | `STRUCTURED_OUTPUT_INVALID_JSON` | PASS |
| `Infinity` | Typed invalid-JSON error | `STRUCTURED_OUTPUT_INVALID_JSON` | PASS |
| `-Infinity` | Typed invalid-JSON error | `STRUCTURED_OUTPUT_INVALID_JSON` | PASS |
| Finite decimal `1.5` | Parse and validate | Parsed as `1.5` | PASS |
| Decoder `RecursionError` | Typed invalid-JSON error | `STRUCTURED_OUTPUT_INVALID_JSON` | PASS |
| Existing bounded/invalid JSON cases | Preserve prior contract | Full contracts suite green | PASS |

## Regression

```text
python -m pytest tests/autonomy/test_contracts.py -q
============================= 19 passed in 4.08s ==============================

python -m pytest -q
================= 1881 passed, 1 skipped in 420.17s (0:07:00) ================
```

Flakes: none observed. The first iteration exposed an invalid test assumption
about Python 3.12's ability to parse a 2,000-level payload; the test was
replaced with deterministic decoder-failure injection and the corrected suite
passed.

## Static and dependency verification

```text
python -m black --check maple/autonomy/contracts.py tests/autonomy/test_contracts.py
All checks passed.

python -m isort --check-only maple/autonomy/contracts.py tests/autonomy/test_contracts.py
2 files would be left unchanged.

python -m ruff check maple/autonomy/contracts.py tests/autonomy/test_contracts.py
All checks passed!

python -m mypy maple --ignore-missing-imports
Success: no issues found in 102 source files

python -m compileall -q maple
exit 0

python -m pip_audit --strict .
No known vulnerabilities found
```

## Clean package smoke

The smoke ran against exact candidate `65d3b517181e2f52c04c728e695fe0455880e044`.

```text
source_archive_entries=906
wheel_entries=109
build_exit=0
twine_exit=0
install_exit=0
import_exit=0
doctor_exit=0
import_output=1.1.3; finite structured parse=1.5
doctor_output={"checks": {"core": true, "evaluation": true, "events": true, "execution": true, "interop": true, "retrieval": true, "server": true, "sessions": true}, "network": false, "ready": true, "status": "SUCCESS", "version": "1.1.3"}
```

## Security sweep

- Diff-scoped token scan: `diff_secret_scan_matches=0`.
- No new network, shell, subprocess, import, `eval`, execution, storage, or
  authorization path was introduced.
- Strict decoder constants and recursion failures fail closed before schema or
  typed-model validation; the existing UTF-8 byte bound remains active.
- `pip_audit --strict .`: `No known vulnerabilities found`.
- Bandit and Gitleaks are unavailable in this environment; no pass is claimed
  for either tool. The broad workspace token scan contains existing examples,
  redaction fixtures, and user-owned doctrine tests and is not treated as a
  clean secrets result.

**Security verdict:** SIGN-OFF for this scoped change, with the tooling and
independent-verifier limitations above. No human override.

**QA verdict:** PASS for the Slice 210 local acceptance contract.

The broader release remains conditional on the existing CI/header policy,
dependency-governance, clean-main, independent-review, version, and human
publication gates. No publication, cloud action, or website update occurred.
