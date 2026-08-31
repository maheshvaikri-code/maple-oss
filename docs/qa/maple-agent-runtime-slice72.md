# Slice 72 QA - Optional Bounded Protobuf Serialization

**Role:** Backend / Interop / QA / Release
**Commit:** `2b8bb57`
**Date:** 2026-08-25

## Scope

Implement both directions of the advertised `SerializationFormat.PROTOBUF`
path without adding a mandatory runtime dependency.

## Evidence

- Serialization regression: `28 passed in 0.28s`.
- Core/autonomy regression: `240 passed in 3.37s`.
- `python -m mypy maple/ --ignore-missing-imports`: `Success: no issues found
  in 93 source files`.
- `ruff check maple` and `ruff check tools tests`: `All checks passed!`.
- Black reports `93 files would be left unchanged`; isort passes.
- Compile, wheel/sdist, Twine, and network-free doctor gates pass.

## Boundary review

- Uses `google.protobuf.Struct` only when the optional library is available.
- Encodes MAPLE's JSON-compatible representation to preserve integer values and
  existing tuple/set/bytes/inert-object restoration behavior.
- Caps serialized and inbound payloads at 1 MiB.
- Rejects malformed or missing-envelope payloads with structured errors.
- Missing protobuf returns `PROTOBUF_UNAVAILABLE` without import-time failure.
- No arbitrary object reconstruction or code execution is introduced.

## Decision

PASS for the slice. ADR-024 records the schema-light envelope tradeoff. No new
dependency, publication, website mutation, or external service action was
introduced. Exact full-suite and fresh verifier gates remain open.
