# Implementation Plan — Fresh-Context Verifier Preset

**Gate:** G2 (Planning) · **Class:** M · **Role:** Chief Architect → Backend Engineer

## Source / contract

Delivers **enhancement ask #3** from `.Doctrine/integrations/maple.md`:

> A **fresh-context role preset**: broker-enforced per-agent sender
> allowlist + artifact-ref-only payload policy — separation of duties as a
> runtime guarantee instead of a convention.

The integration doc is the frozen contract (G0/G1 equivalent). Two hard
boundaries it sets, which this feature respects:

- **MAPLE routes; gates decide.** This adds *transport-level* enforcement,
  not a review verdict. Gate decisions still live in `docs/` artifacts.
- Separation of duties was already a *convention* (link identification, the
  `03-parallel-execution.md` fan-out). This makes it a *runtime guarantee*.

## What ships

A new opt-in security primitive plus its wiring:

1. `maple/security/separation.py` — the policy and preset:
   - `ArtifactRef(path, sha256)` — a content-pinned artifact pointer with
     `of(path, content)` / `for_file(path)` constructors and `to_dict()`.
   - `is_artifact_ref(value)` — validator for a `{path, sha256}` dict.
   - `SeparationOfDutiesPolicy` — holds a per-agent `sender_allowlist`
     (closed by default) and the `guarded_types` whose payloads must be
     artifact-ref-only; `authorize_send(message) -> Result[None, Err]`.
   - `fresh_context_verifier_preset(orchestrator, builders, verifiers)` —
     builds the doctrine wiring: orchestrator → everyone; each builder and
     verifier → orchestrator only (a verifier can never route back to the
     author it judges).
2. `SecurityConfig.separation_policy: Optional[Any] = None` (new optional
   field, end of dataclass — positional API unchanged).
3. `MessageBroker.send()` enforces the policy when present: on violation it
   raises `SecurityError`, so `Agent.send()` returns `Result.err(...)` —
   consistent with the existing link/authz failure path.
4. Exports from `maple/security/__init__.py` (`SEPARATION_AVAILABLE` flag,
   matching the module's defensive-import style). **Not** re-exported at the
   `maple` top level, to avoid making `import maple` pull in the security
   package (and its optional-dep warning) — users opt in via
   `from maple.security import ...`.

## Two runtime guarantees (and their limits — stated honestly)

- **Sender allowlist** — deterministic and airtight: an agent may send only
  to receivers on its allowlist; an unlisted agent may send to no one
  (`default_allow_unlisted=False`). This is the core separation-of-duties
  guarantee.
- **Artifact-ref-only payload** — for `guarded_types` (default
  `WORK.PACKAGE`, `GATE.RESULT`): the payload must carry ≥1 well-formed
  artifact ref, and no string field may exceed `max_prose_chars` (default
  512). The prose ceiling is a *tunable heuristic*, not a proof — it stops a
  builder from smuggling narrative/reasoning into a verifier's input, which
  is the stated intent ("a builder's reasoning must never travel to a
  verifier — the verifier reads the artifact fresh").

## Files touched

| File | Change |
|------|--------|
| `maple/security/separation.py` | new module |
| `maple/agent/config.py` | +1 optional field on `SecurityConfig` |
| `maple/broker/broker.py` | read policy in `__init__`, enforce in `send()` |
| `maple/security/__init__.py` | export new symbols + `SEPARATION_AVAILABLE` |
| `tests/security/test_separation.py` | new unit + broker-integration tests |
| `CHANGELOG.md`, `docs/plans|reviews|qa/*` | artifacts |

## Test plan (G5)

- `ArtifactRef`: `of`/`for_file`/`to_dict`; rejects bad sha length, non-hex.
- `is_artifact_ref`: valid / missing key / extra key / non-dict / bad sha.
- `SeparationOfDutiesPolicy.authorize_send`: allowed pass; disallowed
  receiver err; unlisted sender err (closed default); `default_allow_unlisted`
  path; guarded type missing ref err; prose-too-long err; non-guarded type
  bypasses payload check; missing sender err.
- `fresh_context_verifier_preset`: orchestrator→builder/verifier ok;
  builder→verifier and builder→builder denied; verifier→builder denied;
  worker→orchestrator ok.
- Broker integration: policy attached via `SecurityConfig`; `verifier→builder`
  `send()` raises `SecurityError`; `verifier→orchestrator` with a valid ref
  is accepted (returns message-id string). Broker singleton reset per test.

## Out of scope (follow-ups, not this change)

- Marking ask #3 "delivered" in `.Doctrine/integrations/maple.md` — editing
  `.Doctrine/` needs human sign-off (root doctrine §12).
- Asks #1, #2, #4, #5 (handler-key normalization, delivery receipts,
  first-class WORK.PACKAGE/GATE.RESULT schemas, `tokens` resource type).
- Publishing / version bump / PyPI (§5 — human-gated).
