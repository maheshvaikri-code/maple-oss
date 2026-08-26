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
| 8 | Release hardening | Security / QA / Release Manager | CI, changelog, release artifacts, package metadata | Full test/lint/type/audit/build matrix and clean-tree checklist | in progress: metadata-clean build, isolated dependency gate, wheel smoke, CI preflight, and focused gates pass; full-suite and independent-review gates remain open |
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
| 91 | Cross-process durable approval-store ownership | Chief Architect / Backend / Security / QA / Release | `docs/adr/037-*`, `maple/autonomy/approval.py`, approval lease tests, API/README/parity docs, changelog, QA/review evidence | Per-record lease acquisition for file get/create/decide/consume/list, no mutation on acquisition failure, explicit uncertain-commit release error, existing atomic/thread-safe behavior retained; input/run store integration remains separate | doing: focused approval + lease boundary `8 passed in 0.32s`; changed-file Ruff/Black/mypy/compile pending; package/doctor/full manifest pending; no publication |

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
