# QA + Security Report - MAPLE Agent Runtime Slice 117 @ 889c476

**QA Engineer · Security Reviewer · Date:** 2026-08-26  
**Build under test:** `889c476` (Slice 117 implementation and public docs;
review/QA artifacts are filed in the following release-evidence commit)

## Acceptance criteria verification

| # | Criterion | How executed | Evidence (real output) | Pass |
|---|---|---|---|---|
| 1 | Built-in stores expose explicit compaction without changing the existing `SessionStore` requirement. | Public import and store contract checks. | `10 passed in 4.88s`; `SessionCompactionStore` is exported; custom stores remain valid without a `compact` method. | Yes |
| 2 | Compaction preserves a host summary and bounded recent tail in order. | In-memory store with four messages, `keep_last=2`, and metadata inspection. | Summary plus the final two messages are retained; compaction increments the version once; `10 passed`. | Yes |
| 3 | Stale, invalid, and no-op requests fail without mutation. | Stale CAS version, over-limit tail, and empty-summary cases. | Typed `SESSION_CONFLICT`, `SESSION_COMPACTION_LIMIT`, and `SESSION_TEXT_INVALID`; original messages/version remain unchanged; `10 passed`. | Yes |
| 4 | File-backed compaction survives process/store restart. | Compact a file store, instantiate a new store, and reload the session. | Summary and retained tail reload from atomic JSON state; `10 passed`. | Yes |
| 5 | Existing autonomy behavior remains green. | Full autonomy suite. | `335 passed in 6.94s`. | Yes |
| 6 | Existing application behavior remains green. | Exact tracked test manifest; five user-owned untracked Doctrine test files excluded. | `1297 passed, 1 skipped in 228.90s (0:03:48)` across 108 tracked test files. | Yes |
| 7 | Public/runtime surfaces are documented and statically valid. | Black, Ruff, changed-boundary mypy, compile, doctor, and diff checks. | Black: `4 files would be left unchanged`; Ruff: `All checks passed!`; mypy: `Success: no issues found in 3 source files`; doctor reports `ready: true`, all eight checks true, `network: false`; compile/diff exit `0`. | Yes |
| 8 | Clean package evidence is collected before release promotion. | Clean archive build from `889c476`, package inspection, Twine checks, and isolated wheel smoke test. | `python -m build --wheel --sdist` exit `0`; Twine wheel/sdist `PASSED`; sdist `535` entries with required public files `6/6`; wheel `104` members; fresh no-dependency smoke printed `SessionCompactionStore summary`. Wheel SHA-256 `21550780b6e898d17a16e54528c02756e1d88653342087c890450afe0bb12afe`; sdist SHA-256 `a56256467416919751a6acc7a771a18311b2ae892f2860d4df997c893872577d`. No publication performed. | Yes |

## Adversarial and edge matrix

| Input/scenario | Expected | Observed | Pass |
|---|---|---|---|
| Empty session or `keep_last` that removes no messages | Typed no-op and no mutation | `SESSION_COMPACTION_NOOP` boundary; existing snapshot unchanged | Yes |
| Negative, boolean, or over-limit `keep_last` | Reject before mutation | `SESSION_COMPACTION_LIMIT` | Yes |
| Empty or oversized summary | Reject before mutation | Typed text/message-size errors; existing snapshot unchanged | Yes |
| Stale expected version | Reject compare-and-set | `SESSION_CONFLICT` | Yes |
| Summary plus recent tail exceeds store quotas | Reject through existing bounded snapshot validation | Existing message/count/byte limits remain active | Yes |
| File write/restart | Preserve only the committed compacted snapshot | Atomic file store reloads summary and tail | Yes |
| Host summary provenance | Do not invent or silently summarize | Caller supplies the summary; no LLM/provider call exists in the path | Yes |
| Sensitive retained history | Keep persistence boundary explicit | API/ADR retain host-owned access-control and retention responsibility | Yes |
| Existing custom `SessionStore` without compaction | Preserve compatibility | Compaction is a separate optional protocol | Yes |

## Regression

Focused session suite:

```text
10 passed in 4.88s
```

Full autonomy suite:

```text
335 passed in 6.94s
```

Final tracked application suite:

```text
1297 passed, 1 skipped in 228.90s (0:03:48)
```

The skip is the existing NATS dependency-gated test. No flaky retry or
retry-until-lucky behavior was used.

## Security sweep

- Precise changed-surface secret-pattern scan: `manual secret-pattern scan: no
  matches`.
- Dangerous-construct scan on the changed source/test surface:
  `session-compaction dangerous-construct scan: no matches`.
- `gitleaks`: unavailable in the environment.
- `bandit`: unavailable in the environment.
- Injection review: summaries and session messages cross the existing bounded
  JSON validation boundary; the implementation adds no shell, SQL, template,
  dynamic evaluation, pickle, or network execution path.
- Bounds/fail-closed review: count, message, metadata, and serialized-session
  limits remain active; stale, invalid, oversized, and no-op compaction calls
  do not mutate the store; file persistence remains atomic.
- Dependency review: no new runtime dependency; implementation uses existing
  session contracts and the standard library.
- Dependency audit command: `python -m pip_audit --progress-spinner off`.
  Real result: `Found 383 known vulnerabilities in 77 packages`; it exited
  `1`, and also listed local packages not auditable from PyPI. This is an
  environment/release-governance finding, not silently accepted as clean.

**Security verdict:** **VETO** for a final repository publication claim until
dependency findings are dispositioned; no new Slice 117 security defect was
found.

**QA verdict:** pass for Slice 117 behavior, boundaries, static checks,
regression coverage, and clean package evidence. Release remains conditional
on dependency-governance disposition; no publication or website change was
performed.
