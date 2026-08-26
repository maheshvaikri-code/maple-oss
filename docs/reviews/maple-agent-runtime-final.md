# Final Code Review - MAPLE Agent Runtime release-readiness pass

**Reviewer role:** Code Reviewer / Chief Architect local pass
**Date:** 2026-08-24
**Branch:** `feat/maple-agent-runtime`

## Scope reviewed

The feature program now includes:

- durable workflow graph/checkpoint/resume;
- bounded typed tool/model contracts and fail-closed guardrails;
- trusted-local bounded execution with cooperative cancellation;
- source-bearing document chunking and lexical retrieval;
- bounded sequenced events with recursive redaction;
- evaluation cases for outputs/schemas/trajectories;
- declared provider capabilities and fallback routing;
- strict interop envelopes and the local `maple doctor --json` preflight;
- bounded live MCP `tools/list` discovery, JSON-RPC `tools/call`, and a
  dependency-free Streamable HTTP transport (ADR-007).
- immutable bounded artifacts and non-executing Markdown code-block parsing
  (ADR-008).
- provider-agnostic completion-backed LLM streaming with text, tool-call, and
  finish chunks (ADR-009).
- provider-native OpenAI-compatible and Anthropic streaming adapters with
  typed request errors and compatibility fallback (ADR-010).
- bounded asynchronous tool fan-out with deterministic result ordering and
  worker-error isolation (ADR-011).
- fail-closed autonomous approval for missing callbacks, callback errors, and
  denials without handler side effects (ADR-012).
- bounded checkpointed workflow fan-out/fan-in with isolated branch state,
  deterministic collision-free merging, and a documented at-least-once pause
  boundary (ADR-013).
- durable in-memory/file approval requests with fail-closed decisions and
  one-time consumption before handler execution (ADR-014).
- dependency-free vector retrieval over caller-supplied embeddings with
  bounded validation, deterministic cosine ranking, quotas, and source
  citations (ADR-015).
- bounded in-process workflow checkpoint history for immutable state-transition
  inspection without replaying node side effects (ADR-016).
- typed model output and optional typed tool input/output boundaries with
  model-derived schemas, pre-handler validation, normalized handler arguments,
  and validated model instances at the tool boundary.
- optional bounded Protobuf serialization through a generic `Struct` envelope,
  with preserved MAPLE special-value handling and explicit unavailable,
  malformed, and size-limit failures.
- opt-in per-goal token accounting and hard budgets across synchronous and
  asynchronous ReAct reasoning/reflection, with fail-closed provider usage
  validation before tool side effects (ADR-025).
- bounded synchronous/asynchronous fan-out for supervised and consensus teams,
  deterministic joins, and per-member worker error isolation (ADR-026).
- opt-in bounded structured-output repair retries with fail-fast defaults,
  sync/async parity, and token-budget accounting (ADR-027).
- async supervised/consensus request budgets and cooperative cancellation with
  native child-task draining, typed interruption errors, and an explicit
  sync-only executor limitation (ADR-028).
- bounded approval-aware agent-as-tool handoffs with input limits, structured
  target results, and redacted target failure errors (ADR-029).

Slice-level review artifacts are filed in `docs/reviews/` and corresponding QA
artifacts in `docs/qa/`. No website, cloud, external publication, license, or
new dependency change was made.

## Gate evidence

```text
Focused LLM/autonomy/CLI regression:
199 passed, 1 warning in 0.86s

Focused provider-stream regression:
5 passed, 1 warning in 0.03s

Focused async tool fan-out regression:
1 passed, 1 warning in 0.02s

Focused approval-boundary regression:
1 passed, 1 warning in 0.02s

Focused MCP/governance regression:
22 passed, 1 warning in 0.59s

Focused artifact regression:
5 passed, 1 warning in 0.04s

Focused regression in isolated `.[dev,security]` environment:
165 passed, 1 warning in 0.34s

Focused changed implementation Ruff check:
All checks passed!

Focused changed implementation Flake8 check:
0

Package build:
Successfully built maple_oss-1.1.3-py3-none-any.whl and maple_oss-1.1.3.tar.gz

Package metadata/build warnings:
None after consolidating metadata and the source manifest

Twine:
maple_oss-1.1.3-py3-none-any.whl: PASSED
maple_oss-1.1.3.tar.gz: PASSED

Wheel install smoke (clean venv, --no-deps):
{"version":"1.1.3","ready":true,"network":false}

Isolated dependency audit:
No broken requirements found.

Doctor:
{"checks":{"core":true,"evaluation":true,"events":true,"execution":true,"interop":true,"retrieval":true},"network":false,"ready":true,"status":"SUCCESS","version":"1.1.3"}
```

