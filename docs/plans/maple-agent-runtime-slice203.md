# Slice 203 plan — native run-ID validation correction

**Brief:** [maple-agent-runtime-slice203.md](../briefs/maple-agent-runtime-slice203.md)
**ADR:** [ADR-147](../adr/147-native-run-id-validation.md)
**Class:** M

| Slice | Role | Scope | Status |
|---|---|---|---|
| 1 | Backend | Change native run-ID fallback from truthiness to `None` omission semantics in workflow and durable-agent start paths | complete in working tree; commit/evidence pending |
| 2 | QA / Code Reviewer / Security | Run focused and full regression, static/type/compile/security checks, and review the bounded diff | pending |
| 3 | Release | Run clean tracked-archive package smoke and update the release ledger without publishing | pending |

## Invariants

- `run_id=None` may generate a bounded local ID.
- An explicit invalid ID must fail before store mutation or model/tool work.
- Agent store failures retain the existing stable outer error envelope.
- No server/client route, dependency, cloud action, publication, or website
  update is part of this slice.

## Deviation log

- The adjacent server `run_id or generated` expressions were audited but not
  changed: the relevant server request normalizers already reject explicit
  empty values before generation, and changing transport code would broaden
  this bounded native correction.
