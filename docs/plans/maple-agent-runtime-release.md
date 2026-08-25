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
| 18 | Bounded workflow checkpoint history | Backend / ML Engineer | `docs/adr/016-*`, workflow history decorator/tests, API docs, README, changelog | Immutable version snapshots, bounded retention, deterministic history limits, underlying store recovery unchanged, no replay claim | done: commit `ef52cfe`; focused workflow `16 passed`; combined feature gate `199 passed` |
| 19 | Bounded conversation session store | Chief Architect / Backend / Security | `docs/adr/017-*`, session stores/tests, autonomy exports, API docs, README, changelog | Validated IDs/roles, bounded messages and metadata, immutable snapshots, atomic file restart persistence, optimistic append conflicts, no replay claim | done: commit `0648efa`; focused sessions `9 passed`; combined feature gate `208 passed` |
| 20 | Loopback workflow run server | Chief Architect / Interop / Backend / Security | `docs/adr/018-*`, server/registry/tests, autonomy exports, API docs, README, changelog | Health, bounded JSON run/resume/inspect routes, stable HTTP errors, workflow reuse, loopback safety, deterministic shutdown | done: commit `7665eaf`; focused server `4 passed`; combined feature gate `212 passed` |
| 21 | Session-aware agent turns | Chief Architect / Backend / Security / ML Engineer | `docs/adr/019-*`, autonomous agent/session tests, API docs, README, changelog | Opt-in sync/async session binding, CAS user turn, user/assistant-only replay, surfaced post-execution persistence errors, no trace/tool replay | done: commit `0b794ba`; focused `7 passed`; combined feature gate `219 passed` |
| 22 | Deterministic retrieval/citation evaluation | ML Engineer / Backend / QA | `docs/adr/020-*`, evaluation module/tests, API docs, README, changelog | Bounded golden queries, lexical/vector hit support, source URI precision/recall/F1, malformed runner isolation, no faithfulness claim | done: commit `a682656`; focused `10 passed`; combined feature gate `225 passed` |
| 23 | Bounded workflow execution journal | Chief Architect / Backend / Security | `docs/adr/021-*`, replay journal/workflow runtime/tests, API docs, README, changelog | Opt-in normalized-output replay, deterministic execution keys/input digests, memory/file bounds, conflict/malformed failure paths, no exactly-once claim | done: commit `1af7f3a`; focused `10 passed`; combined gate `235 passed`; review/QA filed |
| 24 | Deterministic grounded-answer evaluation | ML Engineer / Backend / QA | `docs/adr/022-*`, evaluation module/tests, API docs, README, changelog | Bounded source text, deterministic claim segmentation/token overlap, threshold errors, malformed runner isolation, explicit no semantic-faithfulness claim | done: commit `90203f8`; focused `5 passed`; combined gate `240 passed`; review/QA/build evidence filed |
| 25 | Repository-wide Ruff lint gate closure | DevOps / QA / Code Reviewer | tracked `tests/`, release plan, changelog, review/QA artifacts | `python -m ruff check tools tests`, compile, changed-test regression, focused MAPLE gate | done: commit `cd13435`; Ruff clean; changed surface `621 passed`; focused gate `240 passed`; review/QA filed |
| 26 | Warning-free legacy test gate | QA / Backend / Code Reviewer | `tests/test_basic.py`, `tests/adapters/test_s2_adapter.py`, review/QA artifacts | Targeted pytest, standalone basic runner, Ruff, compile; no targeted warnings | done: commit `948b9ea`; targeted `22 passed`; standalone `6 passed, 0 failed`; review/QA filed |
| 27 | Fail-closed CI quality and security gates | DevOps / QA / Security / Code Reviewer | `.github/workflows/`, CI contract test, release plan, changelog, review/QA artifacts | Workflow YAML parse, gate-semantics contracts, read-only permissions, Ruff, compile, diff check | done: commits `6499244` + `b989a4b`; required checks no longer mask failures; existing Black/isort/mypy/Bandit debt is now release-visible |
| 28 | Repository Black and isort formatter closure | DevOps / QA / Code Reviewer | tracked `maple/` source, release plan, changelog, review/QA artifacts | Black idempotence, isort check, compile, focused runtime regression, fresh build, Twine check | done: commit `76b619a`; 82 source files normalized; focused `240 passed`; fresh wheel/sdist and Twine checks pass; full repository regression remains incomplete |
| 29 | Foundational public-runtime type boundary cleanup | Backend / Security / QA | core Result/message/types, autonomy runtime, MCP discovery, state store, security, core agent, task queue, monitoring, review/QA artifacts | Explicit Python 3.10-target mypy on changed modules, focused regressions, Black/isort/Ruff/compile, aggregate type audit | done: commits `947c8a9`, `8bce55d`, `81c64b1`, `3ae1af0`, `d7e0e2a`, `e09f006`, `46712f9`, `13c6834`, `7448315`, `ced52e0`, `7ab3132`, `31b7402`, `0b91102`, `b03031f`, `9fe26de`, `42c343e`, `3a72934`; focused evidence filed; aggregate reduced to `313 errors in 46 files`; legacy type debt and mypy-target mismatch remain open` |
| 30 | Broker and MCP adapter release boundary cleanup | Backend / Interop / Security / QA | broker core/queue/routing/factory, MCP adapter, adapter regression, review/QA artifacts | Broker suite, MCP suite, fail-closed resource-management regression, explicit target mypy, Black/isort/Ruff/compile | done: commits `c98e871`, `72496ad`, `7a80472`; broker `62 passed`; MCP/adapter `17 passed`; aggregate reduced to `287 errors in 44 files`; remaining legacy type debt stays open` |
| 31 | Resource-management primitive type closure | Backend / Resource / QA | resource specification, manager, negotiation, review/QA artifacts | Full resource suite, explicit target mypy, Black/isort/Ruff/compile, aggregate audit | done: commit `a7d40b1`; resource suite `92 passed`; changed modules type/lint/compile clean; aggregate reduced to `277 errors in 43 files` |
| 32 | Fresh package and deterministic release-gate revalidation | Release / DevOps / QA | `dist/`, package metadata, CLI doctor, release plan, review/QA artifacts | `python -m build --wheel --sdist`, Twine check, network-free doctor, full Maple Black/isort, tools/tests Ruff, compile | done: current tree built wheel/sdist `1.1.3`; Twine both `PASSED`; doctor `ready: true`; formatter/lint/compile checks pass; no publish performed |
| 33 | MCP resource-management adapter integration | Chief Architect / Backend / Resource / Interop / QA | `docs/adr/023-*`, MCP adapter, resource manager, MCP adapter tests, README, changelog, review/QA artifacts | MCP/resource focused suite, explicit target mypy on changed boundaries, Black/isort/Ruff/compile | done: commit `8f28edf`; optional injected manager/negotiator services; allocate/release/negotiate actions validated; focused MCP/resource suite `97 passed`; changed modules have no direct mypy diagnostics; aggregate reduced to `266 errors in 40 files` |
| 34 | Task-monitoring type boundary cleanup | Backend / QA | task monitor, changelog, review/QA artifacts | Monitoring/task-management suite, explicit target mypy on changed module, Black/isort/Ruff/compile, aggregate audit | done: commit `3000b93`; behavior-preserving Optional/return annotations; focused `156 passed`; aggregate reduced to `252 errors in 39 files` |
| 35 | Task-scheduler type boundary cleanup | Backend / QA | task scheduler, changelog, review/QA artifacts | Scheduler suite, explicit target mypy on changed module, Black/isort/Ruff/compile, aggregate audit | done: commit `ed46678`; behavior-preserving policy/metrics/lifecycle annotations and queued-task narrowing; focused `27 passed`; aggregate reduced to `246 errors in 38 files` |
| 36 | Performance-optimizer type boundary cleanup | Backend / QA | performance optimizer, changelog, review/QA artifacts | Performance-optimizer suite, explicit target mypy on changed module, Black/isort/Ruff/compile, aggregate audit | done: commit `58379dd`; behavior-preserving lifecycle/callback/cache/trend annotations; focused `37 passed`; aggregate reduced to `239 errors in 37 files` |
| 37 | Fault-tolerance execution boundary cleanup | Backend / Reliability / QA | fault-tolerance executor, circuit-breaker state boundary, regression test, changelog, review/QA artifacts | Fault-tolerance suite, circuit-state regression, explicit target mypy on changed module, Black/isort/Ruff/compile, aggregate audit | done: commit `4c7d348`; executor/retry/recovery annotations plus validated half-open transition; focused `10 passed`; aggregate reduced to `221 errors in 36 files` |
| 38 | Result-collector aggregation boundary cleanup | Backend / QA | result collector, custom-aggregator guard, changelog, review/QA artifacts | Result-collector suite, explicit target mypy on changed module, Black/isort/Ruff/compile, aggregate audit | done: commit `24a8808`; behavior-preserving lifecycle/callback/filter annotations plus structured absent-callable error; focused `33 passed`; aggregate reduced to `205 errors in 35 files` |
| 39 | CLI and package validation type boundary cleanup | Backend / QA | CLI doctor, package validation/banner contracts, changelog, review/QA artifacts | CLI/basic suite, explicit changed-file mypy with skipped imports, Black/isort/compile, aggregate audit | done: commit `bc6a31e`; behavior-preserving return annotations; focused `8 passed`; aggregate reduced to `201 errors in 33 files` |
| 40 | Serialization and provider-registry type boundary cleanup | Backend / QA | serializer dependency/message boundary, provider registry lifecycle, changelog, review/QA artifacts | Serialization/provider suite, explicit changed-file mypy with skipped imports, Black/isort/compile, aggregate audit | done: commit `91a0502`; behavior-preserving dependency/message/registration annotations; focused `32 passed`; aggregate reduced to `198 errors in 31 files` |
| 41 | Error and state lifecycle type boundary cleanup | Backend / State / QA | consistency manager, state synchronizer, changelog, review/QA artifacts | State consistency/synchronization suite, explicit changed-file mypy with skipped imports, Black/isort/compile, aggregate audit | done: commit `b9d8230`; behavior-preserving constructor annotations; focused `22 passed`; aggregate reduced to `196 errors in 30 files` |
| 42 | Failure-detection type boundary cleanup | Reliability / Discovery / QA | failure detector, circuit-breaker wrapper boundary, changelog, review/QA artifacts | Failure-detection suite, explicit changed-file mypy with skipped imports, Black/isort/compile, aggregate audit | done: commit `4ec10ee`; behavior-preserving detector lifecycle/recovery/callback annotations; focused `14 passed`; aggregate reduced to `181 errors in 29 files` |
| 43 | Discovery registry and capability-matching type boundary cleanup | Discovery / Backend / QA | agent registry, capability matcher, changelog, review/QA artifacts | Combined registry/capability/health suite, explicit changed-file mypy with skipped imports, Black/isort/compile, aggregate audit | done: commit `c746b02`; behavior-preserving optional-input, requirement, lifecycle, and matrix annotations; focused `43 passed`; aggregate reduced to `172 errors in 27 files` |
| 44 | Security link and encryption type boundary cleanup | Security / Backend / QA | link manager, encryption manager, crypto narrowing, changelog, review/QA artifacts | Link/encryption suites, explicit changed-file mypy with skipped imports, Black/isort/compile, aggregate audit | done: commit `e30ce65`; behavior-preserving optional-key/lifecycle and crypto-manager narrowing annotations; focused `34 passed`; aggregate reduced to `163 errors in 25 files` |
| 45 | Communication pattern type boundary cleanup | Backend / Interop / QA | publish-subscribe, request-response, streaming, regression tests, changelog, review/QA artifacts | Communication suite, explicit changed-file mypy with skipped imports, Black/isort/compile, aggregate audit | done: pending source commit; typed agent and pending-request boundaries, broker-result cast, direct-publish string contract, and subscriber narrowing; focused `49 passed`; aggregate reduced to `152 errors in 22 files` |
| 46 | Agent handler registry type boundary cleanup | Backend / QA | message handlers, handler registry, agent regression, changelog, review/QA artifacts | Agent suite, explicit changed-file mypy with skipped imports, Black/isort/compile, aggregate audit | done: commit `47d196b`; typed handler registry storage and lookup, constructor/list contracts, and boolean handler predicate; focused `33 passed`; aggregate reduced to `150 errors in 21 files` |

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

