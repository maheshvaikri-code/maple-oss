# Slice 210 brief - strict structured-output JSON parsing

**Date:** 2026-08-29
**Class:** M (single existing structured-output boundary)
**Roles:** Chief Architect / Backend / Security / QA / Release

## Problem

MAPLE's bounded structured-output parser uses Python's default JSON decoder.
That decoder accepts non-standard `NaN`, `Infinity`, and `-Infinity` values,
which are not JSON and can bypass numeric validation because comparisons with
non-finite values do not reject them. Deeply nested input can also raise a
parser `RecursionError` rather than returning MAPLE's typed structured-output
failure.

## Scope

- In: reject non-standard JSON numeric constants; normalize parser recursion
  failures at the existing `_parse_json_value` boundary; add regression tests
  for structured and typed output paths; document the strict JSON behavior.
- Out: changing the public function signatures, adding a JSON dependency,
  implementing a new schema dialect, changing Pydantic validation, or
  executing model output.

## Acceptance criteria

1. `parse_structured_output` rejects `NaN`, `Infinity`, and `-Infinity` with
   `STRUCTURED_OUTPUT_INVALID_JSON` before schema validation.
2. Deeply nested JSON that exceeds the decoder's safe recursion boundary
   returns `STRUCTURED_OUTPUT_INVALID_JSON` rather than propagating
   `RecursionError`.
3. Valid finite JSON, existing schema checks, and `parse_typed_output` behavior
   remain unchanged.
4. No raw parser detail, model output beyond the existing bounded reason, or
   private data is disclosed by the error boundary.
5. Focused contracts tests, the full suite, static checks, project dependency
   audit, and package smoke remain green.

## Safety boundary

The parser receives model/provider text and is a trust boundary. Strict JSON
decoding prevents non-standard numeric values from entering typed structured
output. This does not claim semantic correctness, schema completeness, or
provider-side structured-generation enforcement.
