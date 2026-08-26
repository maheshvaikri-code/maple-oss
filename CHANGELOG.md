<img width="358" height="358" alt="maple358" src="https://github.com/user-attachments/assets/299615b3-7c74-4344-9aff-5346b8f62c24" />

<img width="358" height="358" alt="mapleagents-358" src="https://github.com/user-attachments/assets/e78a2d4f-837a-4f72-919a-366cbe4c3eb5" />

# MAPLE Changelog

**Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)**

## Unreleased

### Additions

- **Versioned evaluation fixtures and optional judge contract**: `EvalCase`
  now carries a bounded `fixture_version` and trajectory quota, while
  `EvaluationHarness.run` accepts an optional provider-neutral host judge with
  bounded score/decision/rationale results, redacted observations, and typed
  fail-closed errors. Deterministic evaluation remains the baseline; provider
  orchestration, calibration, async judges, and semantic-faithfulness claims
  remain outside this contract. Focused evaluation coverage reports `20 passed
  in 0.24s`; the exact tracked manifest reports `1242 passed, 1 skipped in
  242.17s` across 107 tracked test files. Black, Ruff, changed-boundary mypy,
  compile, diff, and network-free doctor pass. A clean committed-HEAD archive
  rebuilt wheel/sdist `1.1.3`; build and Twine exited 0, the sdist contains 492
  entries including ADR-048, and the workspace-only audit is empty. No
  publication was performed.
- **Provider correlation in agent observability**: bounded provider request IDs
  now flow from `LLMResponse` into sync/async `model.response` lifecycle events
  and `DecisionTrace` JSON export, with malformed IDs omitted. No raw provider
  objects are copied. Focused correlation coverage reports `73 passed in
  1.45s`; the exact tracked manifest reports `1237 passed, 1 skipped in
  249.77s` across 107 tracked test files. Black, Ruff, changed-boundary mypy,
  compile, diff, and network-free doctor pass. A clean committed-HEAD archive
  rebuilt wheel/sdist `1.1.3`; build and Twine exited 0, the sdist contains 491
  entries with ADR-047 and the Slice 101 files, and the workspace-only audit is
  empty. Incremental chunk aggregation, a full trace/span graph, durable/remote
  exporters, and hard cancellation remain separate boundaries. No publication
  was performed.
- **Bounded stream usage and exporter seams**: native OpenAI-compatible and
  Anthropic streams now expose bounded final `TokenUsage` trailers and provider
  request IDs when available; OpenAI usage requests are opt-in and Anthropic
  partial usage is merged. `EventStream` accepts a host-owned exporter that
  receives only redacted events, validates its contract, and isolates exporter
  failures from runs. Focused provider/event coverage reports `16 passed in
  0.28s`; the exact tracked manifest reports `1237 passed, 1 skipped in
  253.10s` across 107 tracked test files. Black, Ruff, changed-boundary mypy,
  compile, diff, and network-free doctor pass. A clean committed-HEAD archive
  rebuilt wheel/sdist `1.1.3`; build and Twine exited 0, the sdist contains 490
  entries with ADR-046 and the Slice 100 files, and the workspace-only audit is
  empty. Automatic provider-to-agent trace linkage, durable/remote exporters,
  and hard cancellation remain separate boundaries. No publication was
  performed.
- **Async-capable tools and handoffs**: added optional awaitable tool handlers,
  async registry execution, and async agent-loop dispatch. Existing synchronous
  tools remain compatible through executor-backed fallback; configured trusted
  execution policies take precedence so async dispatch cannot bypass their
  bounds. Approval, bounded validation, guardrails, and structured error
  handling remain shared. Handoffs use explicitly declared async target/context
  methods when available, while durable handoff identity, ownership transfer,
  remote routing, and hard cancellation remain separate boundaries. Focused
  coverage reports `68 passed in 0.46s`; the exact tracked manifest reports
  `1235 passed, 1 skipped in 215.23s` across 107 tracked test files. Black,
  Ruff, changed-boundary mypy, compile, diff, and network-free doctor pass. A
  clean committed-HEAD archive rebuilt wheel/sdist `1.1.3`; build and Twine
  exited 0, the sdist contains 489 entries with all five slice files, and the
  workspace-only audit is empty. No publication was performed.
- **Editable durable tool approvals**: approved decisions may persist one
  bounded JSON `edited_arguments` object through the in-memory or atomic file
  approval store. Sync and async durable resume execute the persisted edit after
  one-time claim; invalid or denied-with-edit decisions fail closed without
  mutating the pending request. Arbitrary multi-turn request/response HITL and
  cross-process leases remain separate follow-on boundaries.
- **Editable-approval validation**: the focused approval/run/agent slice reports
  `44 passed in 0.46s`; the exact tracked application manifest reports `1197
  passed, 1 skipped in 204.41s`; Ruff, Black, mypy, compile, diff, and doctor
  pass. A clean current archive rebuilt `1.1.3`; Twine passed, the sdist has
  470 entries including ADR-034, and the workspace-only audit is empty.
- **Durable human input**: added bounded in-memory/file request records and the
  `request_human_input` tool. Durable sync/async ReAct runs persist a pending
  input cursor, validate one host response against a JSON-Schema subset, or
  resume with a typed rejection; cross-process leases, notifications, and
  multi-round conversations remain explicit follow-on boundaries.
- **Durable human-input validation**: the focused interaction/run/tool/agent
  slice reports `61 passed in 0.51s`; the exact tracked application manifest
  reports `1202 passed, 1 skipped in 211.16s`; Ruff, Black, mypy, compile, diff,
  and doctor pass. A clean current archive rebuilt wheel/sdist `1.1.3`; Twine
  passed for both; the sdist contains 473 entries, includes ADR-035, and the
  workspace-only audit found zero preserved Doctrine files.
- **Cross-process fencing leases**: added `FileLeaseManager` with bounded
  caller-owned JSON state, OS-level inter-process locking, atomic replacement,
  restart-safe fencing counters, expiry, renew/release, and fail-closed typed
  storage errors. The focused resource/lease slice reports `41 passed in
  3.64s`; the exact tracked manifest reports `1207 passed, 1 skipped in
  214.53s`; Ruff, Black, changed-boundary mypy, compile, and doctor pass. A
  clean archive rebuilt wheel/sdist `1.1.3`; Twine passed for both, the sdist
  contains 475 entries including ADR-035 and ADR-036, and the workspace-only
  audit found zero preserved Doctrine files. Durable-store integration, remote
  authentication, and exactly-once effects remain outside this slice.
- **Approval-store ownership**: `FileApprovalStore` now acquires a namespaced
  per-record fencing lease before file-backed get/create/decide/consume/list
  operations. Acquisition failures return `APPROVAL_LEASE_ERROR` without
  mutation; release failures return `APPROVAL_LEASE_RELEASE_ERROR` with
  uncertain-commit guidance. Focused approval/lease coverage reports `8 passed
  in 0.31s`; the exact tracked manifest reports `1209 passed, 1 skipped in
  199.58s`; Ruff, Black, changed-boundary mypy, compile, diff, and doctor pass.
  A clean archive rebuilt wheel/sdist `1.1.3`; Twine passed for both, the sdist
  contains 477 entries including ADR-037, and the workspace-only audit found
  zero preserved Doctrine files. Input/run store integration and host
  notifications remain outside this slice.
