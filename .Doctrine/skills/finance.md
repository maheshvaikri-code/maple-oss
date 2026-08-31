# Skill: Finance

**Scope.** Startup finance without hope-math — runway, burn, budgets, and
cost models. The skill computes and flags; the human moves money.

## Principles
- Runway = cash / MEASURED burn, recomputed from actuals monthly. Runway
  projected from intentions is a countdown you can't hear.
- Every figure wears a label — measured | estimated | projected — and the
  label survives quotation. A projected number quoted bare becomes a
  measured lie.
- Budgets without owners and review dates are wishes with line items.
- Scenario models state assumptions before conclusions; the reader meets
  the "if" before the "then".
- The skill models, reconciles, and flags. Money movement, signatures,
  and spend commitments belong to the human alone (.Doctrine.md §5).

## Defaults
- Monthly close: actuals in, burn recomputed, runway restated, variance
  against last month's model explained in one paragraph.
- Cloud and token spend joins the engineering cost review — same joins as
  `skills/metrics.md`, same cost lines as `skills/iac.md` — so infra cost
  meets product outcomes instead of living in a separate ledger.
- Each budget line: owner, amount, review date, and the trigger that
  reopens it early.
- Scenario models in threes — base, downside, upside — assumptions listed
  per scenario, sources cited per assumption.
- Anything committing future spend (contracts, annual plans, hires) is
  flagged to the human with the model attached, never actioned.

## Do
- Reconcile the model against bank actuals before quoting any runway
  number anywhere.
- Flag burn inflections the month they appear, not the quarter they hurt;
  a two-month trend is a conversation, not yet a crisis.
- Keep unit costs honest: cost per landed change, per user, per tenant —
  measured where possible, labeled estimated where not.
- Date every figure; "runway: 14 months" means nothing without "as of".

## Don't
- Don't average away a burn spike; investigate it.
- Don't let "projected" quietly become "expected" become "planned".
- Don't build budgets from last year's hope instead of this year's
  actuals.
- Don't net revenue against costs to flatter burn without showing both.
- Don't move, commit, or sign anything — model and flag only.

## Review checklist
- [ ] Runway from measured burn on actuals, dated, reconciled to bank
- [ ] Every figure labeled measured | estimated | projected
- [ ] Labels survive into every quote, summary, and deck
- [ ] Budget lines carry owner and review date
- [ ] Scenarios list assumptions before conclusions
- [ ] Spend commitments flagged to the human, never executed

## Common failure modes
Hope-math runway built on revenue that hasn't landed; labels stripped in
the retelling until a guess reads as fact; budgets nobody owns quietly
overrunning; cloud spend reviewed in a vacuum away from the product it
pays for; the model updated for the board meeting instead of the monthly
close.
