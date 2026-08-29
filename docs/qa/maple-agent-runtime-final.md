# Final QA + Security - MAPLE Agent Runtime release-readiness pass

**QA/Security role:** local QA and security pass
**Date:** 2026-08-24
**Branch:** `feat/maple-agent-runtime`

## Results matrix

| Gate | Result | Evidence / limitation |
|---|---|---|
| New feature regressions | PASS | 199 LLM/autonomy/CLI tests passed; one existing pytest config warning. |
| Live MCP interoperability | PASS | 22 focused tests cover live descriptors, pagination, malformed/unsupported schemas, RPC errors, approval defaults, and real localhost HTTP initialization/session headers. |
| Artifact/code-block boundary | PASS | 5 focused tests cover bounded fence parsing, unclosed/oversized rejection, content-addressed deduplication, file persistence, quota, path validation, and tamper detection; no execution path exists. |
| Provider stream contract | PASS | 5 focused tests cover completion fallback, native OpenAI/Anthropic text and tool-call deltas, 256-character bounds, finish events, async iteration, and typed request errors. |
| Async tool fan-out | PASS | 1 regression test proves independent handlers overlap while results remain in original tool-call order. |
| Autonomous approval boundary | PASS | 1 regression test proves a required tool with no callback returns `APPROVAL_REQUIRED` without invoking its handler. |
| Workflow fan-out/fan-in boundary | PASS | 13 workflow tests cover concurrent branch overlap, bounded branch count, deterministic merge, collision rejection, file-backed pause/resume, and group checkpoint behavior. |
| Durable approval boundary | PASS | 21 approval/agent tests cover bounded records, file restart persistence, CAS decisions, pending side-effect protection, denial, and single-use consumption. |
| Vector retrieval boundary | PASS | 10 retrieval tests cover supplied-vector validation, atomic ingestion, cosine ranking, deterministic ties, source citations, removal, and quotas. |
| Workflow history boundary | PASS | 16 workflow tests cover immutable snapshots, bounded retention/defaults, invalid limits, missing runs, and unchanged recovery semantics. |
| Compile/import | PASS | `python -m compileall -q maple`; top-level public import and doctor smoke test pass. |
| Changed-file Ruff | PASS | New/behavior-touched implementation checks pass. |
| Changed-file Flake8 | PASS | Exact CI-style command returned `0` for the changed runtime surface. |
| Package artifacts | PASS | Metadata-clean wheel and sdist built; Twine checks passed. |
| Installed artifact smoke | PASS | Clean venv installed the wheel with `--no-deps`; `maple doctor --json` returned `ready:true`, `network:false`. |
| Isolated dependency audit | PASS | Fresh `.[dev,security]` environment: `pip check` returned `No broken requirements found.` |
| Local readiness | PASS | `maple --json doctor` returned all eight checks true and `network:false`. |
| Full repository regression | OPEN | Exact-current bounded run on `2b7ea84` collected `1300` items, passed the application suites through `90%`, entered the slow Doctrine gold phase, and was interrupted without failure output or a pytest summary. |
| Dependency consistency | PASS | Isolated MAPLE environment is consistent; shared-interpreter conflicts are unrelated and non-authoritative. |
| Repository-wide lint | PASS | Slice 69 closes the remaining E402 import-boundary debt; broad `ruff check maple` reports zero findings. |
| Typed tool input/output boundary | PASS | 43 focused contract/tool/agent tests and 212 full-autonomy tests cover model-derived schemas, pre-handler input rejection, normalized handler arguments, validated outputs, and invalid-result failure. |
| Optional Protobuf serialization boundary | PASS | 28 core serialization tests cover round-trip special values, malformed envelopes, inbound/outbound 1 MiB limits, and unavailable-dependency failure; core/autonomy regression reports 240 passed. |
| Per-goal token accounting/budget boundary | PASS | 30 focused agent/session tests cover sync/async aggregation, reflection accounting, invalid/missing usage, positive-budget validation, and budget-overrun side-effect protection. |
| Bounded multi-agent orchestration boundary | PASS | 43 agent/orchestrator tests cover sync/async fan-out, deterministic joins, sync-only fallback, bounded limits, and per-member exception isolation. |
| Bounded structured-output repair boundary | PASS | 28 agent tests cover sync/async repair, default fail-fast, retry exhaustion, invalid retry limits, and token-budget consumption across retries. |
| Async orchestration deadline/cancellation boundary | PASS | 24 orchestrator tests cover request-wide timeout, native async task cancellation and draining, cooperative `CancellationToken`, invalid timeout configuration, and consensus deadline behavior. |
| Bounded agent handoff boundary | PASS | 18 tool tests and 234 autonomy tests cover structured target results, approval-by-default, bounded task input, raw-error redaction, target exceptions, invalid target results, and public import. |
| Independent review | OPEN | Fresh verifier sessions are unavailable in this tool context. |
| External publish / website | NOT RUN | Explicitly outside current authorization and scope. |

## 2026-08-25 revalidation

- Focused release regression: `269 passed, 1 skipped in 51.72s` across 270
  communication, agent, error, state, autonomy, discovery, adapter, LLM, and
  broker tests. The skipped case requires the unavailable `nats-py` package.
- Slice 63 revalidation: default mypy now reports `Success: no issues found in
  93 source files`; the cross-surface regression reports `616 passed, 1
  skipped in 173.01s`. The package still declares Python `>=3.8`; only the
  mypy static-analysis target is 3.10.
- Slice 64 security revalidation: the security regression reports `37 passed in
  0.82s`; the cross-surface regression reports `621 passed, 1 skipped in
  170.54s`. Isolated `pip check` is clean, `pip-audit` reports no known
  vulnerabilities, and Bandit `-ll` exits 0 with no medium/high findings.
- Full LLM suite: `36 passed in 0.24s`.
- Repository Black/isort, `ruff check tools tests`, and compile checks pass;
  changed-surface Ruff checks pass. Slice 65 reduced broad legacy
  `ruff check maple` to 171 diagnostics (`E402 140`, `F401 31`); the remaining
  debt was not weakened or hidden.
- The repository-wide command collected 1262 items and reached the slow
  Doctrine gold phase without assertion output, but its bounded terminal
  session ended before pytest emitted a final summary; it remains open.
- Current package preflight: wheel/sdist built successfully, both Twine checks
  passed, and the network-free doctor returned all checks true with
  `ready: true`, `network: false`, version `1.1.3`.
- Full repository completion, the 35 low-severity legacy Bandit findings,
  broad legacy lint, and independent fresh-context verification remain open. No
  publication or website change was performed.

## Slice 65 revalidation

- The affected adapter/queue/health/security/state regression reports `131
  passed in 48.43s`.
- Changed-file Ruff, Black, isort, and mypy checks pass; the FIPA regression
  proves the mapped `REQUEST` performative is emitted as `(request`.
- Broad `ruff check maple` decreased from `250` diagnostics to `171`
  (`E402 140`, `F401 31`). Remaining legacy lint is still an open release
  gate, and no publication or website change was performed.

## Slice 66 revalidation

- The autonomy/state/broker/communication/security regression reports `628
  passed, 1 skipped in 16.35s`.
- Changed-file Ruff, Black, isort, mypy, and compile checks pass.
- Broad `ruff check maple` decreased from `171` diagnostics to `95`
  (`E402 69`, `F401 26`). Remaining repository-wide lint remains an open
  release gate; no publication or website change was performed.

## Slice 67 revalidation

- The affected adapter/agent/broker/communication/discovery/error/resource/
  security/task suite reports `777 passed, 1 skipped in 237.84s`.
- Current S2/resource/link revalidation reports `130 passed in 0.37s`.
- Changed-file Ruff, Black, isort, mypy, and compile checks pass.
- Broad `ruff check maple` decreased from `95` diagnostics to `58` (`E402 58`),
  with zero F401 findings. The remaining E402 debt is still an open release
  gate; no publication or website change was performed.

## Slice 68 revalidation

- The affected autonomy/broker/LLM/monitoring/security/state suite reports
  `635 passed, 1 skipped in 16.90s`.
