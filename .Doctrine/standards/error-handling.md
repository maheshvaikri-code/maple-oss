# Standard: Error Handling

## The taxonomy (classify first, handle second)
1. **Caller errors** — bad input, wrong state. Reject with a precise,
   actionable message. Never retried, never our incident.
2. **Environment errors** — network, disk, dependency down. Expected in
   production: timeout, mapped, maybe retried (with backoff + jitter +
   budget), surfaced with context.
3. **Programmer errors** — broken invariants, impossible states. Fail fast
   and loud (panic/assert/raise); these are bugs to fix, not conditions to
   handle.

Misclassification is the root of most bad error code: retrying caller
errors, "handling" programmer errors, crashing on environment errors.

## Rules
- **No swallowed errors.** Every error is handled, wrapped-with-context, or
  propagated. `catch {}` / `except: pass` / `let _ =` on a `Result` are
  review blockers.
- Context accumulates on the way up: each layer adds what it knows
  (operation, identifiers) — `anyhow::Context` in Rust bins,
  `raise NewError(...) from err` in Python. Never lose the cause chain.
- Handle once: the layer that can act (retry, degrade, report to user)
  handles and logs; layers below propagate silently. One failure, one log
  entry — not a stack-shaped echo.
- Messages carry what/why/next-step for their audience: end-user messages
  are generic + actionable; log entries are specific + correlated.
  Neither contains secrets.
- Failure paths are tested paths: every declared error condition has a test
  provoking it (see `skills/testing.md`).
- Cleanup is guaranteed: RAII/Drop, context managers, `finally` — resources
  survive the error path.

## Rust specifics
- Libraries: `thiserror` enums, variants meaningful to callers,
  `#[non_exhaustive]` if growth is plausible. Binaries: `anyhow` + context.
- `?` everywhere fallible; no `unwrap`/`expect` outside tests/startup
  (see coding standards). Panics = broken invariants only.

## Python specifics
- Package-rooted exception hierarchy (`class QumbaError(Exception)`), typed
  subclasses per taxonomy branch callers can catch distinctly.
- Catch the narrowest type that lets you act; bare `except:` never;
  `except Exception` only at process edges, logged with traceback.

## Checklist
- [ ] Each new error path classified (caller/environment/programmer)
- [ ] Cause chains preserved; context added per layer
- [ ] Logged exactly once, at the handling layer
- [ ] User-facing text actionable; nothing secret in any message
- [ ] Tests provoke every declared failure
