# Implementation Plan - MAPLE Agent Runtime and Release Readiness

**Brief:** [maple-agent-runtime-release.md](../briefs/maple-agent-runtime-release.md)  · **Design/ADRs:** [ADR-001](../adr/001-maple-workflow-runtime.md)  · **Class:** L

## Slices

| # | Slice | Role | Files touched | Proven by (tests) | Status |
|---|-------|------|---------------|-------------------|--------|
| 0 | Baseline and release contract | Chief Architect / DevOps | `docs/`, `pyproject.toml`, CI/tooling | Existing suite, package metadata inspection | done: brief/ADR/plan filed; branch `feat/maple-agent-runtime` |
| 1 | Typed workflow graph, checkpoint store, stable run IDs, interruption, resume | Backend Engineer | `maple/autonomy/workflow.py`, autonomy exports, workflow tests, API docs | Happy path, invalid graph, malformed checkpoint, interruption/resume, duplicate run IDs, state bounds | done: commit `d75c58c`; focused `33 passed`; autonomy `96 passed` |
| 2 | Typed tool inputs/outputs and guardrail boundary | ML Engineer / Backend Engineer | autonomy tools/contracts, LLM types, tests, API docs | Schema failures, guardrail rejection/failure, structured output, compatibility | done: commit `fed365f`; focused `34 passed`; autonomy `107 passed` |
| 3 | Safe bounded execution boundary | Security Reviewer / Backend Engineer | execution module, tool integration, tests, threat documentation | No in-process untrusted execution, timeout, size, cancellation, approval, cleanup | done: commit `9628e7d`; focused `27 passed`; autonomy `114 passed` |
| 4 | Retrieval/data primitives | ML Engineer / Data Engineer | retrieval module, adapters, fixtures, tests, docs | Ingestion, chunking, source refs, empty/large/malformed input, retrieval fixture metrics | done: commit `953f601`; focused `20 passed`; autonomy `120 passed` |
| 5 | Workflow/model/tool event streaming and observability | Backend Engineer / Observability | events, traces, correlation IDs, redaction, tests, docs | Event ordering, bounded buffers, cancellation, redaction, failure telemetry | done: commit `5be8115`; focused `11 passed`; autonomy `125 passed` |
| 6 | Agent evaluation harness and model/provider capabilities | ML Engineer / Interop Engineer | eval fixtures, provider contracts, tests, docs | Golden set, schema/trajectory checks, provider fallback, pinned model metadata | done: commits `4ead28d` + `3a91c6d`; focused `7 passed`; LLM/autonomy `160 passed` |
| 7 | Interoperability and developer experience | Interop / DevOps / Tech Writer | adapters, examples, CLI/task runner, API docs | Round-trip payloads, unknown fields, quickstart, one-command checks | done: commit `bf1614b`; focused `5 passed`; combined LLM/autonomy/CLI `165 passed` |
| 8 | Release hardening | Security / QA / Release Manager | CI, changelog, release artifacts, package metadata | Full test/lint/type/audit/build matrix and clean-tree checklist | in progress: metadata-clean build, isolated dependency gate, wheel smoke, CI preflight, and focused gates pass; full-suite, repository lint, and independent-review gates remain open |
| 9 | Live MCP tool discovery and bounded JSON-RPC transport | Chief Architect / Interop / Backend / Security | `docs/adr/007-*`, MCP adapter/autonomy modules, MCP tests, README, changelog | Live descriptor conversion, pagination, malformed/duplicate rejection, RPC errors, initialization/session headers, focused lint | done: focused MCP suite `22 passed`; changed-surface Ruff/Flake8 and compile pass |
| 10 | Bounded artifact store and code-block extraction | Chief Architect / Security / Backend | `docs/adr/008-*`, autonomy artifact module, artifact tests, README, changelog | Fence parsing, malformed/oversized input, content-addressed identity, file persistence, hash corruption, quota failures, no execution | done: artifact suite `5 passed`; new module Ruff/Flake8 and compile pass |
| 11 | Provider-agnostic LLM stream contract | Chief Architect / ML Engineer / Backend | `docs/adr/009-*`, LLM provider base, stream tests, README, changelog | Text chunk bounds, tool-call deltas, finish event, completion error propagation, async iterator contract | done: stream suite `2 passed`; changed provider Ruff/Flake8 and compile pass |
| 12 | Provider-native LLM streaming adapters | ML Engineer / Backend | `docs/adr/010-*`, OpenAI/Anthropic providers, native stream tests, README, changelog | Native provider events, bounded text, tool-call fragments, typed request errors, compatibility fallback | done: native stream suite `5 passed`; changed provider Ruff/Flake8 and compile pass |
| 13 | Bounded async tool fan-out | Backend / ML Engineer | `docs/adr/011-*`, async ReAct loop, agent regression tests, README, changelog | Concurrent independent handlers, per-step cap, deterministic result order, worker error isolation | done: agent suite `15 passed`; changed agent Ruff/Flake8 and compile pass |
| 14 | Fail-closed autonomous approval | Security Reviewer / Backend | `docs/adr/012-*`, autonomous tool boundary, approval regression, README, changelog | Missing callback denial, callback exception denial, explicit denial, handler side-effect absence | done: approval regression included in `16` agent tests; changed agent Ruff/Flake8 and compile pass |
| 15 | Bounded checkpointed workflow fan-out/fan-in | Chief Architect / Backend / Security | `docs/adr/013-*`, workflow runtime/tests, API docs, README, changelog | Concurrent independent branches, bounded workers, deterministic merge, collision rejection, pause/resume group boundary | done: commit `7f7afb0`; focused workflow `13 passed`; combined feature gate `187 passed` |
| 16 | Durable approval requests and one-time decisions | Chief Architect / Backend / Security | `docs/adr/014-*`, approval stores/agent boundary/tests, API docs, README, changelog | Bounded JSON request, file restart persistence, CAS decision, fail-closed pending state, one-time consume, handler side-effect protection | done: commit `84830a7`; approval/agent `21 passed`; combined feature gate `192 passed` |
| 17 | Dependency-free vector retrieval seam | ML Engineer / Backend | `docs/adr/015-*`, retrieval index/tests, API docs, README, changelog | Supplied embedding contract, finite/dimension/zero validation, one-vector-per-chunk atomic ingestion, deterministic cosine ranking, quotas, source citations | done: commit `2623d74`; focused retrieval `10 passed`; combined feature gate `196 passed` |
| 18 | Bounded workflow checkpoint history | Backend / ML Engineer | `docs/adr/016-*`, workflow history decorator/tests, API docs, README, changelog | Immutable version snapshots, bounded retention, deterministic history limits, underlying store recovery unchanged, no replay claim | done: pending commit; focused workflow `16 passed`; combined feature gate `199 passed` |

