# QA Report: Broker blocker remediation (B1–B3)

**Gate:** G5 · **Roles:** QA Engineer + Security Reviewer (author-run; see
limitation) · **ADR:** [157](../adr/157-broker-configuration-fidelity-and-fail-closed-transport.md)
**Plan:** [maple-broker-blocker-remediation](../plans/maple-broker-blocker-remediation.md)
· **Review:** [G4 report](../reviews/maple-broker-blocker-remediation.md)

## Disposition

**Pass.** All three blockers are demonstrably fixed, the full suite is green,
and no security property regressed. Two items are escalated to the human
rather than waived (§5): a widened behavior change, and a tightened test
assertion. G6 (release) is **not** entered.

## Full suite — real output

```text
================ 1936 passed, 1 skipped in 1701.88s (0:28:21) =================
```

Baseline before this work was `1914 passed, 1 skipped`. The delta is +22: the
new `tests/broker/test_broker_config_fidelity.py`.

### One intermittent failure, investigated and characterised

An earlier full run reported:

```text
FAILED tests/autonomy/test_server.py::test_agent_target_policy_filters_discovery_and_blocks_denied_routes
=========== 1 failed, 1935 passed, 1 skipped in 1709.23s (0:28:29) ============
```

Not caused by this change. Evidence:

| Check | Result |
|---|---|
| Test in isolation | passed |
| `tests/autonomy/test_server.py` ×3 under coverage | 67 passed each run |
| `tests/adapters tests/autonomy` (this change's reload cleanup runs first) | 786 passed |
| Baseline full run, before any change here | passed |
| Confirming full re-run, identical conditions | **1936 passed, 0 failed** |
| Reachability | `maple/autonomy/server.py` references none of `MessageBroker`, `maple.Agent`, `BrokerUnavailableError`, `SecurityError`, `security_config` |

**Mechanism:** `tests/autonomy/test_server.py:84` calls
`urllib.request.urlopen(request, timeout=2)` against a loopback server on a
daemon thread. Two seconds is tight under full-suite load with coverage
tracing on every line. `skills/testing.md` names this failure mode directly.

**Filed as a follow-up, not fixed here** — it is a pre-existing defect in a
test unrelated to the blockers, and the `_request` helper is shared, so
several tests in that file carry the same exposure. Fix is a longer or
load-proportional timeout.

## Blocker verification — live probes

```text
=== B2a: security config now reaches the broker ===
  broker.security_config : True
  broker.link_manager    : LinkManager

=== B2a: a later plain config must NOT clear it ===
  still enforced         : True

=== B2b: strict link policy now rejects an unlinked send ===
  send unlinked -> is_ok : False
  error                  : No valid link exists between sender and receiver

=== B2b: fail closed when the link manager is unavailable ===
  SecurityError raised   : Link enforcement is required but no link manager is
                           available; refusing to send

=== B3: transports fail fast instead of downgrading ===
  nats://prod-host:4222      -> BrokerUnavailableError: BROKER_DEPENDENCY_MISSING
                                cause preserved: NATS broker requires nats-py...
  s2://my-basin              -> BrokerUnavailableError: BROKER_DEPENDENCY_MISSING
                                cause preserved: S2 broker requires streamstore...
```

B1, separately (fresh interpreter — the only honest check):

```text
import maple OK, version 2.0.0
B1 singleton after import: None
SecurityError unified     : True
exported from root        : True BrokerUnavailableError
validate_installation()   : {'status': 'SUCCESS', 'version': '2.0.0', 'ready': True}
B1 singleton after validate: None
```

And the previously-broken shipped example now honors its config:

```text
agent.config.broker_url : localhost:8080
broker.config.broker_url: localhost:8080
OK: broker honors the configured url
```

## Security sign-off

```text
[PASS] SEC-001 default JWT secret still disabled
[PASS] SEC-003 revocation enforced on both paths
[PASS] link policy survives a later security-less config
[PASS] separation policy still adopted on re-init
[PASS] denied send enqueues nothing
[PASS] nats refusal leaves no usable agent
```

The fourth is the important regression guard: generalising
`_refresh_separation_policy` into `_refresh_security_context` did not break the
separation-of-duties guarantee that already worked.

**No new attack surface.** No new dependency, no new network path, no new
deserialization, no new credential handling. Every change either removes a
side effect, propagates an error that was being swallowed, or converts a
fail-open path to fail-closed.

## Quality gates

| Gate | Result |
|---|---|
| `mypy maple/ --ignore-missing-imports` | Success, 103 source files |
| `flake8` with `F401,F811,F841` **not** suppressed | `0` |
| `black --check` | 105 files unchanged |
| `isort --check-only maple` | clean |
| `bandit -r maple/ -ll` | no MEDIUM/HIGH |
| `compileall -q maple` | clean |

## Coverage

Overall 79% (25,704 statements), unchanged — new code and new tests in
proportion. The change is visible where it matters:

| Module | Before | After |
|---|---|---|
| `maple/broker/broker.py` | 78% (lines **216–252 entirely dead**) | **86%** |
| `maple/broker/production_broker.py` | 69% | **80%** |
| `maple/error/types.py` | 79% | 83% |
| `maple/__init__.py` | — | 92% |

Lines 216–252 were the `require_links` enforcement block — the code that
failed open. It had **zero** coverage, which is why the defect shipped. The
whole block (now 246–294) is covered by the new test file alone.

## Test isolation

`tests/adapters tests/broker` passes **150 passed, 1 skipped in both
directions**, confirming the `S2_AVAILABLE` leak documented as F-5 in the G4
review is closed.

## Escalations for the human (§5)

1. **Widened behavior.** Fixing B2a makes `AuthorizationManager` live for
   security-configured agents; it was dead code. It checks the receiver's role,
   so a secure agent cannot send to a peer that never started. Correct for a
   control the user configured, but broader than "fix three blockers." The
   narrower alternative is recorded in the ADR and G4 review.
2. **Tightened test assertion.** `test_s2_url_triggers_s2_broker_path` had
   asserted the silent fallback was acceptable. Stronger now, not weaker — but
   an edit to an existing test's expectations needs human sight.

## Limitation

QA and security review were performed by the session that wrote the code. No
independent fresh-context verifier session is callable in this environment.
The probes, suite output, and coverage deltas are real; adversarial
independence is absent.
