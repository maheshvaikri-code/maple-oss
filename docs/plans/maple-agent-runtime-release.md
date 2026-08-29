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
| 8 | Release hardening | Security / QA / Release Manager | CI, changelog, release artifacts, package metadata | Full test/lint/type/audit/build matrix and clean-tree checklist | in progress: current dirty suite `1810 passed, 1 skipped`, exact clean tracked suite `1693 passed, 1 skipped`, whole-package mypy/format/lint/compile/pip-audit and clean package smoke pass; CI still has `608` Flake8 `E501` findings and `19` header-policy findings, fresh independent verifier sessions are unavailable, and human approval remains required for public session transport, execution isolation, hosted coordination, and publication |
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
| 45 | Communication pattern type boundary cleanup | Backend / Interop / QA | publish-subscribe, request-response, streaming, regression tests, changelog, review/QA artifacts | Communication suite, explicit changed-file mypy with skipped imports, Black/isort/compile, aggregate audit | done: commit `3e879fb`; typed agent and pending-request boundaries, broker-result cast, direct-publish string contract, and subscriber narrowing; focused `49 passed`; aggregate reduced to `152 errors in 22 files` |
| 46 | Agent handler registry type boundary cleanup | Backend / QA | message handlers, handler registry, agent regression, changelog, review/QA artifacts | Agent suite, explicit changed-file mypy with skipped imports, Black/isort/compile, aggregate audit | done: commit `47d196b`; typed handler registry storage and lookup, constructor/list contracts, and boolean handler predicate; focused `33 passed`; aggregate reduced to `150 errors in 21 files` |
| 47 | Error recovery and circuit-breaker result boundary cleanup | Reliability / Backend / QA | retry recovery, circuit breaker, error regression, changelog, review/QA artifacts | Error suite, explicit changed-file mypy with skipped imports, Black/isort/compile, aggregate audit | done: commit `d160110`; narrowed generic recovery and circuit-breaker error values with static-only casts; focused `42 passed`; aggregate reduced to `147 errors in 19 files` |
| 48 | State synchronization result-variable boundary cleanup | State / Backend / QA | state synchronizer, synchronization regression, changelog, review/QA artifacts | Synchronization suite, explicit changed-file mypy with skipped imports, Black/isort/compile, aggregate audit | done: commit `06ae842`; separated set/delete result variables so both state-store result types remain precise; focused `9 passed`; aggregate reduced to `146 errors in 18 files` |
| 49 | Autonomy event payload container type cleanup | Autonomy / Backend / QA | event redaction stream, event regression, changelog, review/QA artifacts | Event suite, explicit changed-file mypy with skipped imports, Black/isort/compile, aggregate audit | done: commit `dfb001b`; separated list and mapping redaction outputs with explicit containers; focused `5 passed`; aggregate reduced to `143 errors in 17 files` |
| 50 | Workflow next-node optionality boundary cleanup | Autonomy / Backend / QA | workflow execution loop, workflow/replay regression, changelog, review/QA artifacts | Workflow/replay suite, explicit changed-file mypy with skipped imports, Black/isort/compile, aggregate audit | done: commit `e084f9b`; initialized next-node state with its declared optional contract before sequential/parallel routing; focused `19 passed`; aggregate reduced to `142 errors in 16 files` |
| 51 | Health-monitor type boundary cleanup | Discovery / Backend / QA | health monitor, health regression, changelog, review/QA artifacts | Health-monitor suite, explicit changed-file mypy with skipped imports, Black/isort/compile, aggregate audit | done: commit `d8bdfa6`; clarified status defaults, monitor lifecycle returns, heartbeat metrics optionality, callback registration, and monitor-loop contracts; focused `15 passed`; aggregate reduced to `136 errors in 15 files` |
| 52 | Legacy interop adapter type boundary cleanup | Interop / Backend / QA | A2A, ACP, FIPA ACL adapters, import/compile evidence, changelog, review/QA artifacts | Explicit changed-file mypy with skipped imports, Black/isort/compile, import smoke, aggregate audit | done: commit `4086f0d`; typed adapter constructors and JSON decode boundary without changing translation behavior; no dedicated adapter tests exist; import smoke passed; aggregate reduced to `132 errors in 12 files` |
| 53 | Production broker factory type boundary cleanup | Broker / Backend / QA | production broker factory, S2/broker regression, changelog, review/QA artifacts | S2/broker suite, explicit changed-file mypy with skipped imports, Black/isort/compile, aggregate audit | done: commit `4114386`; separated in-memory, NATS, and S2 broker locals so concrete factory types do not collide; focused `16 passed`; aggregate reduced to `130 errors in 11 files` |
| 54 | AutoGen adapter type boundary cleanup | Interop / Backend / QA | AutoGen adapter, import/compile evidence, changelog, review/QA artifacts | Explicit changed-file mypy with skipped imports, Black/isort/compile, import smoke, aggregate audit | done: commit `7395bd4`; typed adapter constructors, agent registry, group-chat inputs, and mixed numeric performance metrics; import smoke passed with `AUTOGEN_AVAILABLE: True`; aggregate reduced to `126 errors in 10 files` |
| 55 | Doctrine adapter result-boundary cleanup | Interop / Security / QA | doctrine adapter builders/validators, doctrine adapter regression, changelog, review/QA artifacts | Doctrine adapter suite, explicit changed-file mypy with skipped imports, Black/isort/compile, aggregate audit | done: commit `0128070`; narrowed artifact references, validation error propagation, and agent send results without changing fail-closed behavior; focused `34 passed`; aggregate reduced to `119 errors in 9 files` |
| 56 | Security compatibility façade type closure | Security / Backend / QA | `maple/security/__init__.py`, security-init regression, changelog, review/QA artifacts | Security-init suite, explicit changed-file mypy with skipped imports, Black/isort/compile, aggregate audit | done: commit `bfbb203`; typed intentional fallback classes, token/link state, result contracts, and compatibility imports; focused `30 passed`; aggregate reduced to `95 errors in 8 files` |
| 57 | S2 stream adapter type boundary cleanup | Interop / State / QA | S2 broker/state backend, mocked S2 regression, changelog, review/QA artifacts | S2 adapter suite, explicit changed-file mypy with skipped imports, Black/isort/compile, aggregate audit | done: commit `821cc4d`; typed stream helpers/readers and narrowed optional basin/stream SDK boundaries without changing dependency fallback behavior; focused `16 passed`; aggregate reduced to `87 errors in 7 files` |
| 58 | LLM provider SDK type boundary cleanup | ML Engineer / Backend / QA | OpenAI/Anthropic providers, LLM streaming regression, changelog, review/QA artifacts | Native provider stream suite, explicit changed-file mypy with skipped imports, Black/isort/compile, aggregate audit | done: commit `36521f2`; typed optional SDK configuration, compatible payload containers, and response boundaries without changing provider behavior; focused native stream `3 passed`; aggregate reduced to `62 errors in 5 files` |

| 59 | OpenAI SDK resource-function boundary | Interop / Resource / Security / QA | OpenAI SDK adapter, resource-function regression, changelog, review/QA artifacts | Offline adapter tests, explicit changed-file mypy with skipped imports, Black/isort/Ruff/compile, aggregate audit | done: commit `142e40e`; implemented injected ResourceManager allocation, fail-closed missing-service behavior, and input validation for the previously undefined function route; focused `2 passed`; aggregate reduced to `51 errors in 4 files` |

| 60 | LangGraph recovery and optional-SDK boundary | Interop / Reliability / QA | LangGraph adapter, recovery regression, changelog, review/QA artifacts | Offline recovery tests, explicit changed-file mypy with skipped imports, Black/isort/Ruff/compile, aggregate audit | done: commit `6a5c376`; implemented bounded retry/resource-reallocation/degradation decisions and typed optional SDK fallback without changing graph construction semantics; focused `3 passed`; aggregate reduced to `42 errors in 3 files` |

| 61 | CrewAI tool-boundary closure | Interop / Resource / Security / QA | CrewAI adapter, CrewAI tool regression, changelog, review/QA artifacts | Offline adapter tests, explicit changed-file mypy with skipped imports, Black/isort/Ruff/compile, aggregate audit | done: commit `31e408a`; implemented communication/resource/secure-link/priority tools and typed optional CrewAI fallback without changing crew execution flow; focused `3 passed`; aggregate reduced to `27 errors in 1 file` |

| 62 | NATS broker optional-transport type closure | Broker / Interop / QA | NATS broker, offline NATS regression, changelog, review/QA artifacts | Offline config/not-connected tests, explicit changed-file mypy with skipped imports, Black/isort/Ruff/compile, aggregate audit | done: commit `5f57e50`; typed optional NATS SDK/error aliases, nullable config defaults, stable message IDs/results, callback payloads, and sync event-loop wrapper; focused `1 passed, 1 skipped`; aggregate audit clean for all `93 source files` |
| 63 | Mypy target/toolchain contract closure | Release / DevOps / QA | `pyproject.toml`, release plan, changelog, review/QA artifacts | Default mypy, cross-surface regression, Black/isort/Ruff/compile | done: commit `70d47a9`; retained Python `>=3.8` runtime support while moving the static-analysis target to Python 3.10, which is accepted by mypy 2.x; default audit clean across `93 source files`; cross-surface regression `616 passed, 1 skipped` |
| 64 | Transport and serialization security boundary hardening | Security / Interop / Backend / QA | A2A adapter, MCP transport, serializer, security regressions, changelog, review/QA artifacts | Security regressions, cross-surface regression, isolated `pip check`, `pip-audit`, Bandit `-ll`, Black/isort/Ruff/mypy/compile | done: commit `d3e5358`; bounded A2A registry timeout, explicit MCP URL-boundary regression, restricted size-bounded pickle loading, and malicious-payload coverage; security regression `37 passed`; cross-surface `621 passed, 1 skipped`; isolated dependency audit clean; Bandit medium/high gate exit 0 |
| 65 | Safe legacy lint and FIPA translation closure | Backend / QA / Release | MAPLE package initializers, ACP/FIPA adapters, queue, health monitor, cryptography, consistency, FIPA regression, changelog, review/QA artifacts | Affected regression, changed-file Ruff/Black/isort/mypy, broad Ruff inventory, diff check | done: commit `25001b0`; affected regression `131 passed in 48.43s`; changed files pass Ruff/Black/isort/mypy; broad `ruff check maple` reduced from `250` to `171` diagnostics (`E402 140`, `F401 31`) |
| 66 | Legacy header/import lint closure | Backend / QA / Release | autonomy package initializer, state store/synchronization, broker routing, communication pubsub/request-response, security audit, changelog, review/QA artifacts | Affected regression, changed-file Ruff/Black/isort/mypy/compile, broad Ruff inventory, diff check | done: commit `c42cf58`; affected regression `628 passed, 1 skipped in 16.35s`; changed files pass quality/type checks; broad `ruff check maple` reduced from `171` to `95` diagnostics (`E402 69`, `F401 26`) |
| 67 | Verified unused-import and optional-probe closure | Backend / QA / Release | adapters, agent/config, broker, communication, discovery, error, resources, security, task management, changelog, review/QA artifacts | Affected regression, S2/resource/link revalidation, changed-file Ruff/Black/isort/mypy/compile, broad Ruff inventory, diff check | done: commit `6ebac24`; affected suite `777 passed, 1 skipped`; current S2/resource/link revalidation `130 passed`; changed files pass all quality/type checks; broad `ruff check maple` reduced from `95` to `58` diagnostics (`E402 58`) with zero F401 findings |
| 68 | Residual legacy module-header closure | Backend / QA / Release | autonomy, broker, LLM, monitoring, security, state package headers, changelog, review/QA artifacts | Affected regression, changed-file Ruff/Black/isort/mypy/compile, broad Ruff inventory, diff check | done: commit `11d0b27`; affected suite `635 passed, 1 skipped in 16.90s`; changed files pass all quality/type checks; broad `ruff check maple` reduced from `58` to `19` diagnostics (`E402 19`) |
| 69 | Repository-wide legacy import-boundary closure | Backend / QA / Release | Doctrine adapter and security authentication/separation imports, changelog, review/QA artifacts | Affected regression, repository Ruff, changed-file Black/isort/mypy/compile, diff check | done: code commit `0ea2179`; affected suite `107 passed in 4.02s`; Ruff reports zero findings; changed files pass Black/isort/mypy/compile; optional JWT behavior remains covered |
| 70 | Typed model output boundary | Backend / QA / Release | autonomy contracts, AutonomousConfig, public exports, contract/agent tests, changelog, review/QA artifacts | Focused contract/agent regression, full autonomy regression, Ruff, Black/isort, mypy, compile, package, doctor, diff check | done: code commit `bf2ca4a`; full autonomy regression `210 passed in 3.37s`; typed-output focused regression included in `28 passed in 0.35s`; wheel/sdist and Twine checks pass; all static/readiness gates pass |
| 71 | Typed tool input/output contracts | Backend / QA / Release | autonomy contracts/tools, public exports, README/API docs, contract/tool/agent tests, changelog, review/QA artifacts | Typed schema publication, input/output validation, handler side-effect protection, focused/full autonomy regression, static/package/doctor gates | done: code commit `ded4477`; public docs commit `9236bc4`; focused contract/tool/agent regression `43 passed in 0.37s`; full autonomy regression `212 passed in 3.26s`; mypy/Ruff/Black/isort/compile, wheel/sdist, Twine, and doctor gates pass |
| 72 | Optional bounded Protobuf serialization | Backend / Interop / QA / Release | core serializer, serialization tests, ADR-024, README/API docs, changelog, review/QA artifacts | Protobuf round trip, malformed/oversized input, oversized output, unavailable dependency, core/autonomy regression, static/package/doctor gates | done: code commit `2b8bb57`; core/autonomy regression `240 passed in 3.37s`; Protobuf tests `28 passed in 0.28s`; mypy/Ruff/Black/isort/compile, wheel/sdist, Twine, and doctor gates pass; no dependency added |
| 73 | Bounded per-goal token accounting and hard budget | Backend / QA / Security / Release | autonomy agent, token-budget regressions, ADR-025, README/API docs, changelog, review/QA artifacts | Sync/async usage aggregation, reflection accounting, invalid/missing usage, budget-overrun side-effect protection, static/package/doctor gates | done: code commit `2328b92`; focused agent/session regression `30 passed in 0.31s`; changed-file Ruff/Black/isort/mypy pass; docs and release evidence filed; no dependency added |
| 74 | Bounded concurrent multi-agent orchestration | Backend / QA / Security / Release | orchestrator, sync/async orchestration regressions, ADR-026, README/API docs, changelog, review/QA artifacts | Bounded sync/async fan-out, deterministic joins, sync-only fallback, worker exception isolation, invalid limit, static/package/doctor gates | done: code commit `b2cccfb`; agent/orchestrator regression `43 passed in 0.33s`; changed-file Ruff/Black/isort/mypy pass; docs and release evidence filed; no dependency added |
| 75 | Bounded structured-output repair retries | ML Engineer / Backend / QA / Security / Release | autonomy agent/config, repair regressions, ADR-027, README/API docs, changelog, review/QA artifacts | Sync/async correction, default fail-fast, retry exhaustion, invalid retry limit, token-budget consumption, static/package/doctor gates | done: code commit `e3becdf`; focused agent regression `28 passed in 0.33s`; changed-file Ruff/Black/isort/mypy pass; docs and release evidence filed; no dependency added |
| 76 | Deadline and cooperative cancellation for async orchestration | Backend / QA / Security / Release | orchestrator, async orchestration regressions, ADR-028, README/API docs, changelog, review/QA artifacts | Request-wide timeout, native async task cancellation/drain, cancellation token, invalid timeout, consensus deadline, static/package/doctor gates | done: code commit `7630839`; orchestrator regression `24 passed in 0.43s`; core/autonomy regression `257 passed in 3.60s`; changed-file Ruff/Black/mypy pass; docs and release evidence filed; no dependency added |
| 77 | Bounded agent-as-tool handoffs | Chief Architect / Backend / Security / QA / Release | autonomy tools/exports, handoff regressions, ADR-029, README/API docs, changelog, review/QA artifacts | Structured target result, approval default, bounded task input, raw-error redaction, target exception/invalid-result isolation, public import, static/package/doctor gates | done: code commit `62ebad8`; tool regression `18 passed in 0.25s`; autonomy regression `234 passed in 3.49s`; changed-file Ruff/Black/mypy/compile pass; no dependency added |
| 78 | Explicit unsupported capability inventory | Chief Architect / Security / Release | release brief, README, changelog, state/authentication regressions, QA/review evidence | Cross-reference every remaining `NOT_IMPLEMENTED` runtime path; verify fail-closed tests and no unsupported claim in public feature list | done: Redis state boundary plus mutual-TLS/OAuth2 fail-closed regression coverage (`73 passed in 3.44s`); unsupported/deferred surfaces are explicit; no dependency change |
| 79 | Tracked release-suite warning closure | QA / Release / Backend | `tests/test_fixes.py`, release plan, README, changelog, QA/review evidence | Tracked-test manifest execution, warning-free summary, focused test, Ruff, diff check | done: 100 tracked test files; `1185 passed, 1 skipped in 210.07s`; fixed a test returning a value to pytest; no runtime behavior or dependency change |
| 80 | Clean tracked release artifact boundary | Release / DevOps / QA | clean archive build evidence, release plan, QA/review evidence | Build wheel/sdist from `git archive HEAD`, Twine checks, sdist content audit, no workspace-only files | done: clean snapshot built wheel/sdist `1.1.3`; both Twine checks `PASSED`; 460 sdist files; preserved workspace-only files absent; dirty-workspace artifact not treated as publishable |
| 81 | Agent-framework parity ledger | Release / Chief Architect / QA | `docs/agent-framework-parity.md`, README, changelog, QA/review evidence | Source-backed five-framework matrix, explicit status vocabulary, code-block/sandbox boundary, prioritized gap list | done: functionality-only ledger filed; no adapter-as-parity claim; no runtime/dependency change |
| 82 | Bounded durable synchronous agent-run checkpoints and approval resume | Chief Architect / Backend / Security / QA | `docs/adr/030-*`, `maple/autonomy/runs.py`, autonomy exports/agent, run tests, API docs, README, changelog, QA/review evidence | JSON-safe bounded snapshots, memory/file CAS, atomic restart recovery, per-step cursor, paused approval replacement, no duplicate completed tool call, synchronous resume, static/package/doctor gates | done: `45 passed in 0.36s` compatibility slice; autonomy suite `240 passed in 3.59s`; Ruff/Black/mypy/compile pass; async parity remains a follow-on slice |
| 83 | Current tracked-suite and clean-artifact revalidation | QA / Release / DevOps | tracked test manifest, clean archive build, doctor output, README, changelog, QA/review evidence | Full tracked application suite, warning-free result, clean wheel/sdist, Twine, sdist boundary audit, network-free doctor | done: 101 tracked Python files; `1191 passed, 1 skipped in 217.81s`; clean `1.1.3` wheel/sdist; Twine passed; 466 sdist entries; doctor `ready: true`; workspace-only Doctrine and fresh-review gates remain open |
| 84 | Async durable agent-run checkpoints and approval resume | Chief Architect / Backend / Security / QA | `docs/adr/031-*`, async agent loop, run tests, API/README/parity docs, changelog, QA/review evidence | Async `run_id`, executor-backed bounded persistence, async resume, approval pause before later tool side effects, no duplicate completed tool call, compatibility/static/package/doctor gates | done: `9 passed in 0.30s` async/store slice; tracked suite `1194 passed, 1 skipped in 205.06s`; Ruff/Black/mypy/compile/doctor pass; clean `1.1.3` wheel/sdist, Twine passed, 467 sdist entries; distributed leases/exactly-once/sandbox remain out of scope |
| 85 | Unified bounded agent-run lifecycle event stream | Chief Architect / Backend / Observability / QA | `docs/adr/032-*`, EventStream attachment, sync/async agent lifecycle events, event/run tests, API/README/parity docs, changelog, QA/review evidence | Shared started/resumed/model/tool/paused/completed/failed vocabulary, usage trailers, metadata-only payloads, bounded ring/backpressure visibility, subscriber isolation, no telemetry-induced run failure | done: focused lifecycle slice `10 passed in 0.27s`; tracked suite after response hardening `1195 passed, 1 skipped in 222.53s`; static/doctor/package/Twine gates pass; cancellation/exporter/durable cursors remain follow-on |
| 86 | Deterministic loopback HTTP response closure | Backend / QA / Release | `docs/adr/033-*`, `maple/autonomy/server.py`, server tests, QA/review evidence | Flush bounded JSON responses, explicit connection closure, preserve routes/status/payloads, full tracked regression | done: server suite `4 passed in 2.34s`; exact tracked suite `1195 passed, 1 skipped in 222.53s`; no dependency or protocol surface change |
| 87 | Final current-commit release artifact revalidation | Release / DevOps / QA | clean `git archive HEAD`, wheel/sdist, Twine output, doctor output, release plan, QA/review evidence | Current tracked snapshot only, package metadata, sdist workspace boundary, ADR/module presence, network-free doctor | done: clean `1.1.3` wheel/sdist; Twine passed; 469 sdist entries; ADR-031/032/033 and durable/event modules present; workspace-only audit zero; doctor `ready: true`; no publication performed |
| 88 | Bounded editable durable tool approvals | Chief Architect / Backend / Security / QA / Release | `docs/adr/034-*`, approval stores/agent boundary, sync/async run regressions, API/parity/README docs, changelog, QA/review evidence | Approved-only bounded JSON replacement, in-memory/file persistence, invalid-edit no-mutation, denied-edit rejection, one-time consume, sync/async resume, static/package/doctor gates; arbitrary multi-turn HITL remains explicit follow-on | done: focused approval/run/agent `44 passed in 0.46s`; tracked manifest `1197 passed, 1 skipped in 204.41s`; Ruff/Black/mypy/compile/diff/doctor pass; clean `1.1.3` wheel/sdist, Twine passed, 470 sdist entries, ADR-034 present, workspace-only audit zero; no publication |
| 89 | Bounded durable human-input request/response | Chief Architect / Backend / Security / QA / Release | `docs/adr/035-*`, `maple/autonomy/interactions.py`, durable run cursor/agent/tool, interaction/run/tool tests, API/README/parity docs, changelog, QA/review evidence | Bounded prompt/schema/response records, memory/file persistence, schema-validated response, explicit rejection, sync/async `request_human_input` pause/resume, consumed-decision crash recovery, static/package/doctor gates; leases/notifications/multi-round remain explicit follow-on | done: focused interaction/run/tool/agent `61 passed in 0.51s`; tracked manifest `1202 passed, 1 skipped in 211.16s`; Ruff/Black/mypy/compile/diff/doctor pass; clean archive wheel/sdist `1.1.3`, Twine passed, sdist `473` entries with ADR-035, workspace-only audit zero; no publication |
| 90 | Cross-process durable fencing leases | Chief Architect / Backend / Security / QA / Release | `docs/adr/036-*`, `maple/resources/lease.py`, resource exports/tests, API/README/parity docs, changelog, QA/review evidence | Bounded file-backed lease state, OS-level inter-process lock, atomic replacement, persisted fencing counter, expiry, renew/release, typed fail-closed storage behavior; durable-store integration and remote authentication remain explicit follow-ons | done: focused resource model + file lease `41 passed in 3.64s`; tracked manifest `1207 passed, 1 skipped in 214.53s`; Ruff/Black/compile/doctor pass and changed-boundary mypy pass; clean archive wheel/sdist `1.1.3`, Twine passed, sdist `475` entries with ADR-035/036, workspace-only audit zero; no publication |
| 91 | Cross-process durable approval-store ownership | Chief Architect / Backend / Security / QA / Release | `docs/adr/037-*`, `maple/autonomy/approval.py`, approval lease tests, API/README/parity docs, changelog, QA/review evidence | Per-record lease acquisition for file get/create/decide/consume/list, no mutation on acquisition failure, explicit uncertain-commit release error, existing atomic/thread-safe behavior retained; input/run store integration remains separate | done: focused approval + lease boundary `8 passed in 0.31s`; tracked manifest `1209 passed, 1 skipped in 199.58s`; Ruff/Black/compile/diff/doctor pass and changed-boundary mypy pass; clean archive wheel/sdist `1.1.3`, Twine passed, sdist `477` entries with ADR-037, workspace-only audit zero; no publication |
| 92 | Cross-process durable human-input-store ownership | Chief Architect / Backend / Security / QA / Release | `docs/adr/038-*`, `maple/autonomy/durable_leases.py`, `maple/autonomy/interactions.py`, interaction lease tests, approval regressions, API/README/parity docs, changelog, QA/review evidence | Shared lease wrapper, per-record human-input get/create/respond/reject/consume/list ownership, no mutation on acquisition failure, explicit uncertain-commit release error, approval behavior preserved; run-store integration remains separate | done: focused approval/input/lease boundary `13 passed in 0.48s`; tracked manifest `1211 passed, 1 skipped in 219.68s`; Ruff/Black/compile/diff/doctor pass and changed-boundary mypy pass; clean archive wheel/sdist `1.1.3`, Twine passed, sdist `480` entries with ADR-038, workspace-only audit zero; no publication |
| 93 | Cross-process durable run-store ownership | Chief Architect / Backend / Security / QA / Release | `docs/adr/039-*`, `maple/autonomy/runs.py`, run lease tests, API/README/parity docs, changelog, QA/review evidence | Per-run fencing lease across load and complete CAS save, no read/mutation on acquisition failure, explicit uncertain-commit release error, existing bounds/atomic replacement/CAS preserved; host side-effect policy and notifications remain separate | done: focused run-store suite `14 passed in 2.66s`; tracked manifest `1213 passed, 1 skipped in 228.60s`; Ruff/Black/compile/diff/doctor pass and changed-boundary mypy pass; clean archive wheel/sdist `1.1.3`, Twine passed, sdist `482` entries with ADR-039/run module/run test, workspace-only audit zero; no publication |
| 94 | Bounded human-input host notification and authorization hooks | Chief Architect / Backend / Security / QA / Release | `docs/adr/040-*`, `maple/autonomy/interactions.py`, `maple/autonomy/agent.py`, host callback tests, public exports, API/README/parity docs, changelog, QA/review evidence | Bounded created/responded/rejected notifications without response payload, in-lease actor authorization for respond/reject, fail-closed errors, legacy no-actor compatibility, typed notification failure with persisted state authoritative; remote auth/transport/multi-round remain separate | done: focused host/interaction/run suite `49 passed in 2.80s`; tracked manifest `1215 passed, 1 skipped in 227.81s`; Ruff/Black/compile/diff/doctor pass and changed-boundary mypy pass; clean archive wheel/sdist `1.1.3`, Twine passed, sdist `484` entries with ADR-040/host module/test, workspace-only audit zero; no publication |
| 95 | Bounded same-record multi-round human input and durable resume | Chief Architect / Backend / Security / QA / Release | `docs/adr/041-*`, `maple/autonomy/interactions.py`, `maple/autonomy/agent.py`, built-in tool schema, round/history tests, public exports, API/README/parity docs, changelog, QA/review evidence | Bounded `max_rounds` quota, immutable completed-round history, durable in-memory/file `continue_round`, in-lease authorization and metadata-only continuation notification, sync durable checkpoint waits on the same interaction, multi-round tool result preserves prior responses, legacy one-shot behavior and custom-store compatibility; remote auth/transport remains separate | done: focused slice `23 passed in 2.74s`; tracked manifest `1219 passed, 1 skipped in 215.53s`; Ruff/Black/compile/diff/doctor and changed-boundary mypy pass; clean archive wheel/sdist `1.1.3`, Twine passed, sdist `485` entries with ADR-041/interactions module/run test, workspace-only audit zero; no publication |
| 96 | Bounded per-node workflow retry and durable backoff state | Chief Architect / Backend / Security / QA / Release | `docs/adr/042-*`, `maple/autonomy/workflow.py`, workflow exports/tests, API/README/parity docs, changelog, QA/review evidence | Capped `RetryPolicy`, ordinary node retry on exceptions/invalid outputs, persisted retry counts and `retry_after`, retry context metadata, typed exhaustion, existing no-policy failure behavior, parallel-branch boundary explicit; static/package/doctor gates | done: focused workflow/replay suite `22 passed in 4.20s`; tracked manifest `1222 passed, 1 skipped in 222.42s`; Ruff/Black/compile/diff/doctor and changed-boundary mypy pass; clean archive wheel/sdist `1.1.3`, Twine passed, sdist `486` entries with ADR-042/workflow module/test, workspace-only audit zero; no publication |
| 97 | Durable event cursors and cooperative stream cancellation | Chief Architect / Backend / Security / QA / Release | `docs/adr/043-*`, `maple/autonomy/events.py`, autonomy/top-level exports, event regression, API/README/parity docs, changelog, QA/review evidence | JSON-safe `EventCursor`/`EventBatch`, bounded cursor reads, explicit `EVENT_CURSOR_EXPIRED` retention gaps, existing cancellation-token wait support, public import, static/package/doctor gates; remote transport/provider token linkage/exporter remain separate | done: focused event/lifecycle suite `37 passed in 2.28s`; exact tracked manifest `1226 passed, 1 skipped in 216.99s`; Ruff/Black/compile/diff/doctor and changed-boundary mypy pass; clean archive build/Twine exit 0, sdist `487` entries with all 3 slice files, workspace-only audit zero; no publication |
| 98 | Bounded context-aware handoff filtering | Chief Architect / Backend / Security / QA / Release | `docs/adr/044-*`, `maple/autonomy/tools.py`, `maple/autonomy/agent.py`, handoff/context regressions, API/README/parity docs, changelog, QA/review evidence | Explicit `allowed_context_keys`, recursively bounded/copy-on-boundary JSON context, denied-key and unsupported-target errors, `AutonomousAgent.pursue_goal_with_context`, durable initial context message, legacy no-context compatibility, static/package/doctor gates; async target execution/durable handoff identity/ownership transfer remain separate | done: focused handoff/agent suite `50 passed in 4.40s`; exact tracked manifest `1230 passed, 1 skipped in 227.55s`; Ruff/Black/compile/diff/doctor and changed-boundary mypy pass; clean archive build/Twine exit 0, sdist `488` entries with all 3 slice files, workspace-only audit zero; no publication |
| 99 | Async-capable tool and handoff execution | Chief Architect / Backend / Security / QA / Release | `docs/adr/045-*`, `maple/autonomy/tools.py`, `maple/autonomy/agent.py`, async tool/handoff/agent regressions, API/README/parity docs, changelog, QA/review evidence | Optional awaitable tool handlers, async registry execution, async agent-loop dispatch, executor-backed sync fallback, shared approval/validation/error boundaries, explicit async handoff target/context contracts, static/package/doctor gates; durable handoff identity/ownership transfer and hard cancellation remain separate | done: focused coverage `68 passed in 0.46s`; exact tracked manifest `1235 passed, 1 skipped in 215.23s` across 107 tracked test files; Black/Ruff/changed-boundary mypy/compile/diff/doctor pass; clean archive build/Twine exit 0, sdist `489` entries with all 5 slice files, workspace-only audit zero; no publication |
| 100 | Bounded provider-stream usage/correlation and event exporter seams | Chief Architect / Backend / Security / QA / Release | `docs/adr/046-*`, `maple/llm` stream types/providers, `maple/autonomy/events.py` and exports, provider/event regressions, API/README/parity docs, changelog, QA/review evidence | Optional bounded `TokenUsage` trailers and provider request IDs, OpenAI opt-in usage request, Anthropic partial-usage merge, host-owned redacted exporter with failure isolation, public imports, static/package/doctor gates; automatic run-event trace linkage and remote delivery remain separate | done: focused provider/event suite `16 passed in 0.28s`; exact tracked manifest `1237 passed, 1 skipped in 253.10s` across 107 tracked test files; Black/Ruff/changed-boundary mypy/compile/diff/doctor pass; clean archive build/Twine exit 0, sdist `490` entries with ADR-046 and Slice 100 files, workspace-only audit zero; no publication |
| 101 | Bounded provider correlation in agent events and decision traces | Chief Architect / Backend / Security / QA / Release | `docs/adr/047-*`, `maple/autonomy/agent.py`, `maple/autonomy/observability.py`, lifecycle/run/observability regressions, API/README/parity docs, changelog, QA/review evidence | Copy bounded provider request IDs into sync/async `model.response` metadata and `DecisionTrace`/JSON export, omit malformed IDs, preserve metadata-only redaction and public boundaries, static/package/doctor gates; incremental stream aggregation and full trace/span graph remain separate | done: focused correlation suite `73 passed in 1.45s`; exact tracked manifest `1237 passed, 1 skipped in 249.77s` across 107 tracked test files; Black/Ruff/changed-boundary mypy/compile/diff/doctor pass; clean archive build/Twine exit 0, sdist `491` entries with ADR-047 and Slice 101 files, workspace-only audit zero; no publication |
| 102 | Versioned evaluation fixtures and optional judge contract | Chief Architect / Backend / Security / QA / Release | `docs/adr/048-*`, `maple/autonomy/evaluation.py`, autonomy/top-level exports, evaluation regressions, API/README/parity docs, changelog, QA/review evidence | Bounded `fixture_version` and trajectory expectations, redacted `EvalObservation` judge input, typed score/decision/rationale, per-case judge error isolation, deterministic baseline preservation, static/package/doctor gates; provider orchestration, calibration, async judges, and semantic-faithfulness claims remain separate | done: focused evaluation suite `20 passed in 0.24s` plus runner-trajectory regression; exact tracked manifest `1242 passed, 1 skipped in 242.17s` across 107 tracked test files; Black/Ruff/changed-boundary mypy/compile/diff/doctor pass; clean archive build/Twine exit 0, sdist `492` entries with ADR-048 and workspace-only audit zero; no publication |
| 103 | Durable local handoff identity and ownership transfer | Chief Architect / Backend / Security / QA / Release | `docs/adr/049-*`, `maple/autonomy/handoffs.py`, `maple/autonomy/tools.py`, autonomy/top-level exports, handoff/tool regressions, API/README/parity docs, changelog, QA/review evidence | Bounded hash-only records, in-memory/file atomic stores, explicit source/target ownership transitions, per-record fencing leases, sync/async optional tool integration, target failure normalization, finalization fail-closed behavior, static/package/doctor gates; remote routing, scheduling, notifications, hard cancellation, and exactly-once effects remain separate | done: focused handoff/store suite `30 passed in 0.31s`; exact tracked manifest `1248 passed, 1 skipped in 238.37s` across 108 tracked test files; Black/Ruff/changed-boundary mypy/compile/diff/doctor pass; clean archive build/Twine exit 0, sdist `495` entries with ADR-049 and workspace-only audit zero; no publication |
| 104 | Provider stream aggregation and opt-in agent chunk events | Chief Architect / Backend / Security / QA / Release | `docs/adr/050-*`, `maple/llm/provider.py`, `maple/llm/openai_provider.py`, `maple/autonomy/agent.py`, provider/agent streaming regressions, API/README/parity docs, changelog, QA/review evidence | Bounded async `LLMChunk` aggregation into `LLMResponse`, fragmented JSON tool arguments, ID/index-safe multi-tool assembly, usage/request trailers, typed stream failures, sync/async metadata-only `model.chunk` lifecycle events behind `stream_model_events=False`, static/package/doctor gates; trace/span export, remote transport, backpressure, hard cancellation, and exactly-once delivery remain separate | done: exact tracked manifest `1253 passed, 1 skipped in 260.34s` across 108 tracked test files; focused stream/autonomy coverage `54 passed in 0.61s`; Black/Ruff/changed-boundary mypy/compile/diff/doctor pass with doctor `ready=true`, all eight checks true, network false; clean final-HEAD ZIP archive build/Twine exit 0, sdist `498` entries with all 5 required public files and ADR-050 plus QA/review evidence, workspace-only audit zero; QA behavior pass, code review pass, dependency-governance veto remains, no publication |
| 105 | Bounded local trace spans and model-step linkage | Chief Architect / Backend / Observability / Security / QA / Release | `docs/adr/051-*`, `maple/autonomy/observability.py`, `maple/autonomy/agent.py`, autonomy/root exports, observability/run regressions, API/README/parity docs, changelog, QA/review evidence | Thread-safe `TraceSpan`/`SpanRecorder`, bounded/redacted flat attributes, parent/trace validation, terminal transition enforcement, retention and JSON inspection, optional sync/async model-step span linkage in chunk/response/decision metadata; hosted exporters, sampling, tool spans, remote transport, and backpressure remain separate | done: focused span/run suite `36 passed in 0.43s`; exact tracked manifest `1261 passed, 1 skipped in 260.28s` across 108 tracked test files; Black/Ruff/changed-boundary mypy/compile/diff/doctor pass; package candidate `fc39e9a` build/Twine exit 0, sdist `501` entries, required public files `5/5`, workspace-only audit `0`; QA behavior/artifact pass and code review pass; dependency-governance veto remains; no publication |
| 106 | Bounded local tool spans under model-step parents | Chief Architect / Backend / Observability / Security / QA / Release | `docs/adr/052-*`, `maple/autonomy/agent.py`, tool/run observability regressions, API/README/parity docs, changelog, QA/review evidence | Record each normal sync/async tool execution as a bounded local child span of its open model span, with redacted tool identity and outcome metadata; preserve approval/HITL behavior and run outcomes; hosted exporters, remote routing, sampling/backpressure, and exactly-once effects remain separate | done: focused tool/run/trace suite `38 passed in 0.34s`; exact tracked manifest `1263 passed, 1 skipped in 263.89s` across 108 tracked test files; Black/Ruff/changed-boundary mypy/compile/diff/doctor pass; package candidate `ccdf03d` build/Twine exit 0, sdist `504` entries, required public files `5/5`, workspace-only audit `0`; security scan found no new defect, QA behavior/artifact and code review pass; dependency-governance veto remains; no publication |
| 107 | Bounded local observability retention metrics | Chief Architect / Backend / Observability / Security / QA / Release | `docs/adr/053-*`, `maple/autonomy/events.py`, `maple/autonomy/observability.py`, event/span regressions, API/README/parity docs, changelog, QA/review evidence | Expose thread-safe snapshots of retained capacity, evictions, open spans, and subscriber counts for local buffers; keep metrics bounded, metadata-only, dependency-free, and separate from sampling/remote export | done: focused event/observability suite `30 passed in 0.25s`; exact tracked manifest `1263 passed, 1 skipped in 248.55s` across 108 tracked test files; Black/Ruff/changed-boundary mypy/compile/diff/doctor pass; security scan found no new defect, QA behavior and code review pass; package candidate `beba0f2` build/Twine exit 0, sdist `507` entries, required public files `5/5`, workspace-only audit `0`; dependency-governance veto remains; no publication |
| 108 | Local observability sampling and latency/backpressure metrics | Chief Architect / Backend / Observability / Security / QA / Release | `docs/adr/054-*`, `maple/autonomy/events.py`, `maple/autonomy/observability.py`, event/span regressions, API/README/parity docs, changelog, QA/review evidence | Add stable bounded span sampling, integer local span latency/status counters, accepted publish latency, and subscriber/exporter failure metrics; preserve metadata-only, dependency-free, non-failing observability boundaries | done: focused `32 passed in 0.27s`; tracked regression `1265 passed, 1 skipped in 203.80s`; Black/Ruff/changed-boundary mypy/compile/doctor/security review pass; clean archive package candidate `025b6a7` build/Twine exit 0, sdist `510` entries, required public files `5/5`, workspace-only audit `0`; dependency-governance veto remains; no publication |
| 109 | Durable bounded retry state for parallel workflow branches | Chief Architect / Backend / Security / QA / Release | `docs/adr/055-*`, `maple/autonomy/workflow.py`, workflow/replay regressions, API/README/parity docs, changelog, QA/review evidence | Persist per-branch retry counts and due times, retry failed branches in bounded waves with retry context, preserve deterministic merge and pause/recovery behavior, type exhaustion, keep at-least-once side-effect boundary explicit; static/package/doctor gates | done: focused `24 passed in 0.32s`; tracked regression `1267 passed, 1 skipped in 256.93s`; Black/Ruff/changed-boundary mypy/compile/diff/doctor pass; clean archive candidate `afa57d0` build/Twine exit `0`, sdist `513` entries, required public files `5/5`, workspace-only audit `0`; QA behavior/artifact and code review pass; dependency-governance veto remains; no publication |
| 110 | Bounded model/provider retry classification | Chief Architect / Backend / Security / QA / Release | `docs/adr/056-*`, `maple/llm/types.py`, `maple/llm/provider.py`, OpenAI/Anthropic adapters, autonomous agent, provider/agent regressions, API/README/parity docs, changelog, QA/review evidence | Opt-in capped sync/async retry policy, exact transient error matching, conservative provider exception classification including wrapped stream causes, metadata-only retry events, no tool replay, static/package/doctor gates | done: focused `48 passed in 0.52s`; tracked regression `1273 passed, 1 skipped in 250.94s`; Black/Ruff/changed-boundary mypy/compile/diff/doctor pass; clean archive candidate `1ff12ce` build/Twine exit `0`, sdist `516` entries, required files `6/6`, workspace-only audit `0`; QA and code/security review pass; dependency-governance veto remains; remote scheduling and circuit-integrated coordination remain separate |
| 111 | Bounded local latency percentile metrics | Chief Architect / Backend / Observability / Security / QA / Release | `docs/adr/057-*`, `maple/autonomy/events.py`, `maple/autonomy/observability.py`, event/observability regressions, API/README/parity docs, changelog, QA/review evidence | Bounded integer sample rings, deterministic p50/p95/p99 metrics for event publish and terminal spans, empty/capacity behavior, preservation of existing counters, static/package/doctor gates | done: focused `51 passed in 0.41s`; tracked regression `1273 passed, 1 skipped in 255.46s`; Black/Ruff/changed-boundary mypy/compile/diff/doctor pass; clean archive candidate `0ac263b` build exit `0`, Twine wheel/sdist `PASSED`, sdist `519` entries, required files `6/6`, workspace-only audit `0`; QA and code/security review pass; dependency-governance veto remains; remote aggregation, dashboards, and exporter delivery remain separate |

