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
   The latest bounded attempt reported `1049 passed, 8 warnings in 839.17s`
   before interruption in the remaining Doctrine gold cases. The suspected S2
   adapter was cleared in isolation (16 passed in 0.06s). Fresh-repository
   profiling shows individual Git commands taking roughly 5–15 seconds, with
   the slowest gold cases at 166.96s, 159.74s, 115.61s, and 56.04s. No
   assertion failure was reported.
2. The shared interpreter's `pip check` still reports unrelated package
   conflicts (including `chromadb`, `fsspec`, `pydantic`, `openai`, and
   `langchain-core`), but a fresh environment installed `.[dev,security]` and
   returned `No broken requirements found.` The isolated dependency gate passes.
3. Repository-wide Ruff is not clean because of remaining package-initializer
   and legacy lint debt. Slice 65 reduced the inventory from 250 to 171
   diagnostics (`E402 140`, `F401 31`); changed implementation files and the
   new FIPA regression are clean.
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

## Verdict

**Feature review:** PASS for the eighteen implemented capability slices.
**Publish readiness:** NOT YET APPROVED. A release manager should close the
open full-suite, remaining legacy lint/security debt, repository lint, and
fresh-verifier gates before publishing. External publication remains awaiting
explicit human approval.
