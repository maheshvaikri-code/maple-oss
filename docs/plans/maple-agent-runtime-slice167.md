# Implementation Plan - Authenticated Remote Handoff Payload Delivery

**Brief:** [Slice167 brief](../briefs/maple-agent-runtime-slice167.md)
**Design/ADRs:** [ADR-112](../adr/112-remote-handoff-payload-delivery.md)
**Class:** L

## Slices (ordered; each leaves the tree green)

| # | Slice | Role | Files touched | Proven by (tests) | Status |
|---|---|---|---|---|---|
| 1 | Add `RemoteHandoffTarget` and handoff correlation keyword plumbing | Backend / Interop | `maple/autonomy/server.py`, `maple/autonomy/tools.py`, exports | Remote target validation and local-target compatibility tests | done: `aa27498`; formatting `fa16c9f` |
| 2 | Exercise authenticated sync/async delivery and failure boundaries | QA / Security | `tests/autonomy/test_server.py`, `tests/autonomy/test_tools.py` | Local server/client integration, cancellation, malformed output, auth, and transport tests | done: focused `83 passed in 19.39s`; tracked `1521 passed, 1 skipped` |
| 3 | Document public API and parity/release status | Tech Writer | `README.md`, `docs/api-reference.md`, `docs/agent-framework-parity.md`, `CHANGELOG.md` | Runnable example plus documentation and export checks | done: `73af546` |
| 4 | Review, QA, security, package, and release evidence | Code Reviewer / Security / QA / Release | `docs/reviews/`, `docs/qa/`, release plan | Focused, tracked, lint/type/compile, secret/danger, archive, Twine, and isolated import gates | done: review/QA filed; clean archive gate passed |

## Threat sketch (required for Class L)

Assets touched: bearer token, task/context payload, remote agent result, and
local handoff ownership/result state. Entry points / untrusted inputs: target
agent ID, task/context/session/run values, remote JSON, HTTP status/body, and
cancellation callbacks. Worst plausible abuse: an authorized caller routes a
large or malicious payload to an unintended agent, leaks remote exception data,
or repeats a side-effecting remote handler after a transport crash.

## Risks & rollback points

- Risk: remote output or handler errors cross the boundary unchecked ->
  mitigation: reuse `RunClient` response bounds and `AgentRun` normalization,
  require `completed`, and return typed generic errors -> rollback: remove the
  adapter/export; existing local handoffs remain intact.
- Risk: adding a keyword breaks custom local targets -> mitigation: pass the
  optional keyword only to signature-compatible callables -> rollback: revert
  correlation plumbing without changing the target contract.
- Risk: callers infer exactly-once behavior from deterministic run IDs ->
  mitigation: document no retry/deduplication guarantee and test duplicate
  calls as possible -> rollback: retain current manual remote invocation.

## Deviation log (append-only, as they happen)

- None.

## Status snapshot (update at session end / handoff)

Done (with evidence): implementation, regressions, public documentation, code
review, QA/security, and clean-archive package gate. Next: select the next
highest-value parity gap, with remote durable resume/routing, scheduling, push
delivery, identity federation, and exactly-once policy still separate.
Blocked on: publication authorization remains closed by repository governance.