| 112 | Bounded authenticated workflow HTTP transport | Chief Architect / Backend / Security / QA / Release | `docs/adr/058-*`, `maple/autonomy/server.py`, autonomy exports, server/client regressions, API/README/parity docs, changelog, QA/review evidence | Dependency-free `RunClient` for health/run/resume/inspection, request/path/response bounds, typed transport errors, optional constant-time bearer authentication, loopback-only server compatibility, static/package/doctor gates | done: focused `7 passed in 3.77s`; tracked regression `1276 passed, 1 skipped in 255.31s`; Black/Ruff/changed-boundary mypy/compile/diff/doctor pass; clean archive candidate `c7fe5bd` build exit `0`, Twine wheel/sdist `PASSED`, sdist `522` entries, required files `6/6`, workspace-only audit `0`; QA and code/security review pass; dependency-governance veto remains; TLS termination, token issuance, tenancy, remote scheduling, streaming delivery, and exactly-once effects remain separate |

| 113 | Bounded HTTP event exporter | Chief Architect / Backend / Observability / Security / QA / Release | `docs/adr/059-*`, `maple/autonomy/events.py`, autonomy exports, event regressions, API/README/parity docs, changelog, QA/review evidence | Dependency-free synchronous POST of redacted `AgentEvent` envelopes, HTTPS for authenticated/non-loopback delivery, bearer-header safety, request/response/time bounds, no retry or persistence, exporter failure isolation, static/package/doctor gates | done: focused `22 passed in 4.46s`; fixed non-finite timeout review finding in `d26973f`; tracked regression `1279 passed, 1 skipped in 212.83s`; Black/Ruff/changed-boundary mypy/compile/diff pass; clean archive candidate `b4e7167` build exit `0`, Twine wheel/sdist `PASSED`, sdist `525` entries, required files `6/6`, workspace-only audit `0`; QA and code review pass; dependency-governance veto remains; batching, durable replay, fleet aggregation, hosted trace search, and exactly-once delivery remain separate |

| 114 | Bounded authenticated human-input transport | Chief Architect / Backend / Security / QA / Release | `docs/adr/060-*`, `maple/autonomy/server.py`, autonomy exports, server/interaction regressions, API/README/parity docs, changelog, QA/review evidence | Optional `HumanInputStore` on the bounded loopback `RunServer`; authenticated list/inspect/respond/reject/continue/consume routes with `RunClient`; existing schema, actor authorization, notification, lease, and one-time-consume semantics preserved; request/response/path bounds; no hosted identity, TLS termination, automatic scheduling, or exactly-once side-effect claim | done: focused `19 passed in 5.17s`; auth-required hardening in `d41c65a`; tracked regression `1283 passed, 1 skipped in 275.08s`; Black/Ruff/changed-boundary mypy/compile/diff pass; clean archive candidate `b8a252a` build exit `0`, Twine wheel/sdist `PASSED`, sdist `528` entries, required files `6/6`, workspace-only audit `0`; QA and code review pass; dependency-governance veto remains; hosted identity/deployment, remote scheduling, and exactly-once effects remain separate |
| 115 | Composable bounded sub-workflows | Chief Architect / Backend / Security / QA / Release | `docs/adr/061-*`, `maple/autonomy/workflow.py`, workflow/replay regressions, API/README/parity docs, changelog, QA/review evidence | Parent nodes can run child workflows with explicit bounded input/output state maps; child interruption propagates and resumes through the child store; completed child work is reused after parent journal recovery; malformed maps, missing keys, child failures, and store boundaries fail closed; static/package/doctor gates; distributed routing/scheduling and exactly-once effects remain separate | done: focused `31 passed in 4.62s`; tracked regression `1290 passed, 1 skipped in 234.57s`; Black/Ruff/changed-boundary mypy/compile/diff/doctor pass; clean archive candidate `338650a` build/Twine exit `0`, wheel/sdist `PASSED`, sdist `531` entries, required files `6/6`, workspace-only audit `0`, wheel `104` entries and no-dependency smoke pass; QA and code review pass; dependency-governance veto remains; remote routing/distributed scheduling and exactly-once effects remain separate |

| 116 | Bounded agent tool-result replay | Chief Architect / Backend / Security / QA / Release | `docs/adr/062-*`, `maple/autonomy/agent.py`, `maple/autonomy/tools.py`, agent-run regressions, API/README/parity docs, changelog, QA/review evidence | Explicit `Tool(replay_policy="reuse_success")` opt-in; existing bounded in-memory/file execution journal reused for successful sync/async tool results; deterministic identity excludes regenerated provider call IDs; malformed journal and persistence failures are typed; approval/human-input tools excluded; at-least-once/effect caveat remains; static/package/doctor gates | done: focused `47 passed in 3.11s`; tracked regression `1294 passed, 1 skipped in 226.93s`; Black/Ruff/changed-boundary mypy/compile/diff/doctor pass; clean archive candidate `6224003` builds wheel/sdist, Twine checks `PASSED`, sdist `532` entries, required files `6/6`, wheel `104` entries and no-dependency smoke pass; QA and code review pass; dependency-governance veto remains; remote routing/distributed scheduling and exactly-once effects remain separate |
| 117 | Bounded host-supplied session compaction | Chief Architect / Backend / Security / QA / Release | `docs/adr/063-*`, `maple/autonomy/sessions.py`, autonomy exports, session regressions, API/README/parity docs, changelog, QA/review evidence | Optional `SessionCompactionStore` on built-in memory/file stores; explicit provider-neutral summary plus retained recent tail; optimistic version check; atomic bounded mutation; invalid/no-op/oversized/stale requests fail closed; no automatic LLM summarization; static/package/doctor gates | done: focused `10 passed in 4.88s`; autonomy regression `335 passed in 6.94s`; tracked regression `1297 passed, 1 skipped in 228.90s`; Black/Ruff/changed-boundary mypy/compile/diff/doctor pass; clean archive candidate `889c476` builds wheel/sdist, Twine checks `PASSED`, sdist `535` entries, required files `6/6`, wheel `104` entries and no-dependency smoke pass; QA and code review pass; dependency-governance veto remains; automatic/token-aware summarization, broader trace replay, and cross-process session leases remain separate |

| 118 | Bounded authenticated agent-run transport | Chief Architect / Backend / Security / QA / Release | `docs/adr/064-*`, `maple/autonomy/server.py`, autonomy exports, server/client regressions, API/README/parity docs, changelog, QA/review evidence | Optional host-owned `AgentRegistry` and dependency-free `RunClient.run_agent(...)` route with bounded task/context/session/run inputs, bearer authentication, typed JSON-safe `AgentRun` envelopes, identity binding, and handler exception redaction; no retries, remote persistence, cancellation, scheduling, or exactly-once effects | done: focused `14 passed in 5.68s`; autonomy `338 passed in 7.52s`; tracked `1300 passed, 1 skipped in 212.14s`; Black/Ruff/changed-boundary mypy/compile/diff/doctor pass; clean archive candidate `a6e3575` build/Twine exit `0`, sdist `538` entries, required files `6/6`, wheel `104` entries, no-dependency export smoke pass; QA and code review pass; environment-wide dependency-governance veto remains; remote durable handoff remains separate |
| 119 | Bounded authenticated handoff transport | Chief Architect / Backend / Security / QA / Release | `docs/adr/065-*`, `maple/autonomy/server.py`, autonomy exports, server/client regressions, API/README/parity docs, changelog, QA/review evidence | Optional host-owned `HandoffStore` and dependency-free authenticated routes for digest-only create/inspect/list/accept/complete/fail transitions; existing store validation, ownership, terminal state, and file fencing remain authoritative; no raw payload delivery, principal scopes, retries, scheduling, or exactly-once effects | done: focused `16 passed in 6.24s`; autonomy `340 passed in 9.27s`; tracked `1302 passed, 1 skipped in 214.52s`; Black/Ruff/changed-boundary mypy/compile/diff/doctor pass; clean archive candidate `cafff3c` build/Twine exit `0`, sdist `541` entries, required files `6/6`, wheel `104` entries, no-dependency export smoke pass; QA and code review pass; environment-wide dependency-governance veto remains; remote payload delivery and principal scopes remain separate |
| 120 | Bounded authenticated durable agent-run inspection and resume | Chief Architect / Backend / Security / QA / Release | `docs/adr/066-*`, `maple/autonomy/server.py`, autonomy exports, server/client regressions, API/README/parity docs, changelog, QA/review evidence | Optional `AgentRunStore` checkpoint summaries omit messages/reasoning trace; explicit `AgentRunResumeHandler` callback enables authenticated resume; agent identity is checked, callback results use the existing JSON-safe envelope, and missing store/callback/cross-agent run fail closed; no scheduler, cancellation, retries, principal scopes, remote aggregation, or exactly-once effects | done: focused `18 passed in 10.19s`; autonomy `342 passed in 14.06s`; tracked `1304 passed, 1 skipped in 224.03s`; Black/Ruff/changed-boundary mypy/compile/diff/doctor pass; clean archive candidate `9d1d7aa` build/Twine exit `0`, sdist `505` entries, required files `6/6`, wheel `104` entries, no-dependency export smoke pass; QA and code review pass; environment-wide dependency-governance veto remains; scheduling, cancellation, retries, principal scopes, remote aggregation, and exactly-once effects remain separate |

| 121 | Bounded authenticated event ingestion into a host-owned stream | Chief Architect / Backend / Security / Observability / QA / Release | `docs/adr/067-*`, `maple/autonomy/server.py`, server/client regressions, API/README/parity docs, changelog, QA/review evidence | Optional authenticated `RunServer(event_stream=...)` route accepts one bounded event at a time; `RunClient.publish_event(...)` and existing `HttpEventExporter` round-trip through host-assigned local sequence/timestamp values and the stream's redaction/size boundary; absent stream, malformed fields, unauthorized calls, and invalid payloads fail closed; no batching, durable replay, fleet aggregation, or remote trace search | done: combined event/server suite `36 passed in 10.07s`; autonomy `345 passed in 11.94s`; exact tracked manifest `1307 passed, 1 skipped in 213.45s` across 108 tracked Python test files; Black/Ruff/changed-boundary mypy/compile/diff/doctor pass; clean archive candidate `0ca0924` build/Twine exit `0`, sdist `547` entries, required public files `6/6`, wheel `104` entries, no-dependency event transport smoke pass; QA and code review pass; environment-wide dependency-governance veto remains; batching, durable replay, fleet aggregation, remote trace search, principal scopes, and exactly-once delivery remain separate |
| 122 | Bounded authenticated event inspection by cursor | Chief Architect / Backend / Security / Observability / QA / Release | `docs/adr/068-*`, `maple/autonomy/server.py`, server/client regressions, API/README/parity docs, changelog, QA/review evidence | Authenticated `GET /v1/events?after=<sequence>&limit=<limit>` reads the existing redacted host-owned ring through serializable cursor batches; strict query validation, a `1,000` remote batch cap, explicit retention-gap errors, and bounded response behavior remain authoritative; no durable replay, batching, remote search, fleet aggregation, or exactly-once delivery | done: combined event/server suite `37 passed in 10.68s`; autonomy `346 passed in 12.57s`; exact tracked manifest `1308 passed, 1 skipped in 226.26s` across 108 tracked Python files; Black/Ruff/changed-boundary mypy/compile/diff pass; clean archive candidate `3642805` build/Twine exit `0`, sdist `550` entries, required files `6/6`, wheel `104` entries, no-dependency event inspection smoke pass; QA and code review pass; environment-wide dependency-governance veto remains; durable replay, batching, remote search, fleet aggregation, principal scopes, and exactly-once delivery remain separate |

