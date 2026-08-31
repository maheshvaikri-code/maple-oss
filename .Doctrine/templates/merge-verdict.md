# Merge Verdict — <task> → <protected branch>
<!-- G5 artifact. Enterprise merge profile. File as docs/merges/<task>.md -->

**Tag/commit under verdict:** <sha> · **Class:** L / release-bound
**Date:** · **Convened by:** Release Manager

## Council sign-offs (each independent; unanimity required)
| Member | Verdict | Artifact (path) |
|---|---|---|
| Code Reviewer | APPROVE / REQUEST-CHANGES | docs/reviews/<task>.md |
| Security Reviewer | SIGN-OFF / VETO | docs/qa/<task>-security.md |
| QA Engineer | PASS / FAIL | docs/qa/<task>.md |
| Project Reviewer | SIGN-OFF / RETURN | docs/reviews/<task>-scope.md |
| Compliance Officer (if in scope) | SIGN-OFF / BLOCK | docs/qa/<task>-compliance.md |

## Open findings at verdict time
BLOCKER: must be zero · MAJOR: resolved or waived by the human in
writing (reference below) · vetoes: none, or human override recorded.

## Verdict
- [ ] UNANIMOUS — cleared to merge (Release Manager executes)
- [ ] NOT CLEARED — returned to G3; findings above own the loop
Human waivers/overrides (verbatim, with date): …