- Changed-file Ruff, Black, isort, mypy, and compile checks pass.
- Broad `ruff check maple` decreased from `58` diagnostics to `19`
  (`E402 19`, `F401 0`).
- A full repository attempt on the preceding commit collected `1270` items and
  reached `95%` with no failure output before bounded interruption; it emitted
  no final summary and does not prove the exact current commit. No publication
  or website change was performed.

## Slice 69 revalidation

- The Doctrine adapter and security authentication/separation regression set
  reports `107 passed in 4.02s`.
- Broad `ruff check maple` reports zero findings.
- Changed-file Black, isort, mypy, and compile checks pass.
- Exact-current wheel and sdist build successfully; Twine reports `PASSED` for
  both artifacts.
- The exact-current full repository suite remains open because the bounded
  state-plane run has not emitted a final summary. No publication or website
  change was performed.

## Slice 70 revalidation

- Typed-output contract and agent coverage reports `28 passed in 0.35s`.
- The full autonomy surface reports `210 passed in 3.37s`.
- The new `output_model` boundary advertises model JSON Schema, returns a
  validated Pydantic-style instance, and fails closed on invalid output.
- Mypy reports no issues in 93 source files; repository MAPLE Ruff, tools/tests
  Ruff, Black, isort, compile, and network-free doctor gates pass.
- Exact-current wheel and sdist artifacts built successfully; Twine marked both
  artifacts `PASSED`.
- No new dependency, publication, or website change was performed.

## Slice 71 revalidation

- Typed tool contract coverage reports `43 passed in 0.37s`; the full autonomy
  surface reports `212 passed in 3.26s`.
- `Tool.input_model` publishes a model-derived JSON Schema, validates and
  normalizes arguments before invoking the handler, and prevents handler calls
  on invalid input. `Tool.output_model` validates handler results and returns
  a typed model instance; invalid results fail closed.
- Mypy reports no issues in 93 source files; MAPLE Ruff, tools/tests Ruff,
  Black, isort, compile, and network-free doctor gates pass. Doctor returned
  all eight checks true with `ready: true`, `network: false`, version `1.1.3`.
- Exact-current wheel and sdist artifacts built successfully; Twine marked
  both artifacts `PASSED`.
- No new dependency, publication, or website change was performed. The exact
  repository-wide suite and fresh independent verification remain open.
- Exact-current repository run on `ded4477` collected `1276` items and reached
  the Doctrine gold phase after the application suites passed. The bounded
  session was interrupted after sparse gold-test progress without a pytest
  summary; this is not a full-suite pass.

## Slice 72 revalidation

- Core/autonomy regression reports `240 passed in 3.37s`; the serialization
  suite reports `28 passed in 0.28s`.
- `SerializationFormat.PROTOBUF` now uses an optional bounded
  `google.protobuf.Struct` envelope around MAPLE's JSON-compatible form. Tuple,
  set, bytes, and inert-object handling round-trip without arbitrary class
  reconstruction.
- Malformed envelopes, inbound and outbound payloads over 1 MiB, and missing
  protobuf fail closed with structured errors. No runtime dependency was added.
- Mypy reports no issues in 93 source files; MAPLE Ruff, tools/tests Ruff,
  Black, isort, compile, wheel/sdist, Twine, and network-free doctor gates pass.
- The exact repository-wide suite was rerun after Slice 72 but did not emit a
  final summary; the full-suite and fresh independent-verifier gates remain
  open.
- Exact-current post-Slice-72 run on `2b8bb57` collected `1278` items, reached
  the Doctrine gold phase, and emitted six gold-test completions before the
  bounded session was interrupted. No failure output or pytest summary was
produced; this is not a full-suite pass.

## Slice 73 revalidation

- Agent/session regression reports `30 passed in 0.31s`.
- `Goal.token_usage` aggregates provider prompt, completion, and total tokens
  across sync/async reasoning and reflection responses.
- `AutonomousConfig.max_total_tokens` validates positive integer budgets and
  fails closed for missing or malformed provider usage. Budget overruns return
  `TOKEN_BUDGET_EXCEEDED` before the current response's tools execute; sync and
  async tests verify no handler side effect occurs.
- Changed-file Ruff, Black, isort, and mypy checks pass. No new dependency was
  added; ADR-025, public docs, changelog, QA, and review evidence are filed.
- Exact-current run on `a51e043` collected `1282` items, reached `90%`, and
  entered the slow Doctrine gold phase before bounded interruption. No failure
  output or pytest summary was produced; this is not a full-suite pass. Full
suite and fresh independent-verifier gates remain open.

## Slice 74 revalidation

- Agent/orchestrator regression reports `43 passed in 0.33s`.
- Sync supervised and consensus execution now uses bounded worker fan-out;
  async methods use native async member calls or an executor fallback. Result
  joins remain deterministic and worker exceptions are isolated per member.
- Changed-file Ruff, Black, isort, and mypy checks pass. No new dependency was
  added; ADR-026, public docs, changelog, QA, and review evidence are filed.
- The exact-current repository run on `a51e043` remains the latest bounded
full-suite attempt; it collected `1282` items, reached `90%`, and entered the
slow Doctrine gold phase before interruption without a pytest summary.

## Slice 75 revalidation

- Agent regression reports `28 passed in 0.33s`.
- `AutonomousConfig.max_output_retries` provides opt-in correction attempts for
  typed/schema output and output guardrails, bounded from 0 through 3. Sync and
  async paths share the same behavior; default `0` remains fail-fast.
- Retry responses are accounted as ordinary model responses, appear in the
  reasoning trace, and consume the configured token budget. Exhaustion returns
  the original structured error.
- Changed-file Ruff, Black, isort, and mypy checks pass. ADR-027, public docs,
  changelog, QA, and review evidence are filed; no dependency was added.
- Exact-current run on `1211701` collected `1291` items, reached `90%`, and
  entered the slow Doctrine gold phase before bounded interruption. No failure
  output or pytest summary was produced; the full-suite and fresh
  independent-verifier gates remain open.

## Slice 76 revalidation

- The orchestrator regression reports `24 passed in 0.43s`; the core/autonomy
  regression reports `257 passed in 3.60s`.
- Async supervised and consensus execution now accepts a total
  `timeout_seconds` budget and an existing `CancellationToken`. Native async
  child tasks are canceled and drained, and interruption returns typed
  `ORCHESTRATION_TIMEOUT` or `ORCHESTRATION_CANCELLED` errors.
- Invalid timeout values fail closed as `ORCHESTRATION_CONFIG_INVALID`. Sync-only
  executor fallbacks remain explicitly cooperative because Python cannot
  forcibly stop a running thread.
- Repository Ruff, Black, mypy, and compile checks pass. ADR-028, public docs,
  changelog, QA, and review evidence are filed; no dependency was added.
- Exact-current full-suite and fresh independent-verifier gates remain open;
  no publication or website change was performed.

- Exact-current run on `bd1b179`: pytest collected `1295` items, passed the
  application suites through `90%`, entered `tests/test_doctrine_gold.py`, and
  was bounded/interrupted after sparse gold-phase progress. No failure output or
  pytest summary was produced; this is not a full-suite pass.

## Slice 77 revalidation

- The tool regression reports `18 passed in 0.25s`; the autonomy regression
  reports `234 passed in 3.49s`.
- `create_handoff_tool` exposes one bounded synchronous `pursue_goal` target as
  a normal approval-required-by-default tool. Invalid input is rejected before
  target side effects; target failures, exceptions, and malformed returns are
  normalized without forwarding raw error payloads.
- Ruff, Black, mypy, compile, and public-import checks pass. ADR-029, public
  docs, changelog, QA, and review evidence are filed; no dependency was added.
- The exact-current full-suite and fresh independent-verifier gates remain open;
  no publication or website change was performed.

- Exact-current run on `2b7ea84`: pytest collected `1300` items, passed the
  application suites through `90%`, entered `tests/test_doctrine_gold.py`, and
  was bounded/interrupted after sparse gold-phase progress. No failure output or
  pytest summary was produced; this is not a full-suite pass.

## Slice 78 revalidation