| 123 | Bounded authenticated host-owned agent-run cancellation | Chief Architect / Backend / Security / QA / Release | `docs/adr/069-*`, `maple/autonomy/server.py`, autonomy/root exports, server regressions, API/README/parity docs, changelog, QA/review evidence | Optional `cancel_handler` callback and authenticated `POST /v1/agents/<agent_id>/runs/<run_id>/cancel`; validated IDs, typed `cancelled` `AgentRun` envelope, redacted callback errors, missing-capability `501`, and existing loopback/auth/body bounds; cooperative request only, with token propagation, checkpoint mutation, hard termination, scheduling, retries, principal scopes, and exactly-once effects remaining host-owned | done: feature commit `8ec56bb`; focused server suite `23 passed in 9.78s`; full autonomy `347 passed in 16.99s`; exact tracked manifest `1309 passed, 1 skipped in 236.70s` across 108 tracked Python test files; isort/Black/Ruff/changed-boundary mypy/compile/diff pass; wheel/sdist build and Twine checks pass, wheel `104` entries, sdist `562` entries, isolated no-dependency export smoke pass; QA and code/security review pass; declared-project audit reports no known vulnerabilities; environment-wide dependency-governance veto remains; hard termination, durable cancellation state, scheduling, retries, principal scopes, and exactly-once effects remain separate |

| 124 | Provider-neutral bounded retrieval reranking seam | Chief Architect / Backend / Security / QA / Release | `docs/adr/070-*`, `maple/autonomy/retrieval.py`, autonomy/root exports, retrieval regressions, API/README/parity docs, changelog, QA/review evidence | Host-supplied `RetrievalReranker.score(...)` can rerank bounded lexical or vector hits while preserving source references and original scores; candidate type/ID/uniqueness/score validation, finite callback scores, deterministic ties, redacted failures, and no implicit provider/network behavior | done: feature commit `aeb80bd`; focused retrieval suite `12 passed in 0.07s`; autonomy `349 passed in 16.38s`; exact tracked manifest `1311 passed, 1 skipped in 230.15s` across 108 tracked Python test files; isort/Black/Ruff/changed-boundary mypy/compile/diff pass; wheel/sdist build and Twine checks pass, wheel `104` entries, sdist `565` entries, isolated no-dependency export smoke pass; QA and code/security review pass; declared-project audit reports no known vulnerabilities; environment-wide dependency-governance veto remains; document connectors, managed stores, and semantic evaluation remain separate |

| 125 | Bounded document connector and ingestion contract | Chief Architect / Backend / Security / QA / Release | `docs/adr/071-*`, `maple/autonomy/retrieval.py`, autonomy/root exports, retrieval regressions, API/README/parity docs, changelog, QA/review evidence | Host-owned cursor connector pages feed an explicit document sink; page/document/batch quotas, document/source validation, duplicate-ID and cursor-progress checks, bounded progress reporting, redacted connector/sink failures, and no implicit network/retry/transaction/rollback behavior | done: feature commit `0ea1084`; focused retrieval suite `18 passed in 0.07s`; full autonomy `355 passed in 16.97s`; exact tracked manifest `1317 passed, 1 skipped in 229.72s` across 108 tracked Python test files; isort/Black/Ruff/changed-boundary mypy/compile/diff pass; wheel/sdist build and Twine checks pass, wheel `104` entries, sdist `568` entries, isolated no-dependency export smoke pass; declared-project audit reports no known vulnerabilities; QA and code/security review pass; environment-wide dependency-governance veto remains; durable cursor checkpoints, managed-store adapters, connector rate limits, retries, transactions, rollback, and semantic evaluation remain separate |
| 126 | Bounded durable approval-outcome replay | Chief Architect / Backend / Security / QA / Release | `docs/adr/072-*`, `maple/autonomy/approval.py`, `maple/autonomy/agent.py`, approval/run regressions, API/README/parity docs, changelog, QA/review evidence | Built-in approval stores persist one bounded terminal tool outcome after a consumed approval; repeated execution and durable sync/async run resume replay the stored outcome without invoking the handler again; malformed/oversized outcomes, record conflicts, missing optional recorder capability, and consumed-without-outcome crash windows fail closed; external side effects remain at-least-once and no exactly-once claim is made | done: feature commit `8ea5b6d`; focused approval/run/agent suite `66 passed in 0.43s`; autonomy suite `359 passed in 15.24s`; exact tracked manifest `1321 passed, 1 skipped in 231.38s` across 108 tracked Python test files; isort/Black/Ruff/changed-boundary mypy/compile/diff pass; clean `git archive HEAD` `1.1.3` wheel/sdist build and Twine checks exit `0`, wheel `104` entries, sdist `564` entries with zero workspace-only files, isolated clean-archive no-dependency approval replay export smoke pass; QA and code/security review pass; declared-project pip-audit reports no known vulnerabilities; environment-wide dependency-governance veto remains; distributed transactions, remote approval transport, sandboxing, scheduling, and exactly-once effects remain separate |
| 127 | Authenticated bounded remote approval control transport | Chief Architect / Backend / Security / QA / Release | `docs/adr/073-*`, `maple/autonomy/server.py`, approval/server regressions, API/README/parity docs, changelog, QA/review evidence | Optional authenticated `RunServer`/`RunClient` routes list and inspect bounded approvals and record approve/deny decisions with optional bounded edited arguments; the existing `ApprovalStore` remains authoritative; transport never consumes or executes an approval and makes no hosted identity, scheduling, notification, tenancy, or exactly-once claim | done: feature commit `3b0121c`; focused server suite `26 passed in 11.38s`; autonomy suite `362 passed in 14.29s`; exact tracked manifest `1324 passed, 1 skipped in 253.70s` across 108 tracked Python test files; isort/Black/Ruff/changed-boundary mypy/compile/diff pass; clean `git archive HEAD` `1.1.3` wheel/sdist build and Twine checks exit `0`, wheel `104` entries, sdist `567` entries with zero workspace-only files, isolated clean-archive no-dependency approval transport export smoke pass; QA and code/security review pass; declared-project pip-audit reports no known vulnerabilities; environment-wide dependency-governance veto remains; hosted identity, notifications, scheduling, tenancy, sandboxing, and exactly-once effects remain separate |
| 128 | Bounded durable event journal and restart replay | Chief Architect / Backend / Observability / Security / QA / Release | `docs/adr/074-*`, `maple/autonomy/events.py`, event/server regressions, API/README/parity docs, changelog, QA/review evidence | Optional host-owned `FileEventJournal` persists redacted bounded events through atomic JSON replacement and fencing leases; `EventStream` rehydrates the retained window and cursor sequence after restart; malformed/oversized/non-monotonic records fail closed; no unbounded log, multi-writer allocator, remote aggregation, or exactly-once delivery claim | done: feature commit `f30ae25`; fail-closed timestamp fix `032429f`; evidence normalization `2ae4a9c`; QA/review normalization `3409f39`; focused event suite `20 passed in 0.78s`; exact tracked manifest `1329 passed, 1 skipped in 270.82s` across 108 tracked Python test files; isort/Black/Ruff/changed-boundary mypy/compile/diff pass; clean `git archive HEAD` `1.1.3` wheel/sdist build and Twine checks exit `0`, wheel `104` entries, sdist `570` entries with zero workspace-only files, isolated no-dependency event-journal export smoke pass; declared-project pip-audit reports no known vulnerabilities; QA and code/security review pass; remote aggregation, batching, hosted tracing, and exactly-once delivery remain separate |
| 129 | Bounded authenticated event batch transport | Chief Architect / Backend / Interoperability / Security / Observability / QA / Release | `docs/adr/075-*`, `maple/autonomy/server.py`, server/client event regressions, API/README/parity docs, changelog, QA/review evidence | Authenticated `POST /v1/events/batch` and `RunClient.publish_events(...)` accept 1–100 existing event envelopes, preserve request order and stream-owned redaction/sequence semantics, and return bounded per-item published/failed results; malformed batch structure fails before attempts; partial success, no retry/deduplication, and no durable remote queue or exactly-once claim are explicit | done: feature commit `c542828`; focused server/event suite `50 passed in 21.58s`; exact tracked manifest `1333 passed, 1 skipped in 284.61s` across `108` tracked Python test files; Black/isort/Ruff/changed-boundary mypy/compile/diff/secret/dangerous-construct gates passed; clean feature archive `c542828` built `1.1.3` wheel/sdist with exit `0`, Twine checks `PASSED`, wheel `104` entries, sdist `571` entries, and isolated no-dependency event-journal smoke passed; final closure archive `ab9d2e6` built with exit `0`, Twine checks `PASSED`, wheel `104` entries, sdist `573` entries, and no-dependency event batch/journal smoke passed; QA and code review filed; declared-project pip-audit reported no known vulnerabilities; environment-wide dependency-governance veto remains; durable remote replay, aggregation, backpressure, hosted tracing, and exactly-once effects remain separate |
| 130 | Bounded durable event forwarding and remote aggregation | Chief Architect / Backend / Interoperability / Security / Observability / QA / Release | `docs/adr/076-*`, `maple/autonomy/events.py`, autonomy/root exports, event regressions, API/README/parity docs, changelog, QA/review evidence | Opt-in `EventForwarder` reads at most 100 retained events, sends them through an authenticated `HttpEventBatchSender`, and persists only the contiguous acknowledged prefix through an in-memory or atomic fenced `FileEventCursorStore`; cursor expiry, malformed acknowledgements, transport errors, and cursor-save failures fail closed; duplicate sends remain possible and no implicit retry, remote queue, ordering across forwarders, or exactly-once effect claim is made | done: feature commit `9e74115`; focused event suite `31 passed in 2.70s`; event/server suite `61 passed in 15.24s`; exact tracked manifest `1344 passed, 1 skipped in 245.95s` across `108` tracked Python test files; Black/isort/Ruff/changed-boundary mypy/compile/diff/secret/dangerous-construct gates passed; clean feature archive built with exit `0`, Twine checks `PASSED`, wheel `104` entries, sdist `574` entries, and isolated no-dependency forwarder smoke passed; final closure commit `3384c0d` archive rebuilt with exit `0`, Twine checks `PASSED`, wheel `104` entries, sdist `576` entries; QA and code review filed; declared-project pip-audit reported no known vulnerabilities; environment-wide dependency-governance veto remains; hosted scheduling, backpressure, remote deduplication, hosted aggregation/tracing, tenancy, sandboxing, and exactly-once effects remain separate |
| 131 | Bounded structured evaluation trajectories | Chief Architect / Backend / Security / QA / Release | `docs/adr/077-*`, `maple/autonomy/evaluation.py`, autonomy/root exports, evaluation regressions, API/README/parity docs, changelog, QA/review evidence | Additive `EvalTrajectoryStep` records bounded tool arguments, results, status, and duration; `EvalCase.expected_trajectory` performs exact fixture matching; reports and optional judges receive re-redacted bounded observations; name-only observations remain compatible; no generated-code execution, semantic faithfulness, trace scoring, or hosted judge orchestration claim | done: feature commit `ba2a268`; ADR normalization commit `3194c1e`; focused evaluation suite `24 passed in 0.26s`; evaluation/observability suite `44 passed in 0.40s`; exact tracked manifest `1348 passed, 1 skipped in 274.74s` across `108` tracked Python test files; Black/isort/Ruff/changed-boundary mypy/compile/diff/secret/dangerous-construct gates passed; clean archive build `build_exit=0`, Twine checks `PASSED`, wheel `104` entries, sdist `579` entries, isolated no-dependency structured-trajectory smoke passed; QA and code review filed; declared-project pip-audit reported no known vulnerabilities; environment-wide dependency-governance veto remains; async/provider-owned judges, calibration, trace scoring, semantic faithfulness, generated-code execution, and hosted evaluation remain separate |
| 132 | Bounded event-forwarder scheduling | Chief Architect / Backend / Security / QA / Release | `docs/adr/078-*`, `EventForwarderScheduler`, autonomy/root exports, event regressions, API/README/parity docs, changelog, QA/review evidence | Add an explicit opt-in local polling worker over `EventForwarder`; enforce one active tick, finite intervals, a 1–100 batch budget per tick, cooperative shutdown, typed stop timeout, and sanitized local metrics; preserve durable cursor and at-least-once semantics; no persistent queue, remote deduplication, cross-process ownership, hosted scheduling, or exactly-once claim | done: feature commit `6b2b03a`; focused event/evaluation/observability suite `79 passed in 2.67s`; exact tracked manifest `1352 passed, 1 skipped in 239.48s` across `108` tracked Python test files; Black/isort/Ruff/changed-boundary mypy/compile/diff/secret/dangerous-construct gates passed; project pip-audit reported no known vulnerabilities; clean archive build exit `0`, wheel `104` entries, sdist `580` entries, Twine checks passed, isolated no-dependency scheduler smoke passed; QA and code-review records filed; environment-wide dependency-governance veto remains; hosted scheduling, persistent queues, remote deduplication, cross-process ownership, and exactly-once effects remain separate |
| 133 | Whole-package mypy release-hardening closure | Chief Architect / Backend / QA / Release | `maple/autonomy/evaluation.py`, `workflow.py`, `server.py`, `tools.py`, `agent.py`, release plan, changelog, QA/review evidence | Preserve runtime behavior while eliminating the authoritative `mypy maple/ --ignore-missing-imports` failures through explicit `Result` narrowing, dynamic host/store boundary typing, and executor callback annotations; do not weaken CI or add inline suppressions | done: feature commit `d1765e1`; authoritative whole-package mypy `Success: no issues found in 97 source files`; focused affected suite `156 passed in 13.51s`; exact tracked manifest `1352 passed, 1 skipped in 260.68s` across `108` tracked Python test files; Black/isort/Ruff/compile/diff/security/project-audit gates passed; clean archive build exit `0`, wheel `104` entries, sdist `582` entries, Twine checks passed, isolated no-dependency scheduler smoke passed; QA and review records filed; fresh independent review and environment-wide dependency governance remain open |
| 134 | Bounded remote event deduplication | Chief Architect / Backend / Interoperability / Security / Observability / QA / Release | `docs/adr/079-*`, `InMemoryEventDeduplicationStore`, `HttpEventBatchSender`, `RunServer`/`RunClient` event transport, event/server regressions, API/README/parity docs, changelog, QA/review evidence | Opt-in authenticated receivers claim `(source_id, source_sequence)` before publication, replay matching completed redacted destination events, reject content conflicts and concurrent pending claims, and bound memory by capacity/TTL; no durable distributed deduplication or exactly-once effects | done: feature commit `ba83c84`; focused event/server suite `68 passed in 17.33s`; deduplication regressions `3 passed in 1.86s`; exact tracked manifest `1355 passed, 1 skipped in 286.95s` across `108` tracked Python test files; whole-package mypy, Black/isort/Ruff/compile/diff/secret/dangerous-construct/project-audit gates passed; clean archive build exit `0`, wheel `104` entries, sdist `585` entries, Twine checks passed, isolated no-dependency scheduler smoke passed; QA and review records filed; fresh independent review and environment-wide dependency governance remain open |
| 135 | Bounded approval trace correlation | Chief Architect / Backend / Observability / Security / QA / Release | `docs/adr/080-*`, `ApprovalRequest`, agent approval boundary, local trace/event regressions, API/README/parity docs, changelog, QA/review evidence | Persist optional bounded `trace_id`/`span_id` with durable approval requests, surface them in pending errors, and include active model-span plus pending approval identity in normal sync/async `tool.completed` metadata; no prompt/result retention or hosted trace claim | done: commit `1a756ef`; focused approval/agent suite `14 passed, 30 deselected in 1.35s`; sync/async run correlation regressions `2 passed in 0.35s`; exact tracked manifest `1357 passed, 1 skipped in 227.58s` across `108` tracked Python test files; whole-package mypy, changed-surface Black/isort/Ruff/compile/diff/source secret/source dangerous-construct/project-audit gates passed; clean archive build exit `0`, wheel `104` entries, sdist `588` entries, Twine checks passed, isolated no-dependency approval-trace smoke passed; QA and review records filed; fresh independent review and environment-wide dependency governance remain open; hosted tracing, remote trace search, principal identity, tenancy, distributed persistence, and exactly-once effects remain separate |
| 137 | Bounded durable retrieval cursor checkpoints | Chief Architect / Backend / Security / QA / Release | `docs/adr/082-*`, `DocumentCursorCheckpoint` stores, `ingest_documents`, autonomy/root exports, retrieval regressions, API/README/parity docs, changelog, QA/review evidence | Add optional host-owned in-memory or atomic file cursor checkpoints with bounded payloads, strict revision fencing, completed-stream short-circuiting, corrupt-state fail-closed behavior, and post-sink page advancement; preserve explicit at-least-once sink semantics and no managed-store, retry, transaction, rollback, network, or publication behavior | done: feature commit `39d05d6`; focused retrieval suite `23 passed in 2.81s`; exact tracked manifest `1364 passed, 1 skipped in 229.66s` across `108` tracked Python test files; whole-package mypy, changed-surface Black/isort/Ruff/compile/diff/source secret/source dangerous-construct/project-audit gates passed; clean archive build exit `0`, wheel `104` entries, sdist `596` entries, Twine checks passed, isolated no-dependency checkpoint export smoke passed; QA and review records filed; environment-wide dependency governance veto remains; managed-store adapters, connector-specific rate limits, retries, transactions, rollback, and exactly-once effects remain separate |
| 138 | Bounded connector rate limiting | Chief Architect / Backend / Security / QA / Release | `docs/adr/083-*`, `InMemoryDocumentConnectorRateLimiter`, `ingest_documents`, autonomy/root exports, retrieval regressions, API/README/parity docs, changelog, QA/review evidence | Add optional host-owned trailing-window admission control per connector with bounded call/window settings, typed retry-after denial, monotonic-clock validation, sanitized callback failures, and no hidden sleep/retry/provider selection; preserve checkpoint and connector failure semantics | done: feature commit `3e42af2`; focused retrieval suite `26 passed in 3.74s`; exact tracked manifest `1367 passed, 1 skipped in 242.36s` across `108` tracked Python test files; whole-package mypy, changed-surface Black/isort/Ruff/compile/diff/source secret/source dangerous-construct/project-audit gates passed; clean archive build exit `0`, wheel `104` entries, sdist `599` entries, Twine checks passed, isolated no-dependency rate-limiter export smoke passed; QA and review records filed; environment-wide dependency governance veto remains; managed-store adapters, provider-specific/distributed quotas, retries, sleep, queueing, and exactly-once effects remain separate |
| 139 | Bounded manager-style agent-as-tool delegation | Chief Architect / Backend / Security / QA / Release | `docs/adr/084-*`, `create_agent_tool`, autonomy/root exports, tool regressions, API/README/parity docs, changelog, QA/review evidence | Add a normal approval-by-default `Tool` for nested agent invocation that retains caller ownership, bounds task/context, requires explicit context allowlists, supports declared sync/async target methods, returns only agent/goal/status/result, and sanitizes child failures; handoff ownership, remote routing, retries, child-run replay, and exactly-once effects remain separate | done: implementation `5693545`, docs `1834789`; focused `31 passed in 2.86s`; exact tracked suite `1373 passed, 1 skipped`; whole-package mypy, Ruff, compile, diff, dependency, source-scan, archive, Twine, and wheel-import gates pass; environment-wide dependency governance remains open |
| 140 | Bounded guardrail lifecycle and trace linkage | Chief Architect / Backend / Security / Observability / QA / Release | `docs/adr/085-*`, `GuardrailEvent`/`GuardrailObserver`, `run_guardrails`, agent event stream, contract/agent regressions, API/README/parity docs, changelog, QA/review evidence | Add ordered `started`/`passed`/`rejected`/`failed` policy transitions with bounded stage/index/status and optional trace/span IDs; publish sync/async input/output lifecycle events without guarded values or raw callback errors; observer and event publication failures must not change fail-closed enforcement | done: implementation `28ee94e`; docs `3e12052`; focused `51 passed in 6.00s`; exact tracked suite `1378 passed, 1 skipped`; whole-package mypy, Black/isort/Ruff/compile/diff, project audit, source scans, clean archive, Twine, install, and export-smoke gates pass; environment-wide dependency governance remains open |
| 141 | Bounded multimodal image content and capability routing | Chief Architect / Backend / Interoperability / Security / QA / Release | `docs/adr/086-*`, `ImageContent`/`ChatContent`, provider formatters, `ProviderCapabilities.image_input`/`ProviderRequirements.image_input`, session/run persistence, LLM/provider/session regressions, API/README/parity docs, changelog, QA/review evidence | Add bounded ordered text/image chat parts with HTTPS or validated base64 sources; format OpenAI-compatible image URLs/data URIs and Anthropic data URIs; persist sources as JSON-safe data; select image-capable providers explicitly; fail closed on unsupported forms; no fetching, execution, audio/video, transcoding, generated media, or semantic vision claim | done: implementation `8f521e4`; docs `d708416`; focused `49 passed in 0.54s`; exact tracked manifest `1384 passed, 1 skipped in 253.22s` from `1385` collected; whole-package mypy, Black/isort/Ruff/compile/diff/source scans/project audit, clean archive, Twine, install, and export-smoke gates pass; environment-wide dependency governance remains open |
| 142 | Bounded principal scopes for the local control plane | Chief Architect / Backend / Security / QA / Release | `docs/adr/087-*`, `Principal`, `RunServer` scope enforcement, server regressions, API/README/parity docs, changelog, QA/review evidence | Add immutable host-configured principal IDs and exact/family route scopes for the authenticated local control plane; authorize before body reads; preserve legacy wildcard token behavior; return bounded `403` on missing scopes; no token issuance, dynamic identity, TLS, tenancy, per-agent delivery, hosted policy, or exactly-once effects | done: implementation `dae1ebd`; docs `685110d`; focused `33 passed in 14.21s`; exact tracked manifest `1386 passed, 1 skipped in 234.74s` from `1387` collected; whole-package mypy, Black/isort/Ruff/compile/diff/source scans/project audit, clean archive, Twine, install, and export-smoke gates pass; environment-wide dependency governance remains open |
| 143 | Native async completion for built-in providers | Chief Architect / Backend / ML Engineer / QA / Release | `docs/adr/088-*`, OpenAI/Anthropic providers, provider regressions, API/README/parity docs, changelog, QA/review evidence | Add `complete_async(...)` implementations that await native optional SDK clients for OpenAI-compatible and Anthropic providers; preserve the explicit base-provider synchronous fallback when an async client is unavailable; keep formatting, usage, typed errors, retries, routing, and concurrency semantics bounded | done: implementation commits `3890643`, `cc471b0`; docs commit `5d400b6`; focused `46 passed in 0.41s`; exact tracked manifest `1389 passed, 1 skipped in 230.95s`; whole-package mypy with optional-import boundary flags, changed-surface Black/isort/Ruff, compile, diff, committed-tree source scans, clean archive, Twine, install, and export-smoke gates pass; QA and review records filed; environment-wide dependency governance remains open |
| 144 | Explicit async-completion capability routing | Chief Architect / Backend / ML Engineer / QA / Release | `docs/adr/089-*`, provider capabilities/router, capability regressions, API/README/parity docs, changelog, QA/review evidence | Add declaration-only `ProviderCapabilities.async_completion` and `ProviderRequirements.async_completion` matching; reject providers without an explicit native async declaration; do not inspect arbitrary methods or infer non-blocking behavior; no provider implementation, retry, or new dependency claim | done: implementation commit `923c24f`; docs commit `e1e8619`; focused `21 passed in 0.45s`; exact tracked manifest `1390 passed, 1 skipped in 219.74s`; whole-package mypy with optional-import boundary flags, changed-surface Black/isort/Ruff, compile, diff, committed-tree source scans, clean archive, Twine, install, and export-smoke gates pass; QA and review records filed; environment-wide dependency governance remains open |
| 145 | Bounded working-memory admission and token accounting | Chief Architect / Backend / ML Engineer / QA / Release | `docs/adr/090-*`, working-memory admission, autonomy memory regressions, API/README/parity docs, changelog, QA/review evidence | Bound budgets to 1..1,000,000 estimated tokens and 4,096 entries; validate bounded UTF-8 keys/content/relevance before mutation; reject entries that cannot fit without eviction; preserve oldest-entry eviction for accepted entries; no tokenizer dependency, summarization, automatic compaction, or managed memory | done: implementation commits `c9dfbf2`, `009955b`; docs `70423fc`; QA/review `37ac4c0`; focused `28 passed in 0.29s`; exact tracked manifest `1399 passed, 1 skipped in 238.67s`; whole-package mypy, changed-surface Black/isort/Ruff, compile, committed-range diff, targeted secret/dangerous-construct scans, clean archive, Twine, isolated install, and export-smoke gates pass; clean archive wheel `104` entries, sdist `620` entries, workspace-only entries `0`; Bandit unavailable and environment-wide pip-audit remains a veto at `384` vulnerabilities in `77` packages; automatic/token-aware summarization, managed context, persistence, and cross-process memory remain separate |
| 146 | Fail-closed memory summary archiving | Chief Architect / Backend / ML Engineer / QA / Release | `docs/adr/091-*`, `MemoryManager.summarize_and_archive`, memory regressions, API/README/parity docs, changelog, QA/review evidence | Propagate episodic persistence errors and preserve working memory until a generated summary is durably accepted; preserve existing provider-error and empty-memory behavior; make no cross-store transaction, retry, summarization-quality, or managed-memory claim | done: implementation `30164e5`; docs/ADR/QA/review `0c2b416`; focused `29 passed in 0.32s`; exact tracked manifest `1400 passed, 1 skipped in 231.02s`; whole-package mypy, changed-surface Black/isort/Ruff, compile, committed-range diff, targeted secret/dangerous-construct scans, clean archive, Twine, isolated install, and memory archive export-smoke gates pass; clean archive wheel `104` entries, sdist `623` entries, workspace-only entries `0`; Bandit unavailable and environment-wide pip-audit remains a veto at `384` vulnerabilities in `77` packages; cross-store transactions, automatic summarization, managed/distributed memory, and retry policy remain separate |
| 147 | Bounded episodic-memory retention and serialized event admission | Chief Architect / Backend / ML Engineer / QA / Release | `docs/adr/092-*`, `EpisodicMemory`, autonomy memory regressions, API/README/parity docs, changelog, QA/review evidence | Bound task IDs to 256 UTF-8 bytes, serialized events to 65,536 bytes, and history to 1,024 events per task; reject invalid/oversized records before store writes; propagate store/state errors; retain newest accepted events; no distributed global quota, semantic indexing, summarization, retries, or cross-store transaction claim | done: implementation `2fe0056`; docs/ADR/QA/review `e59b7d3`; focused `38 passed in 0.28s`; exact tracked manifest `1409 passed, 1 skipped in 241.21s`; whole-package mypy, changed-surface Black/isort/Ruff, compile, committed-range diff, targeted secret/dangerous-construct scans, clean archive, Twine, isolated install, and episodic-memory export-smoke gates pass; clean archive wheel `104` entries, sdist `626` entries, workspace-only entries `0`; Bandit unavailable and environment-wide pip-audit remains a veto at `384` vulnerabilities in `77` packages; distributed quotas, semantic indexing, automatic summarization, retries, and cross-store transactions remain separate |
| 148 | Fail-closed episodic search bounds and error propagation | Chief Architect / Backend / QA / Release | `docs/adr/093-*`, `EpisodicMemory.search`, autonomy memory regressions, API/README/parity docs, changelog, QA/review evidence | Bound queries to 4,096 UTF-8 bytes and limits to 1..1,000; reject invalid caller input; propagate state list/read failures; reject malformed stored histories; preserve successful local keyword matching; no semantic index, distributed search, or retry claim | done: implementation `3669575`; docs/ADR/QA/review `90a35cf`; focused `49 passed in 0.29s`; exact tracked manifest `1420 passed, 1 skipped in 232.51s`; whole-package mypy, changed-surface Black/isort/Ruff, compile, committed-range diff, targeted secret/dangerous-construct scans, clean archive, Twine, isolated install, and episodic-search export-smoke gates pass; clean archive wheel `104` entries, sdist `629` entries, workspace-only entries `0`; Bandit unavailable and environment-wide pip-audit remains a veto at `384` vulnerabilities in `77` packages; semantic indexes, distributed search, retries, and automatic repair remain separate |
| 149 | Bounded global task-queue admission and stale-entry lifecycle | Chief Architect / Backend / Security / QA / Release | `docs/adr/094-*`, `TaskQueue`, task-management regressions, API/README/parity docs, changelog, QA/review evidence | Validate `max_queue_size` as an integer from `1` through `100,000`; enforce one guarded queued-item budget across all priorities; discard cancelled/completed stale tuples before assignment; reject capacity-full requeues before task-state mutation; preserve local in-process semantics with no durable/distributed scheduler claim | done: implementation `8e9077e`; docs/ADR/QA/review `0fe3a45`, closure `b95a921`; focused queue/scheduler suite `42 passed in 0.89s`; full tracked task-management suite `142 passed in 22.28s`; full tracked repository manifest `1375 passed, 1 skipped in 234.42s`; mypy, implementation Black/isort, Ruff, compile, feature-surface diff, clean archive, Twine, install, and task-queue export-smoke gates pass; final clean archive wheel `104` entries, sdist `632` entries, workspace-only entries `0`; Bandit unavailable and environment-wide pip-audit remains a veto at `384` vulnerabilities in `77` packages; untracked Doctrine harness aggregate stalled and was interrupted; distributed queues, hosted scheduling, and exactly-once effects remain separate |
| 150 | Lifecycle-safe local scheduler assignment and rollback | Chief Architect / Backend / Security / QA / Release | `docs/adr/095-*`, `TaskQueue.assign_task`, `TaskScheduler`, scheduler lifecycle regressions, API/README/parity docs, changelog, QA/review evidence | Atomically claim queued or freshly dequeued tasks for one agent; reject duplicate/terminal/empty-owner assignment; route scheduler assignment failures through physical `FAILED` -> bounded `requeue_task()` admission; preserve local retry and no durable/distributed scheduler claim | done: implementation `a1dc952`; focused scheduler lifecycle suite `31 passed in 1.36s`; task-management suite `146 passed in 22.25s`; docs/ADR/QA/review `c5e8b0b`, `d322878`; exact repository manifest, security/static/package gates, and final archive evidence complete |
| 151 | Fail-fast bounded `SchedulingPolicy` validation | Chief Architect / Backend / Security / QA / Release | `docs/adr/096-*`, `SchedulingPolicy`, scheduler policy regressions, API/README/parity docs, changelog, QA/review evidence | Reject unknown strategy names, non-boolean flags, non-integer or out-of-range agent concurrency, and non-finite or unsafe scheduling intervals during policy construction; keep local finite bounds and preserve the existing scheduler strategy branches; no dynamic strategy plugins, retry engine, durable policy store, distributed policy coordination, or hosted administration claim | done: implementation `1fefdc2`; docs/ADR/QA/review `5fe0efb`; focused scheduler/policy suite `43 passed in 1.37s`; full tracked task-management suite `158 passed in 22.24s`; full tracked repository manifest `1391 passed, 1 skipped in 218.01s`; mypy, Black/isort/Ruff, compile, diff, targeted secret/dangerous-construct scans, clean archive, Twine, install, and scheduler-policy export-smoke gates pass; clean archive wheel `104` entries, sdist `640` entries, workspace-only entries `0`; Bandit unavailable and environment-wide pip-audit remains a veto at `384` vulnerabilities in `77` packages; dynamic plugins, retry execution, durable/distributed policy, hosted administration, and publication remain separate |
| 152 | Ownership-checked local task completion | Chief Architect / Backend / Security / QA / Release | `docs/adr/097-*`, `TaskQueue.complete_task`, `TaskScheduler.task_completed`, scheduler/task-queue regressions, API/README/parity docs, changelog, QA/review evidence | Require the recorded agent to complete an `ASSIGNED` or `RUNNING` task through the queue lock; record `COMPLETED` and an optional result before releasing scheduler assignment/load; reject missing, empty-owner, wrong-owner, and terminal acknowledgements without mutation; preserve local semantics with no worker heartbeat, durable/distributed ownership, crash reconciliation, or exactly-once external-effect claim | done: implementation `a302c3a`; docs/ADR/QA/review `7e08592`; focused scheduler/task-queue suite `68 passed in 1.96s`; full tracked task-management suite `161 passed in 22.27s`; full tracked repository manifest `1394 passed, 1 skipped in 221.40s`; mypy, Black/isort/Ruff, compile, diff, targeted secret/dangerous-construct scans, clean archive, Twine, install, and task-completion export-smoke gates pass; clean archive wheel `104` entries, sdist `643` entries, workspace-only entries `0`; Bandit unavailable and environment-wide pip-audit remains a veto at `384` vulnerabilities in `77` packages; worker heartbeats, durable/distributed ownership, crash reconciliation, hosted scheduling, and exactly-once effects remain separate |
| 153 | Atomic local task reassignment for scheduler rebalancing | Chief Architect / Backend / Security / QA / Release | `docs/adr/098-*`, `TaskQueue.reassign_task`, `TaskScheduler.rebalance_loads`, scheduler/reassignment regressions, API/README/parity docs, changelog, QA/review evidence | Transfer only `ASSIGNED` work from the recorded current owner to a different destination under the queue lock; reject empty/equal/wrong/stale owners, `RUNNING`, and terminal tasks without mutation; update scheduler load maps only after accepted transfer; preserve local semantics with no worker heartbeat, distributed rebalancing, durable ownership, crash reconciliation, or exactly-once effect claim | done: implementation `5f2bce1`; docs/ADR/QA/review `3c34a7c`; focused scheduler/reassignment suite `70 passed in 1.97s`; full tracked task-management suite `163 passed in 22.26s`; full tracked repository manifest `1396 passed, 1 skipped in 251.10s`; mypy, Black/isort/Ruff, compile, diff, targeted secret/dangerous-construct scans, clean archive, Twine, install, and task-reassignment export-smoke gates pass; clean archive wheel `104` entries, sdist `646` entries, workspace-only entries `0`; Bandit unavailable and environment-wide pip-audit remains a veto at `384` vulnerabilities in `77` packages; worker heartbeats, distributed rebalancing, durable ownership, crash reconciliation, hosted scheduling, and exactly-once effects remain separate |
| 154 | Atomic scheduler capacity admission and reservation rollback | Chief Architect / Backend / Security / QA / Release | `docs/adr/099-*`, `TaskScheduler` capacity reservation, scheduler concurrency regressions, API/README/parity docs, changelog, QA/review evidence | Reserve one per-agent slot under the scheduler lock before `TaskQueue.assign_task`; reject at-capacity agents; release the lock before queue callbacks; roll back reservations on rejected/raised claims; preserve queue ownership authority and local-only semantics with no distributed quota, worker heartbeat, durable reservation, or exactly-once effect claim | done: implementation `4ded373`; docs/ADR/QA/review `adf42ad`; focused scheduler/capacity suite `71 passed in 2.35s`; full tracked task-management suite `164 passed in 23.18s`; full tracked repository manifest `1397 passed, 1 skipped in 270.61s`; mypy, Black/isort/Ruff, compile, diff, targeted secret/dangerous-construct scans, clean archive, Twine, install, and scheduler-capacity export-smoke gates pass; clean archive wheel `104` entries, sdist `649` entries, workspace-only entries `0`; Bandit unavailable and environment-wide pip-audit remains a veto at `384` vulnerabilities in `77` packages; distributed quota, worker heartbeat, durable reservation, hosted scheduling, and exactly-once effects remain separate |
| 155 | Ownership-checked local task failure acknowledgement | Chief Architect / Backend / Security / QA / Release | `docs/adr/100-*`, `TaskQueue.fail_task`, `TaskScheduler.task_failed`, scheduler/failure regressions, API/README/parity docs, changelog, QA/review evidence | Require the recorded agent to fail an `ASSIGNED` or `RUNNING` task through the queue lock with a non-empty error of at most `8,192` UTF-8 bytes; release scheduler assignment/load only after acceptance; reject missing, empty-owner, wrong-owner, oversized-error, and terminal acknowledgements without mutation; keep retry explicit through bounded `requeue_task()` | done: implementation `6bf1d6e`; docs/ADR/QA/review `d5920ea`; focused scheduler/failure suite `74 passed in 2.02s`; full tracked task-management suite `167 passed in 22.33s`; full tracked repository manifest `1400 passed, 1 skipped in 211.56s`; mypy, Black/isort/Ruff, compile, diff, targeted secret/dangerous-construct scans, clean archive, Twine, install, and task-failure export-smoke gates pass; clean archive wheel `104` entries, sdist `652` entries, workspace-only entries `0`; Bandit unavailable and environment-wide pip-audit remains a veto at `384` vulnerabilities in `77` packages; worker heartbeats, automatic retry, durable/distributed ownership, crash reconciliation, and exactly-once effects remain separate |
| 156 | Fail-closed durable pending-request checkpoint invariants | Chief Architect / Backend / Security / QA / Release | `docs/adr/101-*`, `AgentRunCheckpoint` parsing/store normalization, run/lease regressions, API/README/parity docs, changelog, QA/review evidence | Require a `paused` checkpoint to identify exactly one pending approval or human-input record; require `running`, `completed`, and `failed` checkpoints to identify none; reject both IDs before memory/file store mutation; preserve local resume and at-least-once side-effect boundaries without claiming distributed recovery or exactly-once effects | done: implementation/docs `87952cd`; QA/review closure `3f2eb9e`; focused run/lease suite `34 passed in 0.22s`; full autonomy suite `457 passed in 18.69s`; full tracked repository manifest `1458 passed, 1 skipped in 220.84s`; whole-package mypy, changed-source Black/isort/Ruff, compile, changed-surface secret/dangerous-construct scans, clean archive, Twine, install, and invariant smoke pass; clean closure archive wheel `104` entries, sdist `655` entries, workspace-only entries `0`; environment-wide pip-audit remains a veto at `384` vulnerabilities in `77` packages; Bandit unavailable and independent fresh-session review remains open; distributed recovery, notification delivery, remote coordination, and exactly-once effects remain separate |
| 157 | Fail-closed pending-request to tool-call correlation | Chief Architect / Backend / Security / QA / Release | `docs/adr/102-*`, sync/async durable agent resume, run regressions, API/README/parity docs, changelog, QA/review evidence | Require the pending approval or human-input record's `tool_call_id` to match a persisted tool-result placeholder before waiting, consuming, replaying, or executing; return `RUN_PENDING_TOOL_MISSING` and preserve request/checkpoint state on mismatch; keep local correlation and at-least-once boundaries explicit | done: implementation/docs `807a6be`; QA/review closure `75c983d`; focused durable-run suite `36 passed in 0.41s`; full autonomy suite `461 passed in 18.90s`; full tracked repository manifest `1462 passed, 1 skipped in 244.26s`; whole-package mypy, changed-source Black/isort/Ruff, compile, changed-surface secret/dangerous-construct scans, clean archive, Twine, install, and correlation smokes pass; clean closure archive wheel `104` entries, sdist `658` entries, workspace-only entries `0`; environment-wide pip-audit remains a veto at `384` vulnerabilities in `77` packages; Bandit unavailable and independent fresh-session review remains open; distributed repair, notification delivery, remote coordination, and exactly-once effects remain separate |
| 158 | Bounded durable agent-run checkpoint history | Chief Architect / Backend / Security / QA / Release | `docs/adr/103-*`, `AgentRunHistoryStore`, memory/file run stores, run regressions, API/README/parity docs, changelog, QA/review evidence | Add an optional `history()` contract with 1..10,000 retention, detached version-ordered snapshots, CAS-failure exclusion, and typed invalid-limit handling; persist file history through an atomic `.history` sidecar with identity/order/size validation and fail-closed corruption handling; keep history inspection-only with no restore, handler replay, cross-file transaction, or exactly-once claim | done: implementation `44dcc52`; retention resize fix `f0e09fc`; focused run/lease suite `43 passed in 0.46s`; full tracked repository manifest `1467 passed, 1 skipped in 223.55s`; whole-package mypy, Black/isort/Ruff, compile, changed-surface secret/dangerous-construct scans, clean archive, Twine, isolated install, and history restart/resize smokes pass; final release-tip archive built with exit `0`, Twine checks passed, exact clean archive wheel `104` entries, sdist `661` entries, and untracked workspace entries `0`; QA `docs/qa/maple-agent-runtime-slice158.md` and review `docs/reviews/maple-agent-runtime-slice158.md` filed; environment-wide pip-audit remains a veto at `384` vulnerabilities in `77` packages; Bandit unavailable and independent fresh-session review remains open; history is inspection-only and distributed replay, restore, scheduling, notification, hosted storage, and exactly-once effects remain separate |
| 159 | Authenticated remote agent-run history inspection | Chief Architect / Backend / Security / QA / Release | `docs/adr/104-*`, `maple/autonomy/server.py`, server/client regressions, API/README/parity docs, changelog, QA/review evidence | Add `GET /v1/agents/{agent_id}/runs/{run_id}/history?limit=N` over the existing authenticated `agent:read` route; enforce a 1..100 transport limit, current-run ownership, optional-history compatibility, identity validation, and metadata-only responses that omit descriptions/results/errors/messages/reasoning; remain read-only with no restore/replay/exactly-once claim | done: implementation `da72c54`; focused server/run-store suite `77 passed in 15.97s`; exact tracked manifest `1470 passed, 1 skipped in 206.15s`; changed-file Black/Ruff/isort/compile and import-isolated mypy pass; targeted secret/dangerous-construct scans are clean; review `docs/reviews/maple-agent-runtime-slice159.md` and QA `docs/qa/maple-agent-runtime-slice159.md` filed; release-tip `124ca11` build exit `0`, both Twine checks passed, isolated wheel install and packaged history smoke passed, wheel `104` entries, sdist `664` entries, source archive untracked entries `0`; repository-wide Black/isort/mypy remain baseline failures, Bandit is unavailable, and pip-audit remains a veto at `384` vulnerabilities in `77` packages; hosted/distributed retention, restore, replay, and separate history scopes remain separate |
| 160 | Cooperative native agent-run cancellation | Chief Architect / Backend / Security / QA / Release | `docs/adr/105-*`, `docs/briefs/maple-agent-runtime-slice160.md`, native sync/async ReAct loop, `Tool`/`ToolRegistry`, run checkpoints, agent tests, API/README/parity docs, changelog, QA/review evidence | Accept caller-owned `CancellationToken` on sync/async pursue/resume APIs; stop future model/tool/reflection turns; propagate cancellation to executor-backed tools; persist active durable runs as terminal `cancelled` without pending IDs; preserve paused pending interactions before resolution; emit bounded `run.cancelled`; fail closed on invalid token values; retain cooperative/no-hard-kill and at-least-once effect boundaries | done: implementation `cfa3fa6`; approved-tool propagation fix `ed82f76`; focused `128 passed in 0.82s`; final tracked manifest `1482 passed, 1 skipped in 228.90s`; review `docs/reviews/maple-agent-runtime-slice160.md` and QA `docs/qa/maple-agent-runtime-slice160.md` filed; changed-boundary mypy, Black/isort/Ruff, compile, targeted secret/dangerous-construct scans pass; exact candidate `35816ac` package gate passed with build/Twine/isolated install/import; clean git-archive source `754` entries, wheel `104` entries, sdist `668` entries, workspace-only entries `0`; whole-package baseline Black/isort/mypy debt, unavailable Bandit, and environment-wide pip-audit veto remain documented; no publication, deployment, cloud action, or website update performed |
| 161 | Cooperative cancellation through local agent delegation | Chief Architect / Backend / Security / QA / Release | `docs/adr/106-*`, `docs/briefs/maple-agent-runtime-slice161.md`, `Tool`, `create_agent_tool`, `create_handoff_tool`, delegation tests, API/README/parity docs, changelog, QA/review evidence | Pass an exact parent `CancellationToken` to opt-in non-executor handlers and signature-compatible sync/async child targets; reject executor plus handler-injection configuration; preserve legacy targets; finalize cancelled durable handoffs as failed rather than completed; retain cooperative/no-hard-kill and at-least-once boundaries | done: implementation `ae8855a`; docs/review/QA candidate `0cb1622`; focused delegation/tool suite `49 passed in 0.30s`; full autonomy `490 passed in 20.47s`; exact tracked manifest `1491 passed, 1 skipped in 221.72s`; changed-boundary and whole tracked static/security gates pass; clean archive candidate `0cb1622` built wheel `104` entries and sdist `672` entries, Twine passed, isolated import passed, source archive `758` entries, untracked archive entries `0`; review `docs/reviews/maple-agent-runtime-slice161.md` and QA `docs/qa/maple-agent-runtime-slice161.md` filed; no publication, deployment, cloud action, or website update performed |
| 162 | Opt-in local replay for agent-as-tool results | Chief Architect / Backend / Security / QA / Release | `docs/adr/107-*`, `docs/briefs/maple-agent-runtime-slice162.md`, `create_agent_tool`, existing `ExecutionJournal`, sync/async delegation regressions, API/README/parity docs, changelog, QA/review evidence | Expose `replay_policy` on `create_agent_tool` with disabled default; reuse only bounded successful child results through the parent journal at a matching durable run cursor; preserve approval exclusion, cancellation, tool-call-ID rebinding, and at-least-once effects; do not claim child-run restore or exactly-once semantics | done: implementation `6982878`; docs/review/QA candidate `cf191ad`; focused run/handoff/tool suite `96 passed in 0.52s`; full autonomy `492 passed in 20.44s`; exact tracked manifest `1493 passed, 1 skipped in 223.64s`; changed-boundary and whole tracked static/security gates pass; clean archive candidate `cf191ad` built wheel `104` entries and sdist `676` entries, Twine passed, isolated import passed, source archive `762` entries, untracked archive entries `0`; review `docs/reviews/maple-agent-runtime-slice162.md` and QA `docs/qa/maple-agent-runtime-slice162.md` filed; no publication, deployment, cloud action, or website update performed |
| 163 | Opt-in local replay for durable handoff results | Chief Architect / Backend / Security / QA / Release | `docs/adr/108-*`, `docs/briefs/maple-agent-runtime-slice163.md`, `HandoffRecord`/stores, `create_handoff_tool`, server redaction, sync/async handoff regressions, API/README/parity docs, changelog, QA/review evidence | Persist only bounded successful handoff results when explicitly enabled; address retries by explicit `handoff_id`; preserve old records, ownership fencing, cancellation, and generated-ID compatibility; keep authenticated remote handoff transport digest-only; do not claim in-flight child restore or exactly-once effects | done: implementation candidate `ad16afc`; focused `56 passed`; full autonomy `500 passed in 25.80s`; exact tracked manifest `1501 passed, 1 skipped in 228.61s`; review `docs/reviews/maple-agent-runtime-slice163.md` and QA `docs/qa/maple-agent-runtime-slice163.md` filed; changed-boundary Black/isort/Ruff/compile/mypy, whole tracked Ruff/compile, and targeted secret/dangerous-construct scans pass; Bandit unavailable and environment-wide pip-audit baseline remains documented; clean archive package gate passed with source `764`, wheel `104`, sdist `678` entries, Twine passed, isolated import passed; no publication, deployment, cloud action, or website update performed |
| 164 | Opt-in local delegated child-run lifecycle | Chief Architect / Backend / Security / QA / Release | `docs/adr/109-*`, `docs/briefs/maple-agent-runtime-slice164.md`, `create_agent_tool`, native run/resume contracts, sync/async delegation regressions, API/README/parity docs, changelog, QA/review evidence | Require an explicit bounded `child_run_id` when `persist_child_run=True`; pass it to a native child start and resume an existing running/paused child through the matching sync/async resume API; preserve default and legacy behavior, bounded context/cancellation/result handling, and local ownership; do not claim terminal child replay, remote routing, scheduling, or exactly-once effects | done: requirements `8bffd20`; implementation/public docs `21fc4bc`; review/ADR correction `fbbb4b0`; focused delegation/tool suite `106 passed in 4.34s`; full autonomy `503 passed in 26.00s`; exact tracked manifest `1504 passed, 1 skipped in 234.44s`; changed-boundary Black/isort/Ruff/compile/mypy, whole tracked Ruff/compile, and targeted secret/dangerous-construct scans pass; review `docs/reviews/maple-agent-runtime-slice164.md` and QA `docs/qa/maple-agent-runtime-slice164.md` filed; Bandit unavailable and environment-wide pip-audit run remains limited by cache/network JSON decoding with the established `384`-vulnerability, `77`-package baseline; clean file-backed archive package gate passed with source `769`, wheel `104`, sdist `683` entries, Twine passed, isolated import passed; no publication, deployment, cloud action, or website update performed |

