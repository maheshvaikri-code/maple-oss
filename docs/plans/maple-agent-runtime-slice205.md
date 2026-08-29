# Implementation Plan - durable local lexical retrieval

**Brief:** [Slice 205 brief](../briefs/maple-agent-runtime-slice205.md)
**Design/ADR:** [ADR-149](../adr/149-file-lexical-retriever.md)
**Class:** L

## Slices

| # | Slice | Role | Files touched | Proven by (tests) | Status |
|---|---|---|---|---|---|
| 1 | Durable file-backed lexical backend | Backend / Security | `maple/autonomy/retrieval.py`, retrieval tests | Configuration, envelope validation, atomic add/remove, restart, shared-instance fencing, refresh, failure redaction | complete locally: focused retrieval `35 passed` |
| 2 | Public package and documentation surface | Interop / Tech Writer | `maple/autonomy/__init__.py`, `maple/__init__.py`, `README.md`, API/parity/changelog | Imports, runnable example, documentation consistency | complete locally: public import smoke, docs, and changelog updated |
| 3 | Review, QA, packaging, and release evidence | Code Reviewer / QA / Security / Release | `docs/reviews/maple-agent-runtime-slice205.md`, `docs/qa/maple-agent-runtime-slice205.md`, release plan | Focused retrieval tests, full suite, static/security/package gates | complete locally: review/QA filed; full suite, project audit, static, and clean package smoke pass; publication remains conditional |

## Threat sketch

Assets: persisted source documents, retrieval citations, index availability,
and file integrity. Entry points: constructor path/configuration, JSON state,
document add/remove, search, and concurrent local instances. Worst plausible
abuse: a crafted or oversized state file causes memory/CPU exhaustion or a
failed write loses a document update. Mitigations: bounded envelope and
documents, strict JSON/document validation, same-directory atomic replacement,
fsync, local fencing lease, prospective rebuild, fail-closed errors, and no
network or executable deserialization.

## Risks and rollback points

- Risk: rebuilding changes query latency or ranking behavior -> mitigation:
  reuse the existing in-memory index and preserve deterministic tests ->
  rollback: remove the file-backed class and exports without changing the
  in-memory backend.
- Risk: a peer update is overwritten -> mitigation: reload under the existing
  durable lease for every mutation -> rollback: disable shared-directory use
  until a stronger store contract is approved.
- Risk: partial file replacement or disk failure -> mitigation: write,
  flush/fsync, and replace only after complete validation; retain the old file
  on failure -> rollback: restore the prior file-backed implementation.
- Risk: untrusted state record crosses the parser -> mitigation: bounded file
  size, version, mappings, document/source validation, and JSON-only values ->
  rollback: reject the file and require rebuild from a trusted connector.

## Deviation log

- None at plan creation.

## Status snapshot

G0 brief and G1 ADR are filed. Implementation, public surface, review, QA, and
package evidence are complete locally. The implementation commits are
`b9843d7` and bounded-read hardening `5135877`;
the clean archive smoke reports `1838 passed, 1 skipped`, source archive `960`,
wheel `109`, sdist `874`, build/Twine/install/import/doctor exit `0`, and
network-free doctor readiness. This slice is intentionally local-only and does
not require a cloud target, new dependency, publication, or website change.
The existing Slice 193 hosted-coordination, Slice 199 isolation, Slice 200
CI-policy, and release-publication gates remain separate.
