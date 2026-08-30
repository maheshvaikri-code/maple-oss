# Skill: Architecture

**Scope.** The G1 craft: module boundaries, ADRs, data flow, failure modes,
technology selection — a design the build executes without guessing.

## Principles
- Draw boundaries where change happens together. A boundary every feature
  must cross is a wall in the wrong place; move it, don't tunnel it.
- Dependency direction is one-way, always. A cycle is design debt that
  charges interest on every future change.
- Sketch the failure modes before the happy path: what breaks, what
  degrades, what pages someone at 2 a.m. The happy path designs itself.
- Design for deletion. The best module is one you can remove without
  archaeology; if nothing could ever be deleted, everything is coupled.
- Boring first, per the charter: stdlib and proven before novel. Novelty
  must buy something measurable, and the ADR says what and how much.

## Defaults
- One ADR per significant decision (`templates/adr.md`), alternatives
  honestly considered. An ADR with one option is a memo, not a decision.
- Data flow drawn end-to-end — source to sink, error paths included.
  A diagram that only shows success is half a design.
- Capacity and scale assumptions stated with numbers (rows, QPS, payload
  sizes, retention) or explicitly labeled unknown. Silence is not a number.
- Governance surfaces named early: AI-, data-, or security-sensitive
  designs get the matching head's co-sign per `standards/governance.md`.

## Do
- Trace every brief requirement to a design element before calling G1 done;
  the untraced requirement is the one that comes back as a G5 defect.
- Name the contract at each boundary: who owns the state, what crosses,
  and what the caller may assume when the callee fails.
- State each component's blast radius — what else goes down with it, and
  how the system would tell you.
- Prefer removing a box from the diagram to adding an arrow between two.
- Write invalidation triggers into each ADR — the future fact that reopens
  the decision — so revisiting is planned, not litigated.

## Don't
- Don't design for load, tenants, or plugins nobody asked for; record the
  growth path in the ADR and build the small thing.
- Don't leave a TBD in the design and call the gate passed. The design is
  done when the build needs no unresolved TBD — not when the diagram is
  pretty.
- Don't pick technology by familiarity or résumé; pick by the constraint
  table, and show the losing options their honest pros.
- Don't let two modules share mutable state without naming one owner.

## Review checklist
- [ ] Boundaries follow change, not org chart or layer habit
- [ ] Dependency graph one-way; zero cycles
- [ ] Failure modes, degradation, and paging story written down
- [ ] Every significant decision has an ADR with ≥2 real alternatives
- [ ] Capacity assumptions carry numbers or an explicit "unknown"
- [ ] Governance co-sign surfaces identified; matching heads named

## Common failure modes
Boundaries drawn by noun instead of by change, so every feature edits five
modules; ADRs written after the code to bless what already exists;
happy-path diagrams with no error arrows; "scales horizontally" with no
number attached; the novel framework that bought nothing measurable; a
design signed off with three TBDs, each of which resurfaces mid-build as a
stop-the-line question.
