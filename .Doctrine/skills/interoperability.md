# Skill: Interoperability

**Scope.** Everything that crosses a boundary: HTTP/RPC APIs, wire formats,
schema contracts, webhooks, plugins, and cross-language borders
(Rust↔Python via PyO3/maturin, C FFI, WASM).

## Principles
- Contract first, both sides second. The schema/IDL (OpenAPI, proto, JSON
  Schema) is committed and versioned; implementations conform to it.
- Postel with teeth: tolerant in what you accept (ignore unknown fields),
  strict in what you emit (never send undocumented shapes).
- Compatibility is a promise with a definition: write down exactly what may
  change without a major version.
- The two sides never deploy atomically. Design every change to survive a
  window where old and new coexist.

## Defaults
- Additive evolution: new optional fields > changed fields > removed fields
  (removal = major + deprecation period).
- Distinguish absent vs null vs default explicitly in the contract; test
  the distinction round-trips.
- Errors are data: stable machine `code`, human `message`, structured
  `details` — mapped across the boundary in both directions.
- Timeouts, retry policy, and idempotency semantics documented per
  operation; webhooks carry IDs and are consumer-deduplicated.

## FFI specifics
- No panic/exception unwinds across the border — catch at the edge, convert
  to the boundary's error type.
- Ownership and lifetime of every crossing pointer/buffer documented at the
  declaration; conversions are total or explicitly fallible.
- Version the binding layer with the underlying library; test the binding
  from the *foreign* side (Python tests for a PyO3 crate).
- Keep the unsafe surface thin: one audited crossing module, safe wrappers
  everywhere else.

## Do
- Ship round-trip tests with real captured payloads, including a "payload
  from the future" (extra unknown fields).
- Generate types from the contract where the ecosystem allows; drift
  between contract and code is a CI failure.
- Document one canonical example request/response per operation — tested.

## Don't
- Don't break a published contract and call it a fix.
- Don't leak internal enums/IDs/error strings into a public contract.
- Don't parse with regex what has a spec and a parser.
- Don't assume field ordering, map ordering, or float bit-exactness across
  languages.

## Review checklist
- [ ] Contract artifact committed; examples round-trip in tests
- [ ] Unknown-field tolerance tested; emit-strictness tested
- [ ] Error mapping both directions; codes stable
- [ ] FFI: no unwinding, ownership documented, foreign-side tests exist
- [ ] Compatibility stance written; breaking changes flagged to Architect

## Common failure modes
Contract-by-vibes drifting from code; v2 that was really v1.1; enum added,
old clients crash; a PyO3 boundary where a Rust panic aborts Python.
