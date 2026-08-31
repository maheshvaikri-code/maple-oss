# ADR-018: Loopback workflow run server

**Date:** 2026-08-24  Â· **Status:** accepted  Â· **Deciders:** Chief Architect

## Context

MAPLE has a native workflow runtime and durable local checkpoints, but no
small process boundary for local tools, notebooks, or a future website to
start, resume, and inspect a registered workflow. The package already supports
Python 3.8+ and prefers a dependency-light core; adding a web framework before
the HTTP contract and security posture are stable would expand the release
surface prematurely.

## Decision

We will add a stdlib-only `WorkflowRegistry` and `RunServer` for local
development and controlled host processes.

- The server binds to loopback by default and rejects non-loopback hosts unless
  a future explicit remote/authentication decision changes the contract.
- `GET /healthz`, `POST /v1/workflows/{workflow}/runs`,
  `GET /v1/workflows/{workflow}/runs/{run_id}`, and
  `POST /v1/workflows/{workflow}/runs/{run_id}/resume` are the initial
  versioned routes.
- Request bodies, response bodies, workflow names, run IDs, and JSON values are
  bounded; errors use the existing stable `errorType` shape wrapped in an HTTP
  error object. Workflow execution remains the existing trusted local handler
  boundary.
- The server owns its thread and supports deterministic shutdown. It does not
  claim authentication, multi-tenant authorization, TLS, hard sandboxing,
  remote deployment, streaming transport, or arbitrary workflow registration
  over HTTP.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Stdlib loopback server (chosen) | Zero new dependency; easy local smoke tests; explicit small contract | Limited production ergonomics; no auth/TLS | Fits local-first parity and keeps deployment choices open |
| Add FastAPI/ASGI server | Better routing, validation, and production integration | New runtime dependency, server lifecycle and audit surface | Requires a dependency and deployment decision outside this slice |
| Expose workflow calls only as Python APIs | No HTTP attack surface | Cannot serve local tools, notebooks, or a future UI process | Does not close the run-server parity gap |

## Consequences

- Positive: a host can run and inspect registered workflows over a documented,
  bounded local HTTP contract and shut the server down cleanly.
- Negative / debt accepted: loopback-only means this is not a public API
  service; authentication, TLS, remote clients, SSE/WebSocket streaming, and
  production process supervision remain follow-on work.
- Invalidation triggers: reopen when remote access, multi-tenant auth,
  browser-origin access, or production deployment becomes a release
  requirement.
