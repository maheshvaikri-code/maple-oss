# Slice 195 plan - bounded code-block artifact materialization

**Brief:** [maple-agent-runtime-slice195.md](../briefs/maple-agent-runtime-slice195.md)
**Design/ADR:** [ADR-139](../adr/139-bounded-code-block-artifact-materialization.md)
**Class:** L

## Slices

| # | Slice | Role | Files touched | Proven by (tests) | Status |
|---|---|---|---|---|---|
| 1 | CodeBlock digest and materialization helper | Backend / Security | `maple/autonomy/artifacts.py`, artifact tests | Exact bytes/hash/name, invalid block/store, oversized code, no execution | complete in `3382595` |
| 2 | Public surface and documentation | Interop / Tech Writer | exports, README, API reference, parity, changelog | Public import and runnable documentation example | complete in `3382595` |
| 3 | Review, QA, and package evidence | Code Reviewer / QA / Release | review/QA/release plan | Focused/full regression, static checks, clean/current package smoke | complete; review/QA filed |

## Threat sketch

Assets touched: extracted code text, artifact bytes, content hashes, and local
artifact-store metadata. Entry points / untrusted inputs: Markdown source,
direct `CodeBlock` values, block language/index, store implementations, and
file-backed artifact paths. Worst plausible abuse: oversized or malformed code
causes resource exhaustion or a store implementation is bypassed; strict
bounds, existing artifact-store validation, deterministic names, and typed
fail-closed errors contain the boundary.

## Risks and rollback points

- Risk: the helper creates an accidental execution implication -> mitigation:
  name and document it as materialization only and test code containing side
  effects as inert bytes -> rollback: remove the helper/export/docs while
  retaining the existing extractor and stores.
- Risk: direct blocks bypass extractor bounds -> mitigation: validate language,
  index, code type, and the materialization byte cap before `put` -> rollback:
  revert only helper validation.
- Risk: duplicate callers diverge in names or media types -> mitigation: one
  helper owns the default convention -> rollback: restore caller-owned bridge
  code without changing artifact identity rules.

## Deviation log

- None.

## Status snapshot

Complete for the local data-only scope. Implementation commit `3382595`,
review and QA evidence filed, and exact clean package smoke passed. Blocked on:
nothing within this slice; execution, sandboxing, and remote distribution remain
outside scope.
