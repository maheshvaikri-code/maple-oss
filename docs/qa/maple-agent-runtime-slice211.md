# Slice 211 QA and security report - asynchronous document ingestion

**QA Engineer:** QA role
**Security Reviewer:** Security role
**Candidate:** `910bb00`
**Date:** 2026-08-29
**Independent verifier:** Unavailable in this environment; no independent
fresh-session result is claimed.

## Acceptance criteria verification

| Criterion | Evidence | Result |
| --- | --- | --- |
| Await bounded async connector pages and preserve report/cursor semantics | Async retrieval suite: `95 passed in 9.19s`; cursor-page and completion regressions | PASS |
| Checkpoint only after a complete page | `test_async_document_connector_runs_sync_callbacks_in_default_executor`; `test_async_document_connector_does_not_checkpoint_incomplete_page`; checkpoint-save failure regression | PASS |
| Reject invalid bounds, malformed pages, stalled cursors, and duplicate IDs before unsafe writes | Async option matrix, over-limit, empty advancing page, stalled cursor, and duplicate-page regressions | PASS |
| Normalize callback failures without disclosure | Connector/sink/checkpoint/rate-limit failure regressions; `diff_secret_scan_matches=0` | PASS |
| Preserve completion and cancellation behavior | Completed checkpoint-compatible path and `test_async_document_connector_preserves_task_cancellation` | PASS |
| Export and document the public surface without expanding scope | `AsyncDocumentConnector` and `ingest_documents_async` exported from `maple` and `maple.autonomy`; README/API/parity/changelog/ADR updated | PASS |
| Pass repository, static, dependency, and package gates | Full suite, format/lint/type/compile, `pip_audit`, and exact clean package smoke below | PASS |

## Adversarial and edge matrix

| Input/scenario | Expected | Observed | Pass |
| --- | --- | --- | --- |
| Empty page with advancing cursor | Reject before sink mutation | `RETRIEVAL_CONNECTOR_INVALID`; no sink call | PASS |
| Page larger than remaining document budget | Reject before sink mutation | `RETRIEVAL_CONNECTOR_LIMIT`; no sink call | PASS |
| Zero and over-limit `batch_size`, `max_documents`, and `max_batches` | Typed bounded-limit error | `RETRIEVAL_CONNECTOR_LIMIT` | PASS |
| Invalid cursor containing a control character | Typed connector error | `RETRIEVAL_CONNECTOR_INVALID` | PASS |
| Repeated document ID across pages | Reject before duplicate sink write | `RETRIEVAL_CONNECTOR_DUPLICATE_DOCUMENT`; one first-page write only | PASS |
| Stalled cursor | Reject before sink write | `RETRIEVAL_CONNECTOR_CURSOR_STALLED`; no sink call | PASS |
| Connector/sink/checkpoint private exception or result | Generic redacted error | Typed generic error; private text absent | PASS |
| Rate-limit denial | Stop before next fetch | `RETRIEVAL_CONNECTOR_RATE_LIMITED`; one fetch only | PASS |
| Cancelled async connector task | Propagate cancellation; no incomplete checkpoint | `asyncio.CancelledError`; no sink call | PASS |
| Synchronous callbacks from an async caller | Do not block event-loop thread | Sink/checkpoint/rate-limit callbacks ran on executor threads | PASS |
| Unicode and malformed document data | Existing bounded document validation remains authoritative | Covered by existing retrieval/document validation tests in the full suite; async path invokes the same `DocumentBatch.validate()` boundary | PASS |

## Regression

```text
python -m pytest tests/autonomy/test_retrieval.py -q
============================= 95 passed in 9.19s ==============================

python -m pytest -q
================= 1903 passed, 1 skipped in 419.00s (0:06:58) ================
```

Flakes: none observed. The exact-candidate full suite included all new async
tests and completed without failures.

## Static and dependency verification

```text
python -m black --check maple/autonomy/retrieval.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_retrieval.py
4 files would be left unchanged.

python -m isort --check-only maple/autonomy/retrieval.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_retrieval.py
4 files would be left unchanged.

python -m ruff check maple/autonomy/retrieval.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_retrieval.py
All checks passed!

python -m mypy maple --ignore-missing-imports
Success: no issues found in 102 source files

python -m compileall -q maple
compileall_exit=0

python -m pip_audit --strict --progress-spinner off --timeout 30 .
No known vulnerabilities found
```

## Clean package smoke

The smoke used `git archive HEAD` at exact candidate
`910bb000ab7ec75fc1877828a8c6374f96143eca` in an isolated temporary
checkout. Preserved dirty and untracked workspace files were not included.

```text
source_archive_entries=991
wheel_entries=109
sdist_entries=905
build_exit=0
twine_exit=0
install_exit=0
import_exit=0
import_output=1.1.3 AsyncDocumentConnector ingest_documents_async
doctor_exit=0
doctor_output={"checks": {"core": true, "evaluation": true, "events": true, "execution": true, "interop": true, "retrieval": true, "server": true, "sessions": true}, "network": false, "ready": true, "status": "SUCCESS", "version": "1.1.3"}
```

## Security sweep

- Diff-scoped secret scan over added lines:
  `diff_secret_scan_matches=0`.
- Diff-scoped dangerous-construct scan:
  `diff_dangerous_construct_matches=0`.
- No new network, shell, subprocess, deserialization, authorization, or
  execution path was introduced. Async connector data is validated before
  sink mutation, errors are generic, and counts/cursors/documents remain
  bounded by the existing retrieval rules.
- `pip_audit --strict`: `No known vulnerabilities found`.
- Bandit and Gitleaks are unavailable in this environment; no pass is claimed
  for either tool. Fresh independent verifier sessions are also unavailable.

**Security verdict:** SIGN-OFF for this scoped change, with the tooling and
independent-verifier limitations above. No human override.

**QA verdict:** PASS for the Slice 211 local acceptance contract.

The broader release remains conditional on existing CI/header-policy findings,
clean-main, independent-review, version, and human publication gates. No
publication, cloud action, registry write, tag, or website update occurred.
