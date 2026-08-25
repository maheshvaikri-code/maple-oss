# ADR-011: Bounded asynchronous tool fan-out

**Status:** Accepted
**Date:** 2026-08-24

## Context

The asynchronous ReAct entry point is the natural surface for modern agent
framework behavior such as parallel function calls. MAPLE already limits the
number of tool calls per reasoning step, but its async loop executed those
calls one at a time. That made independent tool calls pay the sum of their
latencies and contradicted the loop's documented capability.

## Decision

The async ReAct loop now submits the current step's bounded tool-call list to
the event loop's default executor and awaits all results with
`asyncio.gather(..., return_exceptions=True)`.

- The existing `max_tool_calls_per_step` is the concurrency cap.
- Results are zipped back to the original tool-call list, so the next LLM turn
  sees deterministic tool-message order even if handlers finish differently.
- A worker exception becomes a typed `TOOL_EXECUTION_ERROR` tool result and does
  not discard successful sibling results.
- The synchronous ReAct path remains unchanged.

## Alternatives considered

1. Keep sequential execution. This is simple but leaves independent tools
   unnecessarily serialized.
2. Add a new async tool protocol. This would force existing synchronous tool
   handlers to migrate and expand the public surface.
3. Create a dedicated executor per agent. This adds lifecycle and capacity
   management without improving the bounded contract for this slice.

## Consequences

Positive:

- Independent synchronous tool handlers can overlap during an async agent turn
  without a new dependency.
- Tool-call order remains stable for model context, traces, and tests.
- One failed worker is represented as data while sibling results are retained.

Accepted limitations:

- Approval callbacks and synchronous handlers run in executor threads and must
  be thread-safe when multiple approved calls are present.
- This is concurrent local execution, not a hard isolation boundary; the
  trusted-local execution limitation in ADR-002 still applies.
- Tool quotas and cancellation beyond the per-step cap remain future work.
