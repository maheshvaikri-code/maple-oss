# QA Report: Production hardening and transport security capability

**Gate:** G5 · **Roles:** QA Engineer + Security Reviewer (author-run; see
limitation) · **ADRs:** [159](../adr/159-backpressure-observable-delivery-and-a-race-free-delivery-path.md),
[161](../adr/161-broker-contract-and-the-path-to-multi-host.md) (tactical part)
**Follows:** [ADR-157 QA](maple-broker-blocker-remediation.md),
[ADR-158 QA](maple-analysis-followup-remediation.md)

## Disposition

**Pass.** Four transport defects and one transport-security gap are closed,
each verified by a probe against the running system. Two further ADRs (160,
161) are recorded as design only and are explicitly **not** implemented.

## Full suite

```text
================ 1983 passed, 1 skipped in 3064.69s (0:51:04) =================
```

That run covers ADR-159. The transport-security work (11 tests) landed after
it; its full-suite result is recorded at the end of this document.

Progression across the whole engagement:

| Point | Result |
|---|---|
| Baseline, before any change | 1914 passed |
| After ADR-157 (blockers) | 1936 passed |
| After ADR-158 (follow-ups) | 1966 passed |
| After ADR-159 (hardening) | **1983 passed** |
| After ADR-161 tactical fix | +11 tests |

**+80 tests, all additions.** No test was deleted, skipped, or weakened.

## ADR-159 — measured before and after

The defect, with a stalled consumer and 25,000 sends:

```text
before   accepted 25000   bounded queue 10000   unbounded list 15000
after    accepted 10000   refused 15000        unbounded list     0
```

| Fix | Verification |
|---|---|
| Backpressure | `QUEUE_FULL` with `maxQueueSize` in `details`; nothing accumulates in the fallback |
| Undeliverable accounting | counter, per-receiver WARNING, dead-letter hook all fire |
| Race-free dispatch | handlers snapshotted under the lock, invoked outside it |
| Message size bound | `MESSAGE_TOO_LARGE` with `payloadBytes` and the limit |

17 regression tests in `tests/broker/test_broker_backpressure.py`.

### Two implementation defects caught during the build

Recorded because both were mine and both were caught by verification rather
than review:

1. **The config knob did nothing.** `max_queue_size` was wired only to the
   fallback list while `MessageQueue` stayed hardcoded at 10,000. A probe with
   `max_queue_size=5` accepted 20 messages and refused none. Fixed by passing
   the limit to the queue that actually holds messages.
2. **A docstring contradicted its code.** The size guard claimed non-JSON
   payloads pass through unmeasured; `default=str` meant they were measured.
   A test asserted the docstring and failed. The docstring was wrong, not the
   behavior — corrected, and the test now pins the real contract.

## ADR-161 tactical — transport security capability

**The gap.** `Agent(Config(broker_url="nats://...", security=...))` constructed
successfully while `NATSBroker` enforced **none** of `SecurityConfig`. Verified
by inspection: no reference to `security`, `separation`, `link` or
`require_links` anywhere in `maple/broker/nats_broker.py`; its `send()`
publishes straight to NATS.

This is the fail-open shape ADR-157 removed from the in-memory broker, one
level up — and it is live in the 2.0.0 published to PyPI.

**The fix.** Brokers declare `ENFORCES_SECURITY_POLICY`. When a config requests
`separation_policy`, `require_links` or `strict_link_policy` and the chosen
transport does not declare enforcement, construction raises
`BrokerUnavailableError` with `BROKER_CANNOT_ENFORCE_SECURITY` naming every
unenforced control. A transport that declares nothing is treated as
non-enforcing — absence is not a claim.

11 tests in `tests/broker/test_transport_security_capability.py`, including
that the in-memory path is unaffected and that a silent transport is refused.

**This is a mitigation, not the fix.** The real fix is the broker `Protocol`
and conformance suite in ADR-161, which is not implemented.

## Quality gates

| Gate | Result |
|---|---|
| `mypy maple/ --ignore-missing-imports` | Success, 104 source files |
| `flake8 maple/` as CI runs it (no `F401/F811/F841` suppression) | `0` |
| `black --check maple/` / `isort --check-only maple/` | clean, 104 files |
| `bandit -r maple/ -ll` | no MEDIUM/HIGH |
| `python tools/doctrine_lint.py .` | corpus clean |
| `make format` (new) | runs black + isort on `maple/` |

Three pre-existing `E501` warnings remain in `tests/broker/test_broker.py`,
`test_broker_enhanced.py` and `test_routing.py`. None are in files touched
here, and CI gates `maple/` only. Left alone rather than swept into an
unrelated change.

## Release preparation

- `VERSION` and `__version__` to **2.1.0**; README badge updated.
- README release status corrected. It claimed *"PyPI publication remains
  pending; no PyPI upload has been performed"*. `maple_oss-2.0.0` was uploaded
  to PyPI on 2026-08-31 at 06:05 UTC, verified against the PyPI JSON API.
- `make format` added; the Makefile previously had no formatting target.

**2.1.0 carries behavior-breaking fixes.** They correct controls that silently
did nothing rather than imposing new restrictions, but code relying on the old
behavior will observe changes. Recorded in the changelog under each ADR's
Breaking changes section. The choice of 2.1.0 over 3.0.0 is the human's,
reserving the major version for a feature milestone.

## Not implemented, by design

- **ADR-160 (`AgentScope`)** — status `proposed`. Covers the three
  process-global runtime singletons and the lifetime model.
- **ADR-161 (broker `Protocol` + conformance suite)** — status `proposed`.
  Only the tactical security-capability guard from it is implemented.

Both are design records. Neither should be read as shipped.

## Limitation

QA and security review were performed by the session that wrote the code. No
independent fresh-context verifier is callable in this environment. Every
measurement, suite result and gate output quoted here is real; adversarial
independence is not present.