## Open release findings

1. The full `tests` run remains unfinished evidence, not a full-suite pass.
   The exact-current bounded attempt on `ded4477` collected `1276` items and
   reached `90%` before entering the Doctrine gold cases. The bounded session
   was interrupted without a pytest summary. The suspected S2
   adapter was cleared in isolation (16 passed in 0.06s). Fresh-repository
   profiling shows individual Git commands taking roughly 5–15 seconds, with
   the slowest gold cases at 166.96s, 159.74s, 115.61s, and 56.04s. No
   assertion failure was reported.
2. The shared interpreter's `pip check` still reports unrelated package
   conflicts (including `chromadb`, `fsspec`, `pydantic`, `openai`, and
   `langchain-core`), but a fresh environment installed `.[dev,security]` and
   returned `No broken requirements found.` The isolated dependency gate passes.
3. The full Bandit inventory retains 35 low-severity legacy findings; the
   medium/high gate is clean and the findings are tracked as non-blocking debt.
4. AGENTS.md requires G4/G5 verifiers as fresh sessions, but this tool context
    has no separate fresh-agent session facility. No independent-verifier claim
    is made.

## 2026-08-25 revalidation

- The focused cross-surface gate completed with `269 passed, 1 skipped in
  51.72s`; the full LLM suite completed with `36 passed in 0.24s`.
- The explicit Python 3.10-target mypy audit is now clean across all 93 source
  files, and the default repository invocation is now clean after slice 63
  aligned the static target with mypy 2.x. Package runtime support remains
  `>=3.8`.
- The broader cross-surface regression completed with `616 passed, 1 skipped in
  173.01s`; the repository-wide command collected 1262 items and entered the
  slow Doctrine gold phase without assertion output before its bounded session
  ended without a pytest summary.
- Slice 64 security revalidation completed with `37 passed`; isolated
  `pip check` and `pip-audit` are clean, and Bandit `-ll` exits 0 with zero
  medium/high findings. The full Bandit inventory has 35 low-severity legacy
  findings, which remain tracked as non-blocking debt.
- Black/isort, the enforced `tools`/`tests` Ruff gate, compile, wheel/sdist,
  Twine, and network-free doctor gates pass. The doctor reports all checks true,
  `ready: true`, `network: false`, version `1.1.3`.
- Slice 65 reduced broad legacy `ruff check maple` from 250 to 171 diagnostics
  (`E402 140`, `F401 31`) while keeping changed implementation surfaces clean.
  Remaining legacy lint remains an open release gate.
- Slice 66 reduced the broad inventory from 171 to 95 diagnostics (`E402 69`,
  `F401 26`) by removing secondary module-header and verified unused-import
  debt. The affected regression reports `628 passed, 1 skipped in 16.35s` and
  changed-file quality/type checks pass.
- Slice 67 reduced the broad inventory from 95 to 58 diagnostics (`E402 58`,
  `F401 0`) by removing verified unused imports across 13 runtime files. The
  affected suite reports `777 passed, 1 skipped`; current S2/resource/link
  revalidation reports `130 passed in 0.37s`.
- Slice 68 reduced the broad inventory from 58 to 19 diagnostics (`E402 19`,
  `F401 0`) by converting residual secondary module headers to comments. The
  affected suite reports `635 passed, 1 skipped in 16.90s`.
- The full repository attempt on the preceding commit collected `1270` items,
  reached `95%`, and was bounded/interrupted in Doctrine state tests without a
  pytest summary. Exact-current full-suite evidence remains open.
- Slice 69 closes the remaining 19 repository-wide E402 findings in the
  Doctrine adapter and security authentication/separation import boundaries.
  The affected regression reports `107 passed in 4.02s`; Ruff, Black, isort,
  mypy, and compile checks pass. Broad `ruff check maple` reports zero
  findings.