| 165 | Authenticated remote handoff result delivery | Chief Architect / Backend / Interop / Security / QA / Release | `docs/adr/110-*`, `docs/briefs/maple-agent-runtime-slice165.md`, `RunServer`/`RunClient` handoff transport, result-scope regressions, API/README/parity docs, changelog, QA/review evidence | Attach a bounded JSON result on authenticated handoff completion and retrieve it through an explicit `handoff:result` scope; keep ordinary inspection redacted, preserve store ownership/validation/fencing, reject invalid payloads without mutation, and do not claim push retries or exactly-once effects | done: requirements/ADR `c8abb35`; implementation/docs `3de5e27`; compatibility fix `d346291`; QA/review commit `0c3dc15`; focused `100 passed in 18.40s`; exact tracked `1508 passed, 1 skipped in 223.63s`; Black/isort/Ruff/compile/mypy and targeted secret/dangerous scans pass; Bandit unavailable and environment-wide pip-audit governance veto remains documented; clean archive package gate source `774`, wheel `104`, sdist `688` entries, build/Twine/install/import all pass; no publication, deployment, cloud action, or website update performed |
| 166 | Durable receiver-side event deduplication | Chief Architect / Backend / Interop / Security / QA / Release | `docs/adr/111-*`, `docs/briefs/maple-agent-runtime-slice166.md`, file-backed event deduplication store, event regressions, package exports, README/API/parity docs, changelog, QA/review evidence | Persist bounded source claims and completed redacted destination events across local process restarts; fence concurrent operations, fail closed on malformed/conflicting/oversized state, preserve at-least-once delivery truthfulness, and do not claim distributed exactly-once effects | done: brief/ADR/plan `de56ecc`; implementation/docs `f5abe63`; verification tests `81e8dcf`; review/QA commit `72aa035`; focused events `45 passed in 4.30s`; event+server `85 passed in 22.45s`; exact tracked `1516 passed, 1 skipped in 245.98s`; Black/isort/Ruff/compile/mypy and targeted secret/danger scans pass; Gitleaks/Bandit unavailable and environment-wide pip-audit governance veto remains documented; clean archive package gate at `72aa035` source `779`, wheel `104`, sdist `693` entries, build/Twine/install/import all pass; no publication, deployment, cloud action, or website update performed |
| 167 | Authenticated remote handoff payload delivery | Chief Architect / Backend / Interop / Security / QA / Release | `docs/adr/112-*`, `docs/briefs/maple-agent-runtime-slice167.md`, `RemoteHandoffTarget`, handoff correlation plumbing, server/client/tool regressions, API/README/parity docs, changelog, QA/review evidence | Adapt bounded `RunClient.run_agent(...)` into `create_handoff_tool(...)`; forward allowlisted task/context, bind explicit local `handoff_id` to remote `run_id`, require a validated completed result, preserve local ownership/failure semantics, support sync/async callers, and fail closed without raw remote details; no retries, remote durable restore, scheduling, push delivery, or exactly-once claim | done: design `599a9f8`; implementation `aa27498`; formatting/docs `fa16c9f`/`73af546`; focused `83 passed in 19.39s`; exact tracked `1521 passed, 1 skipped`; review `docs/reviews/maple-agent-runtime-slice167.md`; QA `docs/qa/maple-agent-runtime-slice167.md`; clean archive source `721`, wheel `103`, sdist `696`, build/Twine/install/import pass; no publication, deployment, cloud action, or website update performed |
| 168 | Typed remote agent-run lifecycle | Chief Architect / Backend / Interop / Security / QA / Release | `docs/adr/113-*`, `docs/briefs/maple-agent-runtime-slice168.md`, shared remote envelope normalizer, typed `RunClient` methods, regressions, API/README/parity docs, changelog, QA/review evidence | Additive typed start/resume/cancel results over existing authenticated routes; validate identity, JSON bounds, supported statuses, and cancellation result semantics without changing raw methods or claiming remote persistence/retries/scheduling/exactly-once effects | done: design `bfbeef8`; implementation `2726fab`; docs `77b2d2b`; focused `85 passed in 19.78s`; exact tracked `1523 passed, 1 skipped`; review `docs/reviews/maple-agent-runtime-slice168.md`; QA `docs/qa/maple-agent-runtime-slice168.md`; clean archive source `726`, wheel `103`, sdist `701`, build/Twine/install/import pass; no publication, deployment, cloud action, or website update performed |
| 169 | Native autonomous-agent remote transport adapter | Chief Architect / Backend / Interop / Security / QA / Release | `docs/adr/114-*`, `docs/briefs/maple-agent-runtime-slice169.md`, `maple/autonomy/agent_transport.py`, package exports, adapter/server regressions, API/README/parity docs, changelog, QA/review evidence | Bind a caller-owned `AgentRunStore` to an `AutonomousAgent`-compatible runtime, register sanitized start/resume callbacks, preserve authenticated typed/raw transport contracts, and reject invalid native identities/statuses without checkpoint transfer or distributed exactly-once claims | done: design `c94328e`; implementation/exports `e1812f6`/`b3d8f74`; docs `abf02d6`; focused `90 passed in 20.12s`; exact tracked `1528 passed, 1 skipped`; review `docs/reviews/maple-agent-runtime-slice169.md`; QA `docs/qa/maple-agent-runtime-slice169.md`; clean archive final recheck at `abf02d6` source `733`, wheel `104`, sdist `708`, build/Twine/install/import pass; no publication, deployment, cloud action, or website update performed |
| 170 | Bounded agent capability discovery and deterministic routing | Chief Architect / Backend / Interop / Security / QA / Release | `docs/adr/115-*`, `docs/briefs/maple-agent-runtime-slice170.md`, `maple/autonomy/server.py`, adapter/package exports, server/transport regressions, API/README/parity docs, changelog, QA/review evidence | Register bounded unique public capabilities, list metadata-only descriptors, route exact capabilities deterministically through authenticated raw/typed transport, preserve named-agent compatibility, and avoid retry/failover/scheduling/identity/exactly-once claims | done: design `19390dd`; implementation `d3c720c`; docs/QA closure `1ab851a`; focused `56 passed in 21.28s`; exact tracked `1649 passed, 1 skipped`; clean archive source `801`, wheel `105`, sdist `715`, build/Twine/install/import pass; no publication, deployment, cloud action, or website update performed |
| 171 | Bounded remote agent invocation idempotency | Chief Architect / Backend / Interop / Security / QA / Release | `docs/adr/116-*`, `docs/briefs/maple-agent-runtime-slice171.md`, `maple/autonomy/invocations.py`, `maple/autonomy/server.py`, package exports, store/transport regressions, API/README/parity docs, changelog, QA/review evidence | Optional bounded idempotency keys claim before named/capability handler execution, replay detached success/error responses, reject concurrent/conflicting reuse, preserve absent-key compatibility, and provide atomic fenced local restart state without exactly-once claims | done: store `d824940`; transport `1c19544`; docs/review/QA closure `b6c4c0c` plus final closure commit; focused `21 passed in 4.46s`; exact tracked `1670 passed, 1 skipped in 259.19s`; clean archive source `809`, wheel `106`, sdist `723`, build/Twine/install/import pass; no publication, deployment, cloud action, or website update performed |
| 172 | Opt-in remote handoff idempotency binding | Chief Architect / Backend / Interop / Security / QA / Release | `docs/adr/117-*`, `docs/briefs/maple-agent-runtime-slice172.md`, `RemoteHandoffTarget`, adapter/server regressions, API/README/parity docs, changelog, QA/review evidence | Bind an explicit local handoff ID to the remote `run_id` and `idempotency_key` only under an opt-in flag, preserve default adapter wire behavior, require bounded IDs, and use the receiver's existing host-owned invocation store without exactly-once claims | done: implementation/tests `21c4f2a`; docs/review/QA closure plus final gate; focused `54 passed in 21.77s`; exact tracked `1674 passed, 1 skipped in 262.74s`; clean archive source `815`, wheel `106`, sdist `729`, build/Twine/install/import pass; no publication, deployment, cloud action, or website update performed |
| 175 | Authenticated remote durable checkpoint export and restore | Chief Architect / Backend / Interop / Security / QA / Release | `docs/briefs/maple-agent-runtime-slice175.md`, `docs/adr/120-*`, `maple/autonomy/server.py`, `RunServer`/`RunClient`, remote checkpoint regressions, API/README/parity docs, changelog, QA/review evidence | Add additive `agent:restore`-scoped export and restore routes for complete JSON-safe non-terminal `AgentRunCheckpoint` data; enforce route/store identity, bounded parsing, destination CAS versions, terminal rejection, legacy-store compatibility, and metadata-only receipts without handler execution, automatic retries, scheduling, push delivery, or exactly-once effects | complete: implementation and hardening landed; focused transport regressions `55 passed`; full workspace `1684 passed, 1 skipped`; clean archive/package evidence recorded in QA and review artifacts |
| 176 | Bounded remote human-input push delivery | Chief Architect / Backend / Interop / Security / QA / Release | `docs/briefs/maple-agent-runtime-slice176.md`, `docs/adr/121-*`, `maple/autonomy/interactions.py`, `maple/autonomy/server.py`, package exports, notification/server regressions, API/README/parity docs, changelog, QA/review evidence | Add `HttpHumanInputNotifier`, typed notification parsing, authenticated `interaction:notify` receiver route, and `RunClient.publish_human_input_notification()`; enforce HTTPS off loopback, bounded JSON, callback-before-ack, no response-data emission, one-attempt/no-retry behavior, and preserve local notifier compatibility; no approval push, durable queue, identity federation, or exactly-once effects | complete: implementation `dd64e19`; public docs `062deb7`; focused `62 passed in 25.14s`; full workspace `1693 passed, 1 skipped in 300.28s`; clean archive at `062deb7` source `832`, clean suite `1576 passed, 1 skipped`, wheel `106`, sdist `746`, Twine/install/import/doctor pass; no publication, deployment, cloud action, or website update performed |
| 177 | Bounded remote approval push delivery | Chief Architect / Backend / Interop / Security / QA / Release | `docs/briefs/maple-agent-runtime-slice177.md`, `docs/adr/122-*`, `maple/autonomy/approval.py`, `maple/autonomy/server.py`, package exports, approval/notification regressions, API/README/parity docs, changelog, QA/review evidence | Add `ApprovalNotification`, optional store notifiers, `HttpApprovalNotifier`, authenticated `approval:notify` receiver route, and `RunClient.publish_approval_notification()`; enforce bounded arguments, execution-result exclusion, HTTPS off loopback, callback-before-ack, no retry, and preserve approval-store authority; no durable queue, identity federation, or exactly-once effects | complete: design `f559fd3`; implementation `e0e6b2e`; public docs `f53e95f`; focused `12 passed in 4.46s`; approval/server compatibility `61 passed in 21.11s`; full workspace `1705 passed, 1 skipped in 289.21s`; clean archive at `f53e95f` source `836`, clean suite `1588 passed, 1 skipped`, wheel `106`, sdist `750`, Twine/install/import/doctor pass; API example executed; no publication, deployment, cloud action, or website update performed |
| 178 | Bounded durable notification outbox | Chief Architect / Backend / Interop / Security / QA / Release | `docs/briefs/maple-agent-runtime-slice178.md`, `docs/adr/123-*`, `maple/autonomy/notification_outbox.py`, human-input/approval adapters and exports, outbox regressions, API/README/parity docs, changelog, QA/review evidence | Add a bounded atomic file-backed outbox with deterministic canonical deduplication, restart loading, explicit at-least-once drain, retained failures, typed limits, and human-input/approval notifier adapters; never auto-delete, auto-retry, or claim distributed leases/exactly-once effects | complete: design `07f3ef2`; implementation `995f659`; bounds tests `83336eb`; public docs/review/QA `c064b80`; focused compatibility `36 passed in 4.69s`; full workspace `1715 passed, 1 skipped in 280.37s`; changed-boundary Black/isort/Ruff/mypy/compile pass; clean archive at `c064b80` source `841`, clean suite `1598 passed, 1 skipped in 255.85s`, wheel `107`, sdist `755`, Twine/install/import/doctor pass; no publication, deployment, cloud action, or website update performed |
| 179 | Optional cross-process notification drain fencing | Chief Architect / Backend / Security / QA / Release | `docs/briefs/maple-agent-runtime-slice179.md`, `docs/adr/124-*`, `maple/autonomy/notification_outbox.py`, exports, outbox regressions, API/README/parity docs, changelog, QA/review evidence | Add an opt-in caller-owned `FileLeaseManager` fence and bounded TTL around explicit outbox drains; preserve no-lease compatibility, target-outside-state-lock behavior, typed acquire/release failures, and at-least-once expiry semantics; no automatic renewal or exactly-once effects | complete: design `b48c854`; implementation/tests `5a0affd`; public docs/review/QA/package gate `c331f36`; focused `20 passed in 0.66s`; full workspace `1720 passed, 1 skipped in 279.71s`; clean archive `844` entries, `1603 passed, 1 skipped`, wheel `107`, sdist `758`, Twine/install/import/doctor pass; no publication, deployment, cloud action, or website update performed |
| 181 | Host-owned bearer token-to-principal resolution | Chief Architect / Backend / Security / QA / Release | docs/briefs/maple-agent-runtime-slice181.md, docs/adr/126-*, maple/autonomy/server.py, server regressions, README/API/parity/changelog, QA/review evidence | Add an optional synchronous resolver that maps a validated bearer token to a Principal; apply the selected principal to all existing scopes and target policy, fail closed with generic 401, preserve static-token compatibility, and keep federation/tenancy/issuance outside scope | complete: implementation dcc5001 + hardening 85fde19; public docs/review/QA/package gate af37173; focused server 54 passed in 22.74s; full workspace 1724 passed, 1 skipped in 282.12s; changed-boundary Black/isort/Ruff/mypy/compile pass; clean archive 850 entries, 1607 passed, 1 skipped in 264.35s; wheel 107, sdist 764; Twine/install/import/doctor pass; package version remains 1.1.3; no publication, deployment, cloud action, or website update performed |
| 182 | Bounded AgentRegistry route-policy validation | Chief Architect / Backend / Security / QA / Release | docs/briefs/maple-agent-runtime-slice182.md, docs/adr/127-*, maple/autonomy/server.py, server regressions, QA/review evidence | Validate direct allowed_agent_ids inputs before candidate lookup; preserve None/valid/empty compatibility, return typed bounded errors for malformed policy, and never invoke a handler on invalid policy | complete: implementation `180e09e`; public/review/package gate `0644d9f`; clean 1608 passed, 1 skipped; wheel 107; sdist 767; no publication/cloud/website action |
| 183 | Bounded authenticated remote event/trace search | Chief Architect / Backend / Observability / Interop / Security / QA / Release | docs/briefs/maple-agent-runtime-slice183.md, docs/adr/128-*, maple/autonomy/events.py, maple/autonomy/server.py, event/server regressions, API/README/parity docs, changelog, QA/review evidence | Add exact bounded `trace_id`/`run_id`/`event_type` filters over the retained redacted event window under `event:read`; preserve sequence order, cursor expiry, response bounds, and no hosted/distributed search claim | complete: implementation `205abd1`; public/review/package gate `d041a0b`; clean 1611 passed, 1 skipped; wheel 107; sdist 770; no publication/cloud/website action |
| 184 | Bounded deterministic trace scoring | Chief Architect / Backend / Observability / QA / Release | docs/briefs/maple-agent-runtime-slice184.md, docs/adr/129-*, maple/autonomy/evaluation.py, autonomy/root exports, evaluation regressions, API/README/parity docs, changelog, QA/review evidence | Add versioned identifier-free `TraceEvalSpan`/`TraceEvalCase` fixtures and `EvaluationHarness.run_trace(...)`; score bounded span name/status/parent structure deterministically, project native `TraceSpan` without IDs or attributes, and fail closed on malformed/oversized traces; no semantic faithfulness, provider judge, calibration, hosted aggregation, or trace persistence claim | complete: implementation `a85ca55`; public/docs/review/QA `e3dc496`; focused `50 passed in 0.51s`; full workspace `1732 passed, 1 skipped in 292.49s`; clean archive `859` entries, `1615 passed, 1 skipped`, wheel `107`, sdist `773`, Twine/install/import/doctor pass; no publication/cloud/website action |
| 185 | Bounded durable local task queue | Chief Architect / Backend / Security / QA / Release | docs/briefs/maple-agent-runtime-slice185.md, docs/adr/130-*, maple/task_management/durable_queue.py, task-management regressions, API/README/parity docs, changelog, QA/review evidence | Add `FileTaskQueue` compatible with `TaskQueue`/`TaskScheduler`; persist bounded JSON task state atomically behind a local cross-process fence, hydrate after restart, requeue interrupted `ASSIGNED`/`RUNNING` tasks with explicit at-least-once semantics, and fail closed on malformed/oversized/path-invalid state; no distributed scheduling, automatic retry, hosted queue, or exactly-once effects claim | complete: implementation/docs `2f59090`; focused durable queue `11 passed in 0.63s`; task-management `178 passed in 22.75s`; dirty workspace `1743 passed, 1 skipped in 314.00s`; clean archive `866` entries, `1626 passed, 1 skipped`, wheel `108`, sdist `780`, Twine/install/import/doctor pass; no publication/cloud/website action |
| 186 | Authenticated remote task-queue control plane | Chief Architect / Backend / Security / QA / Release | docs/briefs/maple-agent-runtime-slice186.md, docs/adr/131-*, maple/autonomy/server.py, maple/task_management, server/task-management regressions, API/README/parity docs, changelog, QA/review evidence | Add optional authenticated `RunServer(task_queue=...)` and additive `RunClient` submit/list/inspect/claim/complete/fail methods under distinct `task:*` scopes; enforce bounded JSON, queue ownership, and principal agent/capability policy before mutation; preserve local queue authority and explicitly exclude distributed scheduling, worker heartbeats, automatic retry, handler execution, and exactly-once effects | complete: implementation/docs `f4d518f`; focused server `59 passed in 33.19s`; autonomy + task-management `790 passed in 70.73s`; dirty workspace `1746 passed, 1 skipped in 309.92s`; clean archive `869` entries, `1629 passed, 1 skipped in 253.53s`, wheel `108`, sdist `783`, Twine/install/import/doctor pass; no publication/cloud/website action |
| 187 | Non-blocking remote claim-next capability matching | Architect / Backend / Security / QA / Release | docs/briefs/maple-agent-runtime-slice187.md, docs/adr/132-*, maple/autonomy/server.py, server regressions, API/README/parity docs, changelog, QA/review evidence | Add authenticated `POST /v1/tasks/claim-next` and `RunClient.claim_next_task(...)`; select compatible queued tasks deterministically by priority/creation/task ID, preserve queue-side ownership, return explicit no-work, and exclude blocking polling, liveness, fairness, distributed scheduling, automatic retry, handler execution, and exactly-once effects | complete: implementation `2aabca9`; focused server `60 passed`; autonomy + task-management `791 passed`; dirty workspace `1747 passed, 1 skipped`; clean archive `874` entries, `1630 passed, 1 skipped`, wheel `108`, sdist `788`, Twine/install/import/doctor pass; review `docs/reviews/maple-agent-runtime-slice187.md`; QA `docs/qa/maple-agent-runtime-slice187.md`; no publication/cloud/website action |
| 188 | Owner-safe authenticated remote task cancellation | Architect / Backend / Security / QA / Release | docs/briefs/maple-agent-runtime-slice188.md, docs/adr/133-*, maple/task_management/task_queue.py, maple/task_management/durable_queue.py, maple/autonomy/server.py, queue/server regressions, API/README/parity docs, changelog, QA/review evidence | Add `POST /v1/tasks/{task_id}/cancel` and `RunClient.cancel_task(...)` under `task:cancel`; enforce queue-side atomic owner checks for queued/assigned/running work, preserve local cancellation compatibility, reject terminal/missing/malformed operations, and exclude force termination, lease revocation, retries, distributed coordination, and exactly-once effects | complete: implementation `10d37fe`; focused server/task-management `95 passed`; autonomy + task-management `240 passed`; dirty workspace `1749 passed, 1 skipped`; clean archive `879` entries, `1632 passed, 1 skipped`, wheel `108`, sdist `793`, Twine/install/import/doctor pass; review `docs/reviews/maple-agent-runtime-slice188.md`; QA `docs/qa/maple-agent-runtime-slice188.md`; no publication/cloud/website action |
| 189 | Owner-safe authenticated remote task retry | Architect / Backend / Security / QA / Release | docs/briefs/maple-agent-runtime-slice189.md, docs/adr/134-*, maple/task_management/task_queue.py, maple/task_management/durable_queue.py, maple/autonomy/server.py, queue/server regressions, API/README/parity docs, changelog, QA/review evidence | Add `POST /v1/tasks/{task_id}/retry` and `RunClient.retry_task(...)` under `task:retry`; enforce queue-side atomic owner/state checks for failed work, preserve local requeue compatibility and retry/capacity bounds, and exclude automatic retry, scheduling, lease control, federation, and exactly-once effects | complete: implementation `13c5956`; focused server/task-management `97 passed`; autonomy + task-management `795 passed`; dirty workspace `1751 passed, 1 skipped`; clean archive `884` entries, `1634 passed, 1 skipped`, wheel `108`, sdist `798`, Twine/install/import/doctor pass; review `docs/reviews/maple-agent-runtime-slice189.md`; QA `docs/qa/maple-agent-runtime-slice189.md`; no publication/cloud/website action |
| 190 | Authenticated read-only remote task queue statistics | Architect / Backend / Security / QA / Release | docs/briefs/maple-agent-runtime-slice190.md, docs/adr/135-*, maple/autonomy/server.py, server/task-management regressions, API/README/parity docs, changelog, QA/review evidence | Add `GET /v1/tasks/stats` and `RunClient.task_queue_stats()` under `task:read`; expose only fixed finite `QueueStats` values, fail closed on malformed optional implementations, preserve route isolation, and exclude payloads/results, dashboards, distributed aggregation, scheduling, and queue lifecycle changes | complete: implementation `1cf3081`; evidence `22768be`; focused server `65 passed`; autonomy + task-management `798 passed`; dirty workspace `1754 passed, 1 skipped`; clean archive `889` entries, `1637 passed, 1 skipped`, wheel `108`, sdist `803`, Twine/install/import/doctor pass; review `docs/reviews/maple-agent-runtime-slice190.md`; QA `docs/qa/maple-agent-runtime-slice190.md`; no publication/cloud/website action |
| 191 | Owner-safe authenticated remote task start lifecycle | Architect / Backend / Security / QA / Release | docs/briefs/maple-agent-runtime-slice191.md, docs/adr/136-*, maple/task_management/task_queue.py, maple/task_management/durable_queue.py, maple/autonomy/server.py, queue/server regressions, API/README/parity docs, changelog, QA/review evidence | Add `POST /v1/tasks/{task_id}/start` and `RunClient.start_task(...)` under `task:start`; enforce queue-side atomic owner/state checks for `ASSIGNED` work, record `started_at`, preserve queue statistics accounting and durable restart behavior, and exclude leases, heartbeats, scheduling, automatic execution, distributed coordination, and exactly-once effects | complete: implementation `08f71e1`; focused server + durable queue `80 passed`; autonomy + task-management `800 passed`; dirty workspace `1756 passed, 1 skipped`; clean archive `894` entries, `1639 passed, 1 skipped`, wheel `108`, sdist `808`, Twine/install/import/doctor pass; review `docs/reviews/maple-agent-runtime-slice191.md`; QA `docs/qa/maple-agent-runtime-slice191.md`; no publication/cloud/website action |
| 192 | Whole-package type-boundary closure | Backend / Code Reviewer / QA / Release | docs/briefs/maple-agent-runtime-slice192.md, docs/adr/137-*, maple/autonomy/invocations.py, maple/autonomy/server.py, invocation/server regressions, changelog, QA/review evidence | Preserve runtime behavior while narrowing bounded invocation responses and annotating the remote handoff result boundary; do not weaken mypy or add suppressions/dependencies | done: commit `3b66f6d`; focused `78 passed`; dirty `1756 passed, 1 skipped`; clean revalidation `1639 passed, 1 skipped`; whole-package mypy clean; clean package 899/108/813 with Twine/install/import/doctor pass; review/QA filed; no publication/cloud/website action |
| 193 | Hosted coordination decision gate | Chief Architect / Security / Release | docs/briefs/maple-agent-runtime-slice193.md, docs/plans/maple-agent-runtime-slice193.md, parity ledger, release checklist | Specify identity/tenancy authority, distributed scheduling/liveness/lease semantics, external side-effect policy, and operational target before implementation; do not infer hosted or exactly-once guarantees from local primitives | gated: no code change; human contract inputs required before hosted identity, distributed coordination, or side-effect implementation; no publication/cloud/website action |
| 194 | Owner-safe telemetry-only task heartbeat | Chief Architect / Backend / Interop / Security / QA / Release | docs/briefs/maple-agent-runtime-slice194.md, docs/adr/138-*, maple/task_management/task_queue.py, maple/task_management/durable_queue.py, maple/autonomy/server.py, queue/server regressions, README/API/parity/changelog, QA/review evidence | Add `Task.heartbeat_at`, owner-checked in-memory/durable updates, legacy record compatibility, and authenticated `POST /v1/tasks/{task_id}/heartbeat` / `RunClient.heartbeat_task()` under `task:heartbeat`; preserve monotonic telemetry and exclude expiry, leases, reassignment, scheduling, distributed liveness, and exactly-once effects | complete: implementation `bb7690c`; review/QA/release closure `ca8ac16`; focused `105 passed`; dirty `1759 passed, 1 skipped`; clean archive `906` entries, `1642 passed, 1 skipped`, wheel `108`, sdist `820`, Twine/install/import/doctor pass; no publication/cloud/website action |
| 195 | Bounded code-block artifact materialization | Chief Architect / Backend / Security / Interop / QA / Release | docs/briefs/maple-agent-runtime-slice195.md, docs/adr/139-*, maple/autonomy/artifacts.py, artifact tests, exports, README/API/parity/changelog, QA/review evidence | Add `CodeBlock.sha256` and `materialize_code_block()` over the existing artifact-store contract; preserve exact UTF-8 bytes and deterministic bounded names, fail closed for malformed/oversized inputs and store errors, and exclude execution, sandboxing, network fetches, and remote distribution | complete: implementation `3382595`; review `docs/reviews/maple-agent-runtime-slice195.md`; QA/security `docs/qa/maple-agent-runtime-slice195.md`; focused `25 passed`; dirty `1765 passed, 1 skipped`; clean archive `849` files, `1648 passed, 1 skipped`, wheel `108`, sdist `825`; dirty package `108/834` with Twine/install/import/doctor pass; no publication/cloud/website action |
| 196 | Bounded provider failover | Chief Architect / Backend / ML / Security / Interop / QA / Release | docs/briefs/maple-agent-runtime-slice196.md, docs/adr/140-*, maple/llm/capabilities.py, provider tests, exports, README/API/parity/changelog, QA/review evidence | Add opt-in `FallbackLLMProvider` and `ProviderRouter.create(..., failover=True)` for at most eight deterministic completion attempts on exact transient errors; preserve default behavior, fail fast on non-transient errors, reject native-streaming failover, and exclude health services, load balancing, hosted routing, and exactly-once effects | done: implementation `823c5ba`, hardening `69c5fb6`; review/QA evidence filed; focused `31 passed`, full dirty `1775 passed, 1 skipped`; declared audit clean; no publication/cloud/website action |
| 197 | Offline provider completion contracts | Chief Architect / Backend / ML / Interop / Security / QA / Release | docs/briefs/maple-agent-runtime-slice197.md, docs/adr/141-*, `maple/llm/provider.py`, OpenAI/Anthropic adapters, provider contract fixtures, README/API/parity/changelog, QA/review evidence | Add deterministic sync/async fake-client fixtures for OpenAI-compatible and Anthropic completion mapping; reject malformed tool arguments and present malformed usage before tool execution/accounting; preserve missing-usage compatibility and exclude live SDK claims, provider discovery, hosted routing, and distributed state | complete: implementation `1c1277d`, boundary tests `683b8a9`; review `docs/reviews/maple-agent-runtime-slice197.md`; QA/security `docs/qa/maple-agent-runtime-slice197.md`; focused `39 passed`, full `1790 passed, 1 skipped`; clean candidate `ad11c89` tracked suite `1673 passed, 1 skipped`, source `862`, wheel `108`, sdist `838`, build/Twine/install/import/doctor pass; wheel `4bf330f9d4f25b00c79ced99f6f811bb0311b3469832adb352258becb3d02a6f`, sdist `2de357eb414a8bc0ad73b8de58ff5e23ad7f3b0061d8571f7ab6fb136c2bc5b0`; no publication/cloud/website action |
| 198 | Bounded provider-neutral judge calibration | Chief Architect / ML / Security / QA / Release | docs/briefs/maple-agent-runtime-slice198.md, docs/adr/142-*, `maple/autonomy/evaluation.py`, evaluation regressions/exports, README/API/parity/changelog, QA/review evidence | Add bounded human-labeled `EvalCalibrationCase` fixtures and sync/async sequential calibration reports with agreement and optional score mean absolute error; redact and bound observations/rationales, isolate judge failures per case, reject malformed datasets before callback invocation, and exclude provider orchestration, judge training/tuning, hosted persistence, and semantic/statistical claims | complete: design `88119cb`; implementation `35b446e`; boundary evidence `904f48a`; review `a3d6e8a`; QA/security `docs/qa/maple-agent-runtime-slice198.md`; dirty `1795 passed, 1 skipped`; clean candidate `a3d6e8a` `1678 passed, 1 skipped`, source `928`, wheel `108`, sdist `842`, build/Twine/install/import/doctor pass; wheel `7a728557af0b36d2347ee788bdf307d8eb6d8cc64a6f0b72e8a25f4c435e16cd`, sdist `f0212a48b42974174cb99cd8a7928c2b63a5b99b3a35d56060f2abe9ae6d5795`; no publication/cloud/website action |
| 199 | Execution integration isolation gate | Chief Architect / Security | docs/briefs/maple-agent-runtime-slice199.md, docs/adr/143-*, docs/plans/maple-agent-runtime-slice199.md, parity/release notes | Define the isolation, approval, artifact, quota, cleanup, identity, and side-effect contract before any code-interpreter/browser/computer-use/sandbox implementation; preserve `TrustedLocalExecutor` as trusted-only and code-block materialization as non-executing | gated: G0/G1 design complete; G2 requires human decisions or explicit scope removal; no code, dependency, subprocess, network, cloud, publication, or website action |
| 200 | CI quality gate reconciliation | DevOps / Chief Architect / QA / Release | docs/briefs/maple-release-readiness-slice200.md, docs/adr/144-*, docs/plans/maple-release-readiness-slice200.md, `.github/workflows/`, workflow contract tests | Reconcile local Black/isort/Ruff/mypy behavior with workflow Flake8 and author-header checks; preserve failing-on-findings behavior, document any legal/header policy, and verify clean-clone release commands without suppressions | gated: Gate 1 reproduction complete; `608` Flake8 `E501` findings and `19` missing author notices require human policy decision; no workflow policy, license, publication, cloud, or website action |