- The release brief and README now explicitly distinguish supported local
  state/authentication/execution surfaces from Redis, mutual-TLS, OAuth2, and
  untrusted-code paths that fail closed or remain deferred.
- `rg -n "NOT_IMPLEMENTED" maple` was used as the inventory cross-check. The
  state/authentication regression reports `73 passed in 3.44s`, including Redis
  `list_keys` and mutual-TLS/OAuth2 fail-closed assertions; Ruff passes on both
  changed test files.
- No unsupported feature was implemented by documentation alone.
- No dependency, credential, cloud call, publication, or website mutation was
  performed. The exact full-suite and fresh independent-verifier gates remain
  open.

## Doctrine gold gate boundary

- An isolated run of `tests/test_doctrine_gold.py` collected 21 tests and
  completed `3 passed in 521.65s (0:08:41)` before bounded interruption.
- Pytest reported no assertion failure. The slowest completed calls were
  `test_chain_fork_detected` at `189.32s`, `test_artifact_tamper_fails_check`
  at `118.43s`, and `test_bad_tag_rejected_before_git_or_paths` at `61.33s`.
- This is diagnostic evidence, not a full-suite pass; the gold and exact
  repository gates remain open pending a practical, complete run.

## Slice 79 revalidation — tracked repository suite

- Git supplied 100 tracked Python test files to pytest, excluding preserved
  untracked workspace Doctrine fixtures.
- `python -m pytest <tracked test files> --no-cov -p no:dash -p no:benchmark
  -q --tb=short --durations=20` -> `1185 passed, 1 skipped in 210.07s`.
- The prior `PytestReturnNotNoneWarning` in `tests/test_fixes.py` was removed by
  keeping the standalone helper's boolean contract while adding a pytest
  wrapper that asserts instead of returning a value. The focused test reports
  `2 passed in 0.61s`; Ruff and `git diff --check` pass.
- This closes the tracked application-suite gate. The separate untracked
  Doctrine gold verifier and fresh independent review remain open.

## Slice 80 revalidation — clean tracked release artifact boundary

- A temporary `git archive HEAD` snapshot was built with
  `python -m build --wheel --sdist --no-isolation`.
- The clean snapshot produced wheel and sdist artifacts for version `1.1.3`;
  `twine check` reported `PASSED` for both.
- The clean sdist contained 460 files, and the explicit audit found no
  preserved workspace-only Doctrine tests, `docs/brief.md`, `docs/maximus.md`,
  or `tools/doctrine_*.py` files.
- The earlier dirty-workspace artifact was not treated as a release candidate.
  The build boundary is now documented as clean-checkout/archive only.

## Slice 81 revalidation — agent-framework parity ledger

- `docs/agent-framework-parity.md` records the five-framework comparison set
  selected by the release brief: LangGraph, CrewAI, Microsoft Agent Framework,
  LlamaIndex, and OpenAI Agents SDK.
- The ledger is functionality-focused and source-backed. It excludes adoption
  and licensing, does not treat protocol adapters as native parity, and
  distinguishes code-block/artifact extraction from executable code.
- MAPLE's remaining gaps are explicitly ordered: durable agent-run state and
  arbitrary request/response HITL; context-aware async/durable handoffs;
  composable workflows with retry policy; unified streaming/trace export;
  deeper trajectory/judge evaluation; and separately reviewed sandbox,
  browser, hosting, managed data, and language surfaces.
- The exact current `git archive HEAD` snapshot also rebuilt wheel/sdist
  `1.1.3`; Twine passed both artifacts, and the 463-entry sdist included the
  parity ledger while excluding all preserved workspace-only Doctrine files.
- Documentation-only change; no runtime behavior or dependency changed.

## Slice 82 revalidation — durable synchronous agent runs

- `tests/autonomy/test_runs.py` reports `6 passed in 0.25s` for store bounds,
  JSON-safe parsing, file restart persistence, CAS conflicts, approval pause/
  resume, and completed-tool non-repetition after model interruption.
- The compatibility set (`test_runs.py`, `test_agent.py`,
  `test_agent_sessions.py`, and `test_approval.py`) reports `45 passed in
  0.36s`.
- Public imports for `AgentRunCheckpoint`, `AgentRunStore`,
  `InMemoryAgentRunStore`, and `FileAgentRunStore` pass. Changed-source
  Ruff, Black, mypy, and compile checks pass.
- The synchronous boundary is documented; `pursue_goal_async` does not claim
  durable run persistence yet. Cross-process leases, exactly-once effects,
  and full trace replay remain explicitly out of scope.

## Slice 83 revalidation — current tracked suite and clean artifact

- Git supplied 101 tracked Python test files to pytest, excluding preserved
  untracked workspace Doctrine fixtures.
- `python -m pytest <tracked test files> --no-cov -p no:dash -p no:benchmark
  -q --tb=short --no-header` -> `1191 passed, 1 skipped in 217.81s` with no
  warning output.
- `python -m maple.cli doctor --json` returned `ready: true`, `status:
  SUCCESS`, `version: 1.1.3`, all eight checks true, and `network: false`.
- A clean `git archive HEAD` snapshot built wheel and sdist `1.1.3`; both
  `twine check` invocations passed. The sdist contained 466 entries,
  included `maple/autonomy/runs.py`, and contained zero preserved
  workspace-only Doctrine files.
- This closes the tracked application-suite and current clean-artifact gates.
  The workspace-only Doctrine gold verifier and fresh independent review are
  still open; no publication or website action was taken.

## Slice 84 revalidation — async durable agent runs

- `tests/autonomy/test_runs.py` reports `9 passed in 0.30s`, covering async
  checkpoint creation, approval pause/resume after restart, pause-before-later
  side effects, and no duplicate completed tool call after model interruption.
- The exact tracked application suite contains 101 Python test files and
  reports `1194 passed, 1 skipped in 205.06s` with no warning output.
- Ruff, Black, mypy, compile, and network-free doctor checks pass. Doctor
  returned `ready: true`, `status: SUCCESS`, version `1.1.3`, all eight checks
  true, and `network: false`.
- A clean `git archive HEAD` snapshot rebuilt wheel and sdist `1.1.3`; both
  Twine checks passed. The sdist contained 467 entries, included
  `maple/autonomy/runs.py` and ADR-031, and contained zero preserved
  workspace-only Doctrine files.
- Async durable persistence uses executor-backed local stores and serializes
  durable tool calls so approval pauses precede later side effects. Distributed
  leases, exactly-once effects, sandboxing, and durable streaming remain out of
  scope.

## Slice 85 revalidation — unified agent-run lifecycle events

- `tests/autonomy/test_runs.py` reports `10 passed in 0.27s`, covering shared
  sync/async lifecycle vocabulary, usage trailers, redaction-compatible
  metadata-only payloads, approval pause events, and resumed-run events.
- The existing agent/session/event compatibility set reports `40 passed in
  0.35s`. Ruff, Black, mypy, compile, and network-free doctor checks pass;
  doctor returned `ready: true`, all eight checks true, and `network: false`.
- A clean `git archive HEAD` snapshot rebuilt wheel and sdist `1.1.3`; both
  Twine checks passed. The sdist contained 468 entries, included ADR-032, and
  contained zero preserved workspace-only Doctrine files.
- The latest exact tracked run before the loopback response hardening reported
  `1194 passed, 1 failed, 1 skipped in 218.95s`; ADR-033 then addressed the
  response flush/close race without changing the server contract.

## Slice 86 revalidation — loopback response closure

- `tests/autonomy/test_server.py` reports `4 passed in 2.34s`, covering health,
  run, resume, malformed JSON, unknown workflow, and oversized-body responses.
- The exact tracked application suite now reports `1195 passed, 1 skipped in
  222.53s` with no warning output.
- The response path explicitly flushes bounded JSON and marks the connection
  closed after sending the existing status/payload contract. No dependency,
  route, protocol, or external-hosting behavior changed.

## Slice 87 revalidation — final current-commit artifact boundary

- A clean `git archive HEAD` snapshot built wheel and sdist `1.1.3`; both Twine
  checks passed.
- The sdist contained 469 entries, included ADR-031, ADR-032, ADR-033,
  `maple/autonomy/runs.py`, and the lifecycle-event implementation, and the
  workspace-only audit found zero preserved Doctrine files.
