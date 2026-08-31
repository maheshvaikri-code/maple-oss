# ADR-156: Restricted host-owned HTTP transports

**Status:** Accepted for Slice 212 implementation
**Date:** 2026-08-29
**Deciders:** Chief Architect / Backend / Security / QA / Release

## Context

MAPLE's local event exporter, event batch sender, approval notifier,
human-input notifier, and workflow client are dependency-free HTTP boundaries.
Their constructors already bound endpoints to HTTP(S), rejected credentials,
and required HTTPS for authenticated non-loopback delivery. The request path
still delegated to the broad stdlib `urlopen()` opener, so permitted handlers
and redirect behavior were not owned by MAPLE. Bandit B310 reported five
medium findings at those call sites.

## Decision

Add one private `maple.autonomy.http_transport` helper. It builds a stdlib
`OpenerDirector` with proxy, HTTP, HTTPS, error, and a constrained redirect
handler only. It rejects non-HTTP(S) request URLs, URL credentials, malformed
targets, cross-origin redirects, and HTTPS-to-HTTP downgrade redirects. The
five call sites use the helper; their existing exception mapping, bounds,
headers, and result behavior remain unchanged.

## Alternatives considered

| Option | Pros | Cons | Why not |
| --- | --- | --- | --- |
| Private HTTP(S)-only opener with same-origin redirects (chosen) | Keeps zero runtime dependencies, centralizes the trust boundary, preserves proxy support, and removes the repeated audit finding | Conservative redirect policy can reject cross-origin delivery workflows | Correct tradeoff for bearer-bearing, bounded host callbacks |
| Add targeted `# nosec B310` comments at five call sites | Small diff and no transport change | Leaves opener and redirect policy implicit; duplicates the security argument | Does not make the runtime boundary explicit |
| Replace urllib with a third-party HTTP client | More mature transport features and redirect controls | Adds runtime dependency, policy/licensing/audit surface, and migration cost | Not justified for five bounded one-attempt calls |
| Disable redirects globally without a shared helper | Simple behavior and no redirect leak | Duplicates setup and changes compatibility without one owned validation point | Less reusable and less explicit than the chosen boundary |

## Failure posture and consequences

Malformed or unsafe request/redirect targets raise `URLError`, which existing
callers map to their established transport failure behavior. HTTP status and
response-size handling is unchanged. A cross-origin or downgrade redirect is
treated as a transport failure, and a notification/export operation remains
best-effort or fail-closed exactly as before. The opener has no file/custom
scheme handlers and does not store cookies or requests.

The helper is private; no public API, wire schema, dependency, or version is
changed. Invalidation triggers: a future requirement for cross-origin
redirects, custom TLS/certificate pinning, signed redirects, or hosted
identity reopens this ADR as a separately reviewed transport contract.

## Rollback

Revert the helper and five call-site substitutions, retaining the regression
test only if the older behavior is intentionally re-specified. No persisted
state or migration is involved.
