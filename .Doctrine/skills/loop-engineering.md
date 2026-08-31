# Skill: Loop Engineering

The gates G0–G7 are the company's **outer loop**. This skill governs the
**inner loop** — the act → observe → validate → decide cycle you run dozens
of times inside G3 (and inside every fix at G4/G5). Prompt engineering is
what you say per call; context engineering is what you see per call; loop
engineering is **what calls happen, when to iterate, when to gate, and when
to stop**. Undisciplined inner loops are where fabrication, thrash, and
budget burn are born.

## Loop anatomy — every iteration has five beats

1. **Anchor** — restate the acceptance criterion this iteration serves
   (verbatim from the brief/plan). The criterion is the loop invariant.
2. **Act** — the smallest change that produces an observable result.
3. **Observe** — RUN it. Real command, real output, pasted. Predicted
   output is not observation (Non-Negotiable #1).
4. **Validate** — pass the result through a deterministic gate, in order:
   compiles/lints → tests pass → acceptance criterion advanced →
   no regression elsewhere → still inside scope. A gate says **no**
   mechanically; "looks right" is not a gate.
5. **Decide** — exactly one of: *iterate* (criterion not met, budget
   remains) · *done* (criterion met with evidence) · *stop & escalate*
   (budget out, or thrash detected, or the plan is wrong).

## Execution caps — loops end by design, not exhaustion

- Set an iteration budget when entering a loop: default **5** per
  acceptance criterion (S), **10** (M/L). Budget out → stop, write down
  what was tried, escalate or return to G2 re-planning. An honest
  "stuck after N attempts, here's the evidence" beats attempt N+20.
- **Thrash detector**: same file edited 3× with no test-delta, or the
  same error message twice after "fixing" it → the hypothesis is wrong.
  Stop patching; go up a level (re-read the plan, re-read the actual
  code, question the diagnosis).
- **Flaky-test rule**: a test that fails intermittently is a defect to
  file, not a retry target. Max one re-run to confirm flakiness; never
  loop until lucky-green.
- Re-anchor every 5 iterations: re-read the acceptance criteria. Long
  loops drift — the fix that "works" often no longer serves the brief.

## Deterministic validation (the DCCV pattern)

Wire the loop so something mechanical says no at each level: spec ↔ story
↔ acceptance criteria ↔ test coverage ↔ regression impact ↔ observed
behavior — and a failure at any level feeds **back to the level that owns
it**, not to another patch on top. Symptom-level patches that silence a
gate without satisfying its level are defects.

## Measure the loop (the CodeMonk pattern)

Record per task, file in the QA report / retro (G7 reads these):
- **Iterations-to-green** per criterion (converging or wandering?)
- **Churn ratio** — lines rewritten vs. lines surviving to the commit
- **Interventions** — how many times the human had to step in, and where
- Escapes: any defect found at G4/G5 that the inner loop's gates missed
  → that's a missing gate, propose it at G7.

## Cross-run persistence

Before a session ends mid-loop, write a loop journal entry in the plan
file: criterion in progress, attempts made, hypotheses killed, next step.
A resumed loop that repeats a dead end is a doctrine failure, not bad luck.

## Common failure modes

- **Thrash** — editing in circles; caps + detector above exist for this.
- **Victory on partial green** — "the important tests pass." All means all.
- **Gate-weakening** — deleting/loosening the failing check (forbidden,
  Non-Negotiable #4).
- **Stale observation** — reasoning from a file state you already edited;
  re-read after every apply.
- **Scope creep mid-loop** — "while I'm here" fixes; new finding = new
  task at G0, note it and stay on the criterion.
- **Retry-as-strategy** — rerunning unchanged code hoping for different
  output; only a *changed hypothesis* earns another iteration.