- **Human-input store ownership**: extracted the shared `DurableRecordLease`
  wrapper and applied it to `FileHumanInputStore` for per-record
  get/create/respond/reject/consume/list fencing. Acquisition failures return
  `HUMAN_INPUT_LEASE_ERROR` without mutation; release uncertainty is typed.
  Focused approval/input/lease coverage reports `13 passed in 0.48s`; the exact
  tracked manifest reports `1211 passed, 1 skipped in 219.68s`; Ruff, Black,
  changed-boundary mypy, compile, diff, and doctor pass. A clean archive
  rebuilt wheel/sdist `1.1.3`; Twine passed for both, the sdist contains 480
  entries including ADR-038, and the workspace-only audit found zero preserved
  Doctrine files. Run-store ownership, notifications, authentication, and
  multi-round interaction remain outside this slice.
- **Run-store ownership**: `FileAgentRunStore` now acquires a namespaced
  per-run fencing lease for load and the complete compare-and-set save
  operation. Acquisition failures return `RUN_CHECKPOINT_LEASE_ERROR` without
  reading or mutating the checkpoint; release uncertainty is typed. Focused
  run-store coverage reports `14 passed in 2.66s`; the exact tracked manifest
  reports `1213 passed, 1 skipped in 228.60s`; Ruff, Black, changed-boundary
  mypy, compile, diff, and doctor pass. A clean archive rebuilt wheel/sdist
  `1.1.3`; Twine passed for both, the sdist contains 482 entries including
  ADR-039, and the workspace-only audit found zero preserved Doctrine files.
  Host notifications, authentication, exactly-once effects, and multi-round
  interaction remain outside this slice.
- **Human-input host hooks**: added local `HumanInputNotifier` and
  `HumanInputAuthorizer` protocols to both human-input stores. Lifecycle
  notifications for created/responded/rejected omit response payloads;
  actor authorization runs inside the record lease and fails closed. Legacy
  no-actor callers remain compatible, while notification failures are typed
  after persistence so the durable record remains authoritative. Focused
  host/interaction/run coverage reports `49 passed in 2.80s`; the exact
  tracked manifest reports `1215 passed, 1 skipped in 227.81s`; Ruff, Black,
  changed-boundary mypy, compile, diff, and doctor pass. A clean archive
  rebuilt wheel/sdist `1.1.3`; Twine passed for both, the sdist contains 484
  entries including ADR-040 and the host-hook regression, and the
  workspace-only audit found zero preserved Doctrine files. Remote
  authentication/transport, exactly-once effects, and multi-round interaction
  remain separate follow-on boundaries.
- **Bounded multi-round human input**: durable human-input requests now support
  an explicit `max_rounds` quota, same-record `continue_round`, and immutable
  completed-round history in memory and atomic file stores. Continuation stays
  behind the per-record lease, authorization covers the `continue` action,
  notifications remain metadata-only, and durable runs can wait on the same
  interaction before resume. The agent preserves prior responses for the
  multi-round tool result while keeping the one-shot result shape compatible.
  Focused coverage reports `23 passed in 2.74s`; the exact tracked manifest
  reports `1219 passed, 1 skipped in 215.53s`; Ruff, Black, compile, diff,
  doctor, and changed-boundary mypy pass. A clean archive rebuilt wheel/sdist
  `1.1.3`; Twine passed for both, the sdist contains 485 entries including
  ADR-041, the interactions module, and the run regression, and the
  workspace-only audit found zero preserved Doctrine files. No publication was
  performed.
- **Bounded per-node workflow retry**: added `RetryPolicy` with capped
  exponential backoff, persisted retry counts/timestamps, retry context
  metadata, and typed `NODE_RETRY_EXHAUSTED` failures for ordinary workflow
  nodes. Existing workflows without a policy still fail immediately; parallel
  branch retry remains a separate boundary. Focused workflow/replay coverage
  reports `22 passed in 4.20s`; the exact tracked manifest reports `1222
  passed, 1 skipped in 222.42s`; Ruff, Black, compile, diff, doctor, and
  changed-boundary mypy pass. A clean archive rebuilt wheel/sdist `1.1.3`;
  Twine passed for both, the sdist contains 486 entries including ADR-042, the
  workflow module, and its regression, and the workspace-only audit found zero
  preserved Doctrine files. No publication was performed.
- **Durable event cursors and cancellation**: added JSON-safe `EventCursor` and
  `EventBatch` values, bounded cursor reads, explicit `EVENT_CURSOR_EXPIRED`
  errors when ring retention has evicted a cursor, and cooperative cancellation
  support for event waiters using MAPLE's existing token contract. Remote
  transport, provider-native token linkage, and hosted exporters remain
  separate boundaries. Focused event/lifecycle coverage reports `37 passed in
  2.28s`; the exact tracked manifest reports `1226 passed, 1 skipped in
  216.99s`; Ruff, Black, compile, diff, doctor, and changed-boundary mypy
  pass. A clean committed-HEAD archive rebuilt wheel/sdist `1.1.3`; build and
  Twine exited 0, the sdist contains 487 entries including all three slice
  files, and the workspace-only audit found zero preserved Doctrine files. No
  publication was performed.
- **Bounded context-aware handoffs**: added an explicit `allowed_context_keys`
  allowlist, recursive JSON bounds and copy-on-boundary behavior, typed denied
  key/unsupported-target failures, and `AutonomousAgent` context-aware goal
  entry points whose initial context is retained in local run checkpoints.
  Legacy no-context handoffs remain compatible; async target execution, durable
  handoff identity, ownership transfer, and remote routing remain separate.
  Focused handoff/agent coverage reports `50 passed in 4.40s`; the exact tracked
  manifest reports `1230 passed, 1 skipped in 227.55s`; Ruff, Black, compile,
  diff, doctor, and changed-boundary mypy pass. A clean committed-HEAD archive
  rebuilt wheel/sdist `1.1.3`; build and Twine exited 0, the sdist contains 488
  entries including all three slice files, and the workspace-only audit found
  zero preserved Doctrine files. No publication was performed.
- **Agent-framework parity ledger**: added a source-backed functionality and
  runtime matrix for LangGraph, CrewAI, Microsoft Agent Framework, LlamaIndex,
  and OpenAI Agents SDK. It separates MAPLE's native infrastructure strengths
  from partial/deferred runtime surfaces and records the next highest-value
  gaps without counting adapters as parity.
- **Durable synchronous agent runs**: added bounded in-memory and atomic file
  `AgentRunStore` implementations with versioned JSON-safe ReAct checkpoints.
  Synchronous goals can pause on durable approval and resume after restart
  without repeating a completed tool call; the async path is extended in the
  following entry.
