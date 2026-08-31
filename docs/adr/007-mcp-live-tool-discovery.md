# ADR-007: Bounded live MCP tool discovery

**Date:** 2026-08-24  
**Status:** accepted  
**Deciders:** Chief Architect, Interoperability Engineer

## Context

MAPLE's MCP discovery helper currently returns two hardcoded MAPLE tool
definitions, while `MCPClient.call_mcp_tool` does not cross a transport
boundary. That makes the public MCP bridge look integrated without being able
to consume an external server's live `tools/list` contract. MCP tool metadata
and tool results are untrusted boundary data, so discovery must be bounded,
fail closed, and explicit about approval and naming.

The supported wire contract for this slice is JSON-RPC 2.0 over Streamable
HTTP with JSON or single-response SSE bodies. The client performs the MCP
initialization handshake before normal requests, sends the negotiated
protocol version on later HTTP requests, and accepts unknown response fields.
The transport is dependency-free and injectable so protocol behavior can be
tested without a network or third-party SDK.

## Decision

We will add a bounded `StreamableHTTPTransport` and an injectable transport
contract to `MCPClient`; `MCPClient` will expose `list_mcp_tools` and replace
the placeholder call path with JSON-RPC `tools/call`. `discover_mcp_tools`
will use a supplied live client/transport to convert the server's descriptors
into MAPLE `Tool` objects, rejecting malformed, oversized, duplicate, or
unsafe descriptors before registration. Dynamic tools will be marked
external and approval-required by default. The existing URL-only helper keeps
its two-tool, no-network compatibility fallback for this minor release;
hosts that want live discovery must supply the client/transport explicitly.

Data flow and error paths:

```text
MCP server -> HTTP/SSE JSON-RPC response -> transport bounds/parsing
           -> client RPC/error mapping -> descriptor validation
           -> MAPLE Tool handler -> client tools/call -> Result
                 | malformed/oversized/error: no Tool is returned
```

The transport owns HTTP response bytes, protocol-version, and session-header
state. The client owns request IDs, MCP method/parameter shapes, and mapping
RPC errors to `Result` data. Discovery owns descriptor validation and MAPLE
tool wrappers. No mutable descriptor state is shared with the registry.

## Alternatives considered

| Option | Pros | Cons | Why not |
|--------|------|------|---------|
| Dependency-free injectable transport plus Streamable HTTP implementation (chosen) | Testable, small dependency surface, supports real HTTP, keeps protocol boundary explicit | SSE is supported only until the matching response; no long-lived notification cache | — |
| Adopt an MCP SDK | Faster access to future protocol features and transports | Adds dependency/API lifecycle risk and hides the bounds MAPLE needs at its trust boundary | Dependency policy and publish readiness favor stdlib-first for this slice |
| Keep hardcoded descriptors / add no transport | Preserves old tests and has no network risk | Cannot discover external capabilities and leaves a callable placeholder | Fails the interoperability requirement |

## Consequences

- Positive: live `tools/list` and `tools/call` are real, testable capabilities;
  malformed metadata cannot silently become executable tools; external tools
  carry a conservative approval marker; old URL-only callers remain offline.
- Negative / debt accepted: Streamable HTTP session resumption, server
  notifications, stdio transport, OAuth, and dynamic list-change caching are
  deferred. Each response is capped at 1 MiB, each discovery is capped at 64
  tools, names at 64 MAPLE characters, descriptions at 4 KiB, and schemas at
  64 KiB; larger servers need a future capacity decision.
- Blast radius: only callers that opt into a client/transport cross the
  network. Transport failures return `Result.err` and leave the registry
  unchanged. The compatibility fallback remains local and has no network
  blast radius.
- Invalidation triggers: a published MCP protocol revision changes required
  initialization/session semantics; the 64-tool or 1 MiB bounds reject a
  supported production server; or MAPLE adds a persistent tool-discovery
  cache/notification requirement.
