# 01 — Workflow: Lifecycle, Gates, and Loops

## Task classes (recap from root)

- **S** — no behavior change → G3 + self-review checklist from `roles/code-reviewer.md`.
- **M** — feature/bugfix/refactor in one module → G2→G5, then merge (G6 only if releasing).
- **L** — new project/module, public API or schema change, cross-cutting → G0→G7.
- **HOTFIX** — prod repair → G3→G4→G5-lite→G6, mandatory G7 within the same
  day. The SRE wears Incident Commander throughout (`roles/sre.md`):
  mitigate first, coordinate, don't type.

When a task grows mid-flight (an M reveals a schema change), stop, reclassify,
and enter the missing earlier gates before continuing.

## The gates

### G0 — Intake (owner: Product Owner)
- **Entry:** a raw request from the human.
- **Do:** interrogate the request; separate problem from proposed solution;
  define scope, non-goals, acceptance criteria, constraints; ask the human
  only questions that materially change the build.
- **Exit:** a Project/Task Brief (`templates/project-brief.md`) the human
  has confirmed, filed under `docs/`.

### G1 — Architecture (owner: Chief Architect)
- **Entry:** approved brief.
- **Do:** module boundaries, data flow, tech selection, failure-mode sketch,
  alternatives considered. One ADR per significant decision.
- **Governance co-sign** (`standards/governance.md`): designs touching
  AI, data architecture, or security-sensitive surfaces get the matching
  head's co-sign on the ADR (Head of AI / Head of Data / CISO) —
  mandatory on `Merge profile: enterprise` repos; a head can send the
  design back here, which is cheaper than a veto catching it at G5.
- **Exit:** design captured in ADR(s) (`templates/adr.md`) — the ADR set
  *is* the design document; no unresolved "TBD" on anything the build needs.

### G2 — Planning (owner: Chief Architect)
- **Entry:** approved design.
- **Do:** slice work into ordered, individually-green steps; per step name
  the role, the files touched, the tests that prove it; identify risks and
  rollback points.
- **Exit:** Implementation Plan (`templates/implementation-plan.md`).
  Plans are promises about sequence, not straitjackets — deviations get
  noted in the plan file as they happen.

### G3 — Build (owner: the engineer role for the skill in play)
- **Entry:** plan step ready.
- **Do:** implement per skills/standards; write tests alongside code; run
  the suite locally; keep commits atomic; update docs touched by the change.
- **Exit:** all plan steps done; suite green with output shown; lints/types
  clean; self-review pass complete.

### G4 — Code Review (owner: Code Reviewer)
- **Entry:** G3 exit.
- **Do:** fresh-eyes diff review per `roles/code-reviewer.md`. Findings are
  severity-ranked: **[BLOCKER]** must fix · **[MAJOR]** fix or human waiver ·
  **[MINOR]** fix now or first thing next task · **[NIT]** optional.
- **Exit:** Review Report filed; zero open BLOCKERs; MAJORs resolved or
  waived by the human in writing.

### G5 — Verification (owners: QA Engineer + Security Reviewer)
- **QA:** execute the test plan derived from acceptance criteria; adversarial
  inputs, edge cases, regression sweep; verify by running, never by reading.
- **Security:** secrets scan, input-boundary audit, dependency audit,
  unsafe-pattern check per `skills/security.md`. **Security holds a veto.**
- **Compliance:** joins G5 when the task touches personal data, regulated
  domains, or new third-party data flows (`roles/compliance-officer.md`);
  can block pending human legal review.
- **Exit:** QA Report filed; security sign-off recorded (compliance
  sign-off where engaged). G5-lite (HOTFIX): targeted tests on the fix +
  secrets/dep scan only.

### G6 — Release (owner: Release Manager; entry signed by Project Reviewer)
- **Entry:** Project Reviewer confirms the brief was actually built (scope
  audit, DoD audit) — see `roles/project-reviewer.md`.
- **Do:** version per semver, changelog, tag, build artifacts, publish
  **only with explicit human approval**, post-release verification.
- **Enterprise profile** (`Merge profile: enterprise` in the brief):
  release-bound merges additionally require the Merge Council verdict and
  deployment happens only from a hash-chained Gold Build record —
  `standards/merge-and-promotion.md`.
- **Exit:** `templates/release-checklist.md` fully checked.

### G7 — Retrospective (owner: Project Reviewer)
- What worked, what failed, root causes (5-whys on any escaped defect),
  concrete doctrine/tooling amendments proposed. File under `docs/retro/`.
- Repos with metrics adopted (`skills/metrics.md`): attach the CodeMonk
  scorecard (`docs/metrics/`) — CESR drops feed the 5-whys; HITL
  reduction only celebrated while CESR holds.

## Closed loops

- G4/G5 findings → back to **G3** (or **G1** if the defect is architectural).
- Escaped defects found post-release → HOTFIX path → **G7** → doctrine amendment.
- Repeated finding categories across retros → new rule in `standards/` or a
  new check in CI (prefer automation over vigilance).

## Session discipline

At session start: read the current plan file (if mid-task) before touching
code. At session end or context handoff: update the plan file with real
status — what's done (with evidence), what's next, what's blocked.

Repos that adopted the state plane (`state-plane/STATE.md`) additionally
hydrate from `.doctrine-state/` at session start and write a checkpoint +
distillate at session end — the plan file records intent; the state plane
records verified session state.