- **Async durable agent runs**: `pursue_goal_async(..., run_id=...)` now writes
  the same bounded checkpoints through executor-backed local store operations,
  and `resume_run_async()` recovers interrupted or approval-paused runs. Durable
  async tool calls pause before later side effects; distributed leases,
  exactly-once effects, and sandboxing remain outside the contract.
- **Async durable-run validation**: the tracked application suite reports
  `1,194 passed, 1 skipped in 205.06s`; the focused async/store slice reports
  `9 passed in 0.30s`; and a clean archive rebuilt the `1.1.3` wheel/sdist with
  both Twine checks passing and zero preserved workspace-only files.
- **Unified agent-run lifecycle events**: `AutonomousAgent.set_event_stream()`
  now exposes shared sync/async started, resumed, model, tool, pause, complete,
  and bounded failure metadata with usage trailers. Prompts, tool arguments,
  outputs, and final results are not emitted; ring eviction remains visible via
  `EventStream.dropped_count`.
- **Lifecycle-event gate status**: the focused slice reports `10 passed in
  0.27s`; static, doctor, clean-artifact, and Twine checks pass. The latest
  exact tracked run remains conditional after one existing Windows loopback
  oversized-body `ConnectionAbortedError` (`1194 passed, 1 failed, 1 skipped`);
  the isolated test passes and no retry-until-lucky result is claimed.
- **Loopback response hardening**: bounded JSON responses now explicitly flush
  and close their HTTP connection, eliminating the Windows oversized-body
  response race without changing routes or payloads. The server suite reports
  `4 passed in 2.34s`, and the exact tracked suite reports `1,195 passed, 1
  skipped in 222.53s` with no warning output.
- **Final artifact boundary**: the current clean `git archive HEAD` snapshot
  builds wheel/sdist `1.1.3`; both Twine checks pass, the 469-entry sdist
  contains ADR-031/032/033 and the durable/event modules, and the workspace-only
  audit is empty. Doctor reports `ready: true`; nothing was published.
- **Post-slice release revalidation**: the 101 tracked Python test files now
  report `1,191 passed, 1 skipped in 217.81s` with no warning output. A clean
  archive rebuilt wheel/sdist `1.1.3`; both Twine checks passed, the 466-entry
  sdist includes the durable-run module, and network-free doctor readiness is
  true. Workspace-only Doctrine and fresh-review gates remain open.
- **Tracked release-suite revalidation**: the 100 tracked test files now report
  `1,185 passed, 1 skipped in 210.07s` with no warning output; the slow
  workspace-only Doctrine gold verifier remains separately documented as open.
- **Clean tracked release artifacts**: a `git archive HEAD` snapshot built the
  wheel and sdist successfully; both Twine checks passed, and a 460-file sdist
  contained none of the preserved workspace-only files.
- **Explicit release boundaries**: documented the fail-closed status of the
  Redis, mutual-TLS, OAuth2, and untrusted-code execution compatibility
  surfaces and added regression assertions so unsupported functionality is not
  presented as implemented.
- **Bounded agent handoff tools**: `create_handoff_tool` exposes a specialist's
  synchronous `pursue_goal` boundary as an approval-by-default model tool with
  an 8,192-character task limit, structured goal results, and redacted target
  failure errors. The local primitive does not claim durable or distributed
  routing.
- **Deadline-bounded async orchestration**: async supervised and consensus
  execution now accepts a total `timeout_seconds` budget and a cooperative
  `CancellationToken`. Native async child tasks are canceled and drained, while
  sync-only executor fallbacks are documented as unable to be forcibly stopped;
  interruption returns typed `ORCHESTRATION_TIMEOUT` or
  `ORCHESTRATION_CANCELLED` errors.
- **Bounded structured-output repair**: `AutonomousConfig.max_output_retries`
  optionally allows up to three correction attempts for invalid typed/schema
  output or output-guardrail rejection. Retries consume normal reasoning and
  token budgets, preserve structured errors on exhaustion, and default to
  fail-fast behavior.
- **Bounded multi-agent orchestration**: supervisor and consensus execution now
  fan out independent goals with a configurable `max_parallel_agents` limit,
  deterministic result ordering, sync/async entry points, and normalized worker
  exceptions. No distributed scheduler or new dependency is claimed.
- **Per-goal token accounting and hard budgets**: autonomous goals now expose
  aggregate provider token usage through `Goal.token_usage`, with optional
  `AutonomousConfig.max_total_tokens` enforcement across sync/async reasoning
  and reflection. Missing or malformed usage and budget overruns fail closed
  before tool side effects; no new dependency was added.
- **Optional bounded Protobuf serialization**: implemented both directions of
  `SerializationFormat.PROTOBUF` using an optional `google.protobuf.Struct`
  envelope. MAPLE preserves its existing JSON-compatible special-value handling,
  caps inbound and outbound payloads at 1 MiB, rejects malformed envelopes, and
  returns `PROTOBUF_UNAVAILABLE` when protobuf is absent. Core/autonomy coverage
  reports `240 passed in 3.37s`; no dependency was added.
- **Typed tool contracts**: added optional Pydantic-style `Tool.input_model`
  and `Tool.output_model` boundaries. MAPLE now publishes model-derived tool
  schemas, validates inputs before handler execution, normalizes validated
  fields for handlers, and returns validated output model instances. Focused
  contract/tool/agent coverage reports `43 passed in 0.37s`; the full autonomy
  surface reports `212 passed in 3.26s`; no new dependency was added.
- **Typed model outputs**: added additive Pydantic-style `output_model` support
  to `AutonomousConfig`. MAPLE now advertises the model JSON Schema, parses
  bounded JSON, returns a validated model instance, supports Pydantic v1/v2
  method names, and fails closed on invalid model output. The autonomy suite
  reports `210 passed in 3.37s`; no new dependency was added.
- **Repository-wide Ruff closure**: cleaned the final legacy import-boundary
  findings in the Doctrine adapter and security authentication/separation
  modules with narrow E402 handling and preserved optional JWT behavior. The
  affected regression reports `107 passed in 4.02s`; Ruff, Black, isort, mypy,
  and compile checks pass, and broad `ruff check maple` reports zero findings.
  The exact-current full repository suite remains an open release gate.
- **Residual module-header lint closure**: converted secondary module headers
  across autonomy, broker, LLM, monitoring, security, and state package
  surfaces to comments. The affected suite reports `635 passed, 1 skipped`;
  changed-file quality/type checks pass. Broad `ruff check maple` decreased
  from `58` diagnostics to `19` (`E402 19`, `F401 0`). The exact-current full
  repository suite remains an open release gate.
- **Verified unused-import closure**: removed imports proven unused by Ruff
  across 13 runtime files, preserved the S2 optional SDK compatibility probe
  with a narrow line-level exception, and closed two secondary module headers.
  The affected suite reports `777 passed, 1 skipped`; current S2/resource/link
  revalidation reports `130 passed`. Broad `ruff check maple` decreased from
  `95` diagnostics to `58` (`E402 58`) with zero F401 findings. Remaining E402
  debt remains a release gate.