- `python -m maple.cli doctor --json` returned `ready: true`, `status:
  SUCCESS`, version `1.1.3`, all eight checks true, and `network: false`.
- No publication, registry upload, cloud call, website mutation, or user-owned
  untracked-file change was made.

## Slice 88 QA — bounded editable durable approvals

- `tests/autonomy/test_approval.py`, `tests/autonomy/test_runs.py`, and
  `tests/autonomy/test_agent.py` report `44 passed in 0.46s`.
- The exact tracked application manifest reports `1197 passed, 1 skipped in
  204.41s`; the two new approval regressions cover in-memory/file persistence,
  invalid-edit no-mutation, denied-edit rejection, and sync/async durable
  resume execution of the persisted replacement.
- Ruff reports `All checks passed!`; Black reports `94 files would be left
  unchanged`; mypy reports `Success: no issues found in 94 source files`;
  compile and `git diff --check` pass.
- Network-free doctor returns `ready: true`, `status: SUCCESS`, version
  `1.1.3`, all eight checks true, and `network: false`.
- A clean current-commit archive built wheel/sdist `1.1.3`; both Twine checks
  passed, the sdist contains 470 entries including ADR-034, and the
  workspace-only audit found zero preserved Doctrine files. No publication,
  website, cloud, registry, or user-owned untracked-file change was made.

## Slice 89 QA — bounded durable human input

- `tests/autonomy/test_interactions.py`, `tests/autonomy/test_runs.py`,
  `tests/autonomy/test_tools.py`, and `tests/autonomy/test_agent.py` report
  `61 passed in 0.51s`.
- The exact tracked application manifest contains 86 tracked test files and
  reports `1202 passed, 1 skipped in 211.16s`. Coverage includes memory/file
  persistence, schema-invalid response no-mutation, explicit rejection,
  sync/async pause-resume, and consumed-rejection recovery.
- Ruff reports `All checks passed!`; Black reports `95 files would be left
  unchanged`; mypy reports `Success: no issues found in 95 source files`;
  compile and `git diff --check` pass.
- Network-free doctor returns `ready: true`, `status: SUCCESS`, version
  `1.1.3`, all eight checks true, and `network: false`.
- A clean current archive rebuilt wheel/sdist `1.1.3`; Twine passed for both,
  the sdist contains 473 entries including ADR-035, and the workspace-only
  audit found zero preserved Doctrine files. No publication, website, cloud,
  registry, or user-owned untracked file change was made.

## Slice 90 QA — cross-process durable fencing leases

- `tests/resources/test_resource_model.py` plus
  `tests/resources/test_file_lease.py` report `41 passed in 3.64s`.
- Coverage includes restart persistence, fencing-token monotonicity, stale
  release rejection, expiry reacquisition, child-process state sharing,
  corrupt-state fail-closed behavior, and bounded input rejection.
- The exact tracked manifest reports `1207 passed, 1 skipped in 214.53s`.
  Ruff, Black, compile, network-free doctor, and changed-boundary mypy pass;
  repository-wide mypy still reports the pre-existing optional-adapter stub
  findings documented by the release review.
- A clean current archive rebuilt wheel/sdist `1.1.3`; Twine passed for both,
  the sdist contains 475 entries including ADR-035 and ADR-036, and the
  workspace-only audit found zero preserved Doctrine files.
- No publication, website, cloud, registry, or user-owned untracked file
  change was made.

## Slice 91 QA — cross-process durable approval-store ownership

- `tests/autonomy/test_approval.py` plus
  `tests/autonomy/test_approval_leases.py` report `8 passed in 0.32s`.
- Coverage proves default per-record lease use, fail-closed acquisition while
  another holder owns the approval, no decision mutation on that failure,
  release after a decision, and preservation of the existing approval
  lifecycle.
- The exact tracked manifest reports `1209 passed, 1 skipped in 199.58s`.
  Ruff, Black, compile, diff, network-free doctor, and changed-boundary mypy
  pass.
- A clean current archive rebuilt wheel/sdist `1.1.3`; Twine passed for both,
  the sdist contains 477 entries including ADR-037 and the approval lease
  regression, and the workspace-only audit found zero preserved Doctrine files.
- No publication, website, cloud, registry, or user-owned untracked file
  change was made.

## Slice 92 QA — cross-process durable human-input-store ownership

- `tests/autonomy/test_approval.py`,
  `tests/autonomy/test_approval_leases.py`,
  `tests/autonomy/test_interactions.py`, and
  `tests/autonomy/test_interaction_leases.py` report `13 passed in 0.48s`.
- Coverage proves the shared lease wrapper preserves approval behavior and
  protects human-input create/respond/consume transitions, including no
  mutation while an external holder owns the record.
- The exact tracked manifest reports `1211 passed, 1 skipped in 219.68s`.
  Ruff, Black, compile, diff, network-free doctor, and changed-boundary mypy
  pass.
- A clean current archive rebuilt wheel/sdist `1.1.3`; Twine passed for both,
  the sdist contains 480 entries including ADR-038 and the shared durable
  lease helper, and the workspace-only audit found zero preserved Doctrine files.
- No publication, website, cloud, registry, or user-owned untracked file
  change was made.

## Slice 93 QA — cross-process durable run-store ownership

- `tests/autonomy/test_runs.py` and
  `tests/autonomy/test_run_leases.py` report `14 passed in 2.66s`.
- Coverage proves external run ownership blocks both load and compare-and-set
  save without checkpoint mutation, and that a successful save releases its
  run lease for another store instance.
- The exact tracked manifest reports `1213 passed, 1 skipped in 228.60s`.
  Ruff, Black, compile, diff, network-free doctor, and changed-boundary mypy
  pass.
- A clean current archive rebuilt wheel/sdist `1.1.3`; Twine passed for both,
  the sdist contains 482 entries including ADR-039, the run module, and the
  run lease regression, and the workspace-only audit found zero preserved
  Doctrine files.
- No publication, website, cloud, registry, or user-owned untracked file
  change was made.

## Slice 94 QA — bounded human-input host notification and authorization hooks

- `tests/autonomy/test_interaction_host.py` plus the interaction, lease, agent,
  and run regression set reports `49 passed in 2.80s`.
- Coverage proves created/responded/rejected notifications carry bounded request
  metadata without the response payload; missing, denied, exceptional, and
  malformed actor authorization fail closed; authorization runs before the
  leased state transition; and notification failure is typed after the durable
  record has been persisted.
- The exact tracked manifest reports `1215 passed, 1 skipped in 227.81s`.
  Ruff, Black, compile, diff, network-free doctor, and changed-boundary mypy
  pass.
- A clean current archive rebuilt wheel/sdist `1.1.3`; Twine passed for both,
  the sdist contains 484 entries including ADR-040, the host-hook module, and
  the host regression, and the workspace-only audit found zero preserved
  Doctrine files.
- Remote authentication/transport and multi-round human interaction remain
  explicit follow-on boundaries. No publication, website, cloud, registry, or
  user-owned untracked file change was made.

## Slice 95 QA — bounded same-record multi-round human input

- The interaction, host, lease, and durable run regression set reports
  `23 passed in 2.74s`.
- Coverage proves a `max_rounds` quota, ordered immutable round history,
  restart-safe file persistence, same-interaction checkpoint waiting, and
  preservation of prior responses in the multi-round tool result. Continuation
  authorization and metadata-only notification are also covered.
- Ruff, Black, compile, diff, and changed-boundary mypy pass for the edited
  runtime boundary. The exact tracked manifest reports `1219 passed, 1 skipped
  in 215.53s`.
- A clean current archive rebuilt wheel/sdist `1.1.3`; Twine passed for both,
  the sdist contains 485 entries including ADR-041, the interactions module,
  and the run regression, and the workspace-only audit found zero preserved
  Doctrine files.
- No publication, website, cloud, registry, or user-owned untracked file
  change was made. Remote authentication/transport and exactly-once external
  effects remain outside the local contract.

## Slice 96 QA — bounded per-node workflow retry and durable backoff state

