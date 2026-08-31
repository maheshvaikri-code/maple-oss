# Language Profile: Rust

**Applies when.** Any crate in the repo — libraries, binaries, PyO3/FFI.

## Toolchain
- `rust-toolchain.toml` pins the channel; MSRV declared in `Cargo.toml`
  and tested in CI. `Cargo.lock` committed for bins and libs alike.

## Format & lint
- `rustfmt` (checked in CI) · `clippy --all-targets -- -D warnings`.
  Nobody debates whitespace in review, ever.

## Types & idioms
- Borrow before clone; `&str`/`&[T]` in APIs over owned where possible;
  `impl Trait` params for flexibility.
- Prefer exhaustive `match` over `_` arms on your own enums — let the
  compiler find your missed cases when variants grow.
- Avoid lifetime gymnastics a small redesign would erase.
- Newtypes over primitive obsession at public boundaries.

## Errors
- `Result` everywhere fallible. Libraries: `thiserror` enums with
  meaningful variants. Binaries: `anyhow` with `.context()` at each layer.
- **No `.unwrap()`/`.expect()` in library code paths.** Permitted in
  tests, examples, and `main` startup where failure is unrepresentable —
  with `expect("why this cannot fail")` phrasing.
- No `panic!` for expected conditions; panics are for broken invariants.
- `unsafe` is a loan against review time: minimal block, `// SAFETY:`
  comment stating the upheld invariants, Security-Reviewer eyes at G5.

## Testing
- `cargo test` green with output shown; `proptest` where the logic has
  algebra (roundtrips, ordering, idempotence); `criterion` for benches;
  `loom` for tricky concurrent structures.

## Dependencies
- `cargo audit` (or `cargo deny`) in CI; features minimized; no git
  dependencies on main; every addition passes `standards/dependency-policy.md`.

## Review checklist add-ons
- [ ] No unwrap/expect in library paths; expect() messages say why
- [ ] `unsafe` blocks minimal with SAFETY comments
- [ ] Public API takes borrows where it can; exhaustive matches on own enums
- [ ] MSRV honored; clippy clean at -D warnings
