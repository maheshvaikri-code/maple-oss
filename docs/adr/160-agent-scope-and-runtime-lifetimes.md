# ADR-160: AgentScope — runtime lifetimes and in-process isolation

**Date:** 2026-09-01
**Status:** accepted — implemented 2026-09-01
**Deciders:** Chief Architect

## Context

Three classes in the MAPLE runtime hold process-global mutable state. Found by
an AST survey of `maple/`, not by grepping for remembered names, so the list is
the complete one:

| Class | Shape | Consequence |
|---|---|---|
| `MessageBroker` | `__new__` singleton **and** 5 class-level dicts | One bus per process |
| `Agent._shared_registry` | cached class attribute | One `AgentRegistry` per process |
| `LLMProviderRegistry._providers` | class dict, `@classmethod register` | One provider table per process |

Six real attributes across three classes. Two further hits in the survey —
`_RestrictedUnpickler._SAFE_GLOBALS` and
`StreamableHTTPTransport.SUPPORTED_PROTOCOL_VERSIONS` — are allowlist constants
that belong at class level and are excluded. Every "module-level global" the
survey reported was an `__all__` export list, a false positive of the check
itself rather than a finding.

`maple/autonomy/` has **no** class-level mutable state. Its stores take explicit
paths and keep state on instances. The defect is confined to the 1.x core.

### Why this matters beyond tidiness

The broker singleton has already produced shipped defects. ADR-157 fixed a
chain of them — an import-time agent pinning the broker's configuration, every
later `SecurityConfig` discarded, link enforcement failing open — all
downstream of "one bus, first config wins."

The registry is worse in kind. It leaks across tenants:

```text
two agents on deliberately different buses:
  memory://tenant-a  and  memory://tenant-b

  same registry object : True
  tenant-a can see     : ['tenant-a-worker', 'tenant-b-worker']
```

Discovery enumerates agents from another tenant, and capability matching would
select across the boundary. The same lifetime defect is a *messaging* problem
in the broker and a *visibility* problem in the registry.

### The key is already in the API

`Config.broker_url` carries a namespace that the implementation discards. The
path component of `memory://` is referenced nowhere in `maple/`:

```text
Agent(Config(broker_url="memory://tenant-a"))
Agent(Config(broker_url="memory://tenant-b"))
  -> same broker object
  -> both report broker_url "memory://tenant-a"
```

The API already expresses the scope. Only the implementation ignores it.

## Decision

Introduce **`AgentScope`**: one object owning the three runtime registries,
keyed by the namespace already present in `broker_url`.

```text
AgentScope("tenant-a")
  |
  +-- MessageBroker    queues, handlers, topics  (instance state)
  +-- AgentRegistry    discovery view
  +-- provider table   LLM configuration
```

An `Agent` belongs to exactly one scope and can see only that scope's bus,
registry and providers.

### Lifetimes, and which are coherent for a message bus

The four lifetimes from dependency-injection practice do not apply equally
here, because a bus is defined by shared state. Naming them explicitly:

| Lifetime | Disposition | Reason |
|---|---|---|
| **Singleton** | **Default, retained** | Agents must reach each other, which requires shared state. Correct for the unnamed default scope. |
| **Scoped** | **Adopted** | One runtime per named scope. The valuable addition: multi-tenancy, test isolation, and it removes the config-pinning defect class at the root. |
| **Threaded** | **Rejected** | A bus per thread means agents on different threads cannot message each other — that is not a bus. |
| **Transient** | **Already in use, unnamed** | A new instance per construction breaks in-memory messaging, but is *correct* for a broker whose state is remote. The NATS broker is naturally transient. |

That last row is the load-bearing observation: **MAPLE already has two lifetime
models and does not name them.** The in-memory broker is singleton *because its
state is local*; a network broker is transient *because its state is remote*.
Lifetime here is not a preference to configure — it is determined by where the
state lives, and the design should say so rather than leave it implicit.

### Migration shape

1. **Move the five class dicts onto the instance.** This is the actual work and
   where the risk sits; everything else follows from it.
2. **Key runtimes by `broker_url`.** `memory://a` and `memory://b` become
   distinct scopes. A bare `memory://` or an absent path resolves to the
   default scope, so existing behavior is preserved exactly.
3. **Give `AgentRegistry` and the provider table the same treatment**, owned by
   the scope rather than by a class attribute.
4. **Delete the singleton surgery from the tests** — 8 call sites across 7
   files currently reset `_instance` and clear five class dicts by hand. That
   ritual is the clearest evidence the lifetime model does not fit; a scoped
   fixture replaces all of it.

## Alternatives considered

| Option | Decision | Reason |
|---|---|---|
| Remove `__new__`, keep class state | Rejected | Does nothing. The singleton is enforced twice; instances would still share every dict. |
| Explicit `Runtime` object passed to every `Agent` | Rejected for now | Cleaner in isolation, but it is a breaking change to every constructor call and every example. Scope-by-URL achieves the isolation with the key users already write. |
| A `scope=` keyword on `Config` | Deferred | Reasonable as an explicit override later, but a second way to say the same thing invites the two disagreeing. The URL is already the address. |
| Thread-local runtimes | Rejected | See the lifetime table — it breaks cross-thread messaging, which is the primary use. |
| Leave it; document the single-tenant limit | Rejected | The registry leak is a correctness issue, not a documentation gap. An operator cannot work around discovery returning another tenant's agents. |

## Consequences

Positive: two isolated agent worlds can share a process; the ADR-157 defect
class is removed at the root rather than patched per field; test isolation
stops requiring private-attribute surgery; the namespace in `broker_url` starts
meaning what it appears to mean.

Negative — and these need care:

- **The default scope must behave exactly as today**, or every existing
  deployment changes semantics silently. This is the single largest regression
  risk in the change, and the migration is not worth doing without tests that
  pin default-scope behavior first.
- Code reaching into `MessageBroker._agent_queues` and friends as class
  attributes breaks. Inside this repository that is only the test suite; for
  external callers it is private API, but it has been reachable.
- Scope becomes a new concept users must understand. It earns its place only if
  the default requires knowing nothing about it.

## Explicitly out of scope

This gives isolation **within one process**. It does not give multi-process or
multi-host operation — see ADR-161 for the transport contract that governs
those. A scoped registry is still host-local; making discovery work across
hosts is a separate problem on a separate substrate.

## Invalidation triggers

Any new class-level mutable attribute on a runtime class; a second way to
address a scope that can disagree with `broker_url`; or a decision to pass an
explicit runtime object, which would supersede scope-by-URL rather than
complement it.