- **Legacy header/import lint closure**: converted secondary module headers to
  comments and removed verified unused imports across seven runtime files. The
  affected regression reports `628 passed, 1 skipped in 16.35s`; changed-file
  Ruff, Black, isort, mypy, and compile checks pass. Broad `ruff check maple`
  decreased from `171` diagnostics to `95` (`E402 69`, `F401 26`). Remaining
  legacy lint remains a release gate.
- **Safe legacy lint and FIPA closure**: removed verified unused imports and
  locals, redundant formatting, and secondary module-header lint debt across
  seven runtime files; corrected FIPA ACL translation to emit the mapped
  performative and added regression coverage. The affected regression reports
  `131 passed in 48.43s`; changed-file Ruff, Black, isort, and mypy checks pass.
  Broad `ruff check maple` decreased from `250` diagnostics to `171`
  (`E402 140`, `F401 31`). Remaining legacy lint remains a release gate.
- **Release preflight refresh**: the explicit Python 3.10-target mypy audit is
  clean across all 93 source files; the focused cross-surface regression is
  `269 passed, 1 skipped`, the full LLM suite is `36 passed`, and wheel/sdist,
  Twine, formatter, enforced Ruff, compile, and network-free doctor gates pass.
  Full repository regression, broad legacy `maple/` Ruff debt,
  dependency/security audit disposition, and fresh verification remain release
  gates; no publication or website change was performed.
- **Mypy toolchain contract**: retained the package's Python `>=3.8` runtime
  support while setting the static-analysis target to Python 3.10, the minimum
  accepted by mypy 2.x. Default mypy now reports no issues across 93 source
  files, and the wider cross-surface regression is `616 passed, 1 skipped`.
- **Security boundary hardening**: added a bounded A2A registry timeout,
  explicit MCP URL-boundary regressions, and a size-bounded restricted pickle
  unpickler that rejects callable/module globals. The security regression is
  `37 passed`; isolated `pip check` and `pip-audit` are clean, and Bandit
  `-ll` reports zero medium/high findings. Thirty-five low-severity legacy
  findings remain explicitly tracked; no publication or website change was
  performed.
- **OpenAI SDK resource-function boundary**: implemented the previously
  undefined `maple_resource_request` route with injected `ResourceManager`
  allocation, finite-positive input validation, and fail-closed behavior when
  no resource service is configured. The offline adapter regression passes 2
  tests, changed-file mypy/Ruff are clean, and the aggregate audit is now
  `51 errors` in 4 files.
- **LangGraph recovery boundary**: implemented bounded retry,
  resource-reallocation, and graceful-degradation decisions for the adapter's
  existing error route, and made optional LangGraph/LangChain imports type-safe
  across the unavailable-SDK fallback. The offline recovery regression passes
  3 tests, changed-file checks are clean, and the aggregate audit is now
  `42 errors` in 3 files.
- **CrewAI tool-boundary closure**: implemented the advertised MAPLE
  communication, resource, secure-link, and priority tools, with structured
  failures for unavailable services and a type-safe optional CrewAI fallback.
  The offline adapter regression passes 3 tests, changed-file checks are clean,
  and the aggregate audit is now `27 errors` in 1 file.
- **NATS optional-transport type closure**: typed nullable NATS configuration,
  optional SDK/error aliases, message-ID/result boundaries, callback payloads,
  and the synchronous event-loop wrapper without attempting network access.
  The offline NATS checks report `1 passed, 1 skipped` because `nats-py` is not
  installed, and the explicit Python 3.10-target audit is clean across all 93
  source files.
- **LLM provider SDK type boundaries**: clarified optional OpenAI and Anthropic
  client configuration, compatible request payload containers, and response
  parsing boundaries without changing provider behavior. The native provider
  streaming regression passes 3 tests, changed-file mypy is clean with skipped
  imports, and the aggregate audit is now `62 errors` in 5 files.
- **Foundational runtime type-boundary cleanup**: narrowed `Result` unions,
  message/ID builders, autonomy tools and workflows, MCP discovery, state
  storage, security/audit/authentication, core-agent queues, task scheduling,
  and health-monitoring state without weakening runtime behavior. Focused
  regressions and changed-surface quality checks are recorded in the slice 29
  review/QA artifacts. The aggregate type audit is still open at `313 errors`
  in 46 files, and the installed mypy target mismatch remains a release gate.
- **Broker/MCP release boundaries**: typed broker singleton, queue, routing,
  and production-factory state; added explicit MCP adapter boundaries and a
  fail-closed result for unconfigured resource management instead of an
  attribute error. Broker and MCP regressions are recorded in the slice 30
  evidence; aggregate type debt remains open at `287 errors` in 44 files.
- **Resource primitive typing**: clarified resource specification serialization,
  manager initialization, and negotiation request/offer queues without changing
  allocation behavior. The resource package passes 92 tests; aggregate type
  debt remains open at `277 errors` in 43 files.
- **Fresh release-gate revalidation**: the current tree builds the 1.1.3
  wheel/sdist, both artifacts pass Twine validation, the network-free doctor
  reports `ready: true`, and the full Maple formatter plus tools/tests lint and
  compile checks pass. No external publish was performed.
- **MCP resource-management integration**: `MCPAdapter` now accepts optional,
  host-owned `ResourceManager` and `ResourceNegotiator` services. Validated
  `allocate`, `release`, and `negotiate` actions return structured results;
  missing services remain fail-closed. The focused MCP/resource suite passes
  97 tests, and the explicit Python 3.10-target aggregate type audit is now
  `266 errors` in 40 files. See ADR-023 and the slice 33 review/QA evidence.
- **Task monitoring type boundary**: completed public Optional and return
  annotations in `TaskMonitor` without changing monitoring behavior. The
  monitoring/task-management regression surface passes 156 tests, and the
  aggregate explicit Python 3.10-target audit is now `252 errors` in 39 files.
- **Task scheduler type boundary**: completed scheduler policy, metrics,
  lifecycle, callback, and queued-task narrowing without changing scheduling
  behavior. The scheduler regression surface passes 27 tests, and the
  aggregate explicit Python 3.10-target audit is now `246 errors` in 38 files.
- **Performance optimizer type boundary**: completed optimizer lifecycle,
  callback, cache-signature, trend, and loop contracts without changing
  optimization behavior. The performance-optimizer regression surface passes
  37 tests, and the aggregate explicit Python 3.10-target audit is now
  `239 errors` in 37 files.
- **Fault-tolerance boundary**: completed circuit-breaker, executor lifecycle,
  retry, recovery-handler, and callback contracts. Also fixed the executor's
  half-open circuit transition to use a writable validated state boundary;
  fault-tolerance tests pass 10, and the aggregate audit is now `221 errors`
  in 36 files.
