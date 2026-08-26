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
- `rg -n "NOT_IMPLEMENTED" maple` was used as the inventory cross-check; no
  runtime files or tests changed, and no unsupported feature was implemented by
  documentation alone.
- No dependency, credential, cloud call, publication, or website mutation was
  performed. The exact full-suite and fresh independent-verifier gates remain
  open.

## Security conclusions

- No new dependency, credential, cloud call, website mutation, or publication
  action was introduced.
- New execution paths are bounded or fail closed; trusted-local execution is
  explicitly not an untrusted-code sandbox.
- Retrieval, event, evaluation, and interop payloads have explicit size/shape
  controls; event/evaluation outputs redact credential-like keys.
- Security sign-off is limited to the changed feature boundaries. It is not a
  substitute for the unfinished full-suite run or final independent verifier
  pass.

## Release decision

**QA status: CONDITIONAL / NOT PUBLISH-READY.** The implementation is
feature-complete for the tracked implemented capability slices, the built wheel
passes a clean-venv doctor smoke test, and the isolated dependency audit is
clean. The release gate must remain open for the exact full-suite and
fresh-verifier checks. No external release action was taken.
