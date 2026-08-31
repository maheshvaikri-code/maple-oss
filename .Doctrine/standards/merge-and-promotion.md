# Standard: Merge & Promotion (Enterprise Profile)

**OPT-IN.** This profile activates only when the repo declares
`Merge profile: enterprise` in `docs/brief.md` (or the human demands it
for a release). Without it, the default gates (G4→G6) apply unchanged —
a solo repo does not convene a council to merge a bugfix. With it, three
mechanisms bind: the Merge Council, the permission matrix, and the Gold
Build ladder.

## 1. Merge Council — final merge to a protected branch

For Class L work and any release-bound merge:

- The council is: Code Reviewer · Security Reviewer · QA Engineer ·
  Project Reviewer, plus Compliance Officer when personal data or a
  regulated domain is in scope.
- Each member files an INDEPENDENT sign-off (fresh context, no shared
  narrative — Review Board rules from `02-role-protocol.md` apply).
- **Quorum is unanimity.** One BLOCKER, one veto, one missing sign-off =
  no merge. There is no majority vote over a security veto.
- The verdict is a filed artifact: `templates/merge-verdict.md` →
  `docs/merges/<task>.md`, referencing every sign-off by path. A merge
  without a verdict record on disk did not pass the council, whatever
  anyone remembers.

## 2. Permission matrix

| Action | Who may | Enforced by |
|---|---|---|
| Edit implementation code | Builder roles only | verifier agents are tool-denied Edit/Write |
| Merge to protected branch | Release Manager, after council verdict | branch protection: required checks + review count |
| Create release tag `vX.Y.Z` | Release Manager, human's go recorded | annotated tags only; CI re-tests the tagged commit |
| Promote candidate → GOLD | Release Manager | `doctrine_gold record` refuses without verdict + sign-offs + human approval |
| Deploy to production | From a GOLD record only | deploy pipeline reads the gold record; no record, no deploy |
| Override a security/compliance veto | The human ONLY, in writing | recorded in the verdict artifact |

Rights come from the role, never the individual session; a builder who
also wants to approve is two hats too many (separation of duties).

## 3. Gold Build ladder

Deployment is a promotion, not a build:

1. **Candidate** — the annotated tag's commit, full suite re-run on that
   exact commit in CI (no inherited green), artifacts built by pipeline.
2. **Soak** — the candidate runs in a staging environment against the
   promotion criteria named in the plan (health signals, smoke of the
   release scenario). Evidence recorded, not remembered.
3. **GOLD** — `doctrine_gold record` emits
   `docs/releases/gold/<tag>.json` (schema:
   `schemas/gold-build.schema.json`, canonical bytes): artifact sha256s,
   the commit, the council verdict path, every sign-off path, soak
   evidence, the human's recorded approval — and `prev_gold_sha256`
   chaining to the previous gold record, same discipline as state-plane
   checkpoints. `doctrine_gold check` re-verifies all of it.
4. **Deploy** — only from a gold record. **Rollback is the previous gold
   record**, not a rebuild: the chain IS the rollback ladder.

## Do / Don't

- Do run `doctrine_gold check --tag vX.Y.Z` in the deploy pipeline —
  a tampered artifact or missing sign-off fails the deploy, loudly.
- Do keep gold records immutable; a correction is a new record.
- Don't hand-edit a gold record (hash-chained; `check` catches it).
- Don't deploy a candidate "just this once" — that's the incident
  you'll retro next week.
- Don't let the profile creep into Class S/M work; enterprise ceremony
  exists for release-bound merges, not typo fixes.
