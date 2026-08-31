# Skill: Metrics

**Scope.** Measuring the engineering process itself — agent success rates,
review coverage, token economics — so retros argue from numbers, not vibes.

## Principles
- Measure the process, not just the code: the doctrine's gates generate
  evidence; metrics turn it into trend lines.
- A metric that cannot deliver bad news is theater. CESR can drop, ROI can
  go negative, churn can spike — that is what makes them worth reading.
- HITL reduction only counts while CESR holds. Less review with steady
  survival is autonomy; less review with falling survival is rubber-
  stamping wearing autonomy's clothes.
- Cost joins to outcomes or it is noise: token spend matters per LANDED
  change, keyed by the same item ids the state plane carries.
- Metrics are G7 inputs, never weapons: they rank problems, not people.

## Defaults
- Instrument: CodeMonk (`integrations/codemonk.md`, pinned) — CESR,
  engagement, HITL, token churn, cost per landed change, scorecard.
- `item_id` = the state-plane `task_refs` / brief task slug, end to end.
- Baseline at adoption (`codemonk analyze --repo .`), scorecard attached
  to every G7 retro thereafter; trends over snapshots, not single reads.
- Git alone reads HITL as zero — feed review reality from `docs/reviews/`
  and `docs/qa/` via the enrichment overlay, or the coverage number lies.
- Token capture where the harness allows: `codemonk wrap --otel <agent>`
  or the `collect` OTLP endpoint; estimated figures stay labeled estimated.

## Do
- Investigate every CESR drop as an escaped-defect signal — it feeds the
  same 5-whys the retro already owns.
- Watch token churn per gate: spend on superseded/reverted attempts is
  the quantitative shadow of thrash (`skills/loop-engineering.md`).
- Recalibrate thresholds from your own history (`codemonk calibrate`),
  not from defaults, once enough data exists.
- Quote metrics with their fidelity note (measured vs estimated vs
  git-heuristic) — the honesty law applies to numbers too.

## Don't
- Don't compare individuals or shame sessions; aggregate by process stage.
- Don't target a metric (Goodhart) — targets belong to outcomes; metrics
  monitor whether the process still earns its ceremony.
- Don't present estimated ROI as measurement — CodeMonk labels its cost
  assumptions; keep the label attached when you quote it.
- Don't cherry-pick windows; retros read the standing trend dashboard.

## Review checklist
- [ ] item_id joins state plane, commits, and token logs consistently
- [ ] Review enrichment wired (HITL reflects docs/reviews, not git-zero)
- [ ] Scorecard attached to the G7 retro with fidelity notes
- [ ] CESR drops triaged with a 5-whys, not explained away
- [ ] Thresholds calibrated from history once data allows

## Common failure modes
Dashboards nobody reads until the incident; HITL "improvement" that is
review erosion (the CESR gate exists precisely for this); ROI quoted
without its assumption footer; metrics wielded in reviews as leverage;
measuring only what the harness makes easy and calling it the process.
