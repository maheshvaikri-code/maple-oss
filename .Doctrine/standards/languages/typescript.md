# Language Profile: TypeScript

**Applies when.** UI code, Node services, or any TS/JS package in the repo.

## Toolchain
- Node LTS pinned (`.nvmrc`/`engines`); one package manager per repo,
  its lockfile committed; `tsconfig.json` with `strict: true` always.

## Format & lint
- ESLint + Prettier in CI, same as everything else: enforced, not
  debated.

## Types & idioms
- No `any` without an inline justification comment; `unknown` + narrowing
  at boundaries instead.
- Types at the data boundary: parse/validate responses (e.g. zod) before
  they enter typed code; interfaces for public props.
- Discriminated unions over boolean flags; `as const` over magic strings;
  exhaustiveness-checked switches (`never` default arm).
- Async: no floating promises (lint-enforced); `AbortSignal` accepted by
  long-running operations.

## Errors
- Errors are `Error` subclasses with a `cause`; never throw strings.
- Boundaries decide: UI surfaces the five states (`skills/ui.md`),
  services map errors per `standards/error-handling.md`. No empty
  `catch {}` — handle, wrap-with-cause, or rethrow.

## Testing
- Vitest (or Jest) with output shown; fast-check where the logic has
  algebra; Testing Library for components — assert behavior, not
  implementation details.

## Dependencies
- `npm audit` (or ecosystem equivalent) in CI; beware micro-packages —
  stdlib/platform first; every addition passes
  `standards/dependency-policy.md`.

## Review checklist add-ons
- [ ] strict mode on; no unjustified `any`; boundaries parse, not cast
- [ ] Unions discriminated; switches exhaustive
- [ ] No floating promises; cancellation paths where operations are slow
- [ ] Errors subclass Error with cause; no empty catch
