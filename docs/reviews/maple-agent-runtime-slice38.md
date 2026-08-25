# Review — MAPLE agent-runtime slice 38

## Scope

Close the result collector's public type-boundary debt and make missing custom
aggregation callable state explicit.

## Review findings

- Collector lifecycle, callback, timeout, metadata, filtering, cleanup, and
  background-loop contracts are explicit.
- `create_aggregation_group` now types its extension keyword arguments.
- Custom aggregation validates the callable before invoking it and returns a
  structured `Result.err` instead of reaching a `None` call.
- Existing aggregation algorithms and callback ordering are unchanged.

## Decision

Slice accepted. The absent-callable guard is a narrow caller/program-state
error at the aggregation boundary; broader aggregation semantics remain
unchanged.
