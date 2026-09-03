# ADR-164: Configuration is validated at construction

**Date:** 2026-09-02
**Status:** accepted
**Deciders:** Chief Architect + Security Reviewer

## Context

`Config` has no `__post_init__` and no `validate()`. Every invalid value below
is accepted at construction and surfaces later as something else entirely.

### Measured

Nine invalid configurations, all accepted:

```text
empty agent_id         ACCEPTED
whitespace agent_id    ACCEPTED
agent_id is an int     ACCEPTED
agent_id is None       ACCEPTED
empty broker_url       ACCEPTED
garbage broker_url     ACCEPTED
unknown scheme         ACCEPTED
negative queue         ACCEPTED
zero queue             ACCEPTED
```

What each one then does:

| Config | Downstream symptom |
| --- | --- |
| `agent_id=""` or `None` | Agent starts, `send()` returns **`Ok`**, **nothing is delivered** |
| `max_queue_size=-5` | **Every** send fails `QUEUE_FULL` — an operator hunts a slow consumer that does not exist |
| `max_queue_size=0` | Delivers anyway; the bound means nothing |

The first is the familiar shape: work accepted with an `Ok` that promised
nothing.

### The serious one: a typo defeats ADR-157

ADR-157 made a transport that cannot honour `SecurityConfig` refuse at
construction, so a `nats://` deployment can never silently run in-process.
`_create_broker` matches with `broker_url.startswith("nats://")`. Measured:

```text
nats://host:4222     -> refused: BrokerUnavailableError   (working as designed)
nats:/host:4222      -> MessageBroker                     (one slash)
NATS://host          -> MessageBroker                     (wrong case)
natss://host         -> MessageBroker                     (typo)
redis://host         -> MessageBroker                     (unsupported transport)
s2:/x                -> MessageBroker                     (one slash)
```

**A single character defeats the guarantee.** Deploy with `NATS://prod-cluster`
and every message stays in-process while the deployment reports healthy — the
exact failure ADR-157 exists to prevent, reachable by holding shift.

## Decision

### Validate in `__post_init__`, and raise

Validation happens at construction, because the whole point is that the error
arrives where the mistake was made rather than three layers away. A constructor
cannot return a `Result`, so this raises: `ConfigurationError`, carrying the
same `.error` dict as MAPLE's other typed errors and subclassing `ValueError`
so ordinary handling works.

`Config.validate()` is also exposed for callers assembling configuration
dynamically and wanting the check without constructing.

### What is checked

| Field | Rule | Because |
| --- | --- | --- |
| `agent_id` | non-empty `str` after stripping | an unroutable id makes every `send()` a silent no-op |
| `broker_url` | non-empty `str`, scheme recognised | see below |
| `max_queue_size` | integer ≥ 1 | negative bricks every send with a misleading `QUEUE_FULL` |
| `max_message_bytes` | integer ≥ 1 | a non-positive limit rejects everything |
| `connection_pool_size`, `max_concurrent_requests`, `batch_size` | integer ≥ 1 | same shape |

Bounds are checked as **integers**, so `max_queue_size=1.5` is refused rather
than silently truncated somewhere downstream.

### Scheme rules, and why they are not stricter

Three rules, in order:

1. If the text before the first `:` names a transport MAPLE knows —
   `memory`, `nats`, `s2`, compared **case-insensitively** — the URL must be in
   `scheme://` form. `nats:/host` and `NATS://host` are refused, naming the
   correct form. This is not guesswork: MAPLE is recognising its own transport
   names.
2. Otherwise, if the URL contains `://`, the scheme is an unsupported
   transport. Refused, listing what is supported. `redis://`, `natss://`,
   `kafka://` all land here.
3. Otherwise there is no scheme, and the value is treated as in-memory exactly
   as today.

Rule 3 exists because `localhost:8080` appears in **8 places** including
`examples/helloworld.py`. Refusing scheme-less values would break the flagship
example and every user who copied it, to prevent a mistake nobody is making —
nobody types `localhost:8080` believing they configured a cluster. The
dangerous case is naming a transport and not getting it, and rules 1 and 2
cover that.

`_create_broker` also matches schemes case-insensitively, so `NATS://` now
reaches the fail-closed path instead of missing it.

## Alternatives considered

| Option | Decision | Reason |
| --- | --- | --- |
| Return `Result` from a `validate()` and leave the constructor permissive | Rejected | Optional validation is validation nobody runs. The defect is that bad config is *accepted*. |
| Refuse every unrecognised `broker_url`, scheme-less included | Rejected | Breaks `localhost:8080` in 8 places including `helloworld.py`, for a mistake with no failure mode. |
| Warn on a bad scheme instead of refusing | Rejected | ADR-157 settled this: a control that cannot be honoured must refuse, not log. A warning in a deploy log is not seen. |
| Normalise `NATS://` to `nats://` silently | Rejected | It fixes this instance and hides the fact that the config is wrong. Refusing with the correct form teaches; correcting conceals. |
| Validate at `Agent()` instead of `Config()` | Rejected | `Config` is passed around and inspected before an agent exists; the error belongs where the value is set. |

## Consequences

Positive: mistakes fail where they are made, with a message naming the field
and the fix; ADR-157's fail-closed guarantee stops being defeatable by a typo;
`Ok`-but-undeliverable from an empty `agent_id` becomes impossible.

Negative:

- **Configurations that "worked" now raise.** They did not work — they ran with
  a silently different transport, or accepted sends nothing could deliver — but
  the exception is new and arrives at construction.
- **One in-tree test constructs `Config(broker_url="x://h")`** to exercise an
  unrelated code path. Its URL is incidental and is updated to a valid one.
- **The known-scheme list is now a maintained thing.** A new transport must be
  added to it or its URLs are refused. A test asserts the list matches the
  schemes `_create_broker` actually dispatches on, so the two cannot drift.

## Invalidation triggers

A transport whose URLs are not scheme-shaped; a decision to accept
configuration from untrusted input, which would need validation to become a
security boundary rather than a correctness one; or dynamic reconfiguration,
where construction is no longer the moment values are set.
