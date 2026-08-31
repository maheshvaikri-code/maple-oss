# MAPLE 2.0.0 Blind Code Review

**Review lane:** Code Reviewer
**Review mode:** Serial blind author-run review; no independent reviewer session is callable in this environment
**Target:** `a5182521370ede3e5a157281b2a37ea2e1133198` (`feat/maple-agent-runtime`)
**Baseline:** `origin/main`
**Review inputs:** [release brief](../brief.md), [publication plan](../plans/maple-publication-website-cloud-registry.md), and `origin/main...HEAD` only
**Website/cloud/registry scope:** Website remains in standing; no deployment, cloud, registry, merge, tag, or publication action was performed.

## Verdict

**CHANGES REQUESTED.** The implementation has broad passing regression coverage, but the advertised Python compatibility contract is false on Python 3.8. Public release metadata and executable demos also contain stale production claims. This lane does not grant release sign-off.

## Findings

### CR-001 — MAJOR — Python 3.8 support is advertised but the package cannot import

**Location:** `pyproject.toml:34-45`; `maple/core/result.py:111`; `maple/resources/manager.py:232`; `maple/security/authentication.py:121`

`pyproject.toml` declares `requires-python = ">=3.8"` and advertises Python 3.8. The runtime uses built-in generic annotations such as `dict[str, Any]`, `tuple[...]`, and `set[str]` without postponed annotation evaluation. Python 3.8 raises during class definition before `import maple` completes.

**Observed evidence:**

```text
TypeError: 'type' object is not subscriptable
... maple/core/result.py, line 111, in Result
    def to_dict(self) -> dict[str, Any]:
python38_import_exit=1
```

The CI matrix begins at Python 3.9, so this contract failure is not covered by the hosted matrix.

**Required action:** Either restore Python 3.8 compatibility with postponed annotations/`typing` aliases and an actual Python 3.8 test job, or raise `requires-python` and remove the Python 3.8 classifier and documentation claims. Add a regression test for the selected contract.

### CR-002 — MINOR — Release metadata says Production/Stable while the release plan says candidate

**Location:** `pyproject.toml:29`; [publication plan](../plans/maple-publication-website-cloud-registry.md)

The package classifier is `Development Status :: 5 - Production/Stable`, while the release plan records an unpublished candidate with website, cloud, registry, approval, and protected-branch gates still outstanding. The public package metadata should match the actual release state.

**Required action:** Select an accurate classifier and update it only when the human-controlled publication gates are complete.

### CR-003 — MINOR — Executable demo output contradicts the reconciled 2.0.0 documentation

**Locations:** `demo_package/launch_demos.py:247-260`; `demo_package/complete_experience.py:288,467,519,528`; `demo_package/quick_demo.py:187,206`; `demo_package/maple_demo.py:1230-1251`

The launcher still prints `Production Ready v1.1.1`, `25-100x` competitor claims, “only protocol” claims, “proven performance,” and “enterprise-grade security.” The checked-in README work correctly narrows claims, but executable public demos remain stale and unsupported.

**Required action:** Make demo output version-aware, label simulated/illustrative benchmarks, and remove absolute comparative/security claims unless reproducible evidence is shipped with the demo.

### CR-004 — MINOR — Added documentation does not pass `git diff --check`

**Evidence:** `git diff --check origin/main...HEAD` reports trailing whitespace and blank-at-EOF findings across newly added ADR, QA, and review Markdown files. Some trailing spaces are Markdown hard breaks, but the branch does not satisfy a clean diff check.

**Required action:** Normalize intentional hard breaks or configure/document the accepted Markdown convention, then make the repository diff clean.

## Positive verification

- Targeted contract/release/CLI/Doctrine tests: `38 passed in 107.76s`.
- Hosted final checks for `a518252`: CI, Tests, Code Quality, and Security Scan all succeeded.
- Package build and `twine check` passed for both sdist and wheel.
- CLI doctor reported `version: 2.0.0`, `ready: true`, and `network: false`.

## Disposition

CR-001 through CR-003 remain open. CR-004 is a hygiene follow-up. Return to the builder before release sign-off.
