# QA + Security Report — bounded code-block artifact materialization @ 3382595

**QA Engineer** · **Security Reviewer** · **Date:** 2026-08-29  
**Build under test:** exact implementation commit `3382595`

## Acceptance criteria verification

| # | Criterion | How executed | Evidence (real output) | Pass |
|---|-----------|--------------|------------------------|------|
| 1 | Exact UTF-8 bytes and SHA-256 identity | Focused tests, public example, clean isolated install | `25 passed in 0.44s`; public example returned `artifactId=sha256:91be880a2146cf6ba9a9fb83bfef2842a5dcfe95e02b471f7a4472144021e1e9`; clean import/materialization returned `materialize=sha256:3a6eb0790f39ac87c94f3856b2dd2c5d110e6811602261a9a923d3bb23adc8b7` | Yes |
| 2 | Deterministic bounded safe name | Adversarial boundary script and focused tests | `index zero/max: PASS`; `duplicate: PASS`; focused assertion verified `code-block-2.python` | Yes |
| 3 | In-memory/file parity and restart readability | Focused test plus adversarial restart check | `restart/inert side effect: PASS`; clean isolated import completed with `import_exit=0` | Yes |
| 4 | Typed fail-closed errors and no execution/partial mutation | Invalid object/name, limit+1, full store, raising store, inert side-effect text | `malformed/unsafe: PASS`; `limit+1: PASS`; `raising store: PASS`; `restart/inert side effect: PASS` | Yes |
| 5 | Public export and runnable documentation | Top-level API test and exact API example executed through stdin | `25 passed in 0.44s`; example printed an `Artifact.to_dict()` with `name: 'code-block-0.python'` and `mediaType: 'text/plain'` | Yes |

## Adversarial & edge matrix

| Input/scenario | Expected | Observed | Pass |
|----------------|----------|----------|------|
| Empty code | Store zero-length bytes with stable digest | `empty: PASS` | Yes |
| Unicode code | Preserve UTF-8 bytes exactly | `unicode: PASS` | Yes |
| Payload limit−1 (131071 bytes) | Materialize successfully | `limit-1: PASS` | Yes |
| Payload limit (131072 bytes) | Materialize successfully | `limit: PASS` | Yes |
| Payload limit+1 (131073 bytes) | Typed `CODE_BLOCK_TOO_LARGE`, no store write | `limit+1: PASS` | Yes |
| Negative index | Reject invalid `CodeBlock` | `index -1: PASS` | Yes |
| Zero and maximum index | Accept bounded values | `index zero/max: PASS` | Yes |
| Index maximum+1 (1000001) | Reject invalid `CodeBlock` | `index 1000001: PASS` | Yes |
| Duplicate bytes | Return the same content-addressed artifact | `duplicate: PASS` | Yes |
| Malformed store/path-like name | Typed error before mutation | `malformed/unsafe: PASS` | Yes |
| Store quota full | Typed error and preserve prior artifact | Focused test passed; `full` path reported `ARTIFACT_STORE_FULL` | Yes |
| Store raises exception | Typed `CODE_ARTIFACT_STORE_ERROR` | `raising store: PASS` | Yes |
| Code containing file-writing expression | Remain inert; no side-effect file | `restart/inert side effect: PASS` | Yes |
| Concurrent calls | No concurrency guarantee claimed by this synchronous helper | Not applicable to this local contract | N/A |
| Interrupted operation | No interruptible execution/network operation in scope | Not applicable to this local data-only helper | N/A |

The first matrix harness invocation failed because the harness incorrectly
used the payload limit (`131073`) as the index upper-bound probe. Its real
terminal output was `AssertionError: 131073`. The product had already passed
the payload checks. The corrected probe used the implementation’s documented
index bound (`1_000_000`) and produced the complete PASS matrix above; no
product change was made for this harness correction.

## Regression

Focused suite:

```text
============================= 25 passed in 0.44s ==============================
```

Dirty-worktree full suite, including the preserved user-owned Doctrine tests:

```text
================= 1765 passed, 1 skipped in 337.57s (0:05:37) =================
EXIT_CODE=0
```

Exact clean archive `3382595`:

