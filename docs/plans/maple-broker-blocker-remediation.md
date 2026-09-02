# Plan: Broker blocker remediation (B1–B3)

**Class:** L · **ADR:** [157](../adr/157-broker-configuration-fidelity-and-fail-closed-transport.md)
**Source brief:** full-repository analysis of 2.0.0, 2026-08-31
**Owner:** Chief Architect → Backend Engineer

## Scope

Four code changes plus their regression tests. No refactor of the singleton,
no unrelated cleanup, no release.

| # | Defect | File | Change |
|---|---|---|---|
| 1 | Import-time seeding of the broker singleton | `maple/__init__.py` | Delete the auto-`validate_installation()` block; make the function side-effect-free |
| 2 | `SecurityConfig` discarded on re-init | `maple/broker/broker.py` | `_refresh_security_context()` adopts security block, link manager, auth manager |
| 3 | `require_links` fails open | `maple/broker/broker.py` | Un-nest the check; raise `SecurityError` when policy is unenforceable |
| 4 | Transport silently downgrades | `maple/agent/agent.py` | Raise `BrokerUnavailableError` carrying the typed error |
| 5 | `SecurityError` defined twice (supports #3) | `maple/broker/broker.py`, `maple/__init__.py` | Single definition, exported from package root |

## Implementation order

Deliberately sequenced so each step is independently verifiable:

1. **#1 first.** Until the import-time agent is gone, no test of #2 can be
   trusted — the singleton is already poisoned before the test starts.
2. **#5** next: #3 needs one catchable `SecurityError`.
3. **#2 and #3** together: both live in `MessageBroker`, and #3's fail-closed
   guard is only reachable once #2 can adopt a security config.
4. **#4** last: independent of the others, in a different module.

## Tests to add (`tests/broker/test_broker_config_fidelity.py`)

Failure paths first, per `skills/testing.md`.

- `test_import_maple_does_not_construct_broker_singleton` — after a fresh
  interpreter `import maple`, `MessageBroker._instance is None`.
- `test_validate_installation_has_no_broker_side_effect` — calling it leaves
  `_instance` untouched.
- `test_security_config_adopted_by_initialized_singleton` — second agent's
  `SecurityConfig` reaches `broker.security_config`.
- `test_security_config_not_cleared_by_later_plain_config` — the never-clear
  invariant.
- `test_link_manager_built_when_security_adopted`.
- `test_require_links_without_link_manager_raises` — the fail-closed guard.
- `test_strict_link_policy_rejects_unlinked_send` — the original B2 probe,
  as a test.
- `test_nats_url_without_driver_raises_broker_unavailable` — B3.
- `test_s2_url_without_driver_raises_broker_unavailable` — B3.
- `test_broker_unavailable_error_carries_typed_cause` — the error is not lost.

Each test resets the singleton before and after (`_instance`, and the five
class-level dicts) following the established `_reset_broker_singleton` pattern
in `tests/broker/test_broker.py`.

## Test to update, not delete

`tests/adapters/test_s2_adapter.py::TestAgentS2URLDetection` currently asserts
the fallback this plan removes. It is rewritten to assert the fail-fast
contract. Flagged explicitly at G4 — a changed assertion needs a reviewer's eye,
and doctrine §7.4 forbids weakening a test to go green. This is the opposite:
the assertion becomes stricter.

## Docs to update

- `CHANGELOG.md` — Unreleased, with a **Breaking changes** subsection.
- `docs/getting-started.md` and `docs/best-practices.md` — the `require_links`
  examples now describe a control that actually enforces.
- `README.md` — note the fail-fast transport contract.

## Verification

- Full suite (~21 min), real output pasted into the QA record.
- `mypy maple/`, `flake8`, `black --check`, `isort --check-only`, `bandit -ll`.
- Re-run the three original analysis probes; all must now show the fixed
  behavior.
- Coverage on `maple/broker/broker.py` must rise (the 216–252 dead zone).

## Explicitly out of scope

Core-primitive coverage (`result.py` 68%, `message.py` 59%), the dead
`maple/monitoring/` package, CI workflow consolidation, the `CI Summary` gate
hole, `example/` vs `examples/`. All filed in the analysis; none are blockers.

## Assumption on record

`tests/comprehensive_test_suite.py` is not collected by pytest (`python_files =
["test_*.py"]` does not match it), so its `nats://` config block cannot be
affected. Verified with `--collect-only`: "no tests collected".
