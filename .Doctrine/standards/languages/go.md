# Language Profile: Go

**Applies when.** Any module with a `go.mod` — services, CLIs, libraries.

## Toolchain
- Go version pinned by the `toolchain` directive in `go.mod`; CI builds
  with exactly that — no "latest" drift between laptops and pipeline.
- Modules only. `go.sum` always committed; `go.work` never is.

## Format & lint
- `gofmt` + `goimports` are non-negotiable; unformatted code fails CI.
- `golangci-lint run` with a committed `.golangci.yml`; at minimum
  `govet` · `errcheck` · `staticcheck` · `errorlint` · `ineffassign`.
- `//nolint` requires a directive and a reason: `//nolint:errcheck // why`.

## Types & idioms
- Interfaces are small (1–3 methods) and defined at the consumer, not the
  implementation. Accept interfaces, return concrete types.
- `context.Context` is the first parameter of anything that blocks or
  crosses a process boundary; propagated, never stored in a struct.
- Every goroutine has an owner and an exit path: whoever starts it knows
  how it stops (context cancel, closed channel). No fire-and-forget.
- Channels: sender closes; direction-typed in signatures (`<-chan`,
  `chan<-`); buffer sizes chosen for a stated reason, not vibes.
- Make the zero value useful; `NewX` constructors only where invariants
  demand them. Package names are short nouns — no `util`/`helpers` dumps.

## Errors
- Errors are values. Wrap at each layer that adds meaning:
  `fmt.Errorf("loading config: %w", err)`; branch with
  `errors.Is`/`errors.As`, never string matching.
- **`_ =` on an error return is a BLOCKER** — handle, wrap, or return.
  The no-swallow rule (`standards/error-handling.md`) applies verbatim.
- Sentinel (`var ErrNotFound = errors.New(…)`) or typed errors for
  anything callers branch on. `panic` only for broken invariants.

## Testing
- Stdlib `testing` preferred; `testify` permitted for assertion ergonomics,
  not suite frameworks.
- Table-driven tests are the default shape: named cases, `t.Run` subtests.
- `go test -race ./...` in CI, always — races caught here cost minutes.
- Fuzz targets for parsers and anything decoding untrusted bytes.

## Dependencies
- Minimal by culture: stdlib covers HTTP, JSON, crypto — justify every
  import that duplicates it.
- `govulncheck ./...` in CI; findings block merge.
- No `replace` directives committed to main branches.

## Review checklist add-ons
- [ ] Every error handled, wrapped with `%w`, or returned — none dropped
- [ ] Every goroutine has a documented owner and exit path
- [ ] `context.Context` first-param and propagated end to end
- [ ] Interfaces consumer-defined, small, and actually needed
- [ ] `go test -race` and `govulncheck` clean in CI