- Slice 70 adds the typed model output boundary. `AutonomousConfig.output_model`
  advertises the model schema and returns a validated Pydantic-style instance;
  invalid output fails closed. Focused coverage reports `28 passed in 0.35s`,
  and the full autonomy surface reports `210 passed in 3.37s`.
- Slice 71 adds optional typed tool input/output boundaries. Focused
  contract/tool/agent coverage reports `43 passed in 0.37s`, and the full
  autonomy surface reports `212 passed in 3.26s`. Exact static, package, and
  doctor gates pass; exact full-repository completion remains open.
- The exact-current repository run on `ded4477` collected `1276` items and
  reached the Doctrine gold phase without failure output, but was bounded and
  interrupted before pytest emitted a final summary.
- Slice 72 core/autonomy regression reports `240 passed in 3.37s`, including
  `28 passed in 0.28s` for the Protobuf boundary. Static, package, and doctor
  checks pass; the exact full repository suite has not yet been rerun after
  the slice.
- The post-Slice-72 exact repository attempt on `2b8bb57` collected `1278`
  items, reached the Doctrine gold phase, and emitted six gold-test completions
  before bounded interruption without failure output or a pytest summary.
- The exact-current run on `a51e043` collected `1282` items, reached `90%`, and
  entered the slow Doctrine gold phase before bounded interruption. No failure
  output or pytest summary was produced.
- The exact-current run on `1211701` collected `1291` items, reached `90%`, and
  entered the slow Doctrine gold phase before bounded interruption. No failure
  output or pytest summary was produced.

## Slice 73 revalidation

- The agent/session regression reports `30 passed in 0.31s`.
- `Goal.token_usage` is additive and preserves existing positional `Goal` and
  `AutonomousConfig` construction while aggregating provider usage across sync,
  async, and reflection responses.
- A configured `max_total_tokens` requires valid provider usage and returns
  structured `TOKEN_USAGE_UNAVAILABLE`, `TOKEN_USAGE_INVALID`, or
  `TOKEN_BUDGET_EXCEEDED` errors. Budget overflow is checked before tool
  execution; sync and async regressions prove handler side effects are absent.
- Changed-file Ruff, Black, isort, and mypy checks pass. No dependency or
  external integration was introduced. Exact full-suite and fresh-context
verification remain open.

## Slice 74 revalidation

- The agent/orchestrator regression reports `43 passed in 0.33s`.
- Sync and async supervised/consensus execution now fans out independent
  member goals within `max_parallel_agents`, preserves assignment order, and
  isolates worker exceptions as structured errors.
- Changed-file Ruff, Black, isort, and mypy checks pass. No external
  integration or dependency was introduced; exact full-suite and fresh-context
verification remain open.

## Slice 75 revalidation

- The agent regression reports `28 passed in 0.33s`.
- `max_output_retries` is validated from 0 through 3 and applied consistently
  to sync and async typed/schema/guardrail output failures. Retries remain
  ordinary reasoning steps and are charged to provider token usage.
- Exhaustion remains fail-closed with the original structured error. Changed
  static checks pass; no model, dependency, or external integration changed.
  Exact full-suite and fresh-context verification remain open.

## Slice 76 revalidation

- The orchestrator regression reports `24 passed in 0.43s`; the combined
  core/autonomy regression reports `257 passed in 3.60s`.
- `execute_supervised_async` and `execute_consensus_async` validate additive
  keyword-only `timeout_seconds` and `CancellationToken` bounds across
  decomposition, fan-out, collection, and synthesis.
- Native async child tasks are canceled and drained before typed
  `ORCHESTRATION_CANCELLED` or `ORCHESTRATION_TIMEOUT` results return. The
  existing sync-only executor fallback is documented as cooperative rather
  than falsely claiming hard thread termination.
- Ruff, Black, mypy, and compile checks pass; ADR-028, public docs, changelog,
  QA, and release-plan evidence are filed. No dependency or external action was
  introduced.
- The exact-current repository attempt on `bd1b179` collected `1295` items and
  passed the application suites through `90%` before entering the slow Doctrine
  gold phase. It was interrupted without failure output or a pytest summary;
  this remains an open release gate.
- A newer exact-current attempt on `2b7ea84` collected `1300` items and again
  passed the application suites through `90%` before the slow Doctrine gold
  phase. It was interrupted without failure output or a pytest summary.

## Slice 77 revalidation

