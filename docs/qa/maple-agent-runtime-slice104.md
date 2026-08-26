# QA + Security Report — provider stream aggregation and agent chunks @ afc3a33

**QA Engineer** · **Security Reviewer** · **Date:** 2026-08-26  
**Build under test:** `afc3a33 feat(streaming): add bounded agent chunk events`

## Acceptance criteria verification

| # | Criterion | How executed | Evidence (real output) | Pass |
|---|---|---|---|---|
| 1 | Aggregate bounded text, tool calls, finish, usage, and request ID into `LLMResponse` | Provider streaming tests | `5 passed` in `tests/llm/test_provider_streaming.py`; fragmented text/JSON arguments, trailers, and ID-based multi-tool assembly covered | Yes |
| 2 | Preserve native OpenAI/Anthropic stream adapter compatibility | Native adapter tests | `3 passed` in `tests/llm/test_provider_native_streaming.py` | Yes |
| 3 | Emit safe chunk progress for sync and async ReAct runs only when opted in | Run/event and autonomy tests | `54 passed` focused across provider, native stream, run, and autonomy tests; sync/async `model.chunk` ordering and payload redaction covered | Yes |
| 4 | Fail closed on malformed or over-quota streams | Adversarial collector tests | Oversized chunk returns `LLM_STREAM_CHUNK_TOO_LARGE`; malformed tool arguments and invalid chunk paths are typed in the implementation contract | Yes |
| 5 | Existing default completion behavior remains unchanged | Exact tracked regression suite | `1253 passed, 1 skipped in 260.34s` across `108` tracked test files | Yes |
| 6 | Release artifact contains committed files only | Clean ZIP archive build and audit | `build_exit=0`, `twine_exit=0`, `sdist_entries=496`, `required_hits=5/5`, `workspace_only_hits=0` | Yes |

## Adversarial & edge matrix

| Input/scenario | Expected | Observed | Pass |
|---|---|---|---|
| Empty text / finish-only chunk | Preserve `None` content and final metadata | Collector returns no content and retains trailer metadata | Yes |
| Chunk larger than 64 KiB | Typed rejection | `LLM_STREAM_CHUNK_TOO_LARGE` | Yes |
| Aggregate content beyond 1 MiB | Typed rejection | `LLM_STREAM_CONTENT_TOO_LARGE` path is bounded in collector | Yes |
| Fragmented JSON tool arguments | Reconstruct only a JSON object | Two fragments became `{"q": "MAPLE"}` | Yes |
| New tool ID without explicit index | Start a separate call | Two calls retained in order by ID | Yes |
| Invalid ID/name/finish reason/index | Typed rejection | Validation returns `LLM_STREAM_*_INVALID` errors | Yes |
| Callback raises | Run outcome remains isolated | Callback exception is swallowed; aggregate result remains typed | Yes |
| Unicode content | Count UTF-8 bytes, preserve text | Content quota uses encoded byte length | Yes |
| Sync and async agent paths | Same lifecycle ordering | `run.started → model.chunk* → model.response → run.completed` | Yes |
| Raw content/tool arguments in lifecycle payload | Never emit | Tests assert metadata-only chunk payloads | Yes |

## Regression

Suite: `python -m pytest @trackedTestFiles --no-cov -p no:dash -p no:benchmark -q --tb=short --no-header`  
Output: `1253 passed, 1 skipped in 260.34s (0:04:20)`  
Flakes: none observed in the final exact run. An earlier Slice 103 run had an
isolated server-test failure that passed on isolation and on its exact rerun;
that is historical and not part of this slice's final run.

## Bugs found

| # | Repro steps (minimal) | Severity | Fixed @ | Re-verified | Regression test |
|---|---|---|---|---|---|
| 1 | Use a provider stream with two new tool IDs and no explicit indexes | Medium | `afc3a33` | Yes | `test_complete_from_stream_starts_new_id_without_an_explicit_index` |
| 2 | Invoke the collector with an oversized content chunk | High | `afc3a33` | Yes | `test_complete_from_stream_fails_closed_for_unbounded_content` |

## Security sweep

Secrets scan: `gitleaks` unavailable; targeted source scan found no embedded
credential values and only expected configuration/metadata references.  
Injection review: no new shell, SQL, path, template, pickle, eval, or exec
surface; lifecycle events intentionally exclude raw content and arguments.  
Dependency audit: `pip-audit` ran against the host environment and reported
`383 known vulnerabilities in 77 packages`; this slice adds no dependency and
the report includes unrelated development/ML packages. The finding remains a
release-governance item because project dependency ranges are broad and must be
audited in the release environment before publication.  
Dangerous constructs: no new subprocess, TLS, unsafe, or temp-file behavior.  
Bounds/fail-closed: content, chunk, argument, tool-call, finish-reason, and
request-ID limits are enforced; provider/callback failures become typed errors
or isolated telemetry failures.

**Security verdict:** VETO for a final repository publication claim until the
dependency-audit findings are dispositioned; slice-level code review found no
new security defect.  
**QA verdict:** pass → behavior and artifact criteria met; publication remains
outside this task and dependency governance remains open.