| 201 | Bounded session history and forking | Chief Architect / Backend / Security / Interop / QA / Release | docs/briefs/maple-agent-runtime-slice201.md, docs/adr/145-*, docs/plans/maple-agent-runtime-slice201.md, maple/autonomy/sessions.py, session regressions, exports, README/API/parity/changelog, QA/review evidence | Retain bounded version-ordered session snapshots in memory and one atomic file envelope; add detached inspection and safe version-based forks with optimistic source checks, legacy direct-snapshot reads, and no execution or message replay | complete: design `ad969a9`, implementation `b2f3809`, review/QA filed; full suite `1805 passed, 1 skipped`; clean package smoke `b10114e` build/Twine/install/import/doctor pass; no publication/cloud/website action |
| 202 | Authenticated local session control plane | Chief Architect / Backend / Interop / Security / QA / Release | docs/briefs/maple-agent-runtime-slice202.md, docs/adr/146-*, docs/plans/maple-agent-runtime-slice202.md, maple/autonomy/server.py, maple/autonomy/sessions.py, server/session regressions, API/README/parity/changelog, QA/review evidence | Add authenticated tip/history inspection and explicit-target data-only session forking over the existing loopback control plane; preserve store ownership, strict bounds, 501 optional-capability compatibility, and no remote mutation/replay/exactly-once claim | gated: direct-library empty-ID correction for create/fork complete at `b6ef016`; clean package smoke from `2c6c3c3` passes build/Twine/install/import/doctor (`883` source entries, `108` wheel entries); HTTP implementation still awaits human approval for additive public routes/scopes and session-content exposure; no publication/cloud/website action |
| 203 | Native run-ID validation correction | Chief Architect / Backend / QA / Release | docs/briefs/maple-agent-runtime-slice203.md, docs/adr/147-*, docs/plans/maple-agent-runtime-slice203.md, maple/autonomy/agent.py, maple/autonomy/workflow.py, workflow/run regressions, API/parity/changelog, QA/review evidence | Distinguish omitted `run_id=None` from explicit invalid values at native workflow and durable-agent starts; reject before checkpoint/provider/tool work while preserving agent store error normalization; do not alter already-validating server transport or add new public surface | complete locally: implementation `742661a`, plan hygiene `d7834d1`; dirty `1810 passed, 1 skipped`; clean tracked `1693 passed, 1 skipped`; clean package `886` source / `108` wheel / `862` sdist with build/Twine/install/import/doctor pass; review/QA filed; no publication/cloud/website action |
| 204 | Trusted local task worker | Chief Architect / Backend / Security / QA / Release | docs/briefs/maple-agent-runtime-slice204.md, docs/adr/148-*, docs/plans/maple-agent-runtime-slice204.md, maple/task_management/task_queue.py, maple/task_management/durable_queue.py, maple/task_management/worker.py, task-management regressions, API/README/parity/changelog, QA/review evidence | Bind registered trusted handlers to bounded queue polling, owner-checked start/complete/fail/cancel transitions, capability/type filtering, execution input/output/timeout bounds, and file restart persistence; exclude sandboxing, background scheduling, remote workers, automatic retry, and exactly-once effects | complete locally: worker/queue `56 passed`; full suite `1829 passed, 1 skipped`; mypy/Black/isort/Ruff/compile and project pip-audit pass; clean-archive package smoke at `d314d98` passed; review/QA filed; fresh independent verifier unavailable; publication remains pending; no cloud/website action |
| 205 | Durable local lexical retrieval | Chief Architect / Backend / Security / QA / Release | docs/briefs/maple-agent-runtime-slice205.md, docs/adr/149-*, docs/plans/maple-agent-runtime-slice205.md, maple/autonomy/retrieval.py, retrieval regressions/exports, API/README/parity/changelog, QA/review evidence | Persist validated source documents and chunking policy in a bounded versioned JSON envelope; rebuild deterministic lexical state after restart; refresh across instances; atomically add/remove under cross-process fencing; fail closed on corrupt state and redacted storage errors; exclude vector persistence, managed stores, network ingestion, distributed coordination, and semantic ranking | complete locally: implementation/public docs `b9843d7`, bounded-read hardening `5135877`, evidence `1a817f2`; focused retrieval `35 passed`; full suite `1838 passed, 1 skipped`; mypy/Black/Ruff/compileall/project pip-audit pass; clean package smoke source `960`, wheel `109`, sdist `874`, build/Twine/install/import/doctor pass; review/QA filed; fresh independent verifier unavailable; publication/cloud/website action remains out of scope |
| 206 | Durable local vector retrieval | Chief Architect / Backend / Security / QA / Release | docs/briefs/maple-agent-runtime-slice206.md, docs/adr/150-*, docs/plans/maple-agent-runtime-slice206.md, maple/autonomy/retrieval.py, retrieval regressions/exports, API/README/parity/changelog, QA/review evidence | Persist validated source documents, chunking policy, and caller-supplied per-chunk vectors in a bounded versioned JSON envelope; rebuild deterministic cosine state after restart; refresh across instances; atomically add/remove under cross-process fencing; fail closed on corrupt state, non-finite vectors, dimension mismatch, and redacted storage errors; exclude embedding generation, managed stores, network ingestion, distributed coordination, and semantic ranking | complete locally: design `411e222`, implementation `0166f13`, rejection hardening `484eae0`/`5366c09`/`926e872`, docs `db19dda`, review/QA filed; focused `43 passed`; full suite `1846 passed, 1 skipped`; mypy/Black/Ruff/compileall/project pip-audit pass; clean package source `965`, wheel `109`, sdist `879`, build/Twine/install/import/doctor pass; fresh independent verifier unavailable; publication/cloud/website action remains out of scope |
| 207 | Bounded retrieval and citation tool | Chief Architect / Backend / Security / QA / Release | docs/briefs/maple-agent-runtime-slice207.md, docs/adr/151-*, docs/plans/maple-agent-runtime-slice207.md, maple/autonomy/retrieval.py, retrieval regressions/exports, API/README/parity/changelog, QA/review evidence | Adapt an existing lexical `RetrievalBackend` into a read-only `Tool` with bounded UTF-8 queries and model-selected top-k, deterministic source URI/title citations, metadata-minimal JSON results, whole-output byte bounds, generic backend/result errors, and no execution of retrieved text; exclude vector query embedding, corpus authorization, network retrieval, managed stores, reranking, and hosted coordination | complete locally: design `a24f57e`, implementation `7fa2d8a`, hardening `1774551`; focused `51 passed in 1.07s`; full suite `1854 passed, 1 skipped in 398.14s`; Black/Ruff/mypy/compileall/project pip-audit pass; clean package source `970`, wheel `109`, sdist `884` with `137` test entries, demo/n8n excluded; build/Twine/install/import/doctor pass; review/QA filed; fresh independent verifier unavailable; no publication/cloud/website action |
| 208 | Host-owned vector retrieval tool | Chief Architect / Backend / Security / QA / Release | docs/briefs/maple-agent-runtime-slice208.md, docs/adr/152-*, docs/plans/maple-agent-runtime-slice208.md, maple/autonomy/retrieval.py, retrieval regressions/exports, API/README/parity/changelog, QA/review evidence | Compose one caller-owned synchronous `EmbeddingProvider` call with one existing local vector-backend search behind a read-only `Tool`; reuse bounded UTF-8 query/top-k validation, metadata-minimal URI/title citations, empty matched terms, whole-output byte bounds, and generic provider/backend/result errors; exclude provider selection, async embedding, retries, corpus authorization, network retrieval, managed stores, reranking, and hosted coordination | complete locally: design `d1e28af`, implementation `3d3f1a`, review/QA filed; focused `64 passed in 1.05s`; full suite `1867 passed, 1 skipped in 391.40s`; Black/Ruff/mypy/compileall/project pip-audit pass; clean package source `975`, wheel `109`, sdist `889` with `137` test entries, demo/n8n excluded; build/Twine/install/import/doctor pass; fresh independent verifier unavailable; no publication/cloud/website action |
| 209 | Async host-owned vector retrieval tool | Chief Architect / Backend / Security / QA / Release | docs/briefs/maple-agent-runtime-slice209.md, docs/adr/153-*, docs/plans/maple-agent-runtime-slice209.md, maple/autonomy/retrieval.py, retrieval regressions/exports, API/README/parity/changelog, QA/review evidence | Compose one awaited caller-owned `AsyncEmbeddingProvider` call with one executor-backed local vector-backend search behind an async-only read-only `Tool`; validate query/vector/top-k before callbacks, reuse metadata-minimal URI/title citations with empty matched terms, whole-output byte bounds, and generic provider/backend/result errors; exclude provider selection, retries, corpus authorization, network retrieval, managed stores, reranking, async backend protocol, and hosted coordination | complete locally: design `1b20668`, implementation `82c8a24`, docs `96f4b46`, review/QA filed; focused `73 passed in 1.14s`; full suite `1876 passed, 1 skipped in 400.38s`; Black/Ruff/mypy/compileall/project pip-audit pass; clean package source `980`, wheel `109`, sdist `894` with `137` test entries, demo/n8n excluded; build/Twine/install/import/doctor pass; fresh independent verifier unavailable; no publication/cloud/website action |

