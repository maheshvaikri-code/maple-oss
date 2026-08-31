# ADR-024: Optional bounded Protobuf serialization

**Date:** 2026-08-25
**Status:** accepted
**Deciders:** Chief Architect

## Context

`SerializationFormat.PROTOBUF` was advertised by the core serializer, but both
directions returned `PROTOBUF_NOT_IMPLEMENTED`. Removing the enum would break
the public format surface; making protobuf a mandatory dependency would expand
the runtime dependency and deployment contract. MAPLE needs a useful local
binary path while preserving installations that do not include protobuf.

## Decision

When `google.protobuf` is available, MAPLE serializes JSON-compatible data
through a bounded `google.protobuf.Struct` envelope containing the MAPLE JSON
representation. The existing JSON preparation/restoration preserves tuples,
sets, bytes, and inert object dictionaries without reconstructing arbitrary
classes. Serialized and inbound payloads are capped at 1 MiB. Missing protobuf
continues to return a structured `PROTOBUF_UNAVAILABLE` error.

The envelope is intentionally schema-light: callers needing a domain-specific
protobuf schema can use their own generated message directly. MAPLE's generic
serializer provides a stable optional transport for its existing data contract,
not a replacement for generated schemas.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Bounded `Struct` envelope (chosen) | Optional, cross-language, preserves existing MAPLE values, no new dependency | Generic payload is JSON inside protobuf | Best compatibility-preserving implementation for the current serializer API |
| Add mandatory `protobuf` dependency | Simple availability and richer APIs | Expands every install's dependency/security/build surface | Violates the current optional-dependency posture |
| Remove the enum | No unsupported promise | Breaking public API and loses binary format capability | Not backward compatible |
| Require a generated message class | Strong schema typing | Cannot fit the existing `serialize(data)` API without a new public contract | Defer to caller-owned generated messages |

## Consequences

- Positive: the advertised format works when the optional library is present,
  with deterministic bounded round trips and fail-closed malformed input.
- Positive: installations without protobuf keep the previous optional behavior
  as an explicit structured error, rather than failing at import time.
- Negative / debt accepted: the generic MAPLE envelope is not a generated
  domain schema and embeds JSON text inside a protobuf message.
- Invalidation triggers: a required generated MAPLE wire schema, a mandatory
  protobuf dependency decision, or a versioned cross-language message contract.
