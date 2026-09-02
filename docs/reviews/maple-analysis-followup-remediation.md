# Code Review: Analysis follow-up remediation (MAJOR + MINOR findings)

**Gate:** G4 · **Reviewer:** Code Reviewer (author-run; no independent
fresh-context reviewer is callable in this environment)
**ADR:** [158](../adr/158-module-boundaries-public-surface-and-one-ci-gate.md)
· Follows [ADR-157](../adr/157-broker-configuration-fidelity-and-fail-closed-transport.md)
**Scope:** every MAJOR and MINOR finding from the 2026-08-31 repository
analysis that was deferred out of the blocker fix.

## Verdict

**Pass, with three flagged items** for human confirmation: two deletions and
one changed exception type.

## What changed, and why each is defensible

| Finding | Change | Why not the alternative |
|---|---|---|
| M1 duplicate CI | `test.yml`, `quality.yml` deleted; their unique checks folded into `ci.yml` | Verified `test.yml`'s 8 matrix combos are a strict subset of `ci.yml`'s 9. Nothing lost. |
| M2 unfailable gate | Explicit failure step on the summary job | It runs `if: always()` by design (the table must print on failure); the gate is the fix, not removing `always()`. |
| M3 dead `monitoring/` | Renamed to `ComponentHealth*`, exported, old names aliased | Deleting would discard 200 lines of passing tests for functionality the README advertises. |
| M5 import cycles | `TYPE_CHECKING` for annotation-only `Config`; `execution.py` relocated to `core/` with a shim | Relocating `Config` instead would be a far larger refactor for an edge that costs nothing to guard. |
| `unwrap()` bare `Exception` | `UnwrapError(Exception)` with `.value` | Subclassing keeps every `except Exception` working; only exact-type matching breaks. |
| flake8 suppressions | `F401/F811/F841` un-suppressed | Verified the tree is clean without them, so this is enforcement of an existing property, not new debt. |
| Flaky loopback timeout | 2s → named `_REQUEST_TIMEOUT_SECONDS = 30` | The value bounds a hang; a healthy request returns in milliseconds. |
| Marketing docstrings | Removed from `message.py`, `result.py`, `types.py` | Unverifiable claims in source the analysis flagged; README was already scrubbed. |
| README test count | 1,912 → 1,936 | It is presented as the release gate figure. |
| CHANGELOG headings | Normalized to `## [version]` | Content untouched; recorded dates preserved verbatim. |
| `example/` vs `examples/` | Merged | Links updated; no tracked reference to the old path remains. |

## Findings

### F-1 — MAJOR (flagged) — two workflows deleted

`test.yml` and `quality.yml` are gone. I verified by enumeration that
`test.yml` contributes no matrix combination `ci.yml` lacks, and that every
distinct check in `quality.yml` (black, isort, license headers, README
sections) now runs in `ci.yml`. Four contract tests in
`tests/test_ci_workflows.py` assert those checks are present so they cannot be
dropped silently.

**Requires human confirmation** if any branch-protection rule currently names
`Code Quality` or the `test.yml` job as a required status check — those rules
must be repointed at `CI Summary`, which can now actually fail. I cannot read
branch protection from the repository.

### F-2 — MAJOR (flagged) — four tracked files deleted

`fix_formatting.py`, `format_all_files.py`, `formatting_status.py`,
`commit_formatting_fixes.py` removed from the repository root.
`fix_formatting.py` wrapped `black`/`isort`; `formatting_status.py` only
printed a cheat sheet; `commit_formatting_fixes.py` wrapped `git add`/
`git commit`. `format_all_files.py` (251 lines) was a regex-based partial
reimplementation of black whose own comments admit it diverges from it —
running it would produce a diff the real formatter in CI then rejects.
`ci.yml` now runs `black --check` and `isort --check-only` directly.

**Correction:** an earlier draft of this review justified the removal as
"superseded by the Makefile and CI". The Makefile has no format target
(`test`, `lint`, `ruff`, `verify` only) — that half of the claim was
asserted without checking. CI is the supersession; the Makefile is not.

Recoverable from git history. Flagged because deleting tracked files is the
user's call, not a reviewer's.

### F-3 — MAJOR (flagged) — `unwrap()` raises a different type

`UnwrapError` subclasses `Exception`, so `except Exception` is unaffected —
verified by a test. Code matching the exact type `Exception` would break. This
is the project's most-used method, so the change is called out prominently
rather than buried.

### F-4 — MINOR (resolved during review) — my cycle checker was wrong twice

My first checker reported `agent ↔ security` as a cycle. It was walking into
function bodies, and that import is function-local — it cannot form an import
cycle. The second version excluded `TYPE_CHECKING` but still counted nested
imports, and reported `agent ↔ broker` as unfixed after I had fixed
`broker.py`; the real remaining edge was in `nats_broker.py`, which I had
missed.

Corrected to count **module-level imports only**. The finding stands as a
caution: a measurement that is nearly right will send you to the wrong file.
Both real cycles are now closed and the checker reports `none`.

### F-6 — MAJOR (fixed, human-approved) — a correct fix woke a wrong check

The changelog heading normalization made `doctrine_lint.py::check_version`
start comparing MAPLE's product version (2.0.0) against the Engineering
Doctrine framework version (0.6.12). The full suite went red on
`tests/test_doctrine_lint.py::TestCorpusClean::test_current_corpus_passes`.

This was escalated rather than patched over, because both available quick
fixes were wrong: reverting the heading format would have restored a real
formatting defect to keep a broken check asleep, and silently loosening the
check is precisely what §5 forbids. Fixed on approval by scoping product-owned
carriers to the doctrine's source repo (ADR-158).

Note the pre-existing test `TestVersionSync::test_desync_caught` built its
temp repo *without* the source-repo marker, so it would have started passing
vacuously. It was rewritten to mark the repo explicitly, preserving its intent,
and two tests were added for the consumer and doctrine-owned cases.

### F-5 — MINOR — `tools/doctrine_*.py` are not black-clean

Pre-existing and untouched. CI gates `black --check maple/`, not `tools/`, so
this is not a regression and not in scope here. My two new tools scripts are
formatted. Worth a future decision on whether `tools/` should be gated.

## Checks

| Check | Result |
|---|---|
| `mypy maple/ --ignore-missing-imports` | Success, **104** source files |
| `flake8` as CI now runs it (no `F401/F811/F841` suppression) | `0` |
| `black --check maple/` / `isort --check-only maple/` | clean, 104 files |
| `bandit -r maple/ -ll` | no MEDIUM/HIGH |
| Module-level import cycles | **none** (was 2 real) |
| `tools/check_license_headers.py` | All 104 files pass |
| `tools/check_readme_sections.py` | All 5 sections present |
| `maple/core/result.py` coverage | 68% → **100%** |

## Scope

Two findings were deliberately **not** actioned:

- **M4 governance coverage.** ADR-157 and ADR-158 establish the pattern for the
  1.x core, but manufacturing retrospective ADRs for modules I did not change
  would be paperwork, not governance. Remains open.
- **270-entry `__all__`.** Now 275. Reducing the public surface of a tagged
  2.0.0 is a breaking change and a product decision, not a defect fix. Flagged
  in the analysis; still the human's call.
