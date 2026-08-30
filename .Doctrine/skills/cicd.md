# Skill: CI/CD

**Scope.** Pipelines (GitHub Actions or equivalent), quality gates in
automation, artifact builds, and release automation to registries.

## Principles
- CI is the doctrine's enforcement arm: every rule that can be a check is a
  check. Humans (and AIs) forget; pipelines don't.
- Fail fast, fail cheap: order stages by cost — fmt → lint → typecheck →
  unit → integration → audit → build.
- A red pipeline is a stop-the-line event, not background noise. A flaky
  test is a bug with a ticket, never a retry-until-green.
- Release automation executes releases; it never decides them. Publish
  steps run on tags, gated on the human having created the tag deliberately.

## Default pipeline
- Triggers: PR + main push (full suite); tag `v*` (release job).
- Rust: `cargo fmt --check` · `cargo clippy --all-targets -- -D warnings` ·
  `cargo test` · `cargo audit` · matrix on stable + MSRV; OS matrix when
  platform-relevant.
- Python: `ruff format --check` · `ruff check` · `pyright` (or mypy) ·
  `pytest` · `pip-audit` · matrix on supported minors (e.g. 3.10–3.13).
- Node/UI: lint · typecheck · test · build.
- Cache package registries/target dirs keyed on lockfile hash.
- Upload build artifacts; keep logs enough to debug without re-running.

## Release job (tag-triggered)
1. Re-run the **full** suite on the tagged commit — no inherited green.
2. Build artifacts (sdist+wheel via maturin/uv build; `cargo package`).
3. Verify metadata (version matches tag; changelog section exists).
4. Publish (PyPI via trusted publishing/OIDC where possible; crates.io) —
   step requires the environment/approval configured for the human's go.
5. Post-publish smoke: install from the registry in a clean job; run the
   quickstart.

## Do
- Keep workflow YAML boring and commented; extract logic into `scripts/`
  so it's runnable and testable locally.
- Pin action versions; least-privilege `permissions:` per workflow.
- Make required checks required — branch protection mirrors the gates.
- Time-bound everything; a hung job fails loudly.
- An OS named as a constraint in the brief gets a CI matrix leg — a unit
  test emulating that OS's behavior is a stopgap, not a substitute.

## Don't
- Don't put secrets in workflow files or echo them into logs.
- Don't `continue-on-error` a quality gate to ship faster.
- Don't publish from a laptop when a pipeline exists; don't let the
  pipeline publish without a human-created tag/approval.
- Don't let CI-only scripts diverge from the local task runner.

## Review checklist
- [ ] Stage order cheap→expensive; total time bounded
- [ ] Matrices match declared support (MSRV, Python minors, OS)
- [ ] Audit steps present and failing-on-findings
- [ ] Release job re-tests the exact tagged commit; smoke-tests the
      published artifact
- [ ] Permissions minimal; actions pinned; no secret leakage in logs

## Common failure modes
Green-by-flake; quality gates commented out "temporarily" forever; releases
that skip the suite because "nothing changed"; the publish token with
god-scope in a fork-triggerable workflow.
