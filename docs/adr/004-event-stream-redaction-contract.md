# ADR-004: Bounded event streaming with redaction

**Status:** Accepted
**Date:** 2026-08-24
**Decision owners:** Chief Architect / Observability / Security Reviewer

## Context

MAPLE has decision traces and a transport-level stream, but no common typed
event contract for workflow/model/tool lifecycle events. Unbounded traces,
callbacks, and raw payloads can leak credentials or exhaust memory.

## Decision

Add `maple.autonomy.events.EventStream` with:

- monotonic per-stream sequence numbers and bounded ring retention;
- JSON-only payloads with depth, item, string, and byte bounds;
- recursive redaction of credential-like keys before retention or delivery;
- synchronous subscribers that are isolated from each other's exceptions;
- snapshot and wait APIs for polling or live consumers;
- structured `Result` errors for invalid, oversized, or malformed events.

This is an in-process observability/event contract, not a durable message broker
or hosted telemetry service. Agent/workflow integrations can publish into it in
later slices without coupling their core logic to a specific exporter.

## Consequences

Events are safe to retain and forward by default, but redaction is defense in
depth rather than a substitute for avoiding secrets in model/tool payloads.
Subscribers run synchronously, so slow callbacks must be isolated by the host
or replaced with a queue-backed adapter.