- The tool regression reports `18 passed in 0.25s`; the combined autonomy
  regression reports `234 passed in 3.49s`.
- `create_handoff_tool` reuses the existing Tool schema, approval, and
  executor-backed async path. The required task string is capped at 8,192
  characters, and invalid input fails before the target is called.
- Target failures expose only stable handoff error types and target error type;
  target exceptions and invalid return values fail closed.
- Ruff, Black, mypy, compile, and public-import checks pass; ADR-029, public
  docs, changelog, plan, and QA evidence are filed. No dependency or external
  action was introduced.

## Slice 78 revalidation

- The public release brief and README now record the remaining intentional
  `NOT_IMPLEMENTED` boundaries: Redis state operations, mutual-TLS, and
  OAuth2. They also distinguish non-executing code-block extraction from the
  trusted-local handler executor.
- The documentation does not claim provider, transport, or sandbox behavior
  that the repository does not implement. A future implementation requires a
  scoped contract, dependency/security review, and failure-path coverage.
- No user-owned untracked files were changed or staged; no external action was
  taken.

## Slice 79 revalidation

- The tracked-test manifest contains 100 Python files and reports `1185 passed,
  1 skipped in 210.07s` with no warning output.
- The only warning was a test function returning a boolean; the fix preserves
  standalone invocation behavior and makes pytest assert the helper result.
- The tracked application suite is green. The workspace-only Doctrine gold
  verifier and fresh-context review are still separate open release gates.

## Slice 80 revalidation

- Release packaging was repeated from a temporary `git archive HEAD` snapshot,
  not the dirty shared workspace.
- Wheel/sdist construction and both Twine checks passed. The sdist content
  audit found zero preserved workspace-only files.
- This is the correct artifact boundary for future publication; no publication
  or external registry action occurred.

## Slice 81 revalidation

- The parity ledger is explicit about the comparison set, observation date,
  status vocabulary, and official framework references.
- The matrix does not make unsupported “built-in” claims for Redis,
  mutual-TLS, OAuth2, untrusted execution, hosted deployment, or language
  breadth. It also states that adapters are interoperability surfaces rather
  than native feature parity.
- The README now links to the ledger and narrows its summary comparison to
  evidence-backed MAPLE boundaries.
- The exact current clean archive rebuilt wheel/sdist `1.1.3`; both Twine
  checks passed, and the 463-entry sdist audit found no preserved workspace-only
  files.
- No code, dependency, user-owned untracked file, external service, website,
  or publication target was changed.

## Slice 82 revalidation

- The new `AgentRunStore` boundary is additive and reuses the existing
  JSON-safe `SessionMessage` representation rather than serializing Goal,
  provider, tool, or executable objects.
- File saves use a temporary file, flush/fsync, and atomic replacement;
  memory/file stores use compare-and-set versions and bounded payloads.
- Approval pause happens before subsequent model-requested tool side effects;
  resume replaces the pending tool placeholder and the regression proves a
  completed tool is not repeated after a model interruption.
- No security, dependency, license, cloud, publication, or website action was
  introduced. Async durable runs remain a separately visible follow-on.

## Slice 83 revalidation

- The current tracked manifest contains 101 Python test files and reports
  `1191 passed, 1 skipped in 217.81s` with no warning output.
- The current clean archive rebuilt wheel/sdist `1.1.3`; both Twine checks
  passed, the sdist contained 466 entries, `maple/autonomy/runs.py` was
  present, and the workspace-only audit found zero preserved Doctrine files.
- The network-free doctor returned `ready: true`, `status: SUCCESS`, all eight
  checks true, and `network: false`.
- These checks close the tracked application and current artifact gates. The
  workspace-only Doctrine gold verifier and fresh-context independent review
  remain open. No external action was taken.

## Slice 84 revalidation

- ADR-031 records the async extension: executor-backed local checkpoint I/O,
  async resume, and serial durable tool dispatch at the approval boundary.
- The focused async/store slice reports `9 passed in 0.30s`; the exact tracked
  application suite reports `1194 passed, 1 skipped in 205.06s` with no warning
  output.
- Current Ruff, Black, mypy, compile, doctor, clean archive, and Twine gates
  pass. The clean sdist contains 467 entries, includes the async implementation
  and ADR-031, and contains zero preserved workspace-only Doctrine files.
