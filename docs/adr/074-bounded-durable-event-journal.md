# ADR-074: Bounded durable event journal

- **Status:** Accepted
- **Date:** 2026-08-27
- **Decision owners:** Chief Architect / Backend / Observability / Security

## Context

MAPLE's `EventStream` already redacts and bounds lifecycle events, retains a
thread-safe in-memory ring, and exposes authenticated cursor reads. A process
restart currently loses the retained event window, which prevents an operator
from replaying local observability evidence after a crash or planned restart.

## Decision

Add a host-owned `FileEventJournal` and an optional `EventStream(journal=...)`
attachment. The journal stores a versioned, bounded JSON event list under an
atomic replacement file and uses the existing durable fencing lease for each
load/append operation. `EventStream` loads the retained journal at startup and
persists each already-redacted event before notifying subscribers or exporters.
The existing `EventCursor`/`EventBatch` read API remains unchanged.

The journal retains at most `max_events`, caps the serialized journal record,
validates event identity/timestamps/payload JSON, and rejects non-monotonic
sequence writes. A restart rehydrates the next sequence after the latest
persisted event. Journal failure prevents in-memory publication and callback or
exporter delivery; no retry or remote aggregation is introduced.

## Security and failure contract

The journal is local host-owned state. Loaded payloads are re-applied through
the configured redaction policy before they become readable, and malformed,
oversized, non-finite, or non-monotonic records fail closed at startup or
append. The file contains already-redacted event content but may still contain
sensitive operational data, so the host owns filesystem access, retention, and
encryption. This design does not provide a multi-writer sequence allocator,
fleet aggregation, remote search, or exactly-once delivery.

## Alternatives considered

1. **Keep only the in-memory ring:** rejected because restart replay remains
   unavailable.
2. **Append unbounded newline records:** rejected because retention and file
   growth would be implicit and crash recovery would need partial-line repair.
3. **Add a database or remote telemetry dependency:** deferred; provider,
   cloud, tenancy, and operational lifecycle require a separate approved
   contract.

## Consequences

Hosts can recover a bounded local event window and continue cursor reads after
restart without a runtime dependency. Persistence adds bounded synchronous
local I/O to `publish`; a configured journal therefore makes disk availability
part of the event publication success contract. Subscribers/exporters still
remain best-effort observability side effects after the durable append.

