# ADR-158: Module boundaries, public surface, and a single CI gate

**Date:** 2026-08-31
**Status:** accepted
**Deciders:** Chief Architect

## Context

The 2026-08-31 full-repository analysis raised, alongside the three blockers
closed in [ADR-157](157-broker-configuration-fidelity-and-fail-closed-transport.md),
a set of MAJOR and MINOR findings. They are unrelated in surface but share a
shape: **the repository asserted things it did not enforce.**

- Two module-level import cycles: `agent ↔ broker` and
  `autonomy ↔ task_management`. Both worked only by accident of import order.
- `maple/monitoring/` was unreachable — no module in `maple/` imported it and
  it was absent from `__all__` — while shipping in the wheel with 200 lines of
  passing tests. Its `HealthMonitor` / `HealthMetrics` names collided with
  `maple/discovery/health_monitor.py`, which does an unrelated job.
- The `CI Summary` job ran `if: always()` and only echoed results. Branch
  protection requiring it would pass over a red build.
- `test.yml` and `quality.yml` fired on the same triggers as `ci.yml` and
  re-ran the same matrix — every push paid for the ~28-minute suite twice.
- CI's flake8 suppressed `F401`, `F811`, and `F841` — real defect detectors —
  although the tree is clean without them.
- `Result.unwrap()` raised bare `Exception`, which callers cannot catch
  selectively. This is the project's central abstraction.
- `tests/autonomy/test_server.py` used a 2-second timeout against a loopback
  server, tight enough to flake under load with coverage tracing.

## Decision

### Module boundaries: cycles broken, not documented

`Config` was imported at runtime by `broker/broker.py` and
`broker/nats_broker.py` but used **only in annotations**. Both now import it
under `TYPE_CHECKING` with `from __future__ import annotations`. The remaining
`agent → broker` edge is one-directional.

`autonomy/execution.py` was a leaf depending only on `core.result`, yet
`task_management/worker.py` had to import *upward* into `autonomy` to reach it.
The implementation moves to `maple/core/execution.py`;
`maple/autonomy/execution.py` remains as a re-export shim so all ten existing
import sites and the published `from maple import ...` path are unchanged.

Measured with a checker that counts **module-level imports only** — function-local
imports and `TYPE_CHECKING` blocks cannot form an import cycle. The earlier
`agent ↔ security` "cycle" was a false positive of that kind.

### Public surface: name it or delete it

`maple/monitoring/` is real, tested, useful code — per-component self-metrics
(CPU, memory, throughput, errors), genuinely distinct from `discovery`'s
registry-heartbeat monitor. Deleting it would discard working functionality;
leaving it unwired kept dead weight in the wheel.

Its classes are renamed `ComponentHealthMonitor` / `ComponentHealthMetrics`,
exported from the package root, and the old names kept as module-level aliases
(the deep-import path was reachable, so removing them would be a silent break).

### Errors: a catchable failure for the central abstraction

`unwrap()` / `unwrap_err()` raise `UnwrapError`, which subclasses `Exception`
so existing broad handlers keep working, and carries the wrapped value on
`.value` so a handler can inspect what it failed to unwrap. This is a caller
contract violation in the taxonomy of `standards/error-handling.md`, not a
domain failure, and it should be distinguishable as such.

### CI: one gate, and it can fail

`quality.yml`'s unique checks (black, isort, license headers, README sections)
fold into `ci.yml`'s lint job; the two inline `python -c` blocks become
`tools/check_license_headers.py` and `tools/check_readme_sections.py`, which
can be linted, typechecked, and run locally. `test.yml` and `quality.yml` are
deleted — verified that `test.yml`'s eight matrix combinations are a subset of
`ci.yml`'s nine.

The summary job gains an explicit failure step. `F401`/`F811`/`F841` are no
longer suppressed.

Four contract tests in `tests/test_ci_workflows.py` lock all of this in, so the
gate hole and the suppressions cannot silently return.

### Governance tooling: presence is not ownership

Normalizing the changelog headings woke a dormant check.
`tools/doctrine_lint.py::check_version` matched `^## \[(\d+\.\d+\.\d+)\]`,
which MAPLE's old `## 2.0.0 - ...` headings never matched. Once they did, it
reported:

