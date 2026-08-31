# Language Profile: .NET (C#)

**Applies when.** Any solution targeting .NET 8+ LTS with C# 12 or later.

## Toolchain
- SDK pinned in `global.json` (`rollForward: latestPatch`); CI restores
  and builds with the pinned SDK, never machine defaults.
- Central package management: versions live in `Directory.Packages.props`;
  project files reference packages unversioned.
- Shared settings in `Directory.Build.props` — one place, not per project.

## Format & lint
- `dotnet format --verify-no-changes` in CI; `.editorconfig` committed.
- Analyzers as errors: `TreatWarningsAsErrors=true` ·
  `AnalysisLevel=latest` · `EnforceCodeStyleInBuild=true`.
- **`<Nullable>enable</Nullable>` everywhere — non-negotiable.** The `!`
  null-forgiving operator requires an inline justification comment.

## Types & idioms
- Records for domain data; mutation via `with` expressions, not setters.
- Pattern matching (`switch` expressions, property patterns) over
  type-check-and-cast chains.
- Async all the way down: **sync-over-async (`.Result`, `.Wait()`) is a
  BLOCKER**; every async method accepts and forwards a `CancellationToken`.
- `IReadOnlyList<T>`/`IEnumerable<T>` on public surfaces; concrete
  collections internally.
- Constructor injection via `IServiceCollection`; no static service access.
- Config via `IOptions<T>` validated at startup — fail fast, name the key.

## Errors
- Throw specific exception types carrying context; wrap at layer
  boundaries with the inner exception preserved.
- **`catch { }` and catch-log-continue are BLOCKERs**
  (`standards/error-handling.md`); catch narrowly, only where you can act.
- `ILogger<T>` with message templates (`"Order {OrderId} failed"`), never
  interpolated strings into the logger.

## Testing
- xUnit + FluentAssertions; `[Theory]`/`[MemberData]` for table-driven cases.
- FsCheck/CsCheck where the logic has algebra: roundtrips, idempotence.
- Testcontainers for real stores; `WebApplicationFactory` for in-process
  API tests over mocked HTTP pipelines.

## Dependencies
- NuGet audit in CI (`dotnet list package --vulnerable`); lock files
  (`packages.lock.json`) committed and restored with `--locked-mode`.
- Prefer the BCL (`System.Text.Json`, built-in DI); justify every package
  that duplicates the runtime.

## Review checklist add-ons
- [ ] No sync-over-async anywhere; `CancellationToken` propagated end to end
- [ ] Nullable annotations honest — no `!` without a justification comment
- [ ] Exceptions specific, inner exception preserved, nothing swallowed
- [ ] Log calls use message templates with named properties
- [ ] New packages: central version, lock file updated, audit clean