| 210 | Strict structured-output JSON parsing | Chief Architect / Backend / Security / QA / Release | docs/briefs/maple-agent-runtime-slice210.md, docs/adr/154-*, docs/plans/maple-agent-runtime-slice210.md, maple/autonomy/contracts.py, contract regressions, API/README/parity/changelog, QA/review evidence | Configure the existing bounded JSON parser to reject non-standard numeric constants and normalize decoder recursion failures to `STRUCTURED_OUTPUT_INVALID_JSON`; preserve valid finite JSON, public signatures, schema/model validation, and no-disclosure behavior; exclude new dependencies, schema-dialect expansion, provider-side enforcement, and execution | complete locally: implementation/docs `65d3b51`; focused `19 passed in 4.08s`; full `1881 passed, 1 skipped in 420.17s`; Black/isort/Ruff/mypy/compileall/project pip-audit pass; clean package source `906`, wheel `109`, build/Twine/install/import/doctor pass; review/QA filed; Bandit/Gitleaks/fresh verifier unavailable; no publication/cloud/website action |
| 211 | Asynchronous document ingestion | Chief Architect / Backend / Interop / Security / QA / Release | docs/briefs/maple-agent-runtime-slice211.md, docs/adr/155-*, docs/plans/maple-agent-runtime-slice211.md, `maple/autonomy/retrieval.py`, retrieval regressions/exports, API/README/parity/changelog, QA/review evidence | Add an async connector and bounded async ingestion helper only after explicit approval of the new public contract and executor/cancellation policy; preserve existing cursor, validation, checkpoint, rate-limit, generic-error, and at-least-once semantics; exclude async index backends, network/provider adapters, corpus policy, remote transport, and exactly-once effects | gated: brief/ADR/plan prepared; implementation intentionally not started; approval required before G1/G2; no publication/cloud/website action |

## Slice 127 closure

## Slice 128

Add a bounded durable event journal behind the existing event-stream contract.
The implementation must preserve redaction, cursor expiry, subscriber/exporter
isolation, and local metrics while making restart replay explicit. Persistence
is synchronous and host-owned; remote batching, fleet aggregation, and hosted
trace search remain separate capabilities.

Threat sketch: the assets are event payloads, cursor position, and diagnostic
history; entry points are event publication, journal load, and cursor reads.
The worst plausible abuse is leaking a tampered payload or exhausting disk or
memory through unbounded event retention. Atomic replacement, fencing leases,
record/size validation, redaction on rehydration, and hard retention bounds
contain the blast radius.

**Date:** 2026-08-27

Slice 128 is complete. `EventStream` now optionally attaches a host-owned
`FileEventJournal` that persists already-redacted, bounded events using atomic
JSON replacement and the existing durable fencing lease. Restart hydration
reapplies redaction, preserves the retained cursor window, and resumes sequence
allocation after the persisted tail; malformed, oversized, non-finite, and
non-monotonic state fails closed before callbacks or exporter delivery.

Evidence is green: the focused event suite passed `20` tests, the exact tracked
manifest passed `1329` tests with `1` skip across `108` tracked Python test
files, static and security checks passed, declared-project pip-audit reported
no known vulnerabilities, and clean-archive packaging passed with a `104`
entry wheel, `570`-entry sdist, Twine exit `0`, and an isolated no-dependency
event-journal export smoke. QA/security sign-off and code review are filed.
The environment remains intentionally local-first: remote event aggregation,
batching, hosted trace search, and exactly-once delivery are not claimed.

## Slice 129

Add a bounded authenticated event-batch route over the existing host-owned
`EventStream`. The server must reject malformed batch structure before any
attempt, preserve request order, return bounded per-item outcomes, and retain
the stream's redaction, local sequence, subscriber/exporter, journal, and
failure semantics. Partial success is explicit; remote retry, deduplication,
durability, aggregation, and exactly-once delivery remain outside the slice.

Threat sketch: the assets are event payloads, local sequence history, and
collector capacity; entry points are authenticated batch HTTP input, client
serialization, and per-item stream publication. The worst plausible abuse is
request amplification, response amplification, or misleading partial-delivery
claims. Authentication, 100-item/request bounds, existing body/response caps,
per-item validation, structured errors, and explicit partial-success semantics
contain the blast radius.

**Date:** 2026-08-27

## Slice 129 closure

The authenticated dependency-free event transport now supports bounded
1–100-item batches through `POST /v1/events/batch` and
`RunClient.publish_events(...)`. The receiver validates whole-batch structure
before attempts, submits valid items in request order through the existing
host-owned `EventStream`, and returns indexed `published`/`failed` outcomes.
Redaction, local sequence/timestamp allocation, retention, subscriber/exporter,
journal, and fail-closed stream behavior remain authoritative. There is no
implicit retry, deduplication, transaction, remote queue, or exactly-once claim.

Evidence is green: the focused server/event suite passed `50` tests and the
exact tracked manifest passed `1333` tests with `1` skip across `108` tracked
Python test files. Black, isort, Ruff, changed-boundary mypy, compile, diff,
secret, and dangerous-construct checks passed. The clean `git archive HEAD`
candidate at `c542828` built the `1.1.3` wheel and sdist with exit `0`; Twine
checks passed with `104` wheel entries and `571` sdist entries, and the
isolated no-dependency event-journal smoke passed. The final closure candidate
at `ab9d2e6` was rebuilt with exit `0`; Twine checks passed with `104` wheel
entries and `573` sdist entries, and the no-dependency event batch/journal
smoke passed. Declared-project pip-audit reported `No known vulnerabilities
found`; no runtime dependency was added.
QA and code-review evidence is filed under `docs/qa/` and `docs/reviews/`.

The environment-wide audit still reports `384` known vulnerabilities across
`77` installed packages and remains a release-governance veto. No publication,
deployment, cloud action, or website update was performed. Durable remote
replay, fleet aggregation, percentile/backpressure views, hosted tracing,
principal scopes, sandboxing, and exactly-once external effects remain separate
parity gaps.

## Slice 130

Add an explicit, dependency-free remote event forwarding pump over the
existing bounded `EventStream`, `FileEventJournal`, and authenticated batch
transport. `EventForwarder` reads one source window of at most 100 events,
submits it through an `EventBatchSender`, and advances a host-owned cursor
only through the contiguous prefix acknowledged by the destination. The
forwarder is synchronous and explicitly invoked; it does not create a
background scheduler, remote queue, deduplication layer, or exactly-once
effect protocol.

Threat sketch: assets are redacted event payloads, source sequence history,
cursor files, bearer credentials, and destination capacity; entry points are
local journal/cursor state, forwarder inputs, remote HTTP responses, and
cross-process cursor operations. The worst plausible abuse is cursor rollback
or corruption causing replay, malformed acknowledgements causing silent loss,
payload leakage, or repeated calls amplifying remote traffic. Atomic fenced
cursor writes, source retention-gap errors, complete indexed acknowledgement
validation, re-redaction, HTTPS requirements, strict byte/count bounds, and
explicit at-least-once semantics contain the blast radius.

**Date:** 2026-08-27

## Slice 130 closure

Slice 130 is complete. MAPLE now has an explicit, synchronous, opt-in
`EventForwarder` that reads one bounded retained window, submits it through an
authenticated `HttpEventBatchSender`, and persists only the contiguous
acknowledged prefix. In-memory and atomic fenced file cursor stores support
restart replay without silently skipping failures. Source retention gaps,
expired or malformed cursor state, malformed or incomplete acknowledgements,
transport errors, and cursor-save failures fail closed. Duplicate sends remain
possible by design after uncertain remote or cursor outcomes; no implicit
retry, remote queue, hosted scheduler, deduplication, cross-forwarder ordering,
or exactly-once effect claim is made.

Evidence is green: the focused event suite passed `31` tests, the event/server
suite passed `61` tests, and the exact tracked manifest passed `1344` tests with
`1` skip across `108` tracked Python test files. Black, isort, Ruff,
changed-boundary mypy, compile, diff, secret, and dangerous-construct checks
passed. A clean feature archive built `maple_oss-1.1.3-py3-none-any.whl` and
`maple_oss-1.1.3.tar.gz` with exit `0`; Twine passed, with `104` wheel entries
and `574` sdist entries, and the isolated no-dependency forwarder smoke passed.
QA and code-review evidence is filed in `docs/qa/` and `docs/reviews/`.

The final closure commit `3384c0d` was rebuilt from a clean tracked archive:
`build_exit=0`, both Twine checks passed, the wheel contained `104` entries,
and the sdist contained `576` entries. The isolated no-dependency forwarder
smoke passed against that archive as well.

Declared-project pip-audit reported no known vulnerabilities and no runtime
dependency was added. The environment-wide audit still reports `384` known
vulnerabilities across `77` installed packages and remains a release-governance
veto. No publication, deployment, cloud action, or website update was
performed.

## Slice 131

Add a provider-neutral, dependency-free structured trajectory contract to the
existing deterministic evaluation harness. The host may supply bounded tool
arguments, results, status, and duration for exact fixture matching. Reports
and optional judges receive a separately redacted bounded copy. The existing
name-only trajectory form remains compatible; execution, semantic scoring, and
hosted trace evaluation remain outside the slice.

Threat sketch: assets are tool arguments, tool results, fixture expectations,
judge observations, and report output; entry points are host runner return
values and serialized fixture data. The worst plausible abuse is secret
disclosure or memory amplification through raw trajectory values, or a
misleading pass caused by inconsistent names and structured steps. Typed JSON
validation, per-step and whole-report bounds, redaction before exposure, exact
name consistency, and no execution of trajectory data contain the blast radius.

**Date:** 2026-08-27

## Slice 131 closure

Slice 131 is complete. `EvalTrajectoryStep` now records bounded JSON-safe tool
arguments, results, status, and duration. `EvalCase.expected_trajectory`
performs exact validated fixture matching, while `EvalObservation.trajectory`
derives or checks tool names without breaking the existing name-only API.
Actual trajectories are re-redacted and bounded before report or judge
exposure. Invalid, inconsistent, oversized, or non-finite values fail closed
per case. The slice does not execute generated code or claim semantic
faithfulness, trace scoring, calibration, or hosted judge orchestration.

Evidence is green: the focused evaluation suite passed `24` tests, the
evaluation/observability suite passed `44` tests, and the exact tracked
manifest passed `1348` tests with `1` skip across `108` tracked Python test
files. Black, isort, Ruff, changed-boundary mypy, compile, diff, secret, and
dangerous-construct checks passed. QA and code-review evidence is filed in
`docs/qa/` and `docs/reviews/`.

The clean tracked archive built successfully with `build_exit=0`; both Twine
checks returned `PASSED`, the wheel contained `104` entries, the sdist
contained `579` entries, and the isolated no-dependency structured-trajectory
smoke passed. No publication, deployment, cloud action, or website update was
performed.

Slice 127 is complete. The authenticated dependency-free control plane now
supports bounded approval listing, inspection, and approve/deny decisions with
optional edited arguments. The configured `ApprovalStore` remains authoritative
for validation, leases, atomicity, conflicts, and durable state. Remote calls
cannot consume or execute an approval, and no hosted identity, notification,
scheduling, tenancy, or exactly-once effect claim is made. ADR-073, public API
documentation, README, parity ledger, changelog, QA, and review artifacts are
filed.

Evidence is green: the focused server suite passed `26` tests, the full
autonomy suite passed `362` tests, and the exact tracked manifest passed `1324`
tests with `1` skip across `108` tracked Python test files. isort, Black, Ruff,
changed-boundary mypy, compile, diff, secret, and dangerous-construct checks
passed. Declared-project pip-audit reported no known vulnerabilities and no
runtime dependency was added. A clean `git archive HEAD` candidate built
`maple_oss-1.1.3-py3-none-any.whl` and `maple_oss-1.1.3.tar.gz` with exit `0`;
Twine passed, with `104` wheel entries and `567` sdist entries, zero
workspace-only files, and a passing isolated no-dependency approval transport
export smoke.

The environment-wide audit still reports `384` known vulnerabilities across
`77` installed packages and remains a release-governance veto. No publication,
deployment, cloud action, or website update was performed. Hosted identity,
notifications, scheduling, tenancy, sandboxing, distributed transactions, and
exactly-once effects remain separate parity gaps.

## Slice 132 design

The next bounded implementation slice adds a local scheduling seam for the
durable event forwarder. The objective is to make periodic forwarding safe and
observable without silently turning `EventForwarder` into a background service.

### Scope

- Add `EventForwarderScheduler` with explicit `start()`, `stop()`, and
  deterministic `run_once()` lifecycle operations.
- Keep one non-daemon worker, one active tick, finite interval validation, and a
  hard 1–100 `max_batches_per_tick` budget.
- Stop a tick early when the forwarder reports no attempted events, while
  preserving the forwarder's existing cursor and at-least-once contract.
- Expose bounded integer counters and sanitized error metrics without retaining
  transport payloads, credentials, or raw exception messages.
- Add regression coverage, public exports, ADR/API/README/parity/changelog
  updates, and release QA/review artifacts.

### Explicit non-goals

This slice does not add a persistent queue, implicit retry, remote
deduplication, cross-process scheduler ownership, hosted aggregation, hosted
telemetry, forceful thread interruption, or exactly-once side effects. A
blocking sender remains governed by its own timeout and can produce a typed
cooperative stop timeout.

## Slice 132 closure

Slice 132 is complete. `EventForwarderScheduler` now provides an explicit,
bounded local polling lifecycle over `EventForwarder`: one owned non-daemon
worker, one active tick, finite intervals, a 1–100 batch budget, cooperative
shutdown, typed stop timeout, and sanitized metrics. `run_once()` supports
deterministic host polling. Existing cursor ownership and at-least-once
delivery remain unchanged; hosted aggregation, durable queues, remote
deduplication, cross-process scheduling, and exactly-once effects remain
separate capabilities.

The exact tracked manifest reports `1352 passed, 1 skipped in 239.48s` across
`108` tracked Python test files. Formatting, lint, changed-boundary typing,
compile, dependency, secret, dangerous-construct, clean archive, Twine, and
isolated import gates passed. QA and code-review evidence is filed under
`docs/qa/maple-agent-runtime-slice132.md` and
`docs/reviews/maple-agent-runtime-slice132.md`. No publication or website
change was performed.

## Slice 127

Add a narrow approval control plane over the existing authenticated loopback
transport. The server exposes bounded list/inspect/decide operations backed by
the configured `ApprovalStore`; the client validates the same limits before
sending. The transport intentionally stops at the decision boundary: local
agent execution remains responsible for consume, handler invocation, durable
outcome recording, and side-effect uncertainty.

Threat sketch: the assets are approval arguments, decisions, and any recorded
tool outcome; entry points are authenticated list/inspect/decide routes; the
worst plausible abuse is unauthorized approval mutation or disclosure of
sensitive tool arguments. Bearer authentication, loopback defaults, bounded
JSON/path/response limits, store-authoritative validation and leases, and no
remote consume/execute route contain the blast radius.

## Slice 126 closure

**Date:** 2026-08-27

Slice 126 is complete. Built-in in-memory and file approval stores now persist
one bounded terminal tool outcome after consumption, and direct execution plus
sync/async durable run resume replay it without invoking the handler again.
Malformed or oversized outcomes, conflicting recordings, recorder failures, and
consumed approvals without outcomes fail closed with typed effect uncertainty.
Custom stores without the optional recorder retain their prior single-use
behavior. ADR-072, the public API/README/parity documentation, changelog, QA
report, and review report are filed.

Evidence is green: the focused approval/run/agent suite passed `66` tests, the
full autonomy suite passed `359` tests, and the exact tracked manifest passed
`1321` tests with `1` skip across `108` tracked Python test files. isort, Black,
Ruff, changed-boundary mypy, compile, and diff checks passed. The final local
clean `git archive HEAD` candidate built `maple_oss-1.1.3-py3-none-any.whl` and
`maple_oss-1.1.3.tar.gz` with exit `0`; Twine passed, with `104` wheel entries
and `564` sdist entries, zero workspace-only files, and a passing isolated
no-dependency approval replay export smoke. Declared-project pip-audit reported
no known vulnerabilities and no runtime dependency was added.

The environment-wide audit still reports `384` known vulnerabilities across
`77` installed packages and remains a release-governance veto. No publication,
deployment, cloud action, or website update was performed. Distributed
transactions, remote approval transport, sandboxing, scheduling, and
exactly-once effects remain separate parity gaps.

## Slice 126

The built-in approval stores gain an optional, bounded terminal-outcome
recording seam. The approval claim remains single-use, but a successful or
typed tool result is recorded after execution so a later run resume can reuse
the result without calling the handler again. A consumed request with no
recorded result is an explicit unrecoverable crash window for this local
contract; MAPLE will not retry it or claim exactly-once external effects.

Threat sketch: the assets are approval records, tool-result content, and
external side effects; entry points are approval decisions, consumed-outcome
recording, direct replay, and sync/async run resume; the worst plausible abuse
is replaying an unbounded or tampered result or accidentally repeating a
side-effecting handler. JSON/size validation, atomic built-in stores,
idempotent recording, and fail-closed missing-outcome behavior contain that
blast radius.

