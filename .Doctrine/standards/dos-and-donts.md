# Standard: Dos and Don'ts

The company's hard rules, in one place. Section 1 exists because the
workforce is an AI; the rest apply to any engineer, silicon or otherwise.

## 1. AI-honesty rules (cardinal — violations invalidate the work)

**Do**
- Run it before you say it. "Tests pass" means you executed them this
  session and are pasting real output.
- Verify APIs against the installed reality: read the code in the venv /
  `cargo doc`/source, check `pip show`/`cargo tree` versions — not memory.
- Say "blocked", "failed", or "I don't know" plainly and early. Propose the
  next step alongside it.
- State assumptions you chose ("assumed UTC timestamps — flag if wrong").
- Show uncertainty honestly: "this compiles and unit-passes; I could not
  test the S3 path without credentials" is a professional sentence.

**Don't**
- Don't invent functions, flags, config keys, or library behavior. If
  unverified, label it unverified.
- Don't fabricate, paraphrase, or "reconstruct" command output. Ever.
- Don't claim completion with TODOs, stubs, or `unimplemented!()` inside.
- Don't delete, skip, `#[ignore]`, or weaken a failing test/assertion/lint
  to go green. Fix the cause or escalate.
- Don't silently narrow scope ("implemented the easy 80%") — narrowed scope
  is reported scope.
- Don't touch files unrelated to the task; don't reformat code you didn't
  change; don't "improve" things nobody asked about without flagging first.
- Don't retry a flaky thing until it passes and report the pass.

## 2. Code

**Do:** keep functions small and single-purpose · name things after what
they mean · comment *why*, never *what* · handle every error path the type
system shows you · delete dead code (git remembers).
**Don't:** no commented-out code in commits · no copy-paste-thrice
(extract on the third) · no clever one-liners where a boring three-liner
reads instantly · no global mutable state without a documented reason.

## 3. Git

**Do:** atomic commits, present-tense conventional messages · branch per
task · pull/rebase before starting · read the diff of every commit before
making it.
**Don't:** never commit secrets (even briefly — history is forever) · never
force-push shared branches · never commit broken code to main · never mix
formatting churn with logic in one commit.

## 4. Testing

**Do:** test behavior, boundaries, and failure paths · regression test per
bug, same commit · keep tests deterministic and independent.
**Don't:** no assert-free tests · no order-dependent suites · no
sleep-based synchronization · no mocking what you own and can run.

## 5. Dependencies

**Do:** stdlib first · justify every new dep in the PR against
`dependency-policy.md` · commit lockfiles · run audits.
**Don't:** no deps for ten lines of writable code · no unpinned installs in
CI · no license-unknown code vendored in · no upgrading everything "while
we're here."

## 6. Security

**Do:** parameterize queries · validate at boundaries · bound every
user-influenced resource · rotate anything that leaked.
**Don't:** never log secrets · never build SQL/shell strings from input ·
never ship `eval`/`pickle`-on-untrusted · never disable TLS verification to
"fix" an error.

## 7. Communication & process

**Do:** update the plan file as reality diverges · file findings with
severity + location + suggestion · escalate per `.Doctrine.md` §5 · write
changelog entries when the change lands.
**Don't:** don't ask the human what the codebase can answer · don't bury
the lede (status first, story second) · don't mark a gate passed with its
checklist unticked · don't let "quick fixes" bypass the pipeline twice in a
row without a retro asking why · don't mark a finding "fixed" without
re-executing the original failing probe and referencing its output —
"fixed" from memory of intent is a §1 honesty violation.
