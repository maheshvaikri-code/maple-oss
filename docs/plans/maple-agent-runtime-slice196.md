# Slice 196 plan - bounded provider failover

**Brief:** [maple-agent-runtime-slice196.md](../briefs/maple-agent-runtime-slice196.md)
**Design/ADR:** [ADR-140](../adr/140-bounded-provider-failover.md)
**Class:** L

## Slices

| # | Slice | Role | Files touched | Proven by (tests) | Status |
|---|---|---|---|---|---|
| 1 | Failover wrapper and router option | Backend / ML / Security | `maple/llm/capabilities.py`, provider tests, exports | deterministic order, sync/async transient failover, fail-fast, bounds, typed exceptions | todo |
| 2 | Public API and parity documentation | Interop / Tech Writer | `maple/llm/__init__.py`, root exports, README/API/parity/changelog | public import and runnable example | todo |
| 3 | Review, QA, and package evidence | Code Reviewer / QA / Release | review/QA/release plan | focused/full regression, static checks, clean/current package smoke | todo |

## Threat sketch

Assets are provider credentials/configuration references, model requests and
responses, usage counters, and bounded error metadata. Untrusted inputs include
requirements, provider descriptors, configs, provider error mappings, and
raised exception types. The main abuse is turning one request into unbounded
provider calls or leaking provider error content. A maximum of eight initialized
providers, one attempt per provider, exact retryable types, sanitized provider
names/exception class names, and no raw error-message aggregation contain the
boundary.

## Risks and rollback points

- Risk: failover changes model/cost unexpectedly -> mitigation: explicit
  `failover=True`, deterministic metadata, and default-off compatibility;
  rollback: remove the option/wrapper while retaining router selection.
- Risk: streaming consumers infer continuity -> mitigation: reject streaming
  requirements at router creation and document completion-only semantics;
  rollback: remove failover export without touching native provider streams.
- Risk: child provider is not thread-safe -> mitigation: no shared mutable
  failover state and explicit child-provider ownership in the ADR; rollback:
  require host serialization in a follow-up contract.

## Deviation log

- None.

## Status snapshot

G1/G2 design is ready for implementation. Next: add the bounded wrapper and
router integration, then prove sync/async and fail-closed boundaries.
