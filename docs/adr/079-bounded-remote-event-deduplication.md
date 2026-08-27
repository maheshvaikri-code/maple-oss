# ADR-079: Bounded Remote Event Deduplication

Status: Accepted for preview

Date: 2026-08-27

## Context

`EventForwarder` deliberately provides at-least-once delivery. A lost remote
response or cursor write can cause a source batch to be submitted again, and a
receiver that blindly publishes every item creates duplicate local events.
The existing authenticated batch transport needs an explicit, bounded
receiver-side option for suppressing those duplicate source deliveries.

The option must remain dependency-free and must not imply durable distributed
coordination or exactly-once external effects.

## Decision

Add `InMemoryEventDeduplicationStore`, an opt-in host-owned store keyed by
`(source_id, source_sequence)`. It retains a content digest and, after
successful publication, the already-redacted destination `AgentEvent`.

`HttpEventBatchSender(source_id=...)` includes the source ID at the batch level
and each source event's sequence in the item. `RunServer` accepts an optional
`event_deduplication_store`; when configured, authenticated batch requests must
include a valid source ID and positive per-item source sequence. `RunClient`
supports the same explicit source envelope through
`publish_events(..., source_id=...)`.

The store reserves a new claim before stream publication. A matching completed
claim returns the prior destination event without publishing again. A matching
pending claim returns `EVENT_DEDUPLICATION_IN_PROGRESS`; a changed payload,
event type, or run ID for the same source key returns
`EVENT_DEDUPLICATION_CONFLICT`. Failed publication releases the pending claim.
The receiving `EventStream` remains responsible for redaction, validation,
local sequence assignment, subscribers, and exporters.

Entries are bounded by configurable capacity and finite TTL. Expiration,
capacity eviction, process restart, and multiple stores can permit a later
duplicate, so this is a best-effort remote duplicate suppression contract, not
durable deduplication, a distributed idempotency service, or an exactly-once
side-effect guarantee.

## Alternatives considered

| Alternative | Decision |
| --- | --- |
| Publish every acknowledged item | Rejected: repeats are visible in the receiver's event stream after ordinary at-least-once recovery. |
| Derive identity from payload or event type | Rejected: distinct events can legitimately have identical content. |
| Persist a distributed deduplication log | Deferred: requires a storage, ownership, eviction, and deployment contract beyond this dependency-free runtime. |
| Claim exactly-once external effects | Rejected: event ingestion cannot control downstream side effects. |

## Security and failure boundaries

- The source ID is bounded and control-character-free; source sequences are
  positive integers.
- The store does not retain raw source payloads, only a SHA-256 content digest
  and the redacted destination event after publication.
- Pending claims prevent concurrent duplicate publication from being silently
  accepted; a blocked claim fails closed until it expires or is released.
- The store is process-local and in-memory. Operators must size capacity and
  TTL for their replay window and treat eviction/restart as duplicate-safe
  rather than as a durability promise.
- Authentication, principal identity, tenancy, TLS termination, and hosted
  scheduling remain host-owned boundaries.
