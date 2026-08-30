# Standard: Dependency Policy

Every dependency is a hire: it gets an interview, a background check, and
its salary is paid in your attack surface, build time, and future migrations.

## Default posture
**Stdlib first.** For libraries this company ships (PyPI/crates.io),
zero-runtime-dependency is the *preferred* state and a feature worth
advertising. Applications may hire more freely — but still through the
interview.

## The interview (answer in the PR that adds it)
1. **Need:** what does it do that ~50 lines of owned code wouldn't? (If the
   answer is "saves 10 lines" — write the 10 lines.)
2. **Health:** maintained? (commits/releases within ~a year, issues
   triaged) · widely used enough to be scrutinized?
3. **Weight:** transitive tree size (`cargo tree` / `pipdeptree`) · build
   time impact · does it drag a runtime (tokio? numpy?) the project
   doesn't otherwise need?
4. **License:** MIT/Apache-2.0/BSD/ISC — fine. LGPL/MPL — flag for thought.
   GPL/AGPL in a shipped library — human decision, explicitly.
   Unknown license — no.
5. **Security:** audit clean today (`cargo audit`/`pip-audit`), no unsafe/
   native surprises unaccounted for.

Record the verdict in one PR paragraph. Failing answers → escalate per
`.Doctrine.md` §5.

## Ongoing obligations
- Lockfiles committed; CI installs from lockfiles only.
- Audits run in CI on every push; findings dispositioned in writing (fix,
  upgrade, accept-with-reason), never ignored silently.
- Upgrades are deliberate: patch/minor batched routinely with changelog
  reading; majors get their own task with the migration named. Never
  "upgrade everything while we're here" inside a feature branch.
- Version-pin philosophy: libraries declare compatible *ranges* (caret),
  apps pin via lockfile. Both commit the lock.
- Dev-dependencies get a lighter interview but the same license/audit bar.

## Vendoring & copying
Copied code is a dependency with the update channel cut: allowed for small,
stable snippets **with** source URL + license comment at the site — and it
inherits our test/review standards immediately.

## Removal
A dep that stops earning its keep (one call site, unmaintained, audit
noise) is removed proactively. Deleting a dependency is a celebrated commit
type here.
