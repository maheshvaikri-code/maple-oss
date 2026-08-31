# ADR-061: Composable Bounded Sub-Workflows

- Status: Accepted
- Date: 2026-08-26
- Decision owners: Chief Architect, Backend, Security, QA

## Context

MAPLE's workflow runtime already supports validated graphs, checkpoints,
interruption, retries, fan-out, and crash-window replay, but a workflow could
not reuse another workflow as a graph node. Flattening every graph makes
ownership and restart boundaries harder to reason about, while passing an
arbitrary callback would leave child state and pause behavior undefined.

## Decision

Add `Workflow.add_subworkflow()` as a normal parent node with two optional,
explicit state maps:

- `input_map` maps parent keys to child keys; omitted means copy the parent
  state with unchanged keys.
- `output_map` maps child keys to parent keys; omitted means copy the completed
  child state with unchanged keys.

The child workflow owns its configured checkpoint store and executes through
the existing `run`, `resume`, and `recover` contracts. A deterministic,
hash-derived child run ID is based on the parent workflow/run, parent
execution key, child workflow, and parent retry count. If the child is
interrupted, the parent persists a bounded `WorkflowPause` payload containing
the child identity and payload; resuming the parent resumes the same child.
Completed children are reused when parent checkpoint or journal recovery
re-enters the node. Missing mapped keys, duplicate map destinations, malformed
child results, and child store errors become typed parent-node failures.

All state still crosses the existing JSON and byte limits. Mapping tables are
limited to 256 entries and state keys to 256 characters. Child handlers remain
trusted local code; external effects are still at-least-once and require
idempotent handlers. This decision does not add distributed scheduling,
remote routing, tenancy, or exactly-once effects.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Explicit child workflow node (chosen) | Reuses checkpoint, pause, retry, and replay contracts; state boundary is visible | Child stores remain separately configured; nested runs need inspection through host stores | — |
| Flatten child graphs into the parent | One checkpoint and one run identifier | Loses child ownership, makes composition invasive, and changes existing graph semantics | Does not preserve reusable child lifecycle boundaries |
| Arbitrary callback/manager node | Small initial API | No durable child identity, mapping contract, or defined pause/recovery semantics | Fails the runtime correctness boundary |
| Remote workflow coordinator | Fleet routing and scheduling could be added later | Requires identity, TLS, tenancy, deployment, and side-effect contracts | Out of local-first scope and requires a separate approved contract |

## Consequences

- Positive: local workflows can compose reusable bounded workflows while
  preserving explicit context filtering, deterministic recovery, and existing
  failure semantics.
- Negative / debt accepted: child checkpoint stores are not automatically
  colocated with a parent override, and nested runs are not a distributed
  scheduler. Child side effects can still repeat across crash windows.
- Invalidation triggers: a hosted scheduler, cross-process child-store
  ownership, or a requirement for exactly-once side effects reopens this ADR
  before those capabilities are added.
