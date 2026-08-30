# Standard: API Design

Applies to HTTP/RPC services **and** library public surfaces — anything
with consumers you can't refactor.

## Universal
- Design for the caller you'll never meet: guessable names, consistent
  vocabulary, one obvious way per operation.
- Small surface, deliberate growth: everything public is a promise under
  semver; when in doubt, keep it private — exposing later is free,
  hiding later is a major version.
- Errors are part of the contract: enumerated, typed, documented alongside
  the operation that raises them.
- Every operation documents: inputs (with constraints), outputs, errors,
  idempotency, and one runnable example.

## HTTP services
- Nouns in paths (`/orders/{id}`), verbs in methods; plural, kebab-case
  paths; camelCase or snake_case JSON — pick one per product, forever.
- Status codes mean things: 200/201/204 success shapes · 400 malformed ·
  401 unauthenticated · 403 unauthorized · 404 absent (or 403-masked —
  decide policy once) · 409 conflict · 422 semantic rejection · 429 with
  `Retry-After` · 5xx = our fault, never for caller errors.
- Error body, uniform:
  `{"error": {"code": "stable_machine_string", "message": "...", "details": {...}}}`
- List endpoints: paginated from day one (cursor preferred), `limit` capped
  server-side, filter/sort params documented and bounded.
- Versioning: additive within a version; breaking = new major
  (`/v2/`), with deprecation notes and overlap period.
- Idempotency: PUT/DELETE naturally; unsafe POSTs accept an
  `Idempotency-Key` where retries are plausible.

## Library APIs (Rust / Python)
- The README quickstart is the API's thesis: if it needs eight imports and
  four concepts for hello-world, redesign.
- Rust: seal what shouldn't be implemented externally · `#[non_exhaustive]`
  on growing enums/structs · builders for >3-arg constructors · take
  `impl Into<...>`/borrows generously, return owned/concrete conservatively
  · re-export the public story at crate root.
- Python: `__all__` is the contract · keyword-only args for options ·
  accept iterables, return concrete types · underscore = private, honored
  by consumers and enforced by review.
- Deprecate loudly, remove slowly: warn a full minor cycle (docs + runtime
  warning) before deletion in a major.

## Checklist
- [ ] Names consistent with the product's existing vocabulary
- [ ] Errors enumerated + typed + documented per operation
- [ ] Pagination/bounds on anything list-shaped
- [ ] Compatibility stance written; breaking changes routed to Architect
- [ ] One runnable, tested example per public operation
