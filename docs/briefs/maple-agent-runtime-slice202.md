# Project/Task Brief — authenticated local session control plane

**Date:** 2026-08-29 · **Class:** L (new public HTTP routes, authorization
scopes, serialization contract, and cross-cutting server/client changes) ·
**Requested by:** human's continuing MAPLE parity/release-readiness objective

## Problem

MAPLE can now retain and branch conversation sessions locally, but a host that
already uses the authenticated loopback control plane cannot inspect a session
or request a data-only branch through that boundary. Operators would otherwise
need direct storage access or an ad hoc host endpoint, leaving session
time-travel and branching less portable than the surrounding agent/run
surfaces.

## Scope

- In: an optional host-owned `SessionStore` binding on `RunServer`; authenticated
  tip inspection, bounded history inspection, and data-only fork routes;
  additive `RunClient` methods; strict session ID/version/query/body
  validation; stable error-to-HTTP mapping; direct-library rejection of an
  explicitly empty fork target; docs, regression tests, and release evidence.
- **Non-goals:** hosted tenancy or identity federation, per-session ACLs,
  remote append/clear/compact/delete, remote session creation, distributed
  coordination, encryption, automatic summarization, execution or replay of
  stored messages, and exactly-once effects.
- Deferred: authenticated remote session mutation and per-session ownership
  policy require a separate human-approved contract; website updates remain
  deferred.

## Acceptance criteria (numbered, testable)

1. Given a `RunServer` configured with a session store and authentication,
   `GET /v1/sessions/{session_id}` returns one validated tip snapshot through
   `RunClient.inspect_session(...)`; a missing session returns typed 404 and a
   missing store returns typed 503.
2. Given retained session versions, `GET
   /v1/sessions/{session_id}/history?limit=N` returns at most the newest
   bounded snapshots in ascending version order; invalid, duplicate, unknown,
   zero, negative, or over-limit query parameters fail with 400 before the
   store history callback runs.
3. Given a valid fork request, `POST /v1/sessions/{session_id}/fork` creates
   the requested target through `RunClient.fork_session(...)`, returns a
   version-zero snapshot, and preserves source/target mutable-state isolation;
   stale, evicted, existing, invalid, and missing cases return typed errors
   without a second mutation attempt.
4. `session:read` authorizes tip/history reads and `session:fork` authorizes
   forks; unauthenticated and insufficient-scope requests are rejected before
   request-body processing, while existing routes and principal policies keep
   their current behavior.
5. A configured custom store with `load` but no optional `history` or `fork`
   capability returns explicit 501 for only the unsupported operation; a store
   callback exception becomes generic 503 without leaking the exception.
6. Returned snapshots are strict JSON-safe, bounded, identity-checked, and
   detached; malformed custom-store values and oversized responses fail closed
   without executing or replaying message/tool content.
7. `fork(source_id, new_session_id="")` fails with `INVALID_IDENTIFIER`, and
   the source store remains unchanged; the regression is covered for the
   in-memory and file-backed stores.
8. Public exports/docs/changelog/parity/release artifacts are updated; focused
   server/session tests, full regression tests, static checks, security checks,
   and clean package smoke are green without a new dependency or external
   publication.

## Direct-library correction completed

The non-transport portion of criterion 7 is complete at `325d04e`. Both
built-in stores now distinguish an omitted target (`None`, which generates a
bounded ID) from an explicitly empty target (`""`, which returns
`INVALID_IDENTIFIER`). The regression proves that the invalid call does not
consume the configured session capacity or create a branch. The authenticated
HTTP routes, scopes, and session-content responses remain human-gated.

## Constraints

- Preserve the existing loopback-only `RunServer` boundary and dependency-free
  HTTP client.
- Reuse the `SessionSnapshot`/`SessionStore` contract and existing principal
  scope model; no second session serialization format.
- Keep remote history response limits at 100 snapshots or fewer, bounded by
  `RunServer.max_response_bytes`; local store limits remain authoritative.
- GET is read-only. Fork has no automatic retry or idempotency claim; an
  explicit target collision returns a typed conflict and callers own retry
  policy.
- No cloud SDK, network service, database migration, or package dependency.

## Assumptions (chosen defaults — correct me if wrong)

- `session:read` and `session:fork` are host-configured coarse scopes; per-
  session ownership and tenant isolation remain outside this local contract.
- The remote read response includes the validated snapshot messages because
  the operation is an explicit authenticated session-inspection surface;
  hosts remain responsible for data classification and retention.
- Omitting a target ID on the direct library API may still generate one, but
  the remote fork route requires an explicit bounded target ID so a caller can
  reason about retry outcomes.
- Optional capability absence is represented as HTTP 501, matching existing
  durable-history transport behavior.

## Open questions (blocking — answered before G1)

- Human approval is required before implementation because this adds public
  `RunServer`/`RunClient` routes, scopes, and a remote session-content response.
  Proposed default: approve the local-only contract above; otherwise remove
  Slice 202 from the build queue.

**Human confirmed:** no · 2026-08-29 · implementation must pause at the §5
public-API escalation until the human responds.
