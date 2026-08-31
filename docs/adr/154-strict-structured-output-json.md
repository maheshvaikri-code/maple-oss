# ADR-154: Strict finite JSON at the structured-output boundary

**Status:** Accepted for Slice 210 implementation
**Date:** 2026-08-29
**Decision owners:** Chief Architect / Backend / Security / QA / Release

## Context

`parse_structured_output()` and `parse_typed_output()` share the bounded
`_parse_json_value()` helper. Python's JSON decoder accepts the JavaScript
extensions `NaN`, `Infinity`, and `-Infinity` by default. Those values are not
JSON and a non-finite number can pass the current numeric-bound checks because
both `<` and `>` comparisons are false. A deeply nested bounded-byte payload
can also cause the decoder to raise `RecursionError`.

## Decision

Keep the existing parser and public APIs, but configure `json.loads()` with a
`parse_constant` callback that raises `ValueError`, and catch
`RecursionError` alongside the existing JSON parse failures. The existing
error mapping remains `STRUCTURED_OUTPUT_INVALID_JSON`; the bounded exception
type name may be retained in the existing `reason` field without returning
raw input or a traceback.

## Alternatives considered

1. **Accept Python JSON extensions.** Rejected because they violate JSON and
   permit non-finite values into structured-output validation.
2. **Pre-scan the text for constant names.** Rejected because it is brittle
   around strings, escapes, and token boundaries; use the decoder hook.
3. **Replace the stdlib decoder or add a dependency.** Rejected because the
   existing decoder is sufficient and the project prefers zero new runtime
   dependencies.
4. **Set a process-wide recursion limit.** Rejected because it changes
   unrelated application behavior; normalize the parser boundary instead.

## Failure and security controls

- Non-standard constants fail before schema or model validation.
- Decoder recursion failures are converted to the existing typed error.
- The parser's existing UTF-8 byte bound remains in force.
- No raw JSON text, provider payload, or traceback is returned.

## Consequences

Valid RFC-compatible JSON behavior is unchanged. Callers that previously
relied on Python-only numeric constants will receive a typed rejection, which
is the intended compatibility correction. The change does not make model
output semantically correct or enforce provider-native structured generation.

## Rollback

Remove the decoder hook, recursion catch, tests, and documentation. No data,
index, external service, or persisted state is changed.