Done (with evidence): G0 brief, G1 ADR, G2 plan, committed G3 feature slices
through bounded workflow execution recovery, and release-hardening evidence
through slice 38, including MCP
interoperability, bounded artifacts, native LLM streaming, deterministic async
tool result ordering, durable approval, workflow fan-out/fan-in, checkpoint
history, bounded conversation sessions, and retrieval/source evaluation; slice
review/QA artifacts are filed. Slice 23 adds an opt-in bounded execution journal
and public running-checkpoint recovery.
Release hardening remains in progress. Slices 19, 20, and 21 are committed and
verified. Slice 22 is committed and verified with deterministic
retrieval/source coverage evaluation. Slice 23 is implemented and
review/QA/build evidence is filed; generation faithfulness remains a separate
follow-on capability. Slice 24 adds a deterministic lexical groundedness proxy;
review/QA/build evidence is filed.
Focused feature gates (240 LLM/autonomy/CLI tests, including 22 MCP, 5
artifact, 5 stream, async tool fan-out, durable approval, workflow fan-out,
vector retrieval, checkpoint history, session-aware agent, retrieval evaluation,
workflow execution-journal, and grounded-answer evaluation regressions),
compile, changed-surface Ruff/Flake8, metadata-clean wheel/sdist builds, Twine
checks, a clean-venv wheel doctor smoke pass, and a fresh `.[dev,security]`
environment with `pip check` reporting no broken requirements all pass.
The repository-wide Ruff gate is clean across `tools` and `tests`, and the
repository Black/isort gates are now clean across `maple/`. Slice 25
recorded `621 passed, 7 warnings` on its changed tracked-test regression; Slice
26 separately recorded `22 passed` with no targeted warning output. The full
repository regression is not complete: the latest bounded attempt
reported `1049 passed, 8 warnings in 839.17s` before interruption in the
remaining Doctrine gold cases. Fresh-repository profiling shows individual
Git commands taking roughly 5–15 seconds on this Windows environment, with
the slowest gold cases at 166.96s, 159.74s, 115.61s, and 56.04s. No assertion
failure was reported. The shared interpreter still has unrelated `pip check`
conflicts, but the isolated dependency gate is clean. The targeted legacy test
warnings are cleared. Slice 27 makes the previously advisory repository
Black/isort/mypy/Bandit and pip-audit checks fail closed; the local audit
currently reports 459 mypy errors across 66 files and no installed Bandit
executable. The full repository regression remains incomplete after the
formatter run reached 86% with no reported assertion failure before a bounded
manual interruption. Slices 29–31's explicit Python 3.10-target type audit now
reports `277 errors in 43 files`; slice 33's follow-up audit now reports
`266 errors in 40 files`, down from the pre-cleanup baseline; slice 36's
follow-up audit now reports `239 errors in 37 files`; slice 37's follow-up
audit now reports `221 errors in 36 files`; slice 38's follow-up audit now
reports `205 errors in 35 files`; slice 39's follow-up audit now reports
`201 errors in 33 files`; slice 40's follow-up audit now reports
`198 errors in 31 files`; slice 41's follow-up audit now reports
`196 errors in 30 files`; slice 42's follow-up audit now reports
`181 errors in 29 files`; slice 43's follow-up audit now reports
`172 errors in 27 files`; slice 44's follow-up audit now reports
`163 errors in 25 files`; the
communication slice 45's follow-up audit now reports `152 errors in 22 files`;
agent-handler slice 46's follow-up audit now reports `150 errors in 21 files`;
installed mypy 2.3 rejects the configured Python 3.8 target, so the support
matrix/toolchain decision remains open. Dependency-audit disposition and
unavailable independent fresh-context verification remain open.
External publishing, cloud selection, and website changes remain explicitly out
of scope until human approval.
