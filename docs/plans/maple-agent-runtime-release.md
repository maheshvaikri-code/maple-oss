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
| 8 | Release hardening | Security / QA / Release Manager | CI, changelog, release artifacts, package metadata | Full test/lint/type/audit/build matrix and clean-tree checklist | in progress: metadata-clean build, isolated dependency gate, wheel smoke, and focused gates pass; full-suite, repository lint, and independent-review gates remain open |

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

Done (with evidence): G0 brief, G1 ADR, G2 plan, and all seven G3 feature
slices through `bf1614b`; slice review/QA artifacts are filed. Release
hardening remains in progress. Focused feature gates, compile, changed-surface
Ruff/Flake8, metadata-clean wheel/sdist builds, Twine checks, a clean-venv
wheel doctor smoke pass, and a
fresh `.[dev,security]` environment with `pip check` reporting no broken
requirements all pass.
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