## Threat sketch

Assets touched: workflow state, tool arguments, model outputs, checkpoint
metadata, source documents, credentials used by adapters, and release
artifacts. Entry points / untrusted inputs: workflow definitions, node output,
resume payloads, tool arguments, retrieved documents, model responses, MCP
metadata, and filesystem/database configuration. Worst plausible abuse:
crafted checkpoint or tool input causes code execution, path traversal, state
corruption, secret leakage, unbounded memory/CPU use, or execution of a
privileged action without approval.

## Risks and rollback points

- Public API drift → keep new runtime in a separate module and document it
  before export → remove the module/export without changing existing APIs.
- Unsafe checkpoint restore → JSON-compatible typed snapshots only; reject
  malformed or oversized input → disable checkpoint persistence while
  preserving in-process execution.
- State-store backend differences → start with an in-memory reference
  store and contract tests → revert the adapter, not the workflow core.
- Scope expansion → append to Deferred and open a new brief amendment →
  keep the current slice green.
- Existing lint debt → record baseline and enforce no new violations on
  changed files → schedule repository-wide cleanup as its own slice.

## Deviation log

- 2026-08-24: Graphify was unavailable (`graphify-out/graph.json` absent and
  the command unavailable); structure analysis used targeted source inspection
  and is marked implementation-derived.

## Status snapshot

Done (with evidence): G0 brief, G1 ADR, G2 plan, and seventeen committed G3
feature slices through dependency-free vector retrieval, including MCP
interoperability, bounded artifacts, native LLM streaming, deterministic async
tool result ordering, durable approval, and workflow fan-out/fan-in; slice
review/QA artifacts are filed. Slice 18 bounded workflow history is implemented
and verified in the working tree and awaits commit.
Release hardening remains in progress.
Focused feature gates (199 LLM/autonomy/CLI tests, including 22 MCP, 5
artifact, 5 stream, async tool fan-out, durable approval, workflow fan-out,
vector retrieval, and checkpoint-history regressions),
compile, changed-surface Ruff/Flake8, metadata-clean wheel/sdist builds, Twine
checks, a clean-venv wheel doctor smoke pass, and a fresh `.[dev,security]`
environment with `pip check` reporting no broken requirements all pass.
The full repository regression is not complete: the latest bounded attempt
reported `1049 passed, 8 warnings in 839.17s` before interruption in the
remaining Doctrine gold cases. Fresh-repository profiling shows individual
Git commands taking roughly 5–15 seconds on this Windows environment, with
the slowest gold cases at 166.96s, 159.74s, 115.61s, and 56.04s. No assertion
failure was reported. The shared interpreter still has unrelated `pip check`
conflicts, but the isolated dependency gate is clean. Repository-wide Ruff
debt and unavailable independent fresh-context verification remain open.
External publishing, cloud selection, and website changes remain explicitly out
of scope until human approval.
