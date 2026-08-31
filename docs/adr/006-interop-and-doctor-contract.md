# ADR-006: Strict interop envelope and local doctor command

**Status:** Accepted
**Date:** 2026-08-24
**Decision owners:** Chief Architect / Interop / DevOps

## Context

MAPLE has many protocol adapters, but no small common envelope for adapter
round-trip tests. The CLI can show version and validate installation, but it
does not provide a machine-readable readiness report for the new runtime
surfaces.

## Decision

Add:

- `maple.autonomy.interop.InteropEnvelope`, strict JSON serialization/parsing,
  bounded payloads, and a round-trip helper for adapter contract tests;
- `maple doctor` with optional `--json`, reporting local core/autonomy,
  retrieval, event, evaluation, and interop readiness checks.

The envelope rejects unknown top-level fields and non-JSON values. The doctor
command is local-only: it does not contact providers, cloud services, or
external adapters.

## Consequences

Adapters can share deterministic contract fixtures without being forced into a
single wire protocol. Operators get a quick preflight signal while still
needing the full release test/audit matrix before publication.
