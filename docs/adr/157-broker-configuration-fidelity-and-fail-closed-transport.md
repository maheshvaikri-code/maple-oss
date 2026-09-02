# ADR-157: Broker configuration fidelity and fail-closed transport selection

**Date:** 2026-08-31
**Status:** accepted
**Deciders:** Chief Architect (with Security Reviewer at G5)

## Context

A full-repository analysis of 2.0.0 found three defects that share one root
cause: `MessageBroker` is a process-wide singleton whose entire configuration
is frozen at first construction, and nothing guarantees that the first
construction belongs to a real user.

1. **Import-time seeding.** `maple/__init__.py` ran `validate_installation()`
   under `if __debug__:` — true in every ordinary interpreter, false only under
   `python -O`. The inline comment claimed the opposite ("only run validation in
   debug mode to avoid import overhead in production"). That function built a
   real `Agent(Config(agent_id="validation_test", broker_url="memory://test"))`,
   so `import maple` pinned the singleton before any user code ran.

2. **Security configuration discarded.** `MessageBroker.__init__` early-returns
   when `_initialized`, so `security_config`, `link_manager`, and
   `_auth_manager` retained the values from that import-time agent — which had
   no security at all. Every user `SecurityConfig` was silently dropped. The
   defect class was already known: `_refresh_separation_policy` exists
   specifically to work around it, but was applied to exactly one field.

3. **Link enforcement failed open.** The `strict_link_policy` rejection was
   nested inside `if self.link_manager:`. With no link manager, the entire
   check was skipped and the send proceeded. A security control that cannot
   run must not silently pass.

4. **Transport downgrade.** `Agent.__init__` used
   `result.unwrap() if result.is_ok() else MessageBroker(config)`, discarding a
   typed `BROKER_DEPENDENCY_MISSING` error. A `nats://` or `s2://` deployment
   missing its driver received an in-memory broker with no warning, and `send()`
   returned `Ok`.

Measured evidence: the link-enforcement block (`broker.py:216-252`) had **zero
test coverage**, which is why the defect shipped.

## Decision

**Keep the singleton. Fix what makes it unsafe.**

`MessageBroker`'s own docstring declares it the in-memory implementation for
development and testing. A process-wide in-memory bus is a coherent design and
1,914 tests depend on its shared-state semantics. What is incoherent is that it
was seeded by an import side effect, silently dropped security configuration,
failed open, and absorbed traffic intended for real transports.

Four changes:

1. **No side effects at import.** Remove the automatic `validate_installation()`
   call. Rewrite the function so it validates the import graph and core types
   without constructing an `Agent`, keeping it public and callable.

2. **Adopt security context from later configs.** Generalize the existing
   `_refresh_separation_policy` precedent into `_refresh_security_context`,
   which adopts a non-`None` `security` block from any later `Config` and
   builds the `link_manager` / `_auth_manager` it implies. Semantics match the
   precedent exactly: **only ever add or replace with a non-`None` value, never
   clear.** A security-less config must not disable an active guarantee.

3. **Fail closed on unenforceable link policy.** When `require_links` is set and
   no link manager is available, raise `SecurityError` instead of proceeding.

4. **Fail fast on unavailable transport.** When a `nats://` or `s2://` URL is
   requested and the driver is missing, raise `BrokerUnavailableError` carrying
   the underlying typed error, rather than degrading to in-memory.

Supporting change: `SecurityError` was defined twice
(`broker.py` and `error/types.py`). Because change 3 makes it load-bearing for a
security guarantee, `broker.py` now re-exports the `error/types.py` class so
both import paths name one type, and it is exported from the package root so
callers can actually catch it.

## Boundary

```text
Config(broker_url=...)
    |
    +-- memory:// or unset ------> MessageBroker (process-wide in-memory bus)
    |                                  |
    |                                  +-- later Config carries security
    |                                  |     --> adopt (add/replace, never clear)
    |                                  |
    |                                  +-- require_links, no link manager
    |                                        --> SecurityError (fail closed)
    |
    +-- nats:// or s2://
            |
            +-- driver present ----> NATSBrokerSync / S2Broker
            |
            +-- driver missing ----> BrokerUnavailableError (fail fast)
                                     (never silently in-memory)
```

## Alternatives considered

| Option | Decision | Reason |
|---|---|---|
| Registry of brokers keyed by `broker_url` | Rejected | Class-level shared state (`_agent_queues`, `_topic_subscribers`) would remain global, producing confusing half-isolation: distinct broker objects sharing one bus. Large blast radius across 1,914 tests for a benefit that fail-fast transport selection already delivers. |
| Drop the singleton entirely | Rejected | The in-memory bus *is* the shared-state mechanism agents use to reach each other in-process. Removing it changes the delivery model, not a defect. Out of scope for a blocker fix on a tagged release. |
| Re-initialize the singleton on every construction | Rejected | Last-config-wins is as arbitrary as first-config-wins, and it lets a security-less agent clear an active policy — the exact failure `_refresh_separation_policy` was written to prevent. |
| Warn instead of raising on missing transport driver | Rejected | A warning in a log the operator may not read is how this defect reached production. `Result`-typed failure is the project's own idiom; construction failure must be loud. |
| Keep singleton, fix seeding + adoption + fail-closed + fail-fast | **Chosen** | Removes all four defects with minimal semantic churn, and follows a precedent already established in the same file. |

## Consequences

Positive: user broker and security configuration take effect; `require_links`
enforces or refuses; a missing transport driver is reported at construction
instead of being discovered in production; `import maple` has no global side
effects; `SecurityError` is one catchable type.

Negative — **behavior changes callers may depend on**:

- `Agent(Config(broker_url="nats://..."))` without `nats-py` now raises
  `BrokerUnavailableError` where it previously returned a working in-memory
  agent. This is the intended fix, but it is a breaking change for any caller
  that relied on the fallback. Same for `s2://` without `streamstore`.
- `require_links=True` with an unavailable link manager now raises on `send()`
  where it previously succeeded.
- `maple.validate_installation()` no longer constructs an `Agent`, so it no
  longer exercises the broker path. It validates imports and core types only.

`tests/adapters/test_s2_adapter.py::test_s2_url_triggers_s2_broker_path`
asserted the old fallback (`self.assertIsInstance(agent.broker, (S2Broker,
MessageBroker))`). It is **updated, not deleted**, to assert the new fail-fast
contract — the test encoded the defect.

## Invalidation triggers

Introducing a second in-process transport that expects to share the in-memory
bus; making `MessageBroker` per-agent; adding a broker whose construction can
succeed partially; or any requirement that a security-less config be able to
*clear* an inherited policy.