- **Result-collector type boundary**: completed collector lifecycle, metadata,
  timeout, callback, filtering, cleanup, and background-loop contracts. Custom
  aggregation now fails with structured data when its callable is absent; the
  result-collector suite passes 33 tests, and the aggregate audit is now
  `205 errors` in 35 files.
- **CLI/package validation type boundary**: annotated the local doctor CLI,
  package validation, and banner contracts without changing their behavior.
  CLI/basic regressions pass 8 tests, the explicit changed-file mypy check is
  clean, and the aggregate audit is now `201 errors` in 33 files.
- **Serialization/provider registry type boundary**: annotated optional
  serialization dependency checks, message serialization input, and built-in
  provider registration lifecycle without changing runtime behavior. The
  serialization/provider suite passes 32 tests, the explicit changed-file
  mypy check is clean, and the aggregate audit is now `198 errors` in 31 files.
- **Error/state lifecycle type boundary**: annotated consistency and
  synchronization manager constructor contracts without changing distributed
  state behavior. The state regression surface passes 22 tests, the explicit
  changed-file mypy check is clean, and the aggregate audit is now
  `196 errors` in 30 files.
- **Failure-detection type boundary**: completed circuit-breaker wrapper,
  detector lifecycle, recovery, callback, and background-loop contracts while
  preserving failure detection behavior. The dedicated discovery regression
  passes 14 tests, the explicit changed-file mypy check is clean, and the
  aggregate audit is now `181 errors` in 29 files.
- **Discovery registry/capability boundary**: clarified optional registry
  filters and registration inputs, capability requirement parameters, matcher
  lifecycle, and compatibility-matrix construction without changing discovery
  behavior. The combined registry/capability/health regression passes 43 tests,
  the explicit changed-file mypy checks are clean, and the aggregate audit is
  now `172 errors` in 27 files.
- **Security link/encryption type boundary**: clarified optional link IDs and
  lifecycle state, encryption metadata, crypto-manager narrowing, and signing
  key inputs without changing cryptographic behavior. The link/encryption
  regressions pass 34 tests, both explicit changed-file mypy checks are clean,
  and the aggregate audit is now `163 errors` in 25 files.
- **Communication pattern type boundary**: clarified agent and stream
  constructors, typed pending request state, narrowed broker result boundaries,
  and normalized direct publish IDs and stream subscribers to their declared
  contracts. The communication regression surface passes 49 tests, all three
  changed-file mypy checks are clean, and the aggregate audit is now
  `152 errors` in 22 files.
- **Agent handler type boundary**: clarified message-handler construction,
  registry storage and lookup, handler predicates, and list results without
  changing dispatch behavior. The agent regression surface passes 33 tests,
  the changed-file mypy check is clean, and the aggregate audit is now
  `150 errors` in 21 files.
- **Error recovery result boundary**: narrowed retry fallback and circuit-breaker
  error values to their generic `Result` contracts using static-only casts;
  runtime error payloads and failure transitions are unchanged. The error suite
  passes 42 tests, both changed-file mypy checks are clean, and the aggregate
  audit is now `147 errors` in 19 files.
- **State synchronization result boundary**: separated the set and delete
  operation results in the synchronizer so their concrete state-store result
  types do not collide during static analysis. The synchronization regression
  passes 9 tests, the changed-file mypy check is clean, and the aggregate audit
  is now `146 errors` in 18 files.
- **Autonomy event payload typing**: separated list and mapping containers in
  recursive event redaction so payload shape and secret replacement remain
  explicit under static analysis. The event regression passes 5 tests, the
  changed-file mypy check is clean, and the aggregate audit is now
  `143 errors` in 17 files.
- **Workflow next-node typing**: initialized the execution loop’s next-node
  value with its declared optional contract before sequential or parallel route
  assignment. Workflow and replay regressions pass 19 tests, the changed-file
  mypy check is clean, and the aggregate audit is now `142 errors` in 16 files.
- **Health-monitor type boundary**: clarified status defaults, monitor lifecycle
  returns, optional heartbeat metrics, callback registration, and background
  loop contracts without changing health evaluation behavior. The health
  regression passes 15 tests, the changed-file mypy check is clean, and the
  aggregate audit is now `136 errors` in 15 files.
- **Legacy interop adapter typing**: clarified A2A, ACP, and FIPA ACL adapter
  constructors and the FIPA JSON decode boundary without changing translation
  behavior. No dedicated adapter tests exist; import smoke, compile, formatter,
  and changed-file mypy checks pass, and the aggregate audit is now
  `132 errors` in 12 files.
- **Production broker factory typing**: separated concrete in-memory, NATS, and
  S2 broker locals so optional backend implementations do not collide during
  static analysis. The S2/broker regression passes 16 tests, the changed-file
  mypy check is clean, and the aggregate audit is now `130 errors` in 11 files.
- **AutoGen adapter typing**: clarified adapter construction, agent registry,
  group-chat inputs, and mixed integer/float performance metrics without
  changing AutoGen translation or send behavior. Import smoke reports
  `AUTOGEN_AVAILABLE: True`, the changed-file mypy check is clean, and the
  aggregate audit is now `126 errors` in 10 files.
- **Doctrine adapter result boundaries**: narrowed artifact-reference values,
  validation error propagation, and agent send results without changing
  fail-closed schema validation or routability behavior. The doctrine adapter
  suite passes 34 tests, the changed-file mypy check is clean, and the aggregate
  audit is now `119 errors` in 9 files.
- **Security compatibility façade typing**: typed intentional authentication,
  authorization, and link fallbacks, including token/link state and result
  contracts, without changing fallback behavior. The security-init regression
  passes 30 tests, the changed-file mypy check is clean, and the aggregate audit
  is now `95 errors` in 8 files.
- **S2 stream adapter typing**: clarified stream helper/read-session contracts
  and narrowed optional basin/stream SDK boundaries without changing dependency
  fallback behavior. The mocked S2 adapter suite passes 16 tests, the
  changed-file mypy check is clean, and the aggregate audit is now
  `87 errors` in 7 files.
- **Repository formatter gate closure**: normalized the tracked `maple/`
  source tree with the configured Black and isort profiles. Both checks are
  now idempotent, the focused runtime gate remains `240 passed`, and a fresh
  wheel/sdist build passes Twine validation. Full-repository regression is
  still incomplete, and type/security debt remains explicitly open.
- **Fail-closed CI quality and security gates**: removed silent success paths
  from the CI, quality, dependency-audit, and security workflows; security
  reports are still collected before the original audit status is returned.
  Read-only contents permissions now protect workflows that do not publish or
  mutate repository state. Existing Black/isort/mypy/Bandit debt is therefore
  visible as a release blocker instead of being masked.
- **Repository lint gate closure**: cleared the 154 repository Ruff findings
  across the tracked test surface without weakening import-smoke coverage;
  `python -m ruff check tools tests` now passes, with a 621-test changed
  surface regression and the focused MAPLE gate still green.
- **Legacy test warning closure**: basic-functionality checks now fail closed
  under pytest while preserving their standalone runner, and S2 cache tests
  use `asyncio.run` instead of deprecated event-loop lookup.
