# Code Review: Broker blocker remediation (B1–B3)

**Gate:** G4 · **Reviewer:** Code Reviewer (author-run; no independent reviewer
session is callable in this environment — recorded as a limitation, not a pass)
**ADR:** [157](../adr/157-broker-configuration-fidelity-and-fail-closed-transport.md)
· **Plan:** [maple-broker-blocker-remediation](../plans/maple-broker-blocker-remediation.md)
**Diff:** `maple/__init__.py`, `maple/agent/agent.py`, `maple/broker/broker.py`,
`maple/error/types.py`, `maple/error/__init__.py`, plus tests and docs.

## Verdict

**Pass, with two flagged items** (below) that a human should confirm rather
than a reviewer waive: a deliberately tightened test assertion, and a
behavior change that widens beyond the three blockers.

## Findings

### F-1 — MAJOR (flagged, not blocking) — a test assertion was tightened

`tests/adapters/test_s2_adapter.py::test_s2_url_triggers_s2_broker_path`
previously asserted `assertIsInstance(agent.broker, (S2Broker, MessageBroker))`.
That assertion encoded the defect: it accepted the silent in-memory fallback as
correct. It now asserts `BrokerUnavailableError` when `streamstore` is absent.

Doctrine §7.4 forbids weakening a test to go green. This is the opposite
direction — the assertion is strictly stronger — but any edit to an existing
test's expectations deserves explicit human sight, so it is recorded here
rather than folded into the diff silently.

### F-2 — MAJOR (flagged) — authorization is now live, which exceeds the three blockers

Fixing B2a means `security_config` reaches the broker, which means
`_auth_manager` is now constructed for security-configured agents. It was
previously always `None` — pinned by the import-time agent — so
`authorize_message()` never ran at all.

`AuthorizationManager.authorize_message` checks **both** sender and receiver
roles ([authorization.py:412](../../maple/security/authorization.py#L412)).
Roles are assigned in `subscribe()`, which `Agent.start()` calls. Consequence:
a security-configured agent can no longer send to a peer that has never
started.

This is the designed behavior of a component that was dead code, not a new
policy I invented. It is the correct direction (a configured control now
runs). But it is a real behavior change beyond "fix three blockers," so it is
called out in the changelog under Breaking changes and pinned by
`test_secure_send_to_unsubscribed_receiver_is_denied`, which exists purely to
make the behavior explicit rather than incidental.

**Human decision available:** if this breadth is unwanted, the narrower option
is to adopt `security_config` and `link_manager` but leave `_auth_manager`
alone. I did not take it, because selectively skipping one security component
is how the original defect was born.

### F-3 — MINOR — resolved during review: re-indented code was untested

The fail-closed fix un-nests ~40 lines of link logic from under
`if self.link_manager:`. Coverage after the first test pass showed lines
271–278 and 287–294 — link reuse and link validation — still dark. A purely
structural change to untested code is exactly the risk that produced these
blockers.

Resolved by adding `test_existing_link_is_reused_for_an_unlinked_message` and
`test_invalid_link_id_is_rejected`. The enforcement block (246–294) is now
fully covered by the new test file alone.

### F-5 — MAJOR (pre-existing, fixed) — order-dependent test leaked module state

The first full-suite run surfaced a failure that did not reproduce in
isolation: `test_url_without_driver_raises_broker_unavailable[s2://...]`
passed alone and failed in the full suite.

Root cause is a pre-existing leak in `tests/adapters/test_s2_adapter.py`.
`_make_broker` and `_make_backend` call `importlib.reload(s2_adapter)` *inside*
`patch.dict('sys.modules', {'streamstore': MagicMock()})`. The reload
re-executes the module's import guard with the mock present, setting
`S2_AVAILABLE = True`. `patch.dict` restores `sys.modules` on exit but not the
module it already reloaded, so the flag stayed `True` for the remainder of the
session. `S2Broker.__init__` then constructed successfully with no SDK
installed, and the factory returned `Ok` where it should have returned `Err`.

`skills/testing.md` names this exactly: "Don't share mutable state between
tests; order-dependence is a bug." Fixed with `self.addCleanup(
_restore_s2_adapter)` on both helpers, which reloads the module once the mock
is out of `sys.modules`.

Two related corrections in the same pass:

- My own B3 tests took their skip-precondition from an `import` probe, which
  could disagree with the code path under test. They now derive it from
  `ProductionBrokerManager.create_broker` itself — the same source of truth —
  so ambient state cannot desync precondition from assertion.
- My rewrite of `test_s2_url_triggers_s2_broker_path` initially branched on
  whether `S2Broker` was importable. That is the wrong signal: the module
  imports cleanly without the SDK and only the constructor refuses. It now
  branches on `S2_AVAILABLE`.

Verified by running `tests/adapters tests/broker` in both orders: 150 passed,
1 skipped, each way.

### F-4 — NIT — `__all__` added to `broker.py`

Introduced alongside the `SecurityError` re-export so the re-exported name is
explicitly public rather than an incidental import. Verified no wildcard
imports of this module exist and `MessageBroker` is the only other top-level
name, so nothing is hidden by it.

## Checks performed

| Check | Result |
|---|---|
| `mypy maple/ --ignore-missing-imports` | Success, 103 files |
| `flake8` (with `F401,F811,F841` **not** suppressed) | 0 |
| `black --check` / `isort --check-only` | clean, 104 files |
| `bandit -r maple/ -ll` | no MEDIUM/HIGH |
| `compileall` | clean |
| New tests in isolation | 22 passed |
| `broker.py` coverage (broker+security+agent suites) | 78% → 83%; the 216–252 dead zone is gone |

## Scope discipline

Out-of-scope items from the analysis were **not** touched: core-primitive
coverage, the dead `maple/monitoring/` package, CI consolidation, the
`CI Summary` gate hole, `example/` vs `examples/`.

One supporting change was made beyond the three blockers — unifying the
duplicate `SecurityError` — justified because B2b makes that exception
load-bearing for a security guarantee, and a control the caller cannot catch
is not a usable control. Both historical import paths still resolve.

`website/README.md` appears modified in the working tree. It is **not** part of
this change; it was already modified before this work began and must be
excluded from the commit.

## Reviewer limitation

This review was performed by the same session that wrote the code. The
adversarial value of a fresh-context reviewer is absent. The live probes and
coverage deltas are real, but a genuinely independent G4 pass has not occurred.