- No distributed lease, exactly-once, sandbox, durable streaming, or hosted
  runtime claim was added. No external service, publication, or website action
  was taken.

## Slice 85 revalidation

- ADR-032 adds an opt-in `EventStream` attachment with shared sync/async
  lifecycle metadata and usage trailers. Payloads omit prompts, tool
  arguments, tool output, and final result data; ring eviction remains visible
  through `dropped_count`.
- The focused lifecycle/run slice reports `10 passed in 0.27s`; the existing
  agent/session/event compatibility set reports `40 passed in 0.35s`.
- Ruff, Black, mypy, compile, doctor, clean archive, and Twine checks pass. The
  clean sdist contains 468 entries, includes ADR-032, and contains zero
  preserved workspace-only Doctrine files.
- The latest exact run had an existing Windows loopback-server
  oversized-body `ConnectionAbortedError`; ADR-033 hardens response flushing
  and closure without changing the server contract.

## Slice 86 revalidation

- The server suite reports `4 passed in 2.34s` after the response flush/close
  hardening.
- The exact tracked application suite reports `1195 passed, 1 skipped in
  222.53s` with no warning output. This closes the current tracked-suite gate.
- No dependency, route, status, payload, external-hosting, publication, or
  website action was introduced.

## Slice 87 revalidation

- The current tracked snapshot builds wheel/sdist `1.1.3` from `git archive
  HEAD`; both Twine checks pass.
- The 469-entry sdist includes ADR-031, ADR-032, ADR-033, and the durable/event
  modules while excluding all preserved workspace-only Doctrine files.
- Network-free doctor returns `ready: true`, all eight checks true, and
  `network: false`. No publication, website, cloud, or registry action was
  taken.

## Slice 88 implementation review

- `ApprovalDecision` now carries an optional keyword-only `edited_arguments`
  replacement. In-memory and atomic file stores validate the replacement with
  the existing JSON depth, item, finite-number, and byte quotas before any
  state transition or file write.
- Approved edits are selected after one-time claim by
  `execute_approved_tool()` and are honored by sync and async durable resume;
  invalid edits and denied-with-edit decisions leave the pending record
  unchanged. Arbitrary multi-turn request/response HITL and cross-process
  approval leases remain explicit gaps.
- Focused approval/run/agent regression reports `44 passed in 0.46s`; the
  exact tracked application manifest reports `1197 passed, 1 skipped in
  204.41s`. Ruff, Black, mypy, compile, and network-free doctor checks pass.
- A clean current-commit archive built wheel/sdist `1.1.3`; both Twine checks
  passed, the sdist contains 470 entries including ADR-034, and the
  workspace-only audit found zero preserved Doctrine files. No publication,
  website, cloud, or registry action was taken.

## Slice 89 implementation review

- Added bounded `HumanInputRequest`/`HumanInputDecision` records with in-memory
  and atomic file stores. Responses are JSON-safe and validated against the
  bounded JSON-Schema subset; rejection is explicit and typed.
- The reserved `request_human_input` tool is available only inside a durable
  run, persists `pending_input_id`, pauses before later tool calls, and resumes
  in sync and async paths after a response or rejection. Consumed decisions
  remain reconstructable after a crash between consume and checkpoint save.
- Focused interaction/run/tool/agent coverage reports `61 passed in 0.51s`;
  the exact tracked application manifest reports `1202 passed, 1 skipped in
  211.16s`. Ruff, Black, mypy, compile, diff, and network-free doctor checks
  pass.
- A clean current archive rebuilt wheel/sdist `1.1.3`; Twine passed for both,
  the sdist contains 473 entries including ADR-035, and the workspace-only
  audit found zero preserved Doctrine files. The feature remains one-shot;
  cross-process leases, notifications, and multi-round conversations are
  explicit follow-on gaps.

## Slice 90 implementation review

- `FileLeaseManager` adds a dependency-free file-backed coordination primitive
  without changing the in-memory `LeaseManager` contract. OS-level locks
  serialize local-process read/modify/write operations, and atomic replacement
  plus fsync protects the durable state boundary.
- Persisted fencing counters survive manager restart; exact holder/token checks
  prevent stale renewal or release, and corrupt/unavailable storage fails
  closed. The focused resource/lease slice reports `41 passed in 3.64s`; the
  exact tracked manifest reports `1207 passed, 1 skipped in 214.53s`. Ruff,
  Black, compile, doctor, and changed-boundary mypy pass. Repository-wide
  mypy retains 11 pre-existing optional-adapter stub findings.
