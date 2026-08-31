# Skill: Infrastructure as Code

**Scope.** Declarative infrastructure (Terraform/Pulumi/CDK or equivalent),
modules, state, environments, and the review discipline around applies.

## Principles
- If it isn't in code, it doesn't exist. A console change is drift, and
  drift is an incident seed — reproduce it in code or revert it.
- Plan before apply, always. The plan output is pasted into review; prod
  applies require an explicit human go (`.Doctrine.md §5`).
- State is sacred: remote, locked, never hand-edited, never committed.
  Editing state by hand is surgery with a shovel.
- Environment parity: dev/stage/prod differ by variables, never by
  architecture. A shape that exists only in prod is untested by definition.
- Cost is a review dimension. New infrastructure states its monthly
  estimate; paid services escalate per `.Doctrine.md §5`.

## Defaults
- Small, versioned modules with narrow inputs over one mega-stack; a
  module you can't read in one sitting is a module you can't review.
- Every resource tagged: owner, env, cost-center. Untagged is
  unaccountable — nobody's pager, nobody's budget.
- Least-privilege IAM written in code and reviewed like code; wildcards
  are findings, not conveniences.
- Destroy protection (lifecycle guards / deletion protection) on every
  stateful resource: databases, buckets, queues with unread messages.
- Drift detection scheduled, not accidental: a recurring plan against
  live infra, diffs surfaced as tickets.
- Local-first: emulate via floci (`skills/cloud-<provider>.md`) before
  touching real cloud; elevation is a pure configuration change.

## Do
- Keep plans small enough to actually read; split stacks when the plan
  output exceeds a reviewer's attention.
- Pin provider and module versions; upgrades are their own reviewed PRs.
- Encode naming conventions in modules so resources can't be misnamed.
- Treat `-target` applies and manual state moves as break-glass: logged,
  explained, followed by a reconciling PR.

## Don't
- Don't click-ops "just this once" — once is how drift starts.
- Don't apply from a laptop when a pipeline exists; don't apply to prod
  without a fresh plan of the exact commit.
- Don't share one state file across unrelated stacks — blast radius.
- Don't put secrets in code, state outputs, or plan logs.
- Don't import resources into state without also writing their code.

## Review checklist
- [ ] Plan output attached; matches stated intent, nothing extra
- [ ] Monthly cost estimate stated; paid services escalated per §5
- [ ] IAM diff least-privilege; no new wildcards
- [ ] Tags present (owner, env, cost-center) on every new resource
- [ ] Stateful resources carry destroy protection
- [ ] Env differences are variables only; architecture identical

## Common failure modes
The console hotfix nobody backported, resurfacing in the next apply as a
mystery diff; the mega-stack whose plan nobody reads anymore; apply before
review because the plan "looked fine locally"; state hand-edited to
unblock a rename, corrupting the run after; the untagged instance that
burned budget for months because it was nobody's.
