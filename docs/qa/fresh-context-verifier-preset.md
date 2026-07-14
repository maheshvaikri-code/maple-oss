# QA Report — Fresh-Context Verifier Preset

**Gate:** G5 (Verification) · **Class:** M · **Platform:** Windows 11, Python 3.12.7

## Acceptance criteria (from the contract, `integrations/maple.md` ask #3)

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| 1 | Broker-enforced per-agent sender allowlist | ✅ | unit + broker + live-agent tests; smoke step 1 |
| 2 | Artifact-ref-only payload policy for guarded types | ✅ | unit + broker tests; smoke step 3 |
| 3 | Separation of duties is a *runtime* guarantee (not bypassable) | ✅ | publish + singleton bypasses closed (G4 H1/H2); smoke step 1 |
| 4 | Opt-in; zero effect when not configured | ✅ | `test_no_policy_means_no_enforcement`; 450-test regression subset green |
| 5 | Honest failure surface (`Result.err`, no fabricated success) | ✅ | `Agent.send()`/`publish()` return `Result.err`; smoke steps 1 & 3 |

## Test evidence (real output)

**Feature suite** — `tests/security/test_separation.py`:
```
52 passed
maple/security/separation.py    140    0   100%
```

**Regression subset** — `tests/broker tests/agent tests/security tests/core tests/communication tests/discovery`:
```
450 passed, 109 warnings in 171.95s
```
(No regressions in any module the change touches: broker `send`/`publish`/`__init__`,
`SecurityConfig`, security package exports.)

**End-to-end smoke** (three live Agents on the in-memory broker, threaded delivery):
```
1) verifier -> builder      : ERR (denied) | Agent 'code-reviewer' is not permitted to send to 'backend-engineer'
2) verifier -> orchestrator : OK (delivered) | 8f150a28-...
3) verifier prose payload   : ERR (denied) | SEND_ERROR (MISSING_ARTIFACT_REF)
RESULT: PASS — separation of duties enforced end-to-end
```

## Known limitations (disclosed, not defects)

- Enforcement is on the **in-memory `MessageBroker`** only; `nats_broker` and the
  S2 adapter do not consult the policy (documented in the module docstring and plan).
- The prose ceiling (`max_prose_chars`, default 512) is a tunable heuristic, not a
  proof — it bounds smuggled narrative; the sender allowlist is the hard guarantee.
- **Pre-existing hang (not this change):** `tests/task_management/test_task_submission.py::TestTaskSubmissionQueuing::test_task_priority_queuing`
  hangs when run after its sibling tests (it passes in isolation in ~5s). Confirmed
  independent of this change by stashing the three source edits
  (`config.py`, `broker.py`, `security/__init__.py`) and reproducing the same hang.
  This is why the full `pytest` run appears to stall (no `pytest-timeout` installed);
  verification was done dir-by-dir around it. Recommend a separate G0 brief to fix
  the order-dependent hang (likely a non-daemon thread / blocking `queue.get`).

### Aggregate test tally (this change's surface + surrounding dirs, all green)

| Group | Result |
|-------|--------|
| broker + agent + security + core + communication + discovery | 450 passed |
| state + resources + task_management (through the pre-existing hang) | ~230 passed, then 1 hang |
| autonomy + llm + monitoring + adapters + test_basic + test_fixes | 146 passed |
| `test_separation.py` (subset of the 450) | 52 passed, 100% cov |

## Sign-off

Feature verified against all acceptance criteria with real output. Working tree is
**not committed** — awaiting human review (root doctrine §5: commits/releases are the
human's call).
