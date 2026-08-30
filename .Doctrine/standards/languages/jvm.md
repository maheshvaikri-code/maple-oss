# Language Profile: JVM (Java / Kotlin)

**Applies when.** Any Gradle or Maven module — Java 21+ LTS or Kotlin 2.x.

## Toolchain
- Java pinned to current LTS via Gradle toolchains (or Maven `release`);
  the committed wrapper (`gradlew`/`mvnw`) is the only way anyone builds.
- Gradle: version catalog (`libs.versions.toml`) is the single source of
  dependency versions; no versions inline in build scripts.

## Format & lint
- Spotless wired into the build: `google-java-format` for Java, `ktlint`
  for Kotlin. `spotlessCheck` fails CI; `spotlessApply` fixes locally.
- Error Prone on Java compilation; Kotlin compiles with `-Werror`.

## Types & idioms
- Domain modeling: records + sealed interfaces (Java), data classes +
  sealed hierarchies (Kotlin). Exhaustive `switch`/`when` over sealed
  types — no `default`/`else` arm hiding future variants.
- Null safety: Kotlin's types, or JSpecify (`@NullMarked`) in Java;
  `Optional` only as a boundary return type — never in fields or params.
- Immutability by default: `final`/`val`, `List.copyOf`; defensive copies
  where mutables cross a boundary.
- Virtual threads for I/O-bound work; structured concurrency
  (`StructuredTaskScope` / coroutine scopes) — no orphaned tasks.
- Constructor injection only; no field injection, no service locators.

## Errors
- Wrap checked exceptions into domain exceptions at layer boundaries,
  always chaining the cause: `throw new PaymentFailed(msg, e)`.
- **catch-log-continue is a BLOCKER** — handle, wrap-with-cause, or
  rethrow (`standards/error-handling.md`); a lost cause chain is a
  swallowed error.
- Kotlin: no `runCatching` that drops the throwable; `Result` only where
  the caller genuinely branches on it.

## Testing
- JUnit 5 + AssertJ (`assertThat`); parameterized tests
  (`@ParameterizedTest` + method sources) for table-shaped cases.
- jqwik (Java) / kotest-property (Kotlin) where the logic has algebra:
  roundtrips, ordering, idempotence.
- Testcontainers for anything touching a real store or broker — no
  in-memory fake pretending to be Postgres.

## Dependencies
- OWASP dependency-check in CI; findings triaged, never silently suppressed.
- No fat "utils" framework for one function; each broad import justified.
- BOMs for framework families; one version per family.

## Review checklist add-ons
- [ ] Sealed types matched exhaustively — no swallowing `else`/`default`
- [ ] Every wrapped exception carries its cause; nothing logged-and-dropped
- [ ] Nullability explicit (Kotlin types / JSpecify); no `Optional` fields
- [ ] Every concurrent task has a scope and a cancellation path
- [ ] New deps: in the version catalog, scanned, and justified
