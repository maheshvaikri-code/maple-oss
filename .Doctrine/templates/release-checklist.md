# Release Checklist — v<X.Y.Z>
<!-- G6 artifact. File as docs/releases/v<X.Y.Z>.md. All boxes or no release. -->

## Entry
- [ ] Project Reviewer sign-off recorded (brief vs delivered audit)
- [ ] Version per semver; rationale one-liner: …
- [ ] Clean working tree on release branch/main

## Verify (on the exact release commit)
- [ ] Full suite green **on this commit** — output pasted
- [ ] Lint/format/typecheck/audit clean
- [ ] CHANGELOG.md section for this version complete, user-readable,
      breaking changes unmissable
- [ ] Version strings consistent (manifest, lockfile, docs, `--version`)
- [ ] Docs/quickstart updated; examples executed

## Ship
- [ ] **Human's explicit go for publishing recorded here:** "…" (date)
- [ ] Annotated tag `vX.Y.Z` created and pushed
- [ ] Artifacts built by pipeline (sdist/wheel · crate · binaries)
- [ ] Published (PyPI / crates.io / …) via pipeline

## Prove
- [ ] Clean-environment install from the registry succeeded
- [ ] Quickstart executed against the published artifact — output pasted
- [ ] Rollback story confirmed: yank command · prior-version pin note

## Close
- [ ] Release notes/GitHub release posted
- [ ] G7 retro scheduled (mandatory for HOTFIX)