- The primitive is intentionally not marketed as remote distributed locking,
  exactly-once external effects, or automatic ownership of durable agent
  stores. A clean archive rebuilt wheel/sdist `1.1.3`; Twine passed for both,
  the sdist contains 475 entries including ADR-035 and ADR-036, and the
  workspace-only audit found zero preserved Doctrine files. Those integrations
remain explicit follow-on work.

## Slice 91 implementation review

- `FileApprovalStore` now obtains a unique-holder, namespaced fencing lease
  before each file-backed operation while retaining its thread lock and atomic
  replacement boundary. Lease acquisition failure is fail-closed and cannot
  mutate the approval record.
- Lease release failure is surfaced explicitly; successful record mutation may
  already be durable, so the API documents the result as an uncertain commit
  requiring inspection before retry. The store does not claim notifications,
  remote authentication, or exactly-once external effects.
- Focused approval/lease coverage reports `8 passed in 0.31s`; the exact tracked
  manifest reports `1209 passed, 1 skipped in 199.58s`. Ruff, Black, compile,
  diff, doctor, and changed-boundary mypy pass. A clean archive rebuilt
  wheel/sdist `1.1.3`; Twine passed for both, the sdist contains 477 entries
  including ADR-037, and the workspace-only audit found zero preserved Doctrine
  files.

## Slice 92 implementation review

- The shared `DurableRecordLease` helper now owns lease acquisition, cleanup,
  typed acquire/release failures, and uncertain-commit detail merging. Approval
  behavior is preserved while `FileHumanInputStore` uses a distinct
  `human-input:<interaction_id>` namespace.
- Human-input validation remains inside the lease boundary, so invalid schema
  responses do not mutate a pending request. Notifications, remote operator
  authentication, multi-round interaction, and run-cursor ownership remain
  explicit gaps.
- Focused approval/input/lease coverage reports `13 passed in 0.48s`; the exact
  tracked manifest reports `1211 passed, 1 skipped in 219.68s`. Ruff, Black,
  compile, diff, doctor, and changed-boundary mypy pass. A clean archive
  rebuilt wheel/sdist `1.1.3`; Twine passed for both, the sdist contains 480
  entries including ADR-038, and the workspace-only audit found zero preserved
  Doctrine files.

## Slice 93 implementation review

- `FileAgentRunStore` now uses the shared `DurableRecordLease` with a distinct
  `run:<run_id>` namespace. Both load and the complete compare-and-set save
  operation are fenced while the existing thread lock, bounds, atomic replace,
  and version conflict behavior remain intact.
- Lease acquisition failure returns `RUN_CHECKPOINT_LEASE_ERROR` before a read
  or mutation. Release uncertainty returns
  `RUN_CHECKPOINT_LEASE_RELEASE_ERROR`; the API and ADR require inspection
  before retrying a potentially committed save.
- Focused run-store coverage reports `14 passed in 2.66s`; the exact tracked
  manifest reports `1213 passed, 1 skipped in 228.60s`. Ruff, Black, compile,
  diff, doctor, and changed-boundary mypy pass. A clean archive rebuilt
  wheel/sdist `1.1.3`; Twine passed for both, the sdist contains 482 entries
  including ADR-039, the run module, and the run lease regression, and the
  workspace-only audit found zero preserved Doctrine files.
- Host notifications, remote authentication, distributed identity,
  exactly-once external effects, and multi-round human input remain explicit
  follow-on gaps; this slice does not overclaim them.

## Slice 94 implementation review

- `HumanInputNotifier` and `HumanInputAuthorizer` are dependency-free local
  protocols attached to both supported stores. Notifications are bounded to
  request metadata and optional actor identity; submitted response payloads are
  excluded.
- Respond/reject authorization is performed before mutation inside the
  per-record lease. Missing actor identity, callback exceptions, malformed
  results, and denial return typed fail-closed errors. Internal consume remains
  an agent-owned transition rather than a host authorization surface.
- Notification callbacks run after persistence and their failure returns
  `HUMAN_INPUT_NOTIFICATION_ERROR`, making the durable record authoritative for
  inspection before retry. The agent preserves legacy custom-store callers when
  no actor is supplied.