- `tests/autonomy/test_workflow.py` and
  `tests/autonomy/test_workflow_replay.py` report `22 passed in 4.20s`.
- Coverage proves bounded retry counts, retry context visibility, persisted
  checkpoint metadata, capped policy validation, typed exhaustion, and
  unchanged immediate-failure behavior when no policy is configured.
- Ruff, Black, compile, diff, and changed-boundary mypy pass for the edited
  workflow boundary. The exact tracked manifest reports
  `1222 passed, 1 skipped in 222.42s`.
- A clean current archive rebuilt wheel/sdist `1.1.3`; Twine passed for both,
  the sdist contains 486 entries including ADR-042, the workflow module, and
  the workflow regression, and the workspace-only audit found zero preserved
  Doctrine files.
- Parallel-branch retry, remote scheduling, and exactly-once external effects
  remain explicit follow-on boundaries. No publication, website, cloud,
  registry, or user-owned untracked file change was made.

## Slice 97 QA — durable event cursors and cooperative stream cancellation

- `tests/autonomy/test_events.py` and the agent lifecycle regression report
  `37 passed in 2.28s`.
- Coverage proves JSON-safe cursor round trips, bounded reads, deterministic
  cursor advancement, explicit retention-gap failure, query bounds, and
  cooperative cancellation through `CancellationToken`.
- Ruff, Black, and changed-boundary mypy pass for the edited event and export
  boundaries; compile and diff checks also pass. The exact tracked manifest
  reports `1226 passed, 1 skipped in 216.99s` across 107 tracked test files.
- A clean archive from committed `HEAD` rebuilt wheel/sdist `1.1.3`; build and
  Twine both exited 0, the sdist contains 487 entries including ADR-043, the
  event module, and its regression, and the workspace-only audit found zero
  preserved Doctrine files.
- This slice remains local and in-process: no durable broker, remote transport,
  provider token stream, or exporter is claimed.

## Slice 98 QA — bounded context-aware handoff filtering

- `tests/autonomy/test_tools.py` and `tests/autonomy/test_agent.py` report
  `50 passed in 4.40s`.
- Coverage proves allowlisted context forwarding to an explicit target contract,
  denied-key rejection before target execution, legacy-target rejection for
  non-empty context, bounded detached context data, and the agent's data-only
  initial context message.
- Ruff, Black, changed-boundary mypy, compile, and diff checks pass for the
  edited handoff and agent boundaries. The exact tracked manifest reports
  `1230 passed, 1 skipped in 227.55s` across 107 tracked test files.
- A clean committed-HEAD archive rebuilt wheel/sdist `1.1.3`; build and Twine
  both exited 0, the sdist contains 488 entries including ADR-044, the handoff
  and agent modules, and their regressions, and the workspace-only audit found
  zero preserved Doctrine files.
- Async target execution, durable handoff identity/leases, explicit ownership
  transfer, remote routing, and exactly-once effects remain unclaimed.

## Slice 99 QA — async-capable tool and handoff execution

- `tests/autonomy/test_tools.py`, `tests/autonomy/test_agent.py`, and
  `tests/autonomy/test_runs.py` report `68 passed in 0.46s` with coverage for
  declared async handlers, async registry execution, async agent dispatch,
  async handoff targets, approval ordering, and executor-policy precedence.
- The async agent path offloads durable approval and human-input store work,
  awaits declared async handlers, and falls back to the existing synchronous
  tool path for legacy tools. A configured trusted executor takes precedence
  over an async handler so timeout, input/output, concurrency, and approval
  policy cannot be bypassed.
- The exact tracked manifest contains 107 tracked Python test files and reports
  `1235 passed, 1 skipped in 215.23s` with no warning output. Black, Ruff,
  changed-boundary mypy, compile, and diff checks pass. Network-free doctor
  returns `ready: true`, `status: SUCCESS`, version `1.1.3`, all eight checks
  true, and `network: false`.
- A clean committed-HEAD archive rebuilt wheel/sdist `1.1.3`; build and Twine
  both exited 0, the sdist contains 489 entries including ADR-045, the async
  agent/tool modules, and both regressions, and the workspace-only audit found
  zero preserved Doctrine files.
- Durable handoff identity/leases, explicit ownership transfer, remote
  routing/authentication, hard cancellation, and exactly-once external effects
  remain outside this local contract. No publication, website, cloud,
  registry, or user-owned untracked file change was made.

## Slice 100 QA — bounded provider-stream usage/correlation and event exporter

- `tests/llm/test_provider_native_streaming.py`,
  `tests/llm/test_provider_streaming.py`, and `tests/autonomy/test_events.py`
  report `16 passed in 0.28s` with offline fixtures for OpenAI usage-only
  trailers, Anthropic partial-usage merging, bounded request IDs, redacted
  exporter delivery, exporter failure isolation, and invalid exporter config.
- Native stream consumers receive an optional final `TokenUsage` trailer and
  bounded provider request ID. OpenAI usage requests are opt-in through
  `LLMConfig.extra["include_stream_usage"]`; missing or malformed usage is not
  invented. `EventExporter` receives only the already-redacted `AgentEvent`,
  and exporter exceptions do not change publish success.
- The exact tracked manifest contains 107 tracked Python test files and reports
  `1237 passed, 1 skipped in 253.10s` with no warning output. Black, Ruff,
  changed-boundary mypy, compile, and diff checks pass. Network-free doctor
  returns `ready: true`, `status: SUCCESS`, version `1.1.3`, all eight checks
  true, and `network: false`.
- A clean committed-HEAD archive rebuilt wheel/sdist `1.1.3`; build and Twine
  both exited 0, the sdist contains 490 entries including ADR-046, the
  provider/event modules, public exports, and their regressions, and the
  workspace-only audit found zero preserved Doctrine files.
- Automatic provider-to-agent event/trace linkage, durable exporter queues,
  remote delivery/authentication, hard cancellation, and exactly-once external
  effects remain outside this local contract. No publication, website, cloud,
  registry, or user-owned untracked file change was made.

## Slice 101 QA — bounded provider correlation in agent events and traces

- `tests/autonomy/test_agent.py`, `tests/autonomy/test_runs.py`,
  `tests/autonomy/test_observability.py`, and the provider stream regressions
  report `73 passed in 1.45s`.
- Sync and async `AutonomousAgent` model responses copy only bounded provider
  request IDs into metadata-only `model.response` events and `DecisionTrace`
  JSON export. IDs over 256 characters or containing control characters are
  omitted; raw provider responses and SDK objects are not emitted.
- The exact tracked manifest contains 107 tracked Python test files and reports
  `1237 passed, 1 skipped in 249.77s` with no warning output. Black, Ruff,
  changed-boundary mypy, compile, and diff checks pass. Network-free doctor
  returns `ready: true`, `status: SUCCESS`, version `1.1.3`, all eight checks
  true, and `network: false`.
- A clean committed-HEAD archive rebuilt wheel/sdist `1.1.3`; build and Twine
  both exited 0, the sdist contains 491 entries including ADR-047, the agent
  and observability modules, and their regressions, and the workspace-only
  audit found zero preserved Doctrine files.
- Incremental provider-chunk aggregation, a full trace/span graph, durable or
  remote exporters, hard cancellation, and exactly-once telemetry remain
  outside this local contract. No publication, website, cloud, registry, or
  user-owned untracked file change was made.

## Slice 102 QA — versioned evaluation fixtures and optional judge contract

- `tests/autonomy/test_evaluation.py` reports `20 passed in 0.24s`, covering
  fixture version propagation, trajectory quotas, redacted/bounded judge
  observations, judge pass/fail scoring, typed judge errors, and malformed or
  unbounded boundaries.
- `EvalCase.fixture_version` is bounded to versions 1 through 32 and is
  surfaced in each `EvalResult` and JSON report entry. Expected and observed
  tool trajectories are bounded to 256 control-free names. `EvalJudgeResult`
  requires a finite 0-to-1 score, an explicit boolean decision, and bounded
  rationale text; judge failures are isolated per case.
