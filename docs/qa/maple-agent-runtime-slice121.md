# QA + Security Report - MAPLE Agent Runtime Slice 121 @ 0ca0924

**QA Engineer / Security Reviewer · Date:** 2026-08-27  
**Build under test:** `0ca0924` (bounded authenticated event ingestion and
bounded early request-body draining)

## Acceptance criteria verification

| # | Criterion | Evidence (real output) | Pass |
|---|---|---|---|
| 1 | A host can expose an existing event stream for authenticated remote ingestion. | Combined event/server suite: `36 passed in 10.07s`; the server assigns local sequence/timestamp values and preserves stream redaction. | Yes |
| 2 | Existing exporters can use the receiver without a new dependency. | The existing `HttpEventExporter` round-trip is covered; no runtime dependency was added. | Yes |
| 3 | Event input and receiver authority remain bounded. | Route requires `event_type` and `payload`; receiver-owned sequence/timestamp, redaction, size, and retention boundaries are exercised. | Yes |
| 4 | Authentication and failure paths fail closed. | Unauthorized calls are typed `UNAUTHORIZED`; missing stream is `EVENT_STREAM_UNAVAILABLE`/`503`; malformed fields are typed `400` errors. | Yes |
| 5 | Early HTTP errors remain deterministic on Windows. | Server suite: `21 passed in 9.41s`; the oversized-body regression passed three consecutive times: `1 passed` at `0.80s`, `0.75s`, and `0.79s`. | Yes |
| 6 | Existing application behavior remains green. | Full autonomy suite: `345 passed in 11.94s`. Exact tracked manifest: `1307 passed, 1 skipped in 213.45s` across `108` tracked Python test files. | Yes |
| 7 | Public/runtime surfaces are documented and statically valid. | Black: `2 files would be left unchanged`; Ruff: `All checks passed!`; changed-boundary mypy: `Success: no issues found in 1 source file`; compile and diff checks pass; doctor reports all eight checks true, `ready=true`, `network=false`. | Yes |
| 8 | The exact runtime commit produces a clean package candidate. | Clean archive `0ca0924`: build exit `0`; both Twine checks `PASSED`; sdist `547` members; wheel `104` members; required public files `6/6`; no-dependency wheel smoke printed `event transport exports ok`. | Yes |

## Contract and adversarial matrix

| Scenario | Expected | Observed | Pass |
|---|---|---|---|
| Event stream configured without a bearer token | Refuse construction | `ValueError` during `RunServer` construction | Yes |
| Missing or wrong bearer token | Do not ingest | Typed `UNAUTHORIZED` response | Yes |
| Missing event stream | Fail closed without socket reset | Typed `EVENT_STREAM_UNAVAILABLE`, HTTP `503` | Yes |
| Missing event fields | Reject before publish | Typed `EVENT_INPUT_INVALID`, HTTP `400` | Yes |
| Sender supplies sequence/timestamp metadata | Do not trust remote ordering | Receiver assigns fresh local stream values | Yes |
| Exported event contains sensitive payload fields | Redact at receiver boundary | Existing stream redaction remains visible after round-trip | Yes |
| Small valid oversized request body | Return typed `413` | Regression passes repeatedly after bounded drain | Yes |
| Agent resume or other early POST response | Avoid Windows connection reset | Bounded request-body drain preserves typed response | Yes |

## Regression evidence

```text
36 passed in 10.07s
345 passed in 11.94s
tracked_python_files=108
1307 passed, 1 skipped in 213.45s (0:03:33)
```

The initial full-manifest attempt exposed two Windows early-response races: a
missing-stream event response and the existing oversized-body `413` test could
surface as `TRANSPORT_ERROR` when the request body was still being sent. The
server now drains only valid, bounded lengths before closing. The focused
server suite and the final tracked manifest are green. No test was weakened or
removed.

## Static, package, and security evidence

- Manual credential-pattern scan on the changed source/test/ADR surface:
  `secret_scan=no matches`.
- Dangerous-construct scan for `eval(`, `exec(`, `pickle`, `subprocess`,
  `os.system`, `shell=True`, and `yaml.load(`):
  `dangerous_construct_scan=no matches`.
- `python -m pip_audit --progress-spinner off --format json .` returned
  `No known vulnerabilities found` with exit `0` across the `13` declared
  runtime packages.
- `gitleaks` and `bandit` are unavailable in the environment.
- The separate environment-wide audit remains a governance veto: the recorded
  prior audit found `383` known vulnerabilities across `77` packages. This is
  not silently represented as a clean project-runtime result.
- Clean package hashes from `0ca0924`:
  - sdist SHA-256:
    `22B9FDDC0A45C078503EC9FC13940CD06CFC3D7C755EE3CF4AF9537E91D2CCEE`
  - wheel SHA-256:
    `22AB3B96E3CCEC9D3679E5AF95ED75C68399BBBB1303CE011191A121C6CE4035`

**Security verdict:** pass for the changed declared runtime surface; **VETO**
for final repository publication until the environment-wide dependency
findings are dispositioned under release policy.

**QA verdict:** pass for Slice 121 behavior, bounds, authentication, stream
authority, Windows response stability, static checks, regression coverage, and
clean package evidence. Batching, durable replay, fleet aggregation, remote
trace search, principal scopes, and exactly-once delivery remain outside the
contract.
