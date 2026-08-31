# MAPLE 2.0.0 Blind QA Review

**Review lane:** QA Engineer
**Review mode:** Serial blind author-run review; no independent reviewer session is callable in this environment
**Target:** `a5182521370ede3e5a157281b2a37ea2e1133198`
**QA verdict:** **CONDITIONAL / NO-GO for publication**

## Executed checks

### Full regression suite

Command:

```text
python -m pytest tests/ -q --no-cov -p no:benchmark -p no:dash --tb=short --no-header
```

Result:

```text
================= 1906 passed, 1 skipped in 647.99s (0:10:47) =================
```

The skip is the expected unavailable external NATS integration. No test failures occurred.

### Focused high-risk suite

Server, execution, sessions, serialization, authentication, and authorization tests:

```text
============================ 195 passed in 32.64s =============================
```

### Runtime/build smoke

- `compileall`: passed.
- `maple doctor --json`: `status: SUCCESS`, `ready: true`, `version: 2.0.0`, `network: false`.
- sdist and wheel build: passed.
- `twine check` for both artifacts: passed.

### Adversarial contract checks

- Python 3.8 import: **failed** at `maple/core/result.py:111` with `TypeError: 'type' object is not subscriptable`, despite the package declaring Python 3.8 support.
- Forged JWT using the hard-coded default signing key: accepted with attacker/admin claims.
- Revoked JWT through the `authenticate()` path: accepted after revocation.
- MessagePack payload above 1 MiB: accepted by the public serializer path.
- A semicolon-bearing `v*` Git tag passes `git check-ref-format`, relevant to the unquoted release-asset shell command.

## Coverage assessment

Core, autonomy, adapters, brokers, communication, discovery, LLM contracts, resources, security, state, task management, CLI, packaging, and Doctrine tests are green locally. The suite does not cover the Python 3.8 import contract, default-secret rejection, JWT revocation through both entry points, serializer-level MessagePack limits, or malicious release-tag workflow evaluation.

## Disposition

The implementation is regression-green on the tested Python 3.12 environment, but QA cannot mark the 2.0.0 publication candidate ready while the advertised compatibility contract and security findings remain open. Website standing was preserved; no website, cloud, or external registry action was performed.