- The exact tracked manifest contains 107 tracked Python test files and reports
  `1242 passed, 1 skipped in 242.17s` with no warning output. Black, Ruff,
  changed-boundary mypy, compile, and diff checks pass. Network-free doctor
  returns `ready: true`, `status: SUCCESS`, version `1.1.3`, all eight checks
  true, and `network: false`.
- A clean committed-HEAD archive rebuilt wheel/sdist `1.1.3`; build and Twine
  both exited 0, the sdist contains 492 entries including ADR-048, the
  evaluation module, public exports, and regressions, and the workspace-only
  audit found zero preserved Doctrine files.
- MAPLE does not select or invoke a judge provider, retry or calibrate judge
  scores, run generated code, or claim semantic faithfulness. Async/provider
  orchestration and hosted evaluation remain separate contracts. No
  publication, website, cloud, registry, or user-owned untracked file change
  was made.

## Slice 103 QA — durable local handoff identity and ownership transfer

- `tests/autonomy/test_handoffs.py` and the existing handoff regressions report
  `30 passed in 0.31s`, covering in-memory and file restart recovery, source /
  target ownership checks, terminal transitions, hash-only persistence, sync
  and async tool integration, and target failure normalization.
- `HandoffRecord` persists only bounded agent IDs, SHA-256 task/context digests,
  state, ownership, target goal ID or failure type, and finite timestamps. The
  explicit state machine is source-owned `pending`, target-owned `accepted`,
  then source-owned `completed` or `failed`; wrong owners and invalid states
  fail closed. File operations use the existing per-record fencing lease and
  atomic replacement.
- The exact tracked manifest contains 108 tracked Python test files and reports
  `1248 passed, 1 skipped in 238.37s` with no warning output. Black, Ruff,
  changed-boundary mypy, compile, and diff checks pass. Network-free doctor
  returns `ready: true`, `status: SUCCESS`, version `1.1.3`, all eight checks
  true, and `network: false`.
- A clean committed-HEAD archive rebuilt wheel/sdist `1.1.3`; build and Twine
  both exited 0, the sdist contains 495 entries including ADR-049, the handoff
  module, public exports, and regressions, and the workspace-only audit found
  zero preserved Doctrine files.
- Remote routing/authentication, scheduling, notifications, hard target
  cancellation, duplicate-delivery resolution, and exactly-once external
  effects remain outside this local identity/state journal. No publication,
  website, cloud, registry, or user-owned untracked file change was made.

## Security conclusions

- No new dependency, credential, cloud call, website mutation, or publication
  action was introduced.
- New execution paths are bounded or fail closed; trusted-local execution is
  explicitly not an untrusted-code sandbox.
- Retrieval, event, evaluation, and interop payloads have explicit size/shape
  controls; event/evaluation outputs redact credential-like keys.
- Security sign-off is limited to the changed feature boundaries. It is not a
  substitute for the workspace-only Doctrine gold verifier or final
  independent verifier pass.

## Release decision

**QA status: CONDITIONAL / NOT PUBLISH-READY.** The exact tracked suite,
focused runtime checks, static checks, current clean archive, Twine, and
network-free doctor gates pass. The workspace-only Doctrine gold verifier and
fresh independent review remain open. No external release action was taken.

## 2026-08-28 current QA revalidation

Slices 171 and 172 are now included in the committed release history:
bounded agent-invocation idempotency plus opt-in remote handoff-ID
binding. The defaults remain backward-compatible, and their per-slice QA
reports are filed at [Slice 171](maple-agent-runtime-slice171.md) and [Slice
172](maple-agent-runtime-slice172.md).

Current real gate output:

```text
python -m pytest -q --no-cov
1674 passed, 1 skipped in 262.74s

python -m maple.cli doctor --json
{"checks": {"core": true, "evaluation": true, "events": true, "execution": true, "interop": true, "retrieval": true, "server": true, "sessions": true}, "network": false, "ready": true, "status": "SUCCESS", "version": "1.1.3"}

clean git archive HEAD: source_archive_entries=815
build_exit=0
wheel_entries=106
sdist_entries=729
twine_exit=0
install_exit=0
isolated_import=passed
version=1.1.3
import_exit=0
```

The changed-surface static and targeted security scans pass. No dependency,
publication, cloud action, registry write, or website mutation was performed.
The established environment-wide pip-audit result remains a governance veto
at `384` vulnerabilities in `77` packages; Gitleaks, Bandit, and the required
fresh independent verifier session are unavailable here.

**Current QA status: CONDITIONAL / NOT PUBLISH-READY.** Local code, tests,
doctor, and package gates pass. Human release authorization and the independent
fresh-session review remain required before publication.

## 2026-08-28 current QA revalidation — Slice 173 release automation

The release and publish workflow changes were tested from the exact committed
archive at `1ac8a72`. The clean archive excludes the preserved untracked
workspace Doctrine files; the dirty workspace suite additionally reported
`1678 passed, 1 skipped in 266.73s`.

```text
python -m pytest tests/test_release_workflows.py -q --no-cov
4 passed in 0.21s

workflow_yaml_parse=passed

python -m pytest -q --no-cov  (clean committed archive)
1561 passed, 1 skipped in 227.39s

python -m maple.cli doctor --json
{"checks": {"core": true, "evaluation": true, "events": true, "execution": true, "interop": true, "retrieval": true, "server": true, "sessions": true}, "network": false, "ready": true, "status": "SUCCESS", "version": "1.1.3"}

clean git archive HEAD: source_archive_entries=821
build_exit=0
wheel_entries=106
sdist_entries=735
twine_exit=0
install_exit=0
isolated_import=passed
version=1.1.3
import_exit=0
```

**Slice 173 QA status: PASS for local workflow safety and packaging checks;
overall release status remains CONDITIONAL / NOT PUBLISH-READY.** `actionlint`
was unavailable, the known environment-wide dependency audit remains a veto,
and the fresh independent verifier plus human approval are still required.

## 2026-08-28 current QA revalidation — Slice 174 workflow supply chain

The action-pin invariant and all workflow YAML files were exercised locally.
The exact committed `4f145b8` archive also passed the full tracked suite and
package smoke checks:

```text
python -m pytest tests/test_release_workflows.py -q --no-cov
5 passed in 0.27s

workflow_yaml_parse=passed
all_workflow_action_refs_are_sha_pinned
uses_total=37
sha_pins=37

python -m pytest -q --no-cov  (clean committed archive)
1562 passed, 1 skipped in 228.60s

python -m maple.cli doctor --json  (isolated wheel)
{"checks": {"core": true, "evaluation": true, "events": true, "execution": true, "interop": true, "retrieval": true, "server": true, "sessions": true}, "network": false, "ready": true, "status": "SUCCESS", "version": "1.1.3"}

clean git archive HEAD: source_archive_entries=824
build_exit=0
wheel_entries=106
sdist_entries=738
twine_exit=0
install_exit=0
isolated_import=passed
version=1.1.3
import_exit=0
```

**Slice 174 QA status: PASS for action provenance and local packaging.** The
overall release remains CONDITIONAL / NOT PUBLISH-READY because v1.1.4 has
not been version-bumped or tagged, the workspace has preserved user changes,
the dependency audit remains a governance veto, and independent review plus
human publication approval are outstanding.

## 2026-08-28 current QA revalidation — Slice 175 remote durable checkpoint transfer

The complete workspace test manifest and changed-surface validation passed
after the checkpoint export/restore implementation and hardening fix:

```text
python -m pytest -q
1684 passed, 1 skipped in 288.93s (0:04:48)
```

The targeted transport regression set reported `55 passed in 31.82s`.
Black, isort, Ruff, mypy, compileall, and the scoped whitespace check passed.
The transfer tests cover full checkpoint export, restore identity and scope,
terminal rejection, malformed input, destination CAS conflicts, legacy-store
compatibility, and metadata-only receipts.

The final committed archive also passed the package gates:

```text
clean git archive HEAD: source_archive_entries=828
python -m pytest -q --no-cov
1567 passed, 1 skipped in 246.06s
build_exit=0
wheel_entries=106
sdist_entries=742
twine_exit=0
install_exit=0
isolated_import=passed
version=1.1.3
import_exit=0
{"checks": {"core": true, "evaluation": true, "events": true, "execution": true, "interop": true, "retrieval": true, "server": true, "sessions": true}, "network": false, "ready": true, "status": "SUCCESS", "version": "1.1.3"}
doctor_exit=0
```

