# Project/Task Brief - Bounded agent route-policy validation

**Date:** 2026-08-28 - **Class:** M (public routing boundary hardening) - **Requested by:** human

## Problem

AgentRegistry.route accepts an optional allowed_agent_ids iterable for the
server's principal target policy. The server supplies a validated tuple, but
direct callers can pass strings, duplicates, malformed identifiers, oversized
iterables, or unhashable values. The current set conversion can raise an
untyped exception or silently produce a policy that was not validated.

## Scope

- In: validate and deterministically copy allowed_agent_ids at the route
  boundary before registry lookup.
- In: return a typed AGENT_ALLOWLIST_INVALID error for malformed policy input.
- In: preserve None as unrestricted compatibility and preserve an empty valid
  tuple as no permitted route target.
- In: guarantee invalid policy input does not invoke an agent handler.
- **Non-goals:** changing principal policy, wildcard matching, routing order,
  retry/failover, scheduling, tenancy, or distributed authorization.

## Acceptance criteria

1. None keeps existing unrestricted routing behavior; valid exact identifier
   iterables route deterministically as before.
2. Strings/bytes, malformed identifiers, duplicates, oversized lists, and
   unhashable values return typed bounded AGENT_ALLOWLIST_INVALID errors.
3. Invalid policy input performs no registry handler call and leaks no raw
   values in the error.
4. Existing server principal policy and all compatibility tests remain green.
5. Plan, review, QA, and release evidence are updated; no publication, cloud,
   registry, or website action occurs.

## Constraints

Stdlib only; reuse existing agent identifier bounds and Error/Result surfaces;
fail closed; preserve deterministic ordering and valid-call behavior; no new
dependency.

**Human confirmed:** no - defensive validation increment recorded for review
