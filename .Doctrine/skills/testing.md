# Skill: Testing

**Scope.** Unit, integration, property/invariant, regression, and golden
testing — the evidence layer for every other skill.

## Principles
- Tests exist to fail. A test that can't fail, or that no one would believe
  when it does, is decoration.
- Test behavior at boundaries, not implementation internals — refactors
  shouldn't shred the suite if behavior held.
- Determinism is non-negotiable: seed randomness, freeze time, isolate
  filesystem/network. Flakiness is a defect in the test, treated like one.
- The pyramid is real: many fast unit tests, fewer integration, a handful
  of end-to-end. Inverting it buys slow, brittle false confidence.

## Property & invariant testing (first-class here)
- Anything with algebra gets property tests: roundtrips
  (encode∘decode = id), idempotence (f∘f = f), ordering/monotonicity,
  conservation ("nothing lost, nothing invented").
- Rust: `proptest`; Python: `hypothesis`. Persist failure seeds/corpus in
  the repo so found bugs stay found.
- State invariants asserted at checkpoints in integration tests, not just
  final-state equality.

## Defaults
- A bug fixed = a regression test added, in the same commit, named after
  the failure (`test_reissue_after_partial_write_regression`).
- Naming: `test_<unit>_<scenario>_<expected>`. Arrange-Act-Assert visible.
- Fixtures/builders over copy-pasted setup; golden files for complex
  output with a deliberate, reviewed update path (never blind-regenerate).
- Coverage is a flashlight, not a target: use it to find dark corners;
  never write assert-free tests to move the number.

## Do
- Write the failure-path tests first — errors, timeouts, malformed input —
  they're where production pain lives.
- Failure-path tests assert the ABSENCE of side effects, not just the
  error code: after a rejected input, prove state files, logs, and stores
  are byte-identical to before.
- Test at limits: empty, one, many, max, max+1, unicode, zero, negative,
  concurrent, interrupted — and cross valid×invalid parts of one input
  (a valid distillate inside an invalid checkpoint still writes nothing).
- Keep unit tests <100ms each; move slow suites behind an explicit target
  that CI still runs.
- Run the suite before every "done"; paste real output into the report.

## Don't
- Don't mock what you own if the real thing runs fast; don't integration-
  test what a unit test proves.
- Don't assert on incidental details (exact log text, dict order, private
  fields) — that's how refactors become archaeology.
- Don't share mutable state between tests; order-dependence is a bug.
- Don't delete/skip/weaken a failing test to go green — the doctrine's
  cardinal sin (see `standards/dos-and-donts.md`).
- Don't test third-party libraries' correctness; test your use of them.

## Review checklist
- [ ] New behavior: happy path + failure paths + boundary values covered
- [ ] Properties/invariants tested where algebra exists
- [ ] Deterministic: seeded, time-frozen, isolated; passes twice in a row
- [ ] Bug fixes carry their regression test
- [ ] Suite output shown, not summarized from imagination

## Common failure modes
Assert-free "tests" farming coverage; mock-everything suites that pass while
production burns; golden files regenerated wholesale to silence a diff;
sleep-based concurrency tests that flake weekly.