**Slice 175 QA status: PASS for the implemented local runtime boundary;
overall release status remains CONDITIONAL / NOT PUBLISH-READY.** The current
environment-wide `pip-audit --format json` run exited `1` with `Found 385 known
vulnerabilities in 78 packages`; Gitleaks, Bandit, actionlint, and the fresh
independent verifier remain unavailable. Version 1.1.4 has not been cut, the
workspace retains preserved user changes, and human publication authorization
is still required.

## 2026-08-28 current QA revalidation - Slice 176 remote human-input push delivery

Acceptance criteria were exercised on the current candidate before package
verification. The transport regression set covered notification round-trips,
created/responded/continued store transitions, response-data exclusion,
receiver authentication and `interaction:notify` scope denial, malformed and
oversized bodies, callback failure with persisted state preserved, non-loopback
HTTPS enforcement, invalid acknowledgements, and unavailable receiver
configuration.

```text
python -m pytest -q tests/autonomy/test_remote_notification_delivery.py tests/autonomy/test_interaction_host.py tests/autonomy/test_server.py --no-cov
62 passed in 25.14s

python -m pytest -q --no-cov
1693 passed, 1 skipped in 300.28s (0:05:00)

python -m black --check maple/autonomy/interactions.py maple/autonomy/server.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_remote_notification_delivery.py
5 files would be left unchanged.

python -m isort --check-only maple/autonomy/interactions.py maple/autonomy/server.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_remote_notification_delivery.py
exit=0

python -m ruff check maple/autonomy/interactions.py maple/autonomy/server.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_remote_notification_delivery.py
All checks passed!

python -m mypy maple/autonomy/interactions.py maple/autonomy/server.py tests/autonomy/test_remote_notification_delivery.py --follow-imports=skip
Success: no issues found in 3 source files

python -m compileall -q maple tests/autonomy/test_remote_notification_delivery.py
compile_exit=0
```

Clean archive/package verification was run from exact committed `062deb7`:

```text
clean git archive HEAD: source_archive_entries=832
python -m pytest -q --no-cov
1576 passed, 1 skipped in 263.09s (0:04:23)
wheel_entries=106
sdist_entries=746
twine_exit=0
install_exit=0
isolated_import=passed
version=1.1.3
import_exit=0
{"checks": {"core": true, "evaluation": true, "events": true, "execution": true, "interop": true, "retrieval": true, "server": true, "sessions": true}, "network": false, "ready": true, "status": "SUCCESS", "version": "1.1.3"}
doctor_exit=0
```

Adversarial result: malformed, enormous, unauthorized, out-of-scope, invalid
acknowledgement, non-HTTPS non-loopback, callback rejection, and future-field
payload cases behaved as specified. No new bug was found, so no regression
fix was required. The environment-wide dependency audit remains a governance
veto (`pip-audit` exit `1`, 385 findings in 78 packages); Gitleaks, Bandit,
actionlint, and the fresh independent verifier were unavailable. No external
state was changed.

**Slice 176 QA status: PASS for the implemented boundary; overall release
status remains CONDITIONAL / NOT PUBLISH-READY.**

## 2026-08-28 current QA revalidation - Slice 177 remote approval push delivery

Acceptance criteria were exercised through model, local-store, HTTP sender,
receiver, and client tests. Coverage includes created/approved/denied events,
file restart persistence, execution-result exclusion, event/status mismatch,
post-persistence failure behavior, auth and `approval:notify` scope denial,
malformed and oversized bodies, receiver no-mutation behavior, non-loopback
HTTPS enforcement, invalid acknowledgements, and unavailable receiver
configuration.

```text
python -m pytest -q tests/autonomy/test_remote_approval_notification.py --no-cov
12 passed in 4.46s

python -m pytest -q tests/autonomy/test_approval.py tests/autonomy/test_approval_leases.py tests/autonomy/test_server.py --no-cov
61 passed in 21.11s

python -m pytest -q --no-cov
1705 passed, 1 skipped in 289.21s (0:04:49)

python -m black --check maple/autonomy/approval.py maple/autonomy/server.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_remote_approval_notification.py
5 files would be left unchanged.

python -m isort --check-only maple/autonomy/approval.py maple/autonomy/server.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_remote_approval_notification.py
exit=0

python -m ruff check maple/autonomy/approval.py maple/autonomy/server.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_remote_approval_notification.py
All checks passed!

python -m mypy maple/autonomy/approval.py maple/autonomy/server.py tests/autonomy/test_remote_approval_notification.py --follow-imports=skip
Success: no issues found in 3 source files

python -m compileall -q maple tests/autonomy/test_remote_approval_notification.py
compile_exit=0
```

The documented API construction example was executed:

```text
FileApprovalStore
```

Clean archive/package verification was run from exact committed `f53e95f`:

```text
clean git archive HEAD: source_archive_entries=836
python -m pytest -q --no-cov
1588 passed, 1 skipped in 258.43s (0:04:18)
wheel_entries=106
sdist_entries=750
twine_exit=0
install_exit=0
isolated_import=passed
version=1.1.3
import_exit=0
{"checks": {"core": true, "evaluation": true, "events": true, "execution": true, "interop": true, "retrieval": true, "server": true, "sessions": true}, "network": false, "ready": true, "status": "SUCCESS", "version": "1.1.3"}
doctor_exit=0
```

Adversarial result: malformed, enormous, unauthorized, out-of-scope,
event/status-inconsistent, execution-result-bearing, invalid-acknowledgement,
non-HTTPS non-loopback, callback rejection, and future-field payload cases
behaved as specified. No new unresolved bug remains. The environment-wide
dependency audit remains a governance veto (`pip-audit` exit `1`, 385 findings
in 78 packages); Gitleaks, Bandit, actionlint, and the fresh independent
verifier were unavailable. No external state was changed.

**Slice 177 QA status: PASS for the implemented boundary; overall release
status remains CONDITIONAL / NOT PUBLISH-READY.**

## 2026-08-28 current QA revalidation - Slice 178 durable notification outbox

Acceptance criteria were exercised through both typed adapters and the
generic outbox contract. Coverage includes atomic enqueue, canonical
deduplication, restart loading, successful durable delivery marks, retained
failures and explicit retry, sanitized target exceptions, queue and record
byte bounds, bounded drain/list limits, malformed-state rejection, no
mutation on invalid state, store integration, and a concurrent observer that
confirms target delivery does not hold the outbox state lock.

```text
python -m pytest -q tests/autonomy/test_notification_outbox.py --no-cov
10 passed in 0.43s

python -m pytest -q tests/autonomy/test_notification_outbox.py tests/autonomy/test_approval.py tests/autonomy/test_interactions.py tests/autonomy/test_remote_approval_notification.py --no-cov
36 passed in 4.69s

python -m pytest -q --no-cov
1715 passed, 1 skipped in 280.37s (0:04:40)

python -m black --check maple/autonomy/notification_outbox.py maple/autonomy/interactions.py maple/autonomy/approval.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_notification_outbox.py
6 files would be left unchanged.

python -m isort --check-only maple/autonomy/notification_outbox.py maple/autonomy/interactions.py maple/autonomy/approval.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_notification_outbox.py
exit=0

python -m ruff check maple/autonomy/notification_outbox.py maple/autonomy/interactions.py maple/autonomy/approval.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_notification_outbox.py
All checks passed!

python -m mypy maple/autonomy/notification_outbox.py maple/autonomy/interactions.py maple/autonomy/approval.py --follow-imports=skip
Success: no issues found in 3 source files

python -m compileall -q maple tests/autonomy/test_notification_outbox.py
compile_exit=0
```

Adversarial result: malformed, oversized, unsafe, full-queue, invalid-limit,
downstream-rejection, downstream-exception, and concurrent-observer cases
behaved as specified. No new dependency was added. The environment-wide
`pip-audit --format json` governance veto and unavailable Gitleaks, Bandit,
actionlint, and fresh independent verifier session remain documented. No
external state was changed.