## Slice 125 closure

**Date:** 2026-08-27

Slice 125 is complete. The bounded host-owned connector/sink contract is
implemented and documented in ADR-071. Evidence is green: the focused
retrieval suite passed `18` tests, the full autonomy suite passed `355` tests,
and the exact tracked manifest passed `1317` tests with `1` skip across `108`
tracked Python test files. isort, Black, Ruff, changed-boundary mypy,
compile, and diff checks passed. The final local archive candidate built
`maple_oss-1.1.3-py3-none-any.whl` and `maple_oss-1.1.3.tar.gz` with exit `0`;
Twine passed, with `104` wheel entries and `568` sdist entries; the isolated
no-dependency connector export smoke passed. Declared-project pip-audit
reported no known vulnerabilities and no runtime dependency was added.

The environment-wide audit still reports `384` known vulnerabilities across
`77` installed packages and remains a release-governance veto. No publication,
deployment, cloud action, or website update was performed. Durable cursor
checkpoints, managed-store adapters, connector rate limits, retries,
transactions, rollback, durable remote event replay/aggregation, provider
judge orchestration, and principal scopes remain the next parity slices.

## Slice 125

Implementation is intentionally limited to a provider-neutral connector seam.
Hosts own file/API/managed-store clients and provide bounded cursor pages;
MAPLE validates each page and feeds an explicit sink. Durable cursor storage,
rate limits, retries, transactions, rollback, and managed-store adapters remain
separate contracts.

## Slice 124 closure

2026-08-27: Slice 124 is behaviorally and package-gate complete. The new
`RetrievalReranker` protocol and `rerank_hits(...)` helper accept bounded
lexical or vector candidates, preserve source references and original scores,
and require finite host-supplied scores with deterministic tie-breaking. The
focused retrieval suite reports `12 passed in 0.07s`; the full autonomy suite
reports `349 passed in 16.38s`; the exact tracked manifest reports `1311
passed, 1 skipped in 230.15s` across 108 tracked Python files. isort, Black,
Ruff, changed-boundary mypy, compile, and diff checks pass. The `aeb80bd`
candidate builds wheel and sdist, both Twine checks pass, the wheel has `104`
entries, the sdist has `565` entries in the release workspace, and an isolated
`-I -S` import smoke test loads the new root/autonomy exports. The
declared-project dependency audit reports no known vulnerabilities; the
separate environment-wide audit remains a release veto with `384` findings
across `77` installed packages. No publication, deployment, cloud action, or
website change was performed. Document connectors, managed stores, provider
orchestration, and semantic evaluation remain separate boundaries.

## Slice 124

Implementation is intentionally limited to a provider-neutral reranking seam.
The helper is host-owned and dependency-free; it does not automatically call a
model or replace the backend's score. It validates the candidate boundary and
returns a separate reranked envelope, leaving document loading, managed
indexes, provider lifecycle, timeout/retry, and semantic faithfulness to
separate contracts.

## Slice 123 closure

2026-08-27: Slice 123 is behaviorally and package-gate complete. The explicit
host-owned `cancel_handler` is an additive callback on `AgentRegistry`; the
authenticated `RunServer`/`RunClient` route requires a normalized `cancelled`
`AgentRun` envelope and redacts callback failures. The focused server suite
reports `23 passed in 9.78s`; the full autonomy suite reports `347 passed in
16.99s`; the exact tracked manifest reports `1309 passed, 1 skipped in 236.70s`
across 108 tracked Python files. isort, Black, Ruff, changed-boundary mypy,
compile, and diff checks pass. The `8ec56bb` candidate builds wheel and sdist,
both Twine checks pass, the wheel has `104` entries, the sdist has `562`
entries in the release workspace, and an isolated `-I -S` import smoke test
loads the new root/autonomy export. The declared-project dependency audit
reports no known vulnerabilities; the separate environment-wide audit remains
a release veto with `384` findings across `77` installed packages. No
publication, deployment, cloud action, or website change was performed.
Cancellation remains cooperative and host-owned: token propagation, durable
state mutation, cleanup, hard termination, scheduling, retries, principal
scopes, and exactly-once side-effect policy are not claimed by this slice.

## Slice 123

Implementation is intentionally limited to the remote control seam. A host
must opt in with `cancel_handler`; MAPLE validates the callback output and
requires the explicit `cancelled` status before returning it over the
authenticated bounded transport. The endpoint does not mutate a durable run
store automatically or infer cancellation authority from a remote caller.

## Slice 122 closure

2026-08-27: Slice 122 is behaviorally and package-gate complete. The combined
event/server suite reports `37 passed in 10.68s`; the full autonomy suite reports
`346 passed in 12.57s`; the exact tracked manifest reports `1308 passed, 1
skipped in 226.26s` across 108 tracked Python files. Black, Ruff,
changed-boundary mypy, compile, diff, and network-free doctor checks pass. A
clean archive candidate from `3642805` builds wheel and sdist successfully,
both Twine checks pass, the sdist has `550` entries, the wheel has `104`
members, required public files are `6/6`, and a fresh no-dependency install
imports the event inspection exports. The declared-project dependency audit
reports no known vulnerabilities; the separate environment-wide audit remains
a release veto with `383` findings across `77` packages. No publication or
website change was performed. The route is limited to the existing redacted
host-owned ring, strict cursor queries, explicit retention-gap errors, and a
remote batch cap of `1,000`; durable replay, batching, remote search, fleet
aggregation, principal scopes, and exactly-once delivery remain separate
reviewed boundaries.

## Slice 122

Implementation is intentionally limited to cursor-based inspection of the
existing host-owned ring. `EventStream.read(...)` remains authoritative for
redaction, retention, cursor expiry, ordering, and event envelopes. Durable
replay, batching, remote search, fleet aggregation, and website changes remain
outside this slice.

## Slice 121 closure

2026-08-27: Slice 121 is behaviorally and package-gate complete. The combined
event/server suite reports `36 passed in 10.07s`; the full autonomy suite reports
`345 passed in 11.94s`; the exact tracked manifest reports `1307 passed, 1
skipped in 213.45s` across 108 tracked Python files. Black, Ruff,
changed-boundary mypy, compile, diff, and network-free doctor checks pass. A
clean archive candidate from `0ca0924` builds wheel and sdist successfully,
both Twine checks pass, the sdist has `547` entries, the wheel has `104`
members, required public files are `6/6`, and a fresh no-dependency install
imports the event transport exports. The declared-project dependency audit
reports no known vulnerabilities; the separate environment-wide audit remains
a release veto with `383` findings across `77` packages. No publication or
website change was performed. Early authenticated, missing-stream, resume, and
oversized-body POST responses drain only bounded request bodies to preserve
typed fail-closed responses on Windows. Batching, durable replay, fleet
aggregation, remote trace search, principal scopes, and exactly-once delivery
remain separate reviewed boundaries.

## Slice 121

Implementation is intentionally limited to a host-owned ingestion seam. The
server does not trust remote sequence or timestamp fields, and the existing
`EventStream` remains authoritative for redaction, retention, subscriber
isolation, exporter isolation, and local metrics. Publication, durable replay,
batching, and website changes remain outside this slice.

## Slice 120 closure

2026-08-27: Slice 120 is behaviorally and package-gate complete. The focused
server suite reports `18 passed in 10.19s`; the full autonomy suite reports
`342 passed in 14.06s`; the exact tracked application manifest reports `1304
passed, 1 skipped in 224.03s` across 108 tracked test files. Black, Ruff,
changed-boundary mypy, compile, diff, and network-free doctor checks pass. A
clean archive candidate from `9d1d7aa` builds wheel and sdist successfully,
both Twine checks pass, the sdist has `505` entries, the wheel has `104`
members, required public files are `6/6`, and a fresh no-dependency install
imports the durable agent transport exports. The declared-project dependency
audit reports no known vulnerabilities; the separate environment-wide audit
remains a release veto with `383` findings across `77` packages. No publication
or website change was performed. Inspection is redacted and resume is only
available through an explicit host callback; scheduling, cancellation, retries,
principal scopes, remote aggregation, and exactly-once effects remain separate.

## Slice 119 closure

2026-08-27: Slice 119 is behaviorally and package-gate complete. The focused
server suite reports `16 passed in 6.24s`; the full autonomy suite reports
`340 passed in 9.27s`; the exact tracked application manifest reports `1302
passed, 1 skipped in 214.52s` across 108 tracked test files. Black, Ruff,
changed-boundary mypy, compile, diff, and network-free doctor checks pass. A
clean archive candidate from `cafff3c` builds wheel and sdist successfully,
both Twine checks pass, the sdist has `541` entries, the wheel has `104`
members, required public files are `6/6`, and a fresh no-dependency install
imports the handoff transport exports. The declared-project dependency audit
reports no known vulnerabilities; the separate environment-wide audit remains
a release veto with `383` findings across `77` packages. No publication or
website change was performed. The handoff transport is digest-only and does
not claim raw payload delivery, principal scopes, notifications, retries,
scheduling, cancellation, or exactly-once effects.

## Slice 118 closure

2026-08-27: Slice 118 is behaviorally and package-gate complete. The focused
server suite reports `14 passed in 5.68s`; the full autonomy suite reports
`338 passed in 7.52s`; the exact tracked application manifest reports `1300
passed, 1 skipped in 212.14s` across 108 tracked test files. Black, Ruff,
changed-boundary mypy, compile, diff, and network-free doctor checks pass. A
clean archive candidate from `a6e3575` builds wheel and sdist successfully,
both Twine checks pass, the sdist has `538` entries, the wheel has `104`
members, required public files are `6/6`, and a fresh no-dependency install
imports the agent transport exports. The declared-project dependency audit
reports no known vulnerabilities; the separate environment-wide audit remains
a release veto with `383` findings across `77` packages. No publication or
website change was performed. The one-way transport does not claim remote
persistence, scheduling, cancellation, resume, retries, or exactly-once
effects; those remain separate reviewed boundaries.

## Slice 117 closure

2026-08-26: Slice 117 is behaviorally and package-gate complete. The focused
suite reports `10 passed in 4.88s`; the full autonomy suite reports `335 passed
in 6.94s`; the exact tracked application manifest reports `1297 passed, 1
skipped in 228.90s`. Black, Ruff, changed-boundary mypy, compile, diff, and
network-free doctor checks pass. Clean archive candidate `889c476` builds wheel
and sdist successfully, both Twine checks pass, the sdist has `535` entries,
required public files are `6/6`, and the wheel has `104` members; a fresh
no-dependency install imports `SessionCompactionStore` and performs a compact
operation. QA and code review pass. Dependency governance remains a release
veto because the environment audit found `383` vulnerabilities in `77`
packages; no publication or website change was performed. Automatic/token-aware
summarization, broader trace replay, and cross-process session leases remain
separate future boundaries. The declared-project dependency audit reports no
known vulnerabilities; the separate environment-wide audit remains a release
veto with `383` findings across `77` packages until governance disposition.

## Slice 116 closure

2026-08-26: Slice 116 is behaviorally and package-gate complete. The focused
suite reports `47 passed in 3.11s`; the exact tracked application manifest
reports `1294 passed, 1 skipped in 226.93s`. Black, Ruff, changed-boundary
mypy, compile, diff, and network-free doctor checks pass. Clean archive
candidate `6224003` builds wheel and sdist successfully, both Twine checks
pass, the sdist has `532` entries, required public files are `6/6`, and the
wheel has `104` members; a fresh no-dependency install imports the new replay
exports and confirms the default policy is disabled. QA and code review pass.
Dependency governance remains a release veto because the environment audit
found `383` vulnerabilities in `77` packages; no publication or website change
was performed. Remote routing, distributed scheduling, and exactly-once
external effects remain separate future boundaries.

## Slice 115 closure

2026-08-26: Slice 115 is behaviorally and package-gate complete. The focused
suite reports `31 passed in 4.62s`; the exact tracked application manifest
reports `1290 passed, 1 skipped in 234.57s`. Black, Ruff, changed-boundary
mypy, compile, diff, and network-free doctor checks pass. Clean archive
candidate `338650a` builds wheel and sdist successfully, both Twine checks
pass, the sdist has `531` entries, required public files are `6/6`, the
workspace-only audit is `0`, and a fresh no-dependency wheel install imports
`Workflow` and `add_subworkflow`. QA and code review pass. Dependency
governance remains a release veto because the environment audit found
`383` vulnerabilities in `77` packages; no publication or website change was
performed. Remote routing, distributed scheduling, and exactly-once external
effects remain separate future boundaries.

## Threat sketch

Slice 114 is the bounded authenticated human-input transport slice. It adds
optional interaction routes to the loopback workflow server and matching
client operations; configuring the store requires a server bearer token, and
the store remains authoritative for actor authorization, schema validation,
leases, notifications, and one-time consumption. Focused coverage reports
`19 passed in 5.17s`; the final tracked manifest reports `1283 passed, 1
skipped in 275.08s`; a clean archive candidate `b8a252a` rebuilt wheel/sdist
`1.1.3`, both Twine checks passed, the sdist contains `528` entries, required
public files are `6/6`, and workspace-only audit is `0`. Hosted identity, TLS
termination, automatic scheduling, and exactly-once side-effect policy remain
separate; dependency governance remains open and no publication was
performed.

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
error-recovery slice 47's follow-up audit now reports `147 errors in 19 files`;
state-synchronization slice 48's follow-up audit now reports `146 errors in 18 files`;
autonomy-event slice 49's follow-up audit now reports `143 errors in 17 files`;
workflow slice 50's follow-up audit now reports `142 errors in 16 files`;
health-monitor slice 51's follow-up audit now reports `136 errors in 15 files`;
legacy-interop slice 52's follow-up audit now reports `132 errors in 12 files`;
production-broker slice 53's follow-up audit now reports `130 errors in 11 files`;
AutoGen slice 54's follow-up audit now reports `126 errors in 10 files`;
doctrine-adapter slice 55's follow-up audit now reports `119 errors in 9 files`;
security-facade slice 56's follow-up audit now reports `95 errors in 8 files`;
S2 slice 57's follow-up audit now reports `87 errors in 7 files`;
LLM-provider slice 58's follow-up audit now reports `62 errors in 5 files`;
OpenAI-SDK slice 59's follow-up audit now reports `51 errors in 4 files`;
LangGraph slice 60's follow-up audit now reports `42 errors in 3 files`;
CrewAI slice 61's follow-up audit now reports `27 errors in 1 file`;
NATS slice 62's follow-up audit reports `Success: no issues found in 93 source files`;
 the package runtime remains `>=3.8` while the mypy 2.x static-analysis target
 is now Python 3.10. Dependency-audit disposition and unavailable independent
 fresh-context verification remain open.
External publishing, cloud selection, and website changes remain explicitly out
of scope until human approval.

2026-08-25 final preflight refresh: the explicit Python 3.10-target mypy audit
is clean across all 93 source files; the focused cross-surface regression is
`269 passed, 1 skipped in 51.72s`; the full LLM suite is `36 passed`; Black,
isort, the enforced `tools`/`tests` Ruff gate, compile, wheel/sdist, Twine, and
network-free doctor checks pass. Broad legacy `ruff check maple` remains open at
264 existing diagnostics. Full repository regression, dependency-audit
disposition, Bandit availability, and independent fresh-context verification
remain open. No publication or website change was performed.

2026-08-25 typecheck contract closure: commit `70d47a9` retains the package's
Python `>=3.8` runtime declaration and changes only the mypy static-analysis
target to Python 3.10 because mypy 2.x rejects Python 3.8 targets. The default
`python -m mypy maple/ --ignore-missing-imports` audit now reports `Success: no
issues found in 93 source files`; the broader cross-surface regression reports
`616 passed, 1 skipped in 173.01s`. Full repository completion, repository-wide
legacy Ruff debt, dependency/security disposition, and fresh verification remain
open.

2026-08-25 security boundary closure: commit `d3e5358` adds the bounded A2A
registry timeout, explicit MCP URL rejection coverage, and a size-bounded
restricted pickle unpickler that rejects callable/module globals. The security
regression is `37 passed in 0.82s`; the cross-surface regression is `621 passed,
1 skipped in 170.54s`. In an isolated `.[dev,security]` environment, `pip check`
reported `No broken requirements found`, `pip-audit` reported `No known
vulnerabilities found`, and Bandit `-ll` exited 0 with zero medium/high
findings. A full Bandit inventory contains 35 low-severity legacy findings
(B101 x1, B105 x4, B110 x22, B112 x3, B311 x3, B403 x1, B405 x1); these are
tracked non-blocking debt and were not introduced by this slice.

2026-08-25 safe lint/FIPA closure: commit `25001b0` removes verified unused
imports/locals, redundant formatting, and non-functional module-header lint
debt across seven runtime files, and corrects FIPA translation to emit the
mapped performative. The affected regression reports `131 passed in 48.43s`;
changed-file Ruff, Black, isort, and mypy checks pass. Broad `ruff check maple`
decreased from `250` diagnostics to `171` (`E402 140`, `F401 31`). Remaining
legacy lint is still tracked as an open release gate.

2026-08-25 header/import lint closure: commit `c42cf58` converts secondary
module headers to comments and removes verified unused imports across seven
runtime files. The affected regression reports `628 passed, 1 skipped in
16.35s`; changed-file Ruff, Black, isort, mypy, and compile checks pass. Broad
`ruff check maple` decreased from `171` diagnostics to `95` (`E402 69`,
`F401 26`). Remaining legacy lint is still an open release gate.

2026-08-25 verified import closure: commit `6ebac24` removes imports proven
unused by Ruff across 13 runtime files and preserves the S2 optional SDK
availability probe with a narrow line-level `F401` exception for `StreamConfig`.
The affected suite reports `777 passed, 1 skipped in 237.84s`; current S2,
resource, and link revalidation reports `130 passed in 0.37s`. Changed-file
Ruff, Black, isort, mypy, and compile checks pass. Broad `ruff check maple`
decreased from `95` diagnostics to `58` (`E402 58`), with zero F401 findings.

2026-08-25 residual module-header closure: commit `11d0b27` converts
secondary module headers across autonomy, broker, LLM, monitoring, security,
and state package surfaces to comments. The affected suite reports `635
passed, 1 skipped in 16.90s`; changed-file Ruff, Black, isort, mypy, and
compile checks pass. Broad `ruff check maple` decreased from `58` diagnostics
to `19` (`E402 19`).

2026-08-25 bounded full-suite attempt: on commit `045fcc7`, pytest collected
`1270 items` and reached `95%` in the Doctrine state tests with no failure
output before the bounded session was manually interrupted; pytest emitted no
final summary. Because slices 68 and 69 followed that attempt, the
exact-current full suite gate remains open.

2026-08-25 repository-wide Ruff closure: the final 19 E402 findings were
closed in the Doctrine adapter and security authentication/separation import
boundaries. The affected regression reports `107 passed in 4.02s`; Ruff,
Black, isort, mypy, and compile checks pass. Broad `ruff check maple` now
reports zero findings. The exact-current full repository suite remains open.

2026-08-25 typed model output boundary: adds `AutonomousConfig.output_model`,
`structured_model_schema`, and `parse_typed_output`. Pydantic-style models are
validated at the structured-output boundary and returned as typed instances;
invalid model output fails closed without exposing validation payloads. The
full autonomy regression reports `210 passed in 3.37s`; focused contract/agent
coverage reports `28 passed in 0.35s`.

2026-08-25 typed tool contract closure: commit `ded4477` adds optional
Pydantic-style `Tool.input_model` and `Tool.output_model` boundaries. Tool
schemas are advertised to the model, invalid inputs fail before handler
execution, valid inputs are passed as normalized model fields, and outputs are
returned as validated model instances. Focused contract/tool/agent coverage
reports `43 passed in 0.37s`; the full autonomy surface reports `212 passed in
3.26s`. Exact static checks, compile, wheel/sdist, Twine, and network-free
doctor gates pass; no new dependency was added. The exact repository-wide
suite and fresh independent verification remain open.

Public surface documentation for the typed tool boundary is recorded in
commit `9236bc4` across the README and API reference. Website changes remain
deferred until separately approved.

2026-08-25 optional Protobuf closure: commit `2b8bb57` implements the
advertised `SerializationFormat.PROTOBUF` path with an optional bounded
`google.protobuf.Struct` envelope. Core/autonomy coverage reports `240 passed
in 3.37s`; the serialization suite reports `28 passed in 0.28s`. Malformed,
oversized, and missing-dependency paths fail closed; no new dependency was
added. Public serialization documentation and ADR-024 are included in the
release evidence update.

2026-08-25 exact-current full-suite attempt: commit `ded4477` collected `1276`
tests and reached `90%` before entering the slow Doctrine gold phase. The
bounded session was interrupted after sparse gold-test progress without a
failure traceback or pytest summary, so the full-suite gate remains open.

2026-08-25 post-Protobuf exact-current attempt: commit `2b8bb57` collected
`1278` tests, reached `90%`, and emitted six Doctrine gold-test completions
before bounded interruption. No failure output or pytest summary was produced;
the exact full-suite gate remains open.

2026-08-25 bounded token-budget closure: commit `2328b92` adds opt-in
`AutonomousConfig.max_total_tokens` enforcement and aggregate `Goal.token_usage`
across synchronous/asynchronous ReAct reasoning and reflection. The focused
agent/session regression reports `30 passed in 0.31s`; missing, malformed, and
over-budget usage paths fail closed before tool side effects. Public docs and
ADR-025 are filed; no new dependency, publication, or website change was made.

2026-08-25 exact-current full-suite attempt on `a51e043`: pytest collected
`1282` items, passed the application suites through `90%`, and entered the slow
Doctrine gold phase before bounded interruption. No failure output or pytest
summary was produced, so the exact full-suite gate remains open.

2026-08-25 bounded orchestration closure: commit `b2cccfb` adds bounded sync
and async fan-out for supervised and consensus teams, stable result joins, and
normalized worker exceptions. The agent/orchestrator regression reports `43
passed in 0.33s`; no new dependency, publication, or website change was made.

2026-08-25 bounded output-repair closure: commit `e3becdf` adds opt-in
`AutonomousConfig.max_output_retries` from 0 through 3. Sync/async correction,
exhaustion, default fail-fast, and token-budget interaction are covered by the
focused agent regression (`28 passed in 0.33s`); no new dependency, publication,
or website change was made.

2026-08-25 exact-current full-suite attempt on `1211701`: pytest collected
`1291` items, passed the application suites through `90%`, and entered the slow
Doctrine gold phase before bounded interruption. No failure output or pytest
summary was produced, so the exact full-suite gate remains open.

2026-08-25 exact-current full-suite attempt on `bd1b179`: pytest collected
`1295` items, passed the application suites through `90%`, and entered
`tests/test_doctrine_gold.py`. After sparse gold-phase progress, the bounded
session was interrupted without failure output or a pytest summary. This is not
a full-suite pass; the exact gate remains open.

2026-08-25 async orchestration lifecycle closure: commit `7630839` adds
request-wide `timeout_seconds` and cooperative `CancellationToken` handling to
async supervised and consensus execution. Native async children are canceled
and drained; invalid configuration and interruption fail with typed errors. The
orchestrator regression reports `24 passed in 0.43s`, and core/autonomy reports
`257 passed in 3.60s`. ADR-028, public docs, changelog, QA, and review evidence
are filed. Sync-only executor cancellation remains explicitly cooperative; no
dependency, publication, or website change was made.

2026-08-25 bounded handoff closure: commit `62ebad8` adds
`create_handoff_tool`, an approval-by-default model-tool boundary for one
specialist's bounded synchronous `pursue_goal` call. Tool coverage reports
`18 passed in 0.25s`; autonomy coverage reports `234 passed in 3.49s`. Target
errors are normalized without raw payload forwarding; ADR-029, public docs,
changelog, QA, and review evidence are filed. No dependency, publication, or
website change was made.

2026-08-25 exact-current full-suite attempt on `2b7ea84`: pytest collected
`1300` items, passed the application suites through `90%`, and entered
`tests/test_doctrine_gold.py`. After sparse gold-phase progress, the bounded
session was interrupted without failure output or a pytest summary. This is not
a full-suite pass; the exact gate remains open.

2026-08-25 isolated Doctrine gold diagnostic on `b67830c`: pytest collected 21
tests and completed `3 passed in 521.65s (0:08:41)` before bounded interruption.
No assertion failure was reported. The slowest completed calls were 189.32s,
118.43s, and 61.33s; this is diagnostic evidence only and does not close the
exact repository gate.

2026-08-25 tracked-suite revalidation after the test-warning fix: Git supplied
100 tracked Python test files to pytest; the run reported `1185 passed, 1
skipped in 210.07s` with no warnings. This closes the tracked application-suite
gate while the workspace-only Doctrine gold verifier and fresh independent
review remain open.

2026-08-25 clean tracked artifact revalidation: a temporary `git archive HEAD`
snapshot built wheel/sdist `1.1.3`; both Twine checks passed. The sdist contained
460 files and the explicit audit found zero preserved workspace-only files. The
dirty shared-workspace artifact remains diagnostic only.

2026-08-25 parity-ledger closure: added a source-backed functionality matrix
for LangGraph, CrewAI, Microsoft Agent Framework, LlamaIndex, and OpenAI Agents
SDK. The ledger explicitly separates MAPLE native/preview/partial/adapter/
deferred/unsupported surfaces, treats code-block extraction as non-executing
artifact data, and orders the next gaps around durable agent runs, HITL,
context-aware handoffs, unified streaming/observability, deeper evaluations,
and separately reviewed execution integrations.

The exact current clean archive at the parity-ledger commit rebuilt wheel/sdist
`1.1.3`; both Twine checks passed, the sdist contained 463 entries including
the ledger, and the preserved workspace-only Doctrine files were absent.

2026-08-25 durable synchronous agent-run slice: ADR-030 defines a bounded
JSON-safe `AgentRunStore` with in-memory/file CAS persistence. The implementation
checkpoints the ReAct message cursor after each completed step, pauses before
additional tool side effects when a durable approval is pending, and resumes a
paused or interrupted run without repeating the completed tool. Focused
store/agent regression evidence reports `45 passed in 0.36s`; asynchronous
run-store integration remains an explicit follow-on rather than an unverified
claim.

Slice 82 implementation evidence: `AgentRunCheckpoint` and the in-memory/file
`AgentRunStore` are exported publicly. Sync ReAct runs checkpoint their message
cursor and token usage after each completed step; durable approval pauses return
`AGENT_RUN_PAUSED`, and `resume_run()` replaces the pending tool result before
continuing. The focused compatibility slice reports `45 passed in 0.36s`, and
the full autonomy directory reports `240 passed in 3.59s`. Async run-store
integration, distributed leases, and exactly-once external effects remain
explicit follow-on boundaries.

