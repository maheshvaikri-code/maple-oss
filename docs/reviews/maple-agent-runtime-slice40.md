# Review — MAPLE agent-runtime slice 40

## Scope

Close the serialization and built-in provider-registry type boundaries while
preserving existing runtime behavior.

## Review findings

- Optional dependency probing now has an explicit lifecycle contract.
- Message serialization accepts the existing dynamic message-like input with
  an explicit type boundary.
- Provider auto-registration now declares its no-result lifecycle contract.
- Serialization formats, provider selection, and error handling are unchanged.

## Decision

Slice accepted. The changes are limited to annotations at internal dynamic
boundaries; optional SDK/provider implementation debt remains separate.