- **CI/release preflight**: GitHub Actions now enforces isolated dependency
  consistency, compilation, the network-free doctor, changed-runtime Flake8,
  focused regressions, and built-wheel verification before package release.
- **Live MCP discovery** (`maple.adapters.mcp_adapter`,
  `maple.autonomy.mcp_tools`): added a dependency-free bounded Streamable HTTP
  transport with lazy MCP initialization, JSON/SSE response parsing, live
  paginated `tools/list`, real JSON-RPC `tools/call`, RPC error mapping, and
  strict external descriptor conversion. Live tools require approval by
  default; the historical URL-only discovery call remains offline for
  compatibility.
- **Artifacts and code blocks** (`maple.autonomy.artifacts`): added immutable
  SHA-256-addressed in-memory and file-backed stores with byte quotas, restart
  persistence, hash verification, and a bounded Markdown fence parser that
  returns code as data without executing it. Native sandbox, shell, browser,
  and computer-use execution remain intentionally unimplemented.
- **Provider-agnostic LLM streaming** (`maple.llm.provider`): the shared
  `stream()` contract now yields bounded text chunks, tool-call deltas, and a
  finish event after a successful completion, while preserving typed provider
  errors. Native low-latency provider streams remain explicit overrides.
- **Provider-native LLM streaming** (`maple.llm.openai_provider`,
  `maple.llm.anthropic_provider`): OpenAI-compatible and Anthropic async SDK
  streams now map native text, tool-use/function-call, and finish events into
  the shared bounded contract. Typed request failures and completion-backed
  compatibility fallback remain available when async clients are absent.
- **Bounded async tool fan-out** (`maple.autonomy.agent`): async ReAct turns
  now execute independent tool calls concurrently within the existing
  per-step cap, preserve original tool-call order for the next model turn, and
  isolate worker exceptions as typed tool results.
- **Fail-closed autonomous approval** (`maple.autonomy.agent`): tools marked
  as approval-required now return typed `APPROVAL_REQUIRED`,
  `APPROVAL_ERROR`, or `APPROVAL_DENIED` results without invoking handlers
  unless an approval callback explicitly approves the action.
- **Bounded workflow fan-out/fan-in** (`maple.autonomy.workflow`): independent
  branch nodes can run concurrently with isolated state snapshots, deterministic
  collision-free merging, and a checkpointed join boundary. The trusted
  in-process implementation remains bounded and does not claim sandboxing,
  per-branch retry, or cross-process coordination.
- **Durable tool approvals** (`maple.autonomy.approval`): added bounded
  in-memory and atomic JSON-file approval stores with pending, approved,
  denied, and one-time consumed states. Autonomous agents can persist a
  pending required-tool action, accept a host decision, and claim it before
  execution; full ReAct conversation replay remains separate.
- **Dependency-free vector retrieval** (`maple.autonomy.retrieval`): added a
  bounded in-memory cosine index over caller-supplied finite embeddings, with
  one-vector-per-chunk validation, deterministic ties, source citations, and
  no embedding-model or vector-database dependency.
- **Deterministic retrieval/citation evaluation** (`maple.autonomy.evaluation`):
  added bounded golden source-URI cases with lexical/vector hit support,
  source-level precision/recall/F1 metrics, malformed-runner isolation, and
  explicit separation from generated-answer faithfulness claims.
- **Deterministic grounded-answer evaluation** (`maple.autonomy.evaluation`):
  added bounded source URI/text fixtures, deterministic claim segmentation and
  lexical support ratios, typed threshold/malformed-runner failures, and an
  explicit no-semantic-entailment/no-LLM-judge boundary.
- **Bounded workflow history** (`maple.autonomy.workflow`): added an
  in-process `HistoryCheckpointStore` decorator that retains immutable,
  version-ordered checkpoint snapshots for inspection without claiming
  executable replay or cross-process durability.
- **Bounded conversation sessions** (`maple.autonomy.sessions`): added
  JSON-safe `SessionMessage`/`SessionSnapshot` values plus thread-safe
  in-memory and atomic file-backed stores with quotas, optimistic append/clear
  conflicts, and typed LLM tool-call conversion. Agent binding and replay stay
  explicit follow-on capabilities.
- **Loopback workflow run server** (`maple.autonomy.server`): added a
  dependency-free `WorkflowRegistry` and bounded local HTTP server with
  health, run, resume, and checkpoint inspection routes, stable JSON errors,
  loopback-only binding, and deterministic shutdown.
- **Session-aware agent turns** (`maple.autonomy.agent`): added opt-in sync
  and async binding to bounded session stores, CAS-protected user-turn
  persistence, user/assistant-only replay, and explicit `Goal.session_error`
  reporting when post-execution persistence fails.
- **Bounded workflow execution journal** (`maple.autonomy.replay`,
  `maple.autonomy.workflow`): added deterministic execution keys, bounded
  in-memory and atomic file journals, normalized-output recovery through
  `Workflow.recover`, conflict/malformed-record fail-closed behavior, and
  explicit documentation that this is not an exactly-once side-effect claim.
- **Release metadata hardening**: `pyproject.toml` is now the single source
  for package metadata, the legacy `setup.py` delegates to it, and the source
  manifest includes only files present in the repository. Wheel/sdist builds
  are warning-free and remain Twine-checkable.
- **Native workflow runtime (preview)** (`maple.autonomy.workflow`): validated
  sequential graphs, stable run IDs, JSON-safe node-boundary checkpoints,
  conditional routing, interruption/resume, atomic file persistence, and
  optimistic checkpoint versions. Public API documentation and regression
  tests are included.
- **Typed agent contracts (preview)** (`maple.autonomy.contracts`): bounded
  JSON-Schema validation for tool and model boundaries, structured output
  parsing, and fail-closed input/output guardrails with regression tests.
- **Trusted local execution (preview)** (`maple.autonomy.execution`): bounded
  trusted-handler execution with input/output byte limits, concurrency,
  timeout, cooperative cancellation, approval, and cleanup semantics. The
  public documentation calls out that it is not a hard-kill sandbox.
- **Retrieval/data primitives (preview)** (`maple.autonomy.retrieval`): bounded
  source-bearing documents, deterministic chunking with offsets, and a
  dependency-free lexical retriever with ranked citations and regression tests.
- **Event streaming and redaction (preview)** (`maple.autonomy.events`): bounded
  sequenced event retention, snapshot/wait/subscriber consumers, structured
  payload limits, and recursive credential-key redaction.
- **Evaluation/provider capabilities (preview)** (`maple.autonomy.evaluation`,
  `maple.llm.capabilities`): deterministic output/trajectory evaluation cases,
  redacted bounded reports, declared capability matching, and provider
  initialization fallback.
- **Interop and doctor CLI (preview)** (`maple.autonomy.interop`, `maple.cli`):
  strict versioned JSON adapter envelopes and a network-free machine-readable
  runtime readiness report.