```text
================= 1648 passed, 1 skipped in 256.39s (0:04:16) =================
source_archive_files=849
test_exit=0
```

Flakes: none observed. The interrupted/harness failure above was a corrected
QA-probe assertion, not a product failure.

## Bugs found

| # | Repro steps (minimal) | Severity | Fixed @ | Re-verified | Regression test |
|---|----------------------|----------|---------|-------------|-----------------|
| 1 | QA probe passed payload boundary `131073` as an index boundary | QA harness error | corrected probe; no product fix | corrected matrix completed with all PASS lines | N/A; probe script corrected |

No product bugs were found.

## Security sweep (per `skills/security.md`)

- Secrets scan of the Slice 195 commit: no credential-pattern matches. The
  broader working-tree scan reported only the known AWS example string at
  `tests/test_doctrine_state.py:453`, a preserved user-added test fixture and
  not part of commit `3382595`.
- Injection review: no new `eval`, `exec`, `pickle`, `subprocess`, shell,
  `yaml.load`, disabled-TLS, or direct caller-path write construct was added;
  the helper validates names and delegates only bounded bytes to `put`.
- Dependency manifest diff: `dependency-manifest-diff: none`.
- Declared project audit:

  ```text
  python -m pip_audit --progress-spinner off --strict .
  No known vulnerabilities found
  ```

- The shared environment audit remains an unresolved governance veto from the
  release baseline: `Found 385 known vulnerabilities in 78 packages`.
- `python -m bandit --version` could not run: `No module named bandit`.
- `gitleaks version` could not run: command not recognized.
- Bounds/fail-closed checks covered source/code size, index/language/name
  validation, typed store failures, content-addressing, and no execution.

**Security verdict:** **VETO for publication/release** — the environment-wide
dependency audit remains unresolved and Bandit/Gitleaks are unavailable. This
is not a Slice 195 code finding; the local feature boundary is fail-closed and
has no new dependency. **Human override:** n/a.

**QA verdict:** pass for Slice 195; implementation and regression criteria are
demonstrably met on the exact commit. A fresh independent verifier session
could not be launched in the current execution context, so no independent
verifier approval is claimed.

## Exact clean package evidence

```text
wheel_entries=108
sdist_entries=825
wheel_sha256=b2a97a41dcc2d67e66c834ec6f5d7d0a6a6944240a9b9b83181ff2f0049c1881
sdist_sha256=218ccc388eea921ff41285dbd33102a65028f4d6ef486b55c9e3775570390b00
Successfully built maple_oss-1.1.3.tar.gz and maple_oss-1.1.3-py3-none-any.whl
...whl: PASSED
...tar.gz: PASSED
CodeBlock=CodeBlock
materialize=sha256:3a6eb0790f39ac87c94f3856b2dd2c5d110e6811602261a9a923d3bb23adc8b7
RunClient=RunClient
RunServer=RunServer
import_exit=0
doctor_exit=0
{"checks": {"core": true, "evaluation": true, "events": true, "execution": true, "interop": true, "retrieval": true, "server": true, "sessions": true}, "network": false, "ready": true, "status": "SUCCESS", "version": "1.1.3"}
```

## Current dirty-worktree package smoke

The package built from the current worktree (including closure evidence and
preserved user-owned files) also passed the install smoke. Hashes are omitted
because the release checklist is included in the source distribution and the
worktree is intentionally not a release candidate.

```text
wheel_entries=108
sdist_entries=834
Successfully built maple_oss-1.1.3.tar.gz and maple_oss-1.1.3-py3-none-any.whl
...whl: PASSED
...tar.gz: PASSED
CodeBlock=CodeBlock
materialize=sha256:3a6eb0790f39ac87c94f3856b2dd2c5d110e6811602261a9a923d3bb23adc8b7
RunClient=RunClient
RunServer=RunServer
{"checks": {"core": true, "evaluation": true, "events": true, "execution": true, "interop": true, "retrieval": true, "server": true, "sessions": true}, "network": false, "ready": true, "status": "SUCCESS", "version": "1.1.3"}
build_exit=0 twine_exit=0 venv_exit=0 install_exit=0 import_exit=0 doctor_exit=0
```