- Focused host/interaction/run coverage reports `49 passed in 2.80s`; the exact
  tracked manifest reports `1215 passed, 1 skipped in 227.81s`. Ruff, Black,
  compile, diff, doctor, and changed-boundary mypy pass. A clean archive rebuilt
  wheel/sdist `1.1.3`; Twine passed for both, the sdist contains 484 entries
  including ADR-040 and the host-hook regression, and the workspace-only audit
  found zero preserved Doctrine files.
- Remote credential verification, transport, distributed identity,
  exactly-once external effects, and multi-round interaction remain explicit
  gaps; this slice does not overclaim them.

## Slice 95 implementation review

- `HumanInputRequest` now persists a maximum-round quota, current round index,
  and ordered completed-round values. Legacy records default to one round, and
  the existing JSON depth, item, record-byte, and file-lease boundaries remain
  active.
- `continue_round` validates the next prompt/schema, authorizes the `continue`
  action before mutation, appends the completed decision, and reopens the same
  interaction ID as pending. File-backed continuation is fenced and its
  `continued` notification excludes response payloads.
- `AutonomousAgent` exposes the continuation helper and preserves the existing
  one-shot response shape. Multi-round tool results include bounded prior
  responses so the resumed model receives the interaction context. Stores that
  do not implement continuation fail with a typed unsupported error.
- Focused interaction/host/run coverage reports `23 passed in 2.74s`; the exact
  tracked manifest reports `1219 passed, 1 skipped in 215.53s`. Ruff, Black,
  compile, diff, doctor, and changed-boundary mypy pass. A clean archive rebuilt
  wheel/sdist `1.1.3`; Twine passed for both, the sdist contains 485 entries
  including ADR-041 and the host regression, and the workspace-only audit found
  zero preserved Doctrine files. No remote authentication, transport,
  distributed ownership, or exactly-once side-effect claim is made.

## Slice 96 implementation review

- `RetryPolicy` validates a maximum of eight retries and a maximum delay of 60
  seconds. Capped exponential delay is deterministic and no-policy workflows
  retain the existing immediate-failure behavior.
- Ordinary node exceptions and invalid node outputs persist
  `NODE_RETRY_SCHEDULED` before retrying. `WorkflowCheckpoint` stores retry
  counts and `retry_after`, `WorkflowContext` exposes the current count, and
  recovery can honor an unexpired schedule. Exhaustion becomes the typed,
  persisted `NODE_RETRY_EXHAUSTED` error without serializing raw exceptions.
- Parallel fan-out branches remain explicitly outside this persisted policy;
  their existing bounded trusted-local execution and side-effect caveat are
  unchanged. Checkpointing does not claim exactly-once external effects.
- Focused workflow/replay coverage reports `22 passed in 4.20s`; the exact
  tracked manifest reports `1222 passed, 1 skipped in 222.42s`. Ruff, Black,
  compile, diff, doctor, and changed-boundary mypy pass. A clean archive rebuilt
  wheel/sdist `1.1.3`; Twine passed for both, the sdist contains 486 entries
  including ADR-042 and the workflow regression, and the workspace-only audit
  found zero preserved Doctrine files. No publication was performed.

## Slice 97 implementation review

- `EventCursor` validates non-negative sequence state and round-trips through a
  JSON-safe mapping. `EventBatch` returns bounded events plus the next cursor
  and retained-window metadata.
- `EventStream.read` caps explicit limits at the configured ring capacity and
  returns `EVENT_CURSOR_EXPIRED` with sequence metadata when retention has
  evicted the requested position. It does not silently invent replay data.
- `wait_for` checks a cooperative cancellation signal before waiting and at a
  bounded polling interval; malformed or exceptional signals fail closed with
  typed errors. Existing event redaction and subscriber isolation are retained.
- Focused event/lifecycle coverage reports `37 passed in 2.28s`; the exact
  tracked manifest reports `1226 passed, 1 skipped in 216.99s` across 107 tracked
  test files. Ruff, Black, compile, diff, doctor, and changed-boundary mypy
  pass. A clean committed-HEAD archive rebuilt wheel/sdist `1.1.3`; build and
  Twine both exited 0, the sdist contains 487 entries including ADR-043, the
  event module, and its regression, and the workspace-only audit found zero
  preserved Doctrine files. Remote transport, provider token linkage, durable
  broker storage, and exporter behavior remain unimplemented by design.

