# Slice 197 plan - offline provider contract fixtures

**Brief:** [maple-agent-runtime-slice197.md](../briefs/maple-agent-runtime-slice197.md)
**Design/ADR:** [ADR-141](../adr/141-offline-provider-contract-fixtures.md)
**Class:** L

## Slices

| # | Slice | Role | Files touched | Proven by (tests) | Status |
|---|---|---|---|---|---|
| 1 | Provider response validation | Backend / ML | `maple/llm/provider.py`, provider parsers, provider tests | malformed JSON/non-object tool arguments and usage fail closed; counters unchanged | complete |
| 2 | Offline OpenAI/Anthropic completion contracts | ML / Interop | `tests/llm/test_provider_contracts.py` | sync/async request mapping, multimodal/tool/system/stop/usage normalization | complete |
| 3 | Review, QA, and package evidence | Code Reviewer / QA / Security / Release | review/QA/release/parity docs | focused/full tests, no-network fixture run, package smoke | todo |

## Threat sketch

Assets touched: model responses, tool-call arguments, usage counters, provider
configuration metadata, and normalized completion results. Entry points are
fake/provider SDK response objects and caller-supplied messages/tools. The
worst plausible abuse is malformed or oversized provider output becoming tool
input, corrupting usage state, or causing unbounded parser work. The design
uses typed parsing, bounded existing chat/tool contracts, non-object rejection,
non-negative integer usage validation, and no raw response/error aggregation.

## Risks and rollback points

- Risk: legitimate provider response variants are rejected -> mitigation:
  fixture both documented text/tool/usage shapes and return a precise typed
  error; rollback: revert parser hardening while retaining fixtures for the
  compatibility gap.
- Risk: duplicate provider parsing logic diverges -> mitigation: keep shared
  validation in the base provider and provider-specific shape extraction thin;
  rollback: remove only the new validation helper.
- Risk: fixtures imply live compatibility -> mitigation: docs explicitly label
  them offline fake-SDK contracts; rollback: remove any live-compatibility
  claim without changing local tests.

## Deviation log (append-only)

- None.

## Status snapshot

G0/G1/G2 accepted for the bounded offline contract. Implementation and focused
contract evidence are complete; next: independent code/security review, QA,
and package evidence. Blocked on: none for this local slice; hosted
coordination remains a separate contract gate.