```text
version desync: .Doctrine.md v0.6.12 != CHANGELOG 2.0.0
```

That compares the **Engineering Doctrine framework version** against **MAPLE's
product version** — unrelated artifacts that will never share a number.

The check's intent is sound; its scoping was not. It gated on whether a
carrier *exists* ("only when the repo keeps one (consumers may not yet)")
rather than on who *owns* it. MAPLE has a CHANGELOG; it simply is not the
doctrine's changelog. All three product-owned carriers were dormant here only
by format accident: `pyproject.toml` uses `dynamic = ["version"]` (no literal
`version = "x.y.z"`), and the README badge is `version-2.0.0` without the `v`
prefix the pattern requires.

Carriers are now split by ownership:

- **Doctrine-owned** (`plugin/.claude-plugin/plugin.json`,
  `tools/doctrine_mcp.py`) ship *with* the doctrine and are checked in every
  repo that has them. `doctrine_mcp.py` is `0.6.12` here and still enforced.
- **Product-owned** (`CHANGELOG.md`, `pyproject.toml`, README badge) are
  checked only in the doctrine's own repo, detected with the same signal
  `check_plugin_parity` already uses — the plugin ships from the source repo
  only.

Changed with explicit human approval (§5: disabling or altering a failing
check is an escalation). Three tests in `tests/test_doctrine_lint.py` pin it:
desync still caught in a source repo, not compared in a consumer repo, and
doctrine-owned carriers still compared everywhere.

## Alternatives considered

| Option | Decision | Reason |
|---|---|---|
| Delete `maple/monitoring/` | Rejected | Discards working, tested functionality that the README already advertises. The defect was that it was unwired and ambiguously named, not that it was worthless. |
| Keep monitoring's names, export as-is | Rejected | Two different `HealthMonitor` classes in one package is a trap for the reader; the ambiguity was itself a finding. |
| Break the cycle by relocating `Config` to `core` | Rejected | A far larger refactor with re-export shims across the package, to fix an edge that is annotation-only and costs nothing to guard. |
| Break `autonomy ↔ task_management` with a function-local import | Rejected | The codebase already leans on that trick; it hides the dependency rather than removing it. Relocating the leaf is honest and the shim keeps compatibility. |
| Make `unwrap` return instead of raise | Rejected | Changes the contract of the project's most-used method. The defect was the *type* raised, not that it raises. |
| Keep `test.yml` for redundancy | Rejected | It is not redundancy, it is duplication: same triggers, subset matrix, no combination `ci.yml` lacks. |
| Rewrite the 1,461-line 2.0.0 changelog entry | Rejected | High risk, low value. Only the heading convention is normalized; recorded dates are preserved verbatim rather than inventing day precision the older entries never had. |

## Consequences

Positive: no module-level import cycles remain; the wheel ships no unreachable
package; `unwrap` failures are catchable; one CI workflow is the gate and it
can actually fail; `core/result.py` goes from 68% to 100% coverage.

Negative — **behavior and layout changes callers may notice**:

- `maple.autonomy.execution` is now a shim. Anything reaching into its module
  internals rather than importing its four public names would break.
- `maple.monitoring.health_monitor.HealthMonitor` still resolves, but the
  canonical name is `ComponentHealthMonitor`.
- `unwrap()` raises `UnwrapError` rather than `Exception`. Code doing
  `except Exception` is unaffected; code matching on the exact type `Exception`
  is not.
- `example/` is merged into `examples/`; `example/helloworld.py` moved to
  `examples/helloworld.py`.
- Four one-off formatting scripts were removed from the repository root.
  Two wrapped `black`/`isort`, one only printed a cheat sheet, and one
  (`format_all_files.py`, 251 lines) was a regex-based partial
  reimplementation of black — a formatter that disagreed with the formatter
  gating CI. `ci.yml` now runs `black --check` and `isort --check-only`
  directly. Note the Makefile has no format target; formatting is run
  directly or via CI.

## Invalidation triggers

Any new module-level import from `broker` into `agent`, or from
`task_management` into `autonomy`; adding a third `HealthMonitor`; adding a
workflow that duplicates `ci.yml`'s triggers and matrix; or re-suppressing
`F401`/`F811`/`F841` — each invalidates a decision here and needs a new one.