## Slice 98 implementation review

- `create_handoff_tool` accepts an explicit context-key allowlist and copies
  nested JSON-compatible context under key, item, depth, string, and byte
  bounds before delegation.
- Unknown context keys return `HANDOFF_CONTEXT_KEY_DENIED` without calling the
  target. Non-empty context requires the explicit
  `pursue_goal_with_context` target method; legacy no-context calls preserve
  the original `pursue_goal` path.
- `AutonomousAgent` exposes context-aware sync/async goal entry points and
  places the bounded context in the initial data-marked system message, so a
  local durable run checkpoint retains it. This is a policy boundary, not
  authentication, secret redaction, or model isolation.
- Focused handoff/agent coverage reports `50 passed in 4.40s`; Ruff, Black,
  changed-boundary mypy, compile, and diff checks pass. The exact tracked
  manifest reports `1230 passed, 1 skipped in 227.55s` across 107 tracked test
  files. A clean committed-HEAD archive rebuilt wheel/sdist `1.1.3`; build and
  Twine both exited 0, the sdist contains 488 entries including ADR-044, the
  handoff and agent modules, and their regressions, and the workspace-only audit
  found zero preserved Doctrine files. Async target transport, durable handoff
  identity/leases, ownership transfer, and remote routing remain explicit
  follow-on work.

## Slice 99 implementation review

- `Tool.execute_async` and `ToolRegistry.execute_async` preserve the existing
  schema, guardrail, result, and error contracts. Declared async handlers are
  awaited; legacy sync handlers use an executor fallback.
- The async `AutonomousAgent` loop resolves approval and durable interaction
  work off-loop, then dispatches through the async tool contract. A configured
  `TrustedLocalExecutor` takes precedence over an async handler, preventing
  policy bypass.
- Async handoffs require explicit target methods, reuse bounded context
  filtering and target-result redaction, and preserve the approval-by-default
  agent boundary. No raw target exception or error payload is forwarded.
- Focused coverage reports `68 passed in 0.46s`; Black, Ruff, changed-boundary
  mypy, compile, and diff checks pass. The exact tracked manifest reports
  `1235 passed, 1 skipped in 215.23s` across 107 tracked test files. A clean
  committed-HEAD archive rebuilt wheel/sdist `1.1.3`; build and Twine exited 0,
  the sdist contains 489 entries including the five Slice 99 files, and the
  workspace-only audit found zero preserved Doctrine files. Durable
  handoff identity, ownership transfer, remote routing, hard cancellation, and
  exactly-once external effects remain unclaimed.

## Slice 100 implementation review

- `LLMChunk` adds optional bounded `TokenUsage` and provider request
  correlation fields without changing existing text, tool-call, or finish
  consumers. OpenAI-compatible usage requests are opt-in; Anthropic partial
  usage fields are merged before the final trailer.
- `EventExporter` is a host-owned protocol attached to `EventStream` after
  redaction and retention. Invalid exporters fail closed at publish time, and
  exporter exceptions are isolated so telemetry cannot change run outcomes.
- Public root/autonomy exports and API/parity documentation describe the new
  fields and limits. No raw SDK object, secret-bearing payload, durable queue,
  or remote transport was added.
- Focused provider/event coverage reports `16 passed in 0.28s`; Black, Ruff,
  changed-boundary mypy, compile, and diff checks pass. The exact tracked
  manifest reports `1237 passed, 1 skipped in 253.10s` across 107 tracked test
  files. A clean committed-HEAD archive rebuilt wheel/sdist `1.1.3`; build and
  Twine exited 0, the sdist contains 490 entries including ADR-046 and the
  Slice 100 files, and the workspace-only audit found zero preserved Doctrine
  files. Automatic provider-to-agent trace linkage, durable/remote exporters,
  hard cancellation, and exactly-once external effects remain unclaimed.

## Verdict

**Feature review:** PASS for the twenty-eight implemented capability slices.
**Publish readiness:** NOT YET APPROVED. A release manager should close the
workspace-only Doctrine gold and fresh-verifier gates before publishing. The
remaining Bandit findings are documented low-severity legacy debt; external
publication remains awaiting explicit human approval.
