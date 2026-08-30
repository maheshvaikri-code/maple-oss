# Standard: Coding Standards

The General rules below are language-neutral and always bind. Everything
ecosystem-specific lives in a language profile — load the profile(s) for
the languages actually in play, nothing else.

## General
- Optimize for the reader. Code is read ~10× more than written; the reader
  is a stranger under time pressure.
- Names are the first documentation: `remaining_retries` not `n`;
  functions are verbs, values are nouns, booleans read as predicates
  (`is_ready`, `has_expired`).
- Functions do one thing; if you need "and" to describe it, split it.
  Depth of nesting > 3 is a smell; early-return the edges.
- Comments explain **why** (constraints, tradeoffs, links to issues/ADRs).
  A comment explaining *what* means the code failed — fix the code.
- No magic values: name constants, with units in the name where ambiguity
  is possible (`TIMEOUT_SECS`).
- Formatting is the formatter's job, enforced in CI. Nobody debates
  whitespace in review, ever.
- Public surface documented; internal helpers earn docs when non-obvious.
- Parse, don't validate: raw input becomes typed structures once, at the
  boundary; everything inward trusts the types.
- Errors follow `standards/error-handling.md`; tests follow
  `skills/testing.md` — in every language.

## Language profiles (`standards/languages/`)

| Language in play        | Load                        |
|-------------------------|-----------------------------|
| Rust                    | `languages/rust.md`         |
| Python                  | `languages/python.md`       |
| TypeScript / JavaScript | `languages/typescript.md`   |
| Go                      | `languages/go.md`           |
| Java / Kotlin (JVM)     | `languages/jvm.md`          |
| C# (.NET)               | `languages/dotnet.md`       |

A language without a profile is not banned — apply the General rules plus
the ecosystem's canonical toolchain (formatter, linter, test runner,
audit), and propose a new profile via a G7 retrospective if the language
recurs.