## Version 1.1.3 - Downstream integration improvements (August 2026)

Hardening and extensibility surfaced by integrating MAPLE into a governed
downstream host. All backward-compatible except two intentional behavior
changes (noted below). Full suite: 1002 passed.

### Additions

- **`exponential_backoff(max_delay=...)`** (`maple.error.recovery`): optional
  per-attempt delay ceiling (`min(delay, max_delay)`, applied after jitter).
  Default `None` keeps the prior unbounded behavior. Prevents a large
  `max_attempts` from stalling a caller holding a resource across the backoff.
- **MCP tool governance** (`maple.autonomy.register_mcp_tools`): opt-in host
  hooks for untrusted MCP servers — `policy(tool, server_id)` (fail-closed
  default-deny), `namespace=True` (`mcp.<server_id>.<name>`, prevents
  shadowing), `max_tools` cap, and `sanitize_tool_name()`. No hooks =
  registers all tools as before.
- **`HealthMonitor.snapshot()`** (`maple.monitoring`): immediate on-demand
  health read computed from live counters, without waiting for the first
  sampling interval.
- **Resource model v2** (`maple.resources`): `ResourceLifecycle`
  (`RENEWABLE`/`CONSUMABLE`) + `DEFAULT_LIFECYCLES`; `register_resource(...,
  lifecycle=...)`; `release()` refunds only renewable resources (consumable
  budgets stay spent). `ResourceRequest.custom` for arbitrary named numeric
  dimensions (gpu/disk/money/api_calls/energy). New `LeaseManager`/`Lease` —
  exclusive, TTL-bounded holds with monotonic fencing tokens. Additive exports.

### Fixes / hygiene

- Replaced deprecated `datetime.utcnow()` with the non-deprecated naive-UTC
  equivalent (`maple.core.message`, `maple.security.cryptography_impl`);
  serialization unchanged.

### Behavior changes (intentional)

- `HealthMonitor.get_health_summary()` on a fresh monitor now returns a live
  summary instead of `{"status": "no_data"}`.
- Removed library `logging.basicConfig` from 7 modules — a library must not
  configure the root logger. MAPLE's own INFO logs no longer print unless the
  host configures logging.

---

## Version 1.1.2 - Doctrine wishlist + broker/task fixes (July 2026)

### Fixes

- **Broker double-delivery**: `MessageBroker.send()` enqueued every direct
  message into *both* the basic per-agent queue and the priority
  `MessageQueue`, and the delivery loop drains both — so each message was
  delivered (and each handler fired) twice. `send()` now enqueues into exactly
  one queue (priority queue, with the basic queue as fallback when it is
  unavailable/full). Added a delivered-exactly-once regression test.
- **`TaskQueue` unresponsive shutdown**: the cleanup thread slept with
  `time.sleep(300)`, so `stop()` blocked on its `join(timeout=5.0)` for the
  full 5 s every time — making test teardowns pile up until the suite looked
  hung. The loop now waits on a `threading.Event` that `stop()` sets, so
  shutdown returns promptly.
- **Handler-key case trap** (`Agent.register_handler`): handler keys are now
  normalized to upper-case, matching `Message` (which upper-cases every
  `message_type`). Previously a handler registered as `"work.package"`
  silently never fired for an incoming `WORK.PACKAGE`. Covers the
  `@agent.handler(...)` decorator path too. 5 regression tests. Implements
  enhancement ask #1 from `.Doctrine/integrations/maple.md`.

### Additions

- **Doctrine profile — `WORK.PACKAGE` / `GATE.RESULT` schemas**
  (`maple.adapters.doctrine_adapter`): typed builders + validators for the two
  doctrine protocol message types, beside the a2a/mcp/crewai adapters.
  `build_work_package` / `build_gate_result` return `Result[Message]`;
  `validate_work_package` / `validate_gate_result` check an incoming message;
  `DoctrineAdapter(agent)` dispatches them. Payloads carry artifact hashedrefs
  (via `ArtifactRef`) not prose, so they satisfy the fresh-context verifier
  preset; verdicts are validated against `GATE_VERDICTS`
  (`PASS`/`FAIL`/`BLOCKED`/`WAIVED`). Imported explicitly like the other
  adapters, so `import maple` stays free of the security layer. 34 tests, 100%
  coverage. Implements enhancement ask #4 from `.Doctrine/integrations/maple.md`.
- **Routability / opt-in delivery check** (`MessageBroker.is_routable`,
  `Agent.send(..., require_routable=True)`): `send()` returning `Ok` means
  *enqueued*, not delivered — a message to a nonexistent agent still enqueues.
  `is_routable(agent_id)` reports whether a receiver has a live subscription,
  and `require_routable=True` makes `Agent.send` return `Result.err` with
  `errorType` `UNROUTABLE` instead of a misleading `Ok`. Opt-in — the default
  `send()` behavior is unchanged. 7 regression tests. Implements enhancement
  ask #2 from `.Doctrine/integrations/maple.md`. (Reachability is checked at
  send time; a post-delivery acknowledgement receipt remains future work.)
- **`tokens` resource type** (`ResourceRequest`): LLM token budget is now a
  first-class resource alongside `compute`/`memory`/`bandwidth` — carried
  through `to_dict`/`from_dict` (so it survives negotiation) and handled by
  `ResourceManager` satisfy/allocate/release (numeric, like compute). Lets
  LLM budget negotiation map to loop-engineering caps. 9 regression tests.
  Implements enhancement ask #5 from `.Doctrine/integrations/maple.md`.
- **Fresh-Context Verifier Preset** (`maple.security.separation`): separation
  of duties as a broker-enforced runtime guarantee instead of a convention.
  - `SeparationOfDutiesPolicy` — a per-agent **sender allowlist** (fail-closed
    by default) plus an **artifact-ref-only payload policy** for guarded
    message types (`WORK.PACKAGE`, `GATE.RESULT`), exposed as
    `authorize_send(message) -> Result`.
  - `fresh_context_verifier_preset(orchestrator, builders, verifiers)` — wires
    orchestrator → everyone and each builder/verifier → orchestrator only, so
    a verifier can never route a review back to the author it is judging.
  - `ArtifactRef(path, sha256)` with `of()` / `for_file()` / `to_dict()` and
    the `is_artifact_ref()` validator — content-pinned artifact pointers so a
    builder's prose never travels into a verifier's context.
  - `MessageBroker.send()` **and** `publish()` enforce an attached policy
    (via new optional `SecurityConfig.separation_policy`), raising
    `SecurityError` on violation so `Agent.send()`/`publish()` return
    `Result.err(...)`. A newly-supplied policy is adopted even on the broker
    singleton's re-init, and `set_separation_policy()` is an explicit setter.
  - Hardening (from a fresh-context G4 review): topic fan-out is covered;
    a ref's `path` and dict keys are subject to the prose ceiling; custom
    `guarded_types` are upper-cased to match `Message`; receiver-less sends
    from a listed agent fail closed; deep/cyclic payloads are rejected
    (`PAYLOAD_TOO_DEEP`) instead of overflowing the stack.
  - Enforcement is applied by the in-memory `MessageBroker`; alternate
    transports (`nats_broker`, S2) are out of scope for this change.
  - 52 new tests. Implements enhancement ask #3 from
    `.Doctrine/integrations/maple.md`.

