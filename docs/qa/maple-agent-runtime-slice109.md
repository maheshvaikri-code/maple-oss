# QA + Security Report - durable parallel-branch retries @ d388b51

**QA Engineer** - **Security Reviewer** - **Date:** 2026-08-26  
**Build under test:** `d388b51 feat(workflow): durable parallel branch retries`

## Acceptance criteria verification

| # | Criterion | How executed | Evidence (real output) | Pass |
|---|---|---|---|---|
| 1 | Persist branch retry counts and due times | Workflow checkpoint implementation and focused regression | `WorkflowCheckpoint`/`WorkflowRun` expose `branch_retry_counts` and `branch_retry_after`; `HistoryCheckpointStore` captured `NODE_RETRY_SCHEDULED` with `{"flaky": 1}` and a positive due time | Yes |
| 2 | Retry only failed branches in bounded waves | `tests/autonomy/test_workflow.py` | Flaky branch receives context retry counts `[0, 1]`, completes with one retry, and the fan-in state remains deterministic | Yes |
| 3 | Preserve typed bounded exhaustion | `tests/autonomy/test_workflow.py` | Always-failing branch returns persisted run status `failed`, `NODE_RETRY_EXHAUSTED`, branch `broken`, and retry count `1` | Yes |
| 4 | Preserve checkpoint version correctness on retry failure/pause paths | Focused workflow/replay regression and implementation review | Terminal failure and interruption refresh the checkpoint after an intermediate retry save; no stale expected-version conflict remains | Yes |
| 5 | Preserve existing workflow/replay behavior | Exact tracked application regression | `1267 passed, 1 skipped in 256.93s` across 1268 collected items; five untracked Doctrine-only tests excluded | Yes |
| 6 | Keep public surface truthful | ADR/API/README/parity/changelog review | ADR-055 documents bounded waves, durable cursor fields, at-least-once effects, and deferred distributed scheduling | Yes |
| 7 | Produce a clean package candidate | Clean committed-HEAD archive audit | Candidate `afa57d0`: build exit `0`, Twine exit `0`, sdist `513` entries, required Slice 109 files present, workspace-only audit `0` | Yes |

## Focused command evidence

```text
python -m pytest tests/autonomy/test_workflow.py tests/autonomy/test_workflow_replay.py -q --no-cov -p no:dash -p no:benchmark --tb=short --no-header
collected 24 items
============================= 24 passed in 0.32s ==============================
```

Static and runtime gates:

```text
python -m black maple/autonomy/workflow.py tests/autonomy/test_workflow.py --check
All done! ...
2 files would be left unchanged.

python -m ruff check maple/autonomy/workflow.py tests/autonomy/test_workflow.py
All checks passed!

python -m mypy maple/autonomy/workflow.py --ignore-missing-imports --follow-imports=skip
Success: no issues found in 1 source file

python -m compileall -q maple
exit code 0

python -m maple.cli doctor --json
{"checks": {"core": true, "evaluation": true, "events": true, "execution": true, "interop": true, "retrieval": true, "server": true, "sessions": true}, "network": false, "ready": true, "status": "SUCCESS", "version": "1.1.3"}

git diff --check
exit code 0
```

Tracked application regression (Doctrine-only untracked tests excluded):

```text
collected 1268 items
================= 1267 passed, 1 skipped in 256.93s (0:04:16) =================
```

## Adversarial and edge matrix

| Input/scenario | Expected | Observed | Pass |
|---|---|---|---|
| Branch succeeds on first attempt | No retry checkpoint; normal fan-in | Existing fan-out regression remains green | Yes |
| Branch fails once with policy | Persist schedule, retry with `retry_count=1` | History snapshot contains `NODE_RETRY_SCHEDULED` and `branch_retry_counts={"flaky": 1}`; handler calls `[0, 1]` | Yes |
| Branch fails through policy budget | Typed exhaustion; no unbounded loop | `NODE_RETRY_EXHAUSTED`, `node=broken`, `retry_count=1`; handler calls `[0, 1]` | Yes |
| Positive branch backoff | Persist finite due time and wait before next wave | Positive `branch_retry_after["flaky"]` captured; focused test completes | Yes |
| No branch policy | Preserve immediate typed failure | Existing no-policy workflow behavior remains covered by full regression | Yes |
| Malformed branch retry metadata | Reject at data boundary | Identifier, count, finite timestamp, and object-shape validation mirror existing retry fields | Yes |
| External branch side effects | Do not claim exactly-once | ADR/API docs retain at-least-once and idempotent-handler requirements | Yes |
| Remote/distributed scheduling request | Remain outside local contract | No transport, lease, hosted scheduler, or new dependency added | Yes |

## Security sweep

Secret scanner: `gitleaks` is unavailable in the environment (`where.exe
gitleaks` found no files). Manual changed-surface review found no new secret,
command, path, deserialization, network, credential, or sandbox handling. The
change only adds JSON-safe checkpoint metadata and local thread waves.

Dependency audit: host `pip-audit` reported `Found 383 known vulnerabilities in
77 packages` and warned about invalid distribution `~gl`. It also listed local
packages that cannot be audited from PyPI. This slice adds no dependency; the
host-environment finding remains an open release-governance item and publication
veto.

Bounds/fail-closed: retry policy limits remain capped at eight retries and 60
seconds, branch fan-out remains capped by `max_parallel_branches`, checkpoint
metadata remains JSON-safe and finite, and checkpoint saves retain CAS version
checks. Branch handler effects are not represented as exactly-once.

**Security verdict:** **VETO** for a final repository publication claim until
dependency findings are dispositioned; no new Slice 109 security defect found.
Human override: n/a.  
**QA verdict:** pass for Slice 109 behavior and local durability boundaries;
clean committed-HEAD package evidence is attached below. No publication was
performed.

## Package audit evidence

```text
source=git archive HEAD
head=afa57d0
build_exit=0
twine_wheel=PASSED
twine_sdist=PASSED
sdist_entries=513
required_public_files=5/5
workspace_only_hits=0
present=docs/adr/055-durable-parallel-branch-retries.md
present=docs/qa/maple-agent-runtime-slice109.md
present=docs/reviews/maple-agent-runtime-slice109.md
absent=AGENTS.md, CLAUDE.md, COMMERCIAL_LICENSE.md
```
