---
name: doctrine-ponytail
description: Doctrine shim for the ponytail behavioral layer. Engage on EVERY code-writing, refactoring, review, or dependency-selection task in a .Doctrine repo — writing features, fixing bugs, scaffolding FDE prototypes, choosing libraries — and whenever the user says "ponytail", "be lazy", "simplest", "minimal", "yagni", or complains about bloat or over-engineering. This shim adds the .Doctrine precedence rules on top of upstream ponytail; consult it before assuming the upstream ladder applies unmodified.
version: 0.1.0
requires: [ponytail >= 4.8.4 installed via adapter]
---

# doctrine-ponytail

Upstream ponytail governs; this shim binds it to `.Doctrine` invariants.

## Operating rules

1. **Run the ladder after understanding, not instead of it.** Read the code the change
   touches and trace the real flow first — lazy about the solution, never about reading.
2. **Apply doctrine precedence** (from INTEGRATION.md): determinism scaffolding is
   never-cut; rung 5 struck in zero-dependency-chartered repos; mode ceiling `full` on
   library/public-API code, `ultra` allowed on FDE P4 prototypes and demos.
3. **Answer rung 2 with graphify when available.** If `graphify-out/graph.json` is
   fresh, `graphify query "<capability>"` / `graphify explain "<symbol>"` before
   concluding nothing reusable exists. One query beats skimming five files.
4. **Say the rung.** When skipping work (rung 1) or replacing a request with one line
   (rung 6), state it in a single line — the rationale is part of the deliverable.
5. **Never trade away** trust-boundary validation, error handling on data loss,
   security, accessibility, or repo-charter invariants, at any mode.

## Anti-patterns this shim exists to stop

Installing a dependency for what stdlib does; re-implementing a helper that lives three
files away; wrapping a native platform feature in a component; "flexible" abstractions
for one call site; deleting hash-gate or conformance-vector code because it "looks
redundant" — that last one is a doctrine violation, not laziness.
