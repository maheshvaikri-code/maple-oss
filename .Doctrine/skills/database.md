# Skill: Database

**Scope.** Schema design, migrations, query construction, and data
integrity — server databases and embedded stores (SQLite, RocksDB) alike.

## Principles
- The database outlives the application code. Design the schema for the
  data's truth, not this week's endpoints.
- Integrity enforced where it can't be bypassed: constraints, FKs,
  uniqueness, NOT NULL, checks — in the store.
- Migrations are history: append-only, numbered, immutable once run
  anywhere. Correcting a migration means writing another one.
- Query performance is empirical: EXPLAIN on realistic volume beats theory.

## Defaults
- Naming: snake_case; tables plural or singular but **consistently**;
  `<table>_id` foreign keys; `created_at`/`updated_at` (UTC) on durable rows.
- Prefer TEXT/INTEGER/timestamp-with-zone honesty over clever encodings;
  JSON columns only for genuinely schemaless payload, never for dodging design.
- Soft-delete only with a reason; if used, every query filters it via a
  view or default scope, not per-call memory.
- Embedded stores: single-writer assumptions documented; compaction and
  size growth measured, not hoped about.

## Do
- Write the migration + rollback story together; test the migration against
  a copy of realistic current data, not just an empty DB.
- Index to match real query shapes; drop indexes nothing uses.
- Batch large writes; wrap related writes in transactions sized to the
  invariant they protect — no larger.
- Keep a seed/fixture path so tests and QA run against known data shapes.

## Don't
- Don't edit or delete an applied migration. Ever.
- Don't run destructive statements (DROP/DELETE/UPDATE-without-WHERE)
  outside a reviewed migration with an explicit human go and a backup story.
- Don't ship N+1 loops — fetch sets, not rows-in-a-loop.
- Don't let the ORM's emitted SQL remain a mystery on hot paths.
- Don't store secrets or derivable data (recompute instead) without cause.

## Review checklist
- [ ] Constraints cover every invariant the code assumes
- [ ] Migration tested forward (fresh + realistic copy); rollback stated
- [ ] Hot queries EXPLAIN-checked; indexes justified
- [ ] Transactions minimal and free of network/O(n) work inside
- [ ] Destructive ops: human-approved, backed up, dry-run first

## Common failure modes
App-enforced "uniqueness" with a race in the middle; migration edited after
teammates ran it; test DB with 10 rows blessing a query that dies at 10M;
JSON column that quietly became the real schema.