---

## Version 1.1.1 - S2.dev Integration (March 2026)

### Additions

- **S2.dev Durable Streaming**: `S2Broker` and `S2StateBackend` for durable message transport and state persistence via [s2.dev](https://s2.dev)
- **S2 Broker Type**: `BrokerType.S2` registered in `ProductionBrokerManager` with auto-detection from `s2://` broker URLs
- **Adapters Package**: New `maple/adapters/__init__.py` with conditional S2 exports
- **834 tests passing**, 16 new S2 adapter tests

### New Dependencies (optional)

```toml
[project.optional-dependencies]
s2 = ["streamstore>=5.0.0"]
```

---

## Version 1.1.0 - Autonomous Agentic AI (March 2026)

### Major Additions

- **LLM Provider Layer**: Pluggable provider system supporting OpenAI, Anthropic, and compatible APIs (vLLM, Ollama, Together)
- **Autonomous Agent**: ReAct-loop powered `AutonomousAgent` with goal pursuit, multi-step reasoning, reflection, and backtracking
- **Tool Framework**: Extensible `Tool` and `ToolRegistry` with built-in MAPLE tools (send_message, query_agents, read/write state, check resources, establish links)
- **Memory System**: Three-tier memory — `WorkingMemory` (context window), `EpisodicMemory` (task history), `SemanticMemory` (learned facts) — backed by existing `StateStore`
- **Multi-Agent Orchestrator**: `AgentOrchestrator` with supervisor and consensus execution patterns, capability-based team formation
- **MCP Tool Discovery**: Discover and register external MCP server tools as native MAPLE tools via `MCPAdapter`
- **Observability**: `DecisionLogger` and `AgentSnapshot` for full decision tracing and agent state inspection

### Infrastructure Improvements

- **Broker Wiring**: NATS broker auto-detection from `broker_url`, `ProductionBrokerManager` integration
- **Authorization Enforcement**: `AuthorizationManager` auto-initialized in `MessageBroker` when security config present
- **Message Queue & Router**: `MessageQueue` (priority ordering) and `MessageRouter` integrated into broker delivery loop
- **Agent Auto-Registration**: Agents auto-register/deregister in `AgentRegistry` on start/stop
- **Cryptographic Handshake**: Agent handshake uses real `CryptographyManager` (AES-256-GCM) with graceful fallback
- **Circuit Breaker Consolidation**: `TaskScheduler` and `FailureDetector` now use shared `error.circuit_breaker.CircuitBreaker`
- **Agent Metrics**: Built-in counters for messages sent/received/failed, handler errors, processing time
- **S2.dev Integration**: `S2Broker` and `S2StateBackend` for durable streaming via [s2.dev](https://s2.dev), auto-detected from `s2://` broker URLs

### Testing & Quality

- **818 tests passing**, 0 failures
- **80% code coverage** across all modules
- New test suites: LLM providers, autonomous agent, tools, memory, orchestrator, observability, performance optimizer, scheduler, result collector, security init

### New Dependencies (optional)

```toml
[project.optional-dependencies]
llm = ["openai>=1.0.0", "anthropic>=0.20.0"]
s2 = ["streamstore>=5.0.0"]
```

---

## Version 1.0.0 - Initial Release (December 2024)

### Major Changes
- **Protocol**: MAPLE (Multi Agent Protocol Language Engine) Multi Agent Communication Protocol
- **Attribution**: Added comprehensive attribution to Mahesh Vaikri throughout codebase
- **Enhanced Comparisons**: Updated all documentation to compare with major protocols:
  - Google A2A (Agent-to-Agent)
  - FIPA ACL (Foundation for Intelligent Physical Agents - Agent Communication Language)
  - AGENTCY
  - Model Context Protocol (MCP)

### Core Features
- **Rich Type System**: Comprehensive type validation with primitive, collection, and special types
- **Result<T,E> Pattern**: Advanced error handling with explicit success/error types
- **Resource Management**: Built-in resource specification, allocation, and negotiation
- **Link Identification Mechanism**: Secure communication channel establishment
- **Distributed State Management**: Consistency models for large-scale agent systems
- **Message Structure**: Standardized header, payload, and metadata format
- **Communication Patterns**: Request-response, publish-subscribe, streaming, and broadcast

### Security Features
- **Authentication**: JWT-based agent authentication
- **Authorization**: Role-based access control
- **Encryption**: End-to-end message encryption
- **Link Security**: Link Identification Mechanism for secure channels

### Documentation Updates
- **Comprehensive API Documentation**: Complete reference for all MAPLE components
- **Protocol Comparison**: Detailed comparison with competing protocols
- **Usage Examples**: Practical examples for common use cases
- **Best Practices**: Guidelines for effective MAPLE implementation

### Performance Characteristics
- **Scalability**: Support for 10,000+ agents
- **Latency**: 5-15ms message delivery
- **Throughput**: 10,000+ messages per second
- **Reliability**: 99.99% uptime with fault tolerance

### Use Cases
- **Manufacturing Systems**: Industrial automation and robotics coordination
- **Financial Trading**: High-frequency trading agent coordination
- **Smart Cities**: IoT and infrastructure management
- **Autonomous Vehicles**: Vehicle-to-vehicle communication
- **Healthcare**: Medical device and information system coordination

### Technical Improvements
- **Memory Optimization**: Efficient message serialization and processing
- **Network Efficiency**: Optimized protocol overhead
- **Error Recovery**: Circuit breaker pattern and retry mechanisms
- **Resource Optimization**: Dynamic allocation based on agent requirements

### Attribution
All files now include proper attribution:
```
# Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)
```

### Repository Structure
```
maple-oss/
├── maple/                 # Core MAPLE implementation
│   ├── core/             # Type system, messages, result handling
│   ├── agent/            # Agent implementation and configuration
│   ├── broker/           # Message routing and delivery
│   ├── security/         # Authentication, authorization, encryption
│   ├── resources/        # Resource management and negotiation
│   ├── communication/    # Communication patterns
│   ├── error/            # Error handling and recovery
│   └── state/            # Distributed state management
├── docs/                 # Comprehensive documentation
├── html_documentation/   # Interactive web documentation
├── sample/               # Usage examples and demos
└── tests/                # Test suite
```

### Breaking Changes
- Package name changed from `mapl` to `maple-oss`
- Import statements updated: `from maple import ...`
- Protocol name changed throughout documentation

### Future Roadmap
- **Formal Verification**: Mathematical verification of protocol correctness
- **Adaptive Protocols**: Self-optimizing communication patterns
- **Cross-Organization**: Multi-tenant agent coordination
- **Quantum Integration**: Quantum-safe cryptography support

**Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)**