2026-08-26 current tracked-suite revalidation: Git supplied 101 tracked Python
test files and pytest reported `1191 passed, 1 skipped in 217.81s` with no
warning output. This closes the tracked application-suite gate after the
durable-run slice.

2026-08-26 current clean artifact revalidation: a temporary `git archive HEAD`
snapshot rebuilt wheel/sdist `1.1.3`; both Twine checks passed, the sdist
contained 466 entries including `maple/autonomy/runs.py`, and the
workspace-only audit found zero preserved Doctrine files. The network-free
doctor returned `ready: true`, all eight checks true, and `network: false`.

2026-08-26 async durable-run closure: ADR-031 extends the bounded run cursor
to `pursue_goal_async` and `resume_run_async`. The focused async/store slice
reports `9 passed in 0.30s`; the tracked application suite reports `1194
passed, 1 skipped in 205.06s`. A clean archive rebuilt wheel/sdist `1.1.3`,
both Twine checks passed, the sdist contained 467 entries including
`maple/autonomy/runs.py` and ADR-031, and the workspace-only audit found zero
preserved Doctrine files. Async durable tool calls are serialized only when
durability is enabled so approval pauses precede later side effects.

2026-08-26 lifecycle-event validation: ADR-032 and the optional
`set_event_stream()` attachment provide shared sync/async `run.started`,
`run.resumed`, `model.response`, `tool.completed`, `run.paused`,
`run.completed`, and bounded `run.failed` metadata with usage trailers. The
focused lifecycle/run slice reports `10 passed in 0.27s`; Ruff, Black, mypy,
compile, doctor, and clean archive/Twine checks pass. The exact tracked run
reported `1194 passed, 1 failed, 1 skipped in 218.95s` because the existing
oversized-body loopback test received Windows `ConnectionAbortedError`; its
isolated reproduction passed, so the release gate remains open rather than
being retried until lucky.

2026-08-26 loopback response hardening: ADR-033 makes every bounded JSON
response explicitly flush and close its HTTP connection. The server suite
reports `4 passed in 2.34s`, and the exact tracked application suite now reports
`1195 passed, 1 skipped in 222.53s` with no warning output. This closes the
intermittent Windows oversized-body response race without changing routes,
status codes, payloads, dependencies, or external hosting behavior.

2026-08-26 final current-commit artifact revalidation: `git archive HEAD`
built wheel/sdist `1.1.3`; both Twine checks passed, the sdist contained 469
entries including ADR-031, ADR-032, ADR-033, and the durable/event modules, and
the workspace-only audit found zero preserved Doctrine files. The network-free
doctor returned `ready: true`, all eight checks true, and `network: false`.

2026-08-26 bounded editable durable approval closure: ADR-034 adds an
approved-only, keyword-only `edited_arguments` replacement to the durable
approval decision. Existing JSON/depth/item/byte quotas validate edits before
mutation; in-memory and file stores persist them, and sync/async resume executes
the replacement after one-time claim. The focused approval/run/agent slice
reports `44 passed in 0.46s`; the tracked manifest reports `1197 passed, 1
skipped in 204.41s`; Ruff, Black, mypy, compile, diff, and doctor pass. A clean
current archive rebuilt wheel/sdist `1.1.3`, both Twine checks passed, the sdist
contained 470 entries including ADR-034, and the workspace-only audit found
zero preserved Doctrine files. Arbitrary multi-turn HITL, cross-process leases,
and publication remain outside this slice.

2026-08-26 bounded durable human-input closure: ADR-035 adds a reserved
`request_human_input` tool, bounded in-memory/file request records, schema-
validated responses, explicit rejection, and a persisted `pending_input_id`
for sync/async durable ReAct resume. The focused interaction/run/tool/agent
slice reports `61 passed in 0.51s`; the tracked manifest reports `1202 passed,
1 skipped in 211.16s`; Ruff, Black, mypy, compile, diff, and doctor pass. A
clean current archive rebuilt wheel/sdist `1.1.3`; Twine passed for both, the
sdist contains 473 entries including ADR-035, and the workspace-only audit
found zero preserved Doctrine files. Cross-process leases, notifications, and
multi-round conversations remain explicit follow-on gaps.

2026-08-26 cross-process durable fencing lease closure: ADR-036 adds
`FileLeaseManager` beside the existing in-memory `LeaseManager`. Each bounded
resource state uses an advisory OS lock, atomic JSON replacement, a persisted
fencing counter, wall-clock expiry, and typed fail-closed storage behavior.
The focused resource-model/file-lease slice reports `41 passed in 3.64s`; the
tracked manifest reports `1207 passed, 1 skipped in 214.53s`; Ruff, Black,
compile, doctor, and changed-boundary mypy pass. A clean archive rebuilt
wheel/sdist `1.1.3`; Twine passed for both, the sdist contains 475 entries
including ADR-035 and ADR-036, and the workspace-only audit found zero
preserved Doctrine files. Automatic ownership of approval/input/run stores,
remote authentication, and exactly-once effects remain explicit follow-on
boundaries.

2026-08-26 approval-store ownership closure: ADR-037 integrates the durable
fencing primitive into `FileApprovalStore`. Every file-backed approval operation
acquires a namespaced per-record lease before reading or mutating state;
acquisition failure returns `APPROVAL_LEASE_ERROR` without mutation, while a
release failure is surfaced as `APPROVAL_LEASE_RELEASE_ERROR` with uncertain-
commit guidance. Input/run store ownership and host notifications remain
separate follow-on slices.

The focused approval/lease boundary reports `8 passed in 0.31s`; the tracked
manifest reports `1209 passed, 1 skipped in 199.58s`; Ruff, Black, compile,
diff, doctor, and changed-boundary mypy pass. A clean archive rebuilt
wheel/sdist `1.1.3`; Twine passed for both, the sdist contains 477 entries
including ADR-037 and the approval lease regression, and the workspace-only
audit found zero preserved Doctrine files.

2026-08-26 human-input-store ownership closure: ADR-038 applies the shared
`DurableRecordLease` wrapper to `FileHumanInputStore`. File-backed get/create,
respond/reject, consume, and list operations now acquire a namespaced fencing
lease; acquisition failure is mutation-free and release uncertainty is typed.
The focused approval/input/lease boundary reports `13 passed in 0.48s`; the
tracked manifest reports `1211 passed, 1 skipped in 219.68s`; Ruff, Black,
compile, diff, doctor, and changed-boundary mypy pass. A clean archive rebuilt
wheel/sdist `1.1.3`; Twine passed for both, the sdist contains 480 entries
including ADR-038 and the shared durable lease helper, and the workspace-only
audit found zero preserved Doctrine files. Run-store ownership, notifications,
remote authentication, and multi-round interaction remain separate follow-on
boundaries.

2026-08-26 run-store ownership closure: ADR-039 applies the shared
`DurableRecordLease` wrapper to `FileAgentRunStore`. File-backed load and the
complete compare-and-set save operation now acquire a namespaced
`run:<run_id>` fencing lease; acquisition failure is read/mutation-free and
release uncertainty is typed. The focused run-store suite reports `14 passed
in 2.66s`; the tracked manifest reports `1213 passed, 1 skipped in 228.60s`;
Ruff, Black, compile, diff, doctor, and changed-boundary mypy pass. A clean
archive rebuilt wheel/sdist `1.1.3`; Twine passed for both, the sdist contains
482 entries including ADR-039, the run module, and the run lease regression,
and the workspace-only audit found zero preserved Doctrine files. Host
notifications, remote authentication, exactly-once external effects, and
multi-round interaction remain separate follow-on boundaries.

2026-08-26 bounded human-input host-hook closure: ADR-040 adds local
`HumanInputNotifier` and `HumanInputAuthorizer` protocols to the in-memory and
file-backed stores. Created/responded/rejected notifications carry bounded
request metadata without the response payload; actor authorization runs inside
the per-record lease and fails closed for missing, denied, exceptional, or
malformed decisions. Legacy callers without an actor remain compatible, and a
notification failure is reported after persistence so the durable record stays
authoritative. The focused host/interaction/run suite reports `49 passed in
2.80s`; the tracked manifest reports `1215 passed, 1 skipped in 227.81s`;
Ruff, Black, compile, diff, doctor, and changed-boundary mypy pass. A clean
archive rebuilt wheel/sdist `1.1.3`; Twine passed for both, the sdist contains
484 entries including ADR-040, the host-hook module, and its regression, and
the workspace-only audit found zero preserved Doctrine files. Remote
authentication/transport, exactly-once external effects, and multi-round
interaction remain separate follow-on boundaries.

2026-08-26 bounded same-record multi-round closure: ADR-041 extends durable
human-input records with an explicit `max_rounds` quota, current round index,
and immutable completed-round history. In-memory and file-backed stores expose
`continue_round`; the file path remains protected by the per-record fencing
lease, host authorization covers the continuation action, and a metadata-only
`continued` notification is emitted after persistence. `AutonomousAgent`
forwards the host operation, the built-in tool accepts the bounded quota, and a
multi-round result preserves prior responses while the original one-shot result
shape remains unchanged. The focused slice reports `23 passed in 2.74s`;
Ruff, Black, compile, diff, doctor, and changed-boundary mypy pass. The exact
tracked manifest reports `1219 passed, 1 skipped in 215.53s`. A clean archive
rebuilt wheel/sdist `1.1.3`; Twine passed for both, the sdist contains 485
entries including ADR-041, the interactions module, and the run regression,
and the workspace-only audit found zero preserved Doctrine files. No
 publication was performed.

2026-08-26 bounded local trace-span closure: ADR-051 adds immutable
`TraceSpan` records and a thread-safe bounded `SpanRecorder` with redacted
flat scalar attributes, parent/trace validation, terminal transitions,
retention, and JSON inspection. Optional sync/async model spans link
metadata-only `model.chunk`/`model.response` events and decision traces. A
follow-up review finding closed a direct-constructor attribute byte-bound gap
in `5200ece`, with a regression test. Focused coverage reports `36 passed in
0.43s`; the exact tracked manifest reports `1261 passed, 1 skipped in 260.28s`
across 108 tracked test files. Black, Ruff, changed-boundary mypy, compile,
diff, and network-free doctor pass. A clean committed-candidate package audit
reports build/Twine exit 0, sdist `501` entries, required public files `5/5`,
and workspace-only audit `0`. QA behavior/artifact and code review pass.
Hosted exporters, sampling, tool spans, remote transport, and backpressure
remain separate boundaries. Dependency-governance disposition remains open;
no publication was performed.

2026-08-26 bounded per-node retry closure: ADR-042 adds `RetryPolicy` with
bounded exponential backoff for ordinary workflow nodes. Exceptions and invalid
node outputs persist `NODE_RETRY_SCHEDULED` before retrying; checkpoints retain
retry counts and `retry_after`, contexts expose `retry_count`, and exhaustion is
persisted as `NODE_RETRY_EXHAUSTED` without serializing raw exceptions. The
focused workflow/replay suite reports `22 passed in 4.20s`; the exact tracked
manifest reports `1222 passed, 1 skipped in 222.42s`; Ruff, Black, compile,
diff, doctor, and changed-boundary mypy pass. A clean archive rebuilt
wheel/sdist `1.1.3`; Twine passed for both, the sdist contains 486 entries
including ADR-042, the workflow module, and its regression, and the
workspace-only audit found zero preserved Doctrine files. Parallel-branch retry
and exactly-once external effects remain separate boundaries. No publication
was performed.

2026-08-26 durable parallel-branch retry closure: ADR-055 extends the same
bounded `RetryPolicy` to named fan-out branches. Retry counts and finite due times
are persisted in checkpoint metadata; failed branches retry in bounded waves with
their `WorkflowContext.retry_count`, while successful branches are merged once in
declaration order. Terminal failure refreshes the latest checkpoint before its
CAS write, preserving version correctness after intermediate retry saves. The
focused workflow/replay suite reports `24 passed in 0.32s`; the exact tracked
manifest reports `1267 passed, 1 skipped in 256.93s`; Black, Ruff, changed-boundary
mypy, compile, diff, and doctor pass. Clean archive candidate `afa57d0` rebuilt
wheel/sdist `1.1.3`; Twine passed for both, the sdist contains `513` entries,
required public files are `5/5`, and the workspace-only audit found zero preserved
Doctrine files. Distributed scheduling and exactly-once external effects remain
separate boundaries. Dependency governance remains open; no publication was
performed.

2026-08-26 durable event cursor closure: ADR-043 adds JSON-safe
`EventCursor`/`EventBatch` values and bounded `EventStream.read` consumption.
Consumers can persist and advance cursors, while a cursor older than the
retained ring fails with `EVENT_CURSOR_EXPIRED` instead of silently skipping
events. `wait_for` accepts MAPLE's cooperative cancellation contract and
returns typed cancellation or malformed-signal errors. Existing redaction,
snapshot, subscriber, and lifecycle behavior is unchanged; remote transport,
provider token linkage, and hosted exporter behavior remain separate. No
publication was performed. The focused event/lifecycle suite reports `37 passed
in 2.28s`; the exact tracked manifest reports `1226 passed, 1 skipped in
216.99s`; Ruff, Black, compile, diff, doctor, and changed-boundary mypy pass.
The committed `HEAD` then rebuilt wheel/sdist `1.1.3` with build and Twine exit
0; the sdist contains 487 entries including all three slice files, and the
workspace-only audit found zero preserved Doctrine files. No publication was
performed.

2026-08-26 bounded handoff-context closure: ADR-044 extends the local handoff
tool with an explicit `allowed_context_keys` allowlist and recursively bounded
JSON context. Context is copied before crossing the boundary; denied keys and
legacy targets without `pursue_goal_with_context` fail closed. Autonomous
agents place the bounded context in their initial system message, which the
existing durable run checkpoint retains. Async target execution, durable
handoff identity/leases, ownership transfer, remote routing, and exactly-once
effects remain separate boundaries. No publication was performed.
The focused handoff/agent suite reports `50 passed in 4.40s`; the exact tracked
manifest reports `1230 passed, 1 skipped in 227.55s`; Ruff, Black, compile,
diff, doctor, and changed-boundary mypy pass. The committed-HEAD archive gate
then rebuilt wheel/sdist `1.1.3` with build and Twine exit 0; the sdist
contains 488 entries including all three slice files, and the workspace-only
audit found zero preserved Doctrine files. No publication was performed.

2026-08-26 async tool/handoff closure: ADR-045 adds optional awaitable tool
handlers, async registry execution, and async agent-loop dispatch. Legacy sync
tools remain compatible through executor-backed fallback, while a configured
trusted executor takes precedence over an async handler so policy bounds cannot
be bypassed. Handoffs await explicitly declared async target/context methods;
approval, bounded validation, guardrails, and target-error redaction remain
shared with sync execution. Durable handoff identity, ownership transfer,
remote routing, and hard cancellation remain separate boundaries. Focused
coverage reports `68 passed in 0.46s`; the exact tracked manifest reports
`1235 passed, 1 skipped in 215.23s` across 107 tracked test files. Black, Ruff,
changed-boundary mypy, compile, diff, and network-free doctor pass. A clean
committed-HEAD archive rebuilt wheel/sdist `1.1.3`; build and Twine exited 0,
the sdist contains 489 entries including all five slice files, and the
workspace-only audit found zero preserved Doctrine files. No publication was
performed.

2026-08-26 bounded stream usage/exporter closure: ADR-046 extends native
OpenAI-compatible and Anthropic `LLMChunk` values with bounded final
`TokenUsage` trailers and request correlation IDs; OpenAI usage requests are
opt-in and Anthropic partial usage is merged. `EventStream` now accepts a
host-owned `EventExporter` that receives only redacted events, validates its
contract, and cannot fail a run. Automatic provider-to-agent trace linkage,
durable/remote exporters, and hard cancellation remain separate boundaries.
The focused provider/event suite reports `16 passed in 0.28s`; the exact
tracked manifest reports `1237 passed, 1 skipped in 253.10s` across 107 tracked
test files. Black, Ruff, changed-boundary mypy, compile, diff, and network-free
doctor pass. A clean committed-HEAD archive rebuilt wheel/sdist `1.1.3`; build
and Twine exited 0, the sdist contains 490 entries including ADR-046 and the
Slice 100 files, and the workspace-only audit found zero preserved Doctrine
files. No publication was performed.

2026-08-26 provider-correlation closure: ADR-047 copies bounded provider
request IDs from `LLMResponse` into sync/async `model.response` lifecycle
metadata and `DecisionTrace` JSON export; IDs over 256 characters or containing
control characters are omitted. No raw provider response or SDK object is
copied. Incremental chunk-to-run aggregation, a full trace/span graph,
durable/remote exporters, and hard cancellation remain separate boundaries.
Focused correlation coverage reports `73 passed in 1.45s`; the exact tracked
manifest reports `1237 passed, 1 skipped in 249.77s` across 107 tracked test
files. Black, Ruff, changed-boundary mypy, compile, diff, and network-free
doctor pass. A clean committed-HEAD archive rebuilt wheel/sdist `1.1.3`; build
and Twine exited 0, the sdist contains 491 entries including ADR-047 and the
Slice 101 files, and the workspace-only audit found zero preserved Doctrine
files. No publication was performed.

2026-08-26 versioned-evaluation/judge slice: ADR-048 adds bounded
`EvalCase.fixture_version` and trajectory quotas, plus an optional local
provider-neutral `EvalJudge` returning a bounded `EvalJudgeResult`. Judge
observations use redacted bounded output; malformed, failing, or unavailable
judges become typed per-case failures. Deterministic evaluation remains the
baseline; provider orchestration, calibration, async judges, and semantic
faithfulness remain separate contracts. No publication was performed.

2026-08-26 durable-handoff closure: ADR-049 adds bounded hash-only
`HandoffRecord`/`HandoffStore` identity with in-memory and atomic file-backed
implementations, explicit source/target ownership transitions, per-record
fencing leases, and optional sync/async handoff-tool integration. Focused
handoff/store coverage reports `30 passed in 0.31s`; the exact tracked manifest
reports `1248 passed, 1 skipped in 238.37s` across 108 tracked test files.
Black, Ruff, changed-boundary mypy, compile, diff, and network-free doctor
pass. A clean committed-HEAD archive rebuilt wheel/sdist `1.1.3`; build and
Twine exited 0, the sdist contains 495 entries including ADR-049, and the
workspace-only audit is empty. Remote routing, scheduling, notifications, hard
cancellation, and exactly-once effects remain outside the contract. No
publication was performed.

2026-08-26 bounded local observability metrics slice: ADR-053 adds
thread-safe `EventStream.metrics()` and `SpanRecorder.metrics()` snapshots for
retained capacity, eviction pressure, subscriber count, and open spans. The
snapshots are integer-only and local; sampling, histograms, remote aggregation,
and exporter delivery remain separate. A minor invalid-capacity typing finding
was fixed in `ec190bc` and re-tested. Focused coverage reports `30 passed in
0.25s`; the exact tracked manifest reports `1263 passed, 1 skipped in 248.55s`
across 108 tracked test files. Black, Ruff, changed-boundary mypy, compile,
diff, and network-free doctor pass. QA behavior and code review pass. A clean
committed-candidate package audit at `beba0f2` reports build/Twine exit 0, sdist
`507` entries, required public files `5/5`, and workspace-only audit `0`.
Dependency-governance disposition remains open; no publication was performed.

2026-08-26 local observability sampling and latency/backpressure slice:
ADR-054 adds stable `SpanRecorder(sample_rate=...)` sampling plus integer local
span completion, status, and latency metrics. `EventStream.metrics()` now also
reports accepted publishes, subscriber/exporter failures, and coarse publish
latency. Focused event/observability coverage reports `32 passed in 0.29s`.
Percentile histograms, durable/remote export, and hosted trace search remain
separate boundaries. Full regression and security review pass. A clean
committed-HEAD archive package audit at `025b6a7` reports build/Twine exit 0,
sdist `510` entries, required public files `5/5`, and workspace-only audit `0`.
Dependency-governance disposition remains open; no publication was performed.

2026-08-26 bounded local tool-span slice: ADR-052 adds optional `agent.tool`
child spans for normal sync and async ReAct tool execution under the active
model span. Spans retain only bounded tool identity, step, error status, and
result length; tool arguments and results are not copied. Existing approval,
human-input, checkpoint, and run-result behavior remains unchanged. Focused
coverage reports `38 passed in 0.34s`; the exact tracked manifest reports
`1263 passed, 1 skipped in 263.89s` across 108 tracked test files. Black, Ruff,
changed-boundary mypy, compile, diff, and network-free doctor pass. QA behavior
and code review pass. Package evidence is pending; hosted exporters, remote
routing, sampling/backpressure, and exactly-once effects remain separate
boundaries. A clean committed-candidate package audit reports build/Twine exit
0, sdist `504` entries, required public files `5/5`, and workspace-only audit
`0`. Dependency-governance disposition remains open; no publication was
performed.

2026-08-28 release automation safety closure: ADR-118 makes the release
workflow tag-driven, removes workflow-dispatch branch mutation, validates tag,
package, and changelog agreement before test and artifact work, and adds an
explicit confirmation gate for manual Test PyPI publication. The stale CI
version summary was removed, and the v1.1.4 G6 checklist is filed. Workflow
tests report `4 passed in 0.21s`; YAML parsing passes; the clean committed
archive at `1ac8a72` reports `1561 passed, 1 skipped in 227.39s`, doctor
success, source archive `821`, wheel `106`, sdist `735`, build/Twine/install/
import exit 0. No tag, publication, registry write, cloud action, or website
update was performed. The v1.1.4 checklist remains conditional pending the
version bump, clean-main release commit, independent review,
security/dependency disposition, and human authorization.

2026-08-28 workflow supply-chain closure: ADR-119 pins all `37/37` existing
GitHub Action references across CI, security, performance, packaging, and
publication workflows to verified full commit SHAs while retaining release
comments. The workflow pin regression suite reports `5 passed in 0.27s`, YAML
parsing passes, and no floating action reference remains. The clean committed
archive at `4f145b8` reports `1562 passed, 1 skipped in 228.60s`, doctor
success, source archive `824`, wheel `106`, sdist `738`, build/Twine/install/
import exit 0. No publication, registry write, cloud action, or website update
was performed.

2026-08-29 authenticated remote task-queue statistics closure: ADR-135 adds
`GET /v1/tasks/stats` and `RunClient.task_queue_stats()` under `task:read`.
The response is a fixed finite `QueueStats` envelope with no task payloads or
results; malformed or unavailable optional statistics fail closed, and both
in-memory and file-backed queues remain compatible. Focused server coverage
reports `65 passed in 28.48s`; the autonomy/task-management gate reports
`798 passed in 73.48s`; the full dirty workspace reports `1754 passed, 1
skipped in 321.08s`. The exact clean archive at `1cf3081` reports `1637
passed, 1 skipped in 260.03s`, source archive `889`, wheel `108`, sdist `803`,
build/Twine/install/import/doctor exit 0, and network-free doctor readiness.
No publication, registry write, cloud action, or website update was performed.

2026-08-29 authenticated remote task-start closure: ADR-136 adds
`TaskQueue.start_task(...)`, `FileTaskQueue` persistence, and
`POST /v1/tasks/{task_id}/start` / `RunClient.start_task(...)` under
`task:start`. Only the recorded owner of an `ASSIGNED` task can move it to
`RUNNING`; the queue records `started_at`, and existing restart recovery,
statistics, and callback semantics remain authoritative. Focused coverage
reports `80 passed in 29.76s`; autonomy/task-management reports `800 passed in
74.75s`; the full dirty workspace reports `1756 passed, 1 skipped in 316.99s`.
The clean implementation archive at `08f71e1` reports `894` source entries,
`1639 passed, 1 skipped in 259.10s`, wheel `108`, sdist `808`, and passing
build/Twine/install/import/doctor gates. No publication, registry write, cloud
action, or website update was performed.

2026-08-29 whole-package type-boundary closure: Slice192 commit `3b66f6d`
narrowed the two bounded invocation-response copies and annotated the dynamic
remote handoff result without changing runtime or wire behavior. Focused
invocation/server coverage reports `78 passed in 29.17s`; the full current
workspace reports `1756 passed, 1 skipped in 331.65s`; and the clean archive
revalidation reports `1639 passed, 1 skipped in 253.58s`. Whole-package mypy
reports `Success: no issues found in 101 source files`; changed-boundary
Black/isort/Ruff/compile/Doctrine checks pass. The clean archive contains `899`
entries, with wheel `108` and sdist `813` members; build, Twine, isolated
install/import, and network-free doctor pass. Review and QA are filed at
`docs/reviews/maple-agent-runtime-slice192.md` and
`docs/qa/maple-agent-runtime-slice192.md`. A first clean-suite attempt had one
transient Windows HTTP connection abort; isolated rerun and bounded clean
revalidation passed. No publication, registry write, cloud action, or website
update was performed.

2026-08-29 hosted coordination decision gate: Slice193 audits the remaining
P0 parity gaps rather than introducing a misleading local heartbeat, lease,
federation, tenancy, or hosted route. The next implementation requires an
explicit identity/tenant authority, distributed scheduler and liveness model,
external side-effect retry/idempotency policy, and local-emulator versus
approved-provider decision. No code, cloud service, publication, registry
write, or website update was performed.

2026-08-29 owner-safe task heartbeat: Slice194 adds a monotonic,
owner-checked `heartbeat_at` telemetry field for active local tasks, persists it
through `FileTaskQueue` with legacy-record compatibility, and exposes the
authenticated `task:heartbeat` route/client method. Heartbeat expiry, lease
renewal, reassignment, worker-failure reconciliation, distributed scheduling,
and exactly-once effects remain outside the contract.

2026-08-29 owner-safe task heartbeat closure: implementation commit `bb7690c`
passes focused queue/server coverage (`105 passed in 30.91s`), the full dirty
workspace (`1759 passed, 1 skipped in 324.36s`), and the exact clean archive
(`1642 passed, 1 skipped in 255.17s`). Whole-package mypy reports no issues in
101 source files; changed-boundary format, lint, compile, and Doctrine checks
pass. The clean archive contains `906` entries; its wheel contains `108`
members and sdist `820` members, with build, Twine, isolated install/import,
and network-free doctor passing. Review and QA are filed at
`docs/reviews/maple-agent-runtime-slice194.md` and
`docs/qa/maple-agent-runtime-slice194.md`. No publication, registry write,
cloud action, or website update was performed.
