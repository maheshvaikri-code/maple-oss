# Standard: Governance, Risk & Security (GRC)

The governance layer sits ABOVE the gates: four heads set policy and
keep registers; the gates enforce. Policy and enforcement never share a
hat — a head who also reviews is grading their own homework.

## The layer

| Head | Governs | Register it owns | Enforced downstream by |
|---|---|---|---|
| Head of AI (`roles/head-of-ai.md`) | model/vendor policy, eval standard, responsible-AI boundary | model inventory | ml-engineer at G3, reviewers at G4/G5 |
| Head of Data (`roles/head-of-data.md`) | data contracts, lineage, retention map, one-definition-per-entity | data inventory | data-engineer at G3, compliance at G5 |
| CISO (`roles/ciso.md`) | security policy set, threat-model registry, exception register | security exceptions (all with EXPIRY) | security-reviewer at G5 (keeps the ship veto) |
| Risk Officer (`roles/risk-officer.md`) | enterprise risk register across all domains | `docs/risk/register.md` | G7 reviews register deltas every retro |

Compliance governance stays with `roles/compliance-officer.md` (G5) —
a "head of compliance" above it would be a title, not an authority.
Hands-on security work is NOT a separate role: engineers build under
`skills/security.md`, the security-reviewer gates it, the CISO sets the
policy they build and gate against. Three hats, no fourth.

## G1 co-sign

When a G1 design touches a governed domain (AI, data architecture,
security-sensitive surface), the matching head co-signs the ADR. On
`Merge profile: enterprise` repos this co-sign is mandatory; elsewhere
it activates when the domain appears or the human asks. A head can send
a design back at G1 — cheaper than the veto catching it at G5.

## Registers — the load-bearing artifacts

- Every register entry has an owner and a review date. An entry nobody
  re-reviews is a surprise on a schedule.
- **Accepted risk = human signature + expiry.** An exception without an
  expiry is a policy change nobody approved. Expired exceptions
  re-escalate automatically at the next G7.
- Registers aggregate what the pipeline already produces — plan Risks
  sections, security dispositions, compliance blocks, retro findings —
  one place, one format (`templates/risk-register.md`), no new
  bureaucracy invented for its own sake.
- The honesty law applies to likelihoods and impacts: a risk rated low
  to avoid a conversation is a fabricated status.

## Cadence, right-sized

Registers are reviewed at every G7 retrospective (they ride the loop
that already exists); threat models re-open when their surface changes,
not on a calendar; the responsible-AI boundary list and security policy
set are re-ratified by the human whenever they change — silently
drifting policy is the failure mode this standard exists to prevent.
