# Skill: Incident Response

**Scope.** Production incidents from first page to closed retro — severity,
command, mitigation, communication, and the learning loop back into doctrine.

## Principles
- Declare early. A false alarm costs minutes; a late declaration costs
  hours. Downgrading a SEV is cheap; discovering one at hour three is not.
- Mitigate first, diagnose second. Rollback beats forward-fix under fire —
  the HOTFIX class (G3→G4→G5-lite→G6) exists exactly for this. Root cause
  is the retro's job, not the pager's.
- One Incident Commander per incident. The IC coordinates, delegates, and
  narrates; the IC does not type fixes. Hands on keyboards belong to
  responders the IC assigns.
- Page on user-visible symptoms, not internal causes. Users don't see CPU;
  they see errors and latency. Causes are dashboards, symptoms are pages.
- Alert fatigue is an outage of attention. Every ignored page trains the
  team to ignore the one that matters.

## Defaults
- Severity ladder: SEV1 = users down — all hands, page now, updates every
  15 min · SEV2 = degraded — owner engaged within 30 min, hourly updates ·
  SEV3 = annoyance — ticket, within a business day. Unsure? Round up.
- Every alert links to a runbook: meaning, first checks, mitigation,
  escalation. An alert without a runbook is homework, not monitoring.
  Alert evidence and structure per `skills/observability.md`.
- SLOs define "reliable enough" per service, agreed in advance; the error
  budget is spent deliberately. Budget burned → releases slow to match.
- Stakeholder communication on a fixed cadence, even when the update is
  "no update" — silence reads as abandonment.
- Blameless postmortem within 48h, feeding the G7 retrospective's 5-whys;
  a HOTFIX already mandates its G7 retro the same day.

## Do
- Timestamp everything during the incident — actions, observations,
  decisions. Evidence collected live beats memory reconstructed after.
- Snapshot evidence before mitigation destroys it (logs, metrics, failing
  state), then mitigate anyway. Users outrank forensics.
- Hand off IC explicitly on shift change: current state, actions in
  flight, next steps. An unowned incident is two incidents.
- End every postmortem with amendments: a doctrine change, a tooling
  change, or a new alert + runbook. "Be more careful" is not an action.

## Don't
- Don't debug on the call while users bleed — restore service first, study
  the corpse in the retro.
- Don't let the IC touch anything beyond the incident doc.
- Don't ship a forward-fix under pressure when a rollback is available.
- Don't name people as causes in postmortems; name conditions and gaps.
- Don't close an incident with action items that lack an owner and a date.

## Review checklist
- [ ] Every new alert: user-visible symptom, linked runbook, tested page
- [ ] Severity levels and response expectations stated, not assumed
- [ ] Incident timeline captured live, with timestamps and evidence
- [ ] Rollback path known and rehearsed before it is needed
- [ ] Postmortem within 48h, blameless, feeding G7 5-whys
- [ ] Action items owned, dated, and landed as doctrine/tooling changes

## Common failure modes
The hero debugging solo for two hours before declaring; the IC deep in a
terminal while nobody coordinates; cause-based alerts firing all night for
symptoms nobody feels; postmortems producing blame or platitudes instead of
amendments; evidence lost to the very restart that cleared the symptom.
