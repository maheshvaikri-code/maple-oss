# ADR-137: Whole-package type-boundary closure

**Status:** Accepted for Slice192
**Date:** 2026-08-29

## Context

The release-hardening audit had three mypy diagnostics: two successful result
paths returned a possibly absent bounded invocation-response copy, and the
remote handoff adapter held a dynamically inferred `Result` value. Runtime
tests already covered these paths, but the static boundary was weaker than
the release contract required.

## Decision

In both in-memory and file-backed invocation stores, assign the copied
completed response to a local, reject an unexpected absent value with the
existing runtime error, and then construct `Result.ok` with the narrowed
response. Annotate the remote handoff adapter's successful result as
`Result[RemoteHandoffResult, Error]`.

## Consequences

- whole-package mypy can verify the existing public runtime boundary;
- runtime behavior and wire envelopes remain unchanged;
- no inline error suppression or dependency change is introduced;
- malformed or unexpectedly absent bounded responses still fail closed;
- hosted coordination, distributed scheduling, and exactly-once effects are
  unaffected and remain separate contracts.
