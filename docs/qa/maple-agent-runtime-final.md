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
| Local readiness | PASS | `maple doctor --json` returned all six checks true and `network:false`. |
| Full repository regression | OPEN | Latest bounded run collected `1270` items and reached `95%` in Doctrine state tests with no failure output before interruption; pytest emitted no final summary. |
| Dependency consistency | PASS | Isolated MAPLE environment is consistent; shared-interpreter conflicts are unrelated and non-authoritative. |
| Repository-wide lint | PASS | Slice 69 closes the remaining E402 import-boundary debt; broad `ruff check maple` reports zero findings. |
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
feature-complete for the eighteen implemented capability slices, the built wheel
passes a clean-venv doctor smoke test, and the isolated dependency audit is
clean. The release gate must remain open for the full-suite, repository-wide
lint, and fresh-verifier checks. No external release action was taken.
