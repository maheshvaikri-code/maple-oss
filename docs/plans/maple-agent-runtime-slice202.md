# Slice 202 plan — authenticated local session control plane

**Brief:** [maple-agent-runtime-slice202.md](../briefs/maple-agent-runtime-slice202.md)  
**Design/ADR:** [ADR-146](../adr/146-authenticated-local-session-control-plane.md)  
**Class:** L

## Slices

| # | Slice | Role | Files touched | Proven by (tests) | Status |
|---|---|---|---|---|---|
| 1 | Contract and direct-library boundary | Chief Architect / Backend / Interop | `maple/autonomy/sessions.py`, session regressions, ADR/brief | explicit empty create/fork ID rejection, typed IDs/versions, no mutation | complete for direct-library correction (`b6ef016`); transport remains gated |
| 2 | Authenticated server/client transport | Backend / Interop / Security | `maple/autonomy/server.py`, server regressions, exports | authenticated tip/history/fork routes, scope isolation, bounded JSON, 501/503 mapping | gated |
| 3 | Public docs and release evidence | Tech Writer / Code Reviewer / QA / Security / Release | README/API/parity/changelog, review/QA/release artifacts | runnable examples, full suite, static/security checks, package smoke | gated |

## Threat sketch

Assets touched: conversation messages, tool-call metadata, session metadata,
and version history. Entry points / untrusted inputs: bearer tokens, path IDs,
history queries, fork JSON, and custom-store return values. Worst plausible
abuse: an unauthorized caller reads conversation content, a malformed response
exhausts memory/response buffers, or a crafted target/version causes an
ambiguous branch; auth-before-body, coarse bounds, strict identity/JSON checks,
and fail-closed typed errors contain the local blast radius.

## Risks & rollback points

- Risk: exposing full session content through a new scope → mitigation: require
  explicit `session:read`, validate authorization before body/path resource
  access, bound responses, and document host data responsibility → rollback:
  remove the routes while preserving local `SessionStore` history/forking.
- Risk: custom stores violate snapshot invariants → mitigation: strict runtime
  type/identity/JSON validation and generic 5xx mapping → rollback: support
  only built-in stores until a future adapter contract exists.
- Risk: public route change is not desired → mitigation: implementation is
  gated on human approval → rollback: keep this proposal as a deferred parity
  item without changing code.

## Deviation log (append-only, as they happen)

- During the direct-library audit, `create("")` was found to have the same
  truthiness bug as `fork(..., new_session_id="")`: it generated a random ID
  instead of rejecting an explicit invalid value. The correction and regression
  were folded into the same local validation boundary at `b6ef016`; no remote
  transport scope was expanded.

## Status snapshot

G0 brief and proposed G1/G2 design are written. The direct-library contract
correction is complete at `b6ef016`: explicit empty IDs are rejected for both
session creation and forking in both built-in stores before mutation, with
focused regression coverage. The authenticated transport remains paused at
the Doctrine §5 public-API escalation pending human approval. No dependency,
publication, cloud, or website action has been taken for Slice 202.
