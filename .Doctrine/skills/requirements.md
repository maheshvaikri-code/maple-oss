# Skill: Requirements

**Scope.** The G0 craft: turning raw requests into briefs with testable
acceptance criteria, real non-goals, and slices the build can prove.

## Principles
- Separate the problem from the proposed solution. Users report solutions
  ("add a button"); briefs record problems — who hurts, how, why now.
- Acceptance criteria are executable sentences: "user can X and observes
  Y." Never "works well" or "is fast" — put a number on the adjective or
  drop it.
- Slice vertically: each slice independently green and demonstrable end to
  end. A slice that is "all the models" demos nothing.
- Edge cases are intake work, not test-time discoveries: empty, huge,
  concurrent, malformed. The QA adversarial classes start here, not at G5.
- Scope is sacred. Mid-build additions go back through G0 as a brief
  amendment or into Deferred — never absorbed silently.

## Defaults
- Brief per `templates/project-brief.md`: problem, scope, non-goals,
  numbered ACs, constraints, assumptions, open questions.
- Non-goals listed with at least one real entry. A brief that says "none"
  hasn't been interrogated.
- Ambiguity policy: trivial → choose a default and record it under
  Assumptions; material (the answer changes the build) → escalate per
  `.Doctrine.md` §5 and block on it.
- Every AC maps to at least one test the plan names; that AC-to-test
  trace is what G5 verifies against.

## Do
- Ask the human only questions whose answers change the build; propose
  defaults for the rest and mark them as assumptions to correct.
- Write each AC so a stranger could run it and call pass or fail without
  asking you anything.
- For every "fast/robust/simple" in a request, extract the measurable
  claim underneath or strike the word from the brief.
- Enumerate, per feature, what happens with zero items, with millions,
  with two concurrent writers, and with garbage input — at intake.
- Park every good idea that arrives mid-task in Deferred, visibly, so it
  is saved rather than smuggled in.

## Don't
- Don't brief the requester's mechanism as the requirement; record it as
  one candidate and let G1 decide.
- Don't write an AC that cannot fail ("handles errors gracefully").
- Don't slice horizontally by layer — schema, then backend, then UI —
  because nothing demos until everything lands.
- Don't ask twenty clarifying questions when two change the build.
- Don't let "small tweak while we're in there" bypass the gate; size is
  irrelevant, scope change is scope change.

## Review checklist
- [ ] Problem stated solution-agnostic; requester's fix listed as an option
- [ ] Every AC observable, numbered, and mapped to a named test
- [ ] Adjectives quantified or deleted; no "fast/robust/well"
- [ ] Slices vertical, independently green, each demonstrable
- [ ] Non-goals include at least one real exclusion
- [ ] Edge-case classes (empty/huge/concurrent/malformed) enumerated

## Common failure modes
Briefs that restate the ticket verbatim, solution and all; acceptance
criteria written to pass rather than to test; non-goals left as "none";
edge cases deferred to QA, who find them at G5 when fixes cost tenfold;
scope absorbed one reasonable tweak at a time until the brief describes a
different project than the one that got built.
