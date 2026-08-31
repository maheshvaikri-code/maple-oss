# Skill: Privacy & Compliance

**Scope.** Personal data through its whole life — collection, storage,
processing, sharing, deletion — and the regulatory obligations riding along.

## Principles
- Classify before you build: know which fields are PII/PHI/financial and
  where they flow. The PII inventory is a design input, not documentation.
- Collect the minimum. Every personal field carries a purpose and a
  recorded lawful basis; "might be useful later" is not a basis.
- Retention is a number with automation behind it, not a policy PDF.
- Rights (access, deletion, export) are designed features with tests;
  bolting them on later means rewriting the storage layer.
- Legal interpretation is ALWAYS a human escalation. The agent flags,
  cites, and stops — it never improvises what a regulation "probably means."

## Defaults
- Pseudonymize or aggregate by default; raw identifiers only where the
  feature genuinely requires them.
- Deletion propagates: primary store, replicas, caches, search indexes,
  derived stores, and — via key destruction or expiry policy — backups and
  logs. Draw the propagation map before the first row is written.
- Data residency declared per store; cross-region replication of personal
  data is a decision with an owner, never a default.
- New vendor touching personal data = subprocessor: DPA check before
  integration, per `standards/dependency-policy.md`.
- PII never in logs, metrics, or traces (see `skills/observability.md`) —
  log opaque IDs and look the person up elsewhere.

## Do
- Sketch a data map per feature: what's collected, why, where it lives,
  who sees it, when it dies. Five lines saves five audits.
- Encrypt with per-subject keys where deletion-from-backups matters:
  destroy the key and the backups go dark.
- Exercise right-to-access and right-to-delete like features: run them
  against seeded data; verify output complete and deletion total.
- Treat suspected personal-data exposure as an incident: contain, then
  escalate to a human immediately — notification clocks may be running.

## Don't
- Don't collect a field because the form library made it easy.
- Don't copy production PII into dev/test/fixtures; synthesize instead.
- Don't let derived stores (analytics, ML features, search) become
  deletion-proof shadows of deleted users.
- Don't ship a "delete account" button that soft-deletes forever.
- Don't answer "is this GDPR-compliant?" yourself — route to a human.

## Review checklist
- [ ] Data map exists: fields classified, purpose + lawful basis recorded
- [ ] Retention set per store with automated deletion wired
- [ ] Deletion propagation covers replicas, caches, derived stores, backups
- [ ] Access/delete/export paths implemented and tested end-to-end
- [ ] No PII in logs/metrics/traces; new vendors DPA-checked
- [ ] Legal questions escalated, not improvised

## Common failure modes
The analytics warehouse that outlives every deletion request; retention
"policies" no cron job has ever read; production dumps in a fixtures
folder; the vendor bolted on Friday who never signed a DPA; an agent
confidently paraphrasing GDPR into an incident.