**Slice 178 QA status: PASS for the bounded local outbox; overall release
status remains CONDITIONAL / NOT PUBLISH-READY.**

Clean archive/package verification was run from exact committed `c064b80`:

```text
clean git archive HEAD: source_archive_entries=841
python -m pytest -q --no-cov
1598 passed, 1 skipped in 255.85s (0:04:15)
build_exit=0
wheel_entries=107
sdist_entries=755
twine_exit=0
install_exit=0
isolated_import=passed
version=1.1.3
import_exit=0
{"checks": {"core": true, "evaluation": true, "events": true, "execution": true, "interop": true, "retrieval": true, "server": true, "sessions": true}, "network": false, "ready": true, "status": "SUCCESS", "version": "1.1.3"}
doctor_exit=0
```

The first Windows PowerShell binary-pipe attempt was discarded after the tar
tool reported a damaged archive; the successful rerun used Git's direct
`--output` archive mode in a fresh temp directory. No repository data was
changed by either attempt. No publication, deployment, cloud action, registry
write, or website update was performed.

## 2026-08-28 current QA revalidation - Slice 179 cross-process notification drain fence

Acceptance criteria were exercised through the approval outbox adapter and
the existing file lease manager. Coverage includes competing local drainers,
no target call on lease denial, typed acquisition/storage failure, release
failure after a committed delivery, release failure attached to a typed drain
error, no-lease compatibility through the existing suite, target execution
outside the outbox state lock, and finite bounded TTL validation.

```text
python -m pytest -q --no-cov tests/autonomy/test_notification_outbox.py tests/resources/test_file_lease.py
20 passed in 0.66s

python -m pytest -q --no-cov
1720 passed, 1 skipped in 279.71s (0:04:39)

python -m black --check maple/autonomy/notification_outbox.py maple/autonomy/interactions.py maple/autonomy/approval.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_notification_outbox.py
6 files would be left unchanged.

python -m isort --check-only maple/autonomy/notification_outbox.py maple/autonomy/interactions.py maple/autonomy/approval.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_notification_outbox.py
exit=0

python -m ruff check maple/autonomy/notification_outbox.py maple/autonomy/interactions.py maple/autonomy/approval.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_notification_outbox.py
All checks passed!

python -m mypy maple/autonomy/notification_outbox.py maple/autonomy/interactions.py maple/autonomy/approval.py --follow-imports=skip
Success: no issues found in 3 source files

python -m compileall -q maple/autonomy/notification_outbox.py maple/autonomy/interactions.py maple/autonomy/approval.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_notification_outbox.py
compileall_exit=0
```

Adversarial result: competing workers are fenced before target invocation;
lease storage and release faults fail closed; successful delivery state is
retained even when release cannot be confirmed; and a TTL expiry remains
truthfully at-least-once rather than exactly-once. No new dependency was
added. The environment-wide `pip-audit` governance veto and unavailable
Gitleaks, Bandit, actionlint, and fresh independent verifier remain
documented. No external state was changed.

**Slice 179 QA status: PASS for the optional local drain fence and clean archive
package gate. Overall release status remains
CONDITIONAL / NOT PUBLISH-READY.**

Clean archive/package verification was run from exact committed `c331f36`:

```text
clean git archive HEAD: source_archive_entries=844
python -m pytest -q --no-cov
1603 passed, 1 skipped in 249.79s (0:04:09)
build_exit=0
wheel_entries=107
sdist_entries=758
twine_exit=0
install_exit=0
version=1.1.3
lease_ttl=30.0
outbox=FileApprovalNotificationOutbox
lease_manager=FileLeaseManager
import_exit=0
{"checks": {"core": true, "evaluation": true, "events": true, "execution": true, "interop": true, "retrieval": true, "server": true, "sessions": true}, "network": false, "ready": true, "status": "SUCCESS", "version": "1.1.3"}
doctor_exit=0
```

The package gate was run from a clean Git archive, so the repository's
untracked doctrine files were not included. No publication, deployment, cloud
action, registry write, or website update was performed.

## 2026-08-28 current QA revalidation - Slice 181 host-owned token-to-principal resolution

Acceptance criteria were exercised through the existing local agent server:
static/resolver exclusivity, direct and Result-wrapped principal resolution,
per-token filtered discovery, per-token named and capability routing, denial
before an oversized request body is read, generic rejection for resolver
errors/exceptions/invalid results, and no callback on missing credentials.

```text
python -m pytest -q --no-cov tests/autonomy/test_server.py
54 passed in 22.74s

python -m pytest -q --no-cov
1724 passed, 1 skipped in 282.12s (0:04:42)

python -m black --check maple/autonomy/server.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_server.py
4 files would be left unchanged.

python -m isort --check-only maple/autonomy/server.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_server.py
exit=0

python -m ruff check maple/autonomy/server.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_server.py
All checks passed!

python -m mypy maple/autonomy/server.py --follow-imports=skip
Success: no issues found in 1 source file

python -m compileall -q maple/autonomy/server.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_server.py
compileall_exit=0
```

Adversarial result: invalid or rejected bearer values fail closed with bounded
401 responses; callback failures do not leak resolver data; every protected
authorization consumer uses the request-selected principal; and existing
static-token tests remain green. No new dependency was added. The
environment-wide dependency audit, Gitleaks, Bandit, actionlint, and fresh
independent verifier remain unavailable or governance-blocked. No external
state was changed.

**Slice 181 QA status: PASS for the host-owned resolver boundary. Overall
release status remains CONDITIONAL / NOT PUBLISH-READY pending clean
archive/package verification and human authorization.**

## 2026-08-28 current QA revalidation - Slice 180 least-privilege agent target policy

Acceptance criteria were exercised through the existing local agent server:
bounded exact agent and capability allowlists, empty-list compatibility,
filtered discovery, named-agent denial before request-body parsing, capability
denial before routing and idempotency claims, no handler invocation on denial,
and bounded non-sensitive policy errors. Capability-only named routes fail
closed when no matching registered agent exists.

```text
python -m pytest -q --no-cov tests/autonomy/test_server.py
52 passed in 22.08s

python -m pytest -q --no-cov
1722 passed, 1 skipped in 290.87s (0:04:50)

python -m black --check maple/autonomy/server.py tests/autonomy/test_server.py
2 files would be left unchanged.

python -m isort --check-only maple/autonomy/server.py tests/autonomy/test_server.py
exit=0

python -m ruff check maple/autonomy/server.py tests/autonomy/test_server.py
All checks passed!

python -m mypy maple/autonomy/server.py --follow-imports=skip
Success: no issues found in 1 source file

python -m compileall -q maple/autonomy/server.py tests/autonomy/test_server.py
compileall_exit=0
```

Adversarial result: denied named routes do not read oversized secret bodies;
denied capability routes do not claim idempotency or invoke handlers; allowed
routes preserve existing behavior; and exact allowlists cannot be widened by
duplicate or over-bound entries. No new dependency was added. The
environment-wide dependency audit, Gitleaks, Bandit, actionlint, and fresh
independent verifier remain unavailable or governance-blocked. No external
state was changed.

**Slice 180 QA status: PASS for the least-privilege local target policy and
clean archive/package gate. Overall release status remains CONDITIONAL / NOT
PUBLISH-READY pending the documented release gates and human authorization.**

Clean archive/package verification was run from exact committed `abb21c9`:

```text
clean git archive HEAD: source_archive_entries=847
python -m pytest -q --no-cov
1605 passed, 1 skipped in 237.77s (0:03:57)
build_exit=0
wheel_entries=107
sdist_entries=761
twine_exit=0
install_exit=0
version=1.1.3
principal=Principal
outbox=FileApprovalNotificationOutbox
lease_manager=FileLeaseManager
corrected_import_exit=0
{"checks": {"core": true, "evaluation": true, "events": true, "execution": true, "interop": true, "retrieval": true, "server": true, "sessions": true}, "network": false, "ready": true, "status": "SUCCESS", "version": "1.1.3"}
doctor_exit=0
```

The package gate used a clean Git archive and therefore excluded preserved
untracked doctrine files. No publication, deployment, cloud action, registry
write, or website update was performed.
