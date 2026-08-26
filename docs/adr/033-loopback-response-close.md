# ADR-033: Flush and close bounded loopback responses

**Date:** 2026-08-26  
**Status:** accepted  
**Deciders:** Backend Engineer / QA

## Context

The dependency-free loopback `RunServer` already advertised
`Connection: close`, but its handler did not explicitly mark the request for
connection closure or flush the response body. On Windows, the oversized-body
413 path could therefore race the client and surface as
`ConnectionAbortedError` during the full tracked suite even though the server
had constructed the correct response.

## Decision

After writing any bounded JSON response, explicitly set
`BaseHTTPRequestHandler.close_connection = True` and flush `wfile`. This keeps
the existing one-response-per-connection contract and makes the bounded error
response visible before the socket is released.

## Consequences

- Loopback success and error responses close deterministically across the local
  Windows test boundary.
- No protocol, route, payload, dependency, or external-hosting behavior is
  broadened.
- The existing server tests remain the regression contract for health, run,
  resume, malformed JSON, unknown workflow, and oversized-body responses.

