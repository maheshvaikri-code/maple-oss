# Skill: Customer Support

**Scope.** Support as intake — tickets, reproductions, response drafts,
and the routing of user pain into the gate system. The human sends.

## Principles
- Severity is user impact, and the report is treated as true until a
  reproduction says otherwise. Disbelief is not triage.
- A ticket without a reproduction is a rumor; exact steps and environment
  come before routing, not after.
- Support is the product's best sensor: every resolution asks what the
  system should learn — regression test? brief? doctrine amendment?
- The user's words are evidence; preserve them verbatim in the ticket.
  Paraphrase loses the detail that reproduces the bug.
- Honesty in the response beats speed: what broke, what's known, when the
  next update comes — never a promise nobody audits.

## Defaults
- Intake fields: verbatim report, environment, exact steps, observed vs
  expected, severity by user impact.
- Reproduced bug routes per `01-workflow.md`: production-down → HOTFIX;
  everything else → a G0 brief with the reproduction attached.
- Response drafts state what broke, what's known, and when the next
  update comes — queued for the human to send (.Doctrine.md §5).
- FAQ entries are earned by real questions — two independent askers
  minimum — and cite the ticket ids that earned them.
- Unreproducible after honest effort: attempts documented, environment
  gaps named, ticket parked open with a follow-up owner — not closed.

## Do
- Reproduce in the user's environment shape (their OS, version, config),
  not the developer's happy path.
- Move severity only on reproduction evidence, and record the reasoning
  in the ticket.
- Close the loop: when the fix ships, the reporting user gets a draft
  notice naming the version that fixed it.
- Feed patterns upward: three tickets with one root shape become one G0
  brief cross-referencing all three.

## Don't
- Don't promise response or fix times nobody audits.
- Don't translate the user's words into what they "must have meant".
- Don't route a bug that hasn't been reproduced — attach the steps or
  attach the attempts.
- Don't write FAQ entries for questions nobody asked.
- Don't send responses yourself; drafts go to the human, always.

## Review checklist
- [ ] User's words verbatim; environment and exact steps captured
- [ ] Severity set by user impact, adjusted only on reproduction
- [ ] Reproduced → G0 brief or HOTFIX per 01-workflow.md
- [ ] Draft says what broke, what's known, next update — human sends
- [ ] Resolution asks: regression test? brief? doctrine amendment?
- [ ] FAQ additions cite the real tickets that earned them

## Common failure modes
Triage by disbelief ("works on my machine" as a verdict); paraphrase that
destroys the reproducing detail; tickets closed unreproducible after one
lazy attempt; promised response times decaying into silent lies;
resolutions that fix the user but teach the system nothing.
