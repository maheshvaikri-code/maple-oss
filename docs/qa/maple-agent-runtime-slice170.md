# QA + Security Report - bounded agent capability discovery and routing

**QA Engineer** / **Security Reviewer** / **Date:** 2026-08-28
**Code candidate:** `d3c720c` (`feat(transport): add agent capability routing`)
**Design baseline:** `19390dd`

## Acceptance criteria verification

| # | Criterion | Evidence (real output) | Pass |
|---|---|---|---|
| 1 | Bounded descriptors, unique capabilities, legacy registration, sorted detached listing | `test_agent_registry_lists_bounded_descriptors_and_routes_exact_match` passes; descriptors expose only IDs and labels | Yes |
| 2 | Authenticated metadata listing and fail-closed boundaries | `test_authenticated_agent_capability_listing_and_routing_round_trip` covers auth, principal scope, missing registry, and metadata shape | Yes |
| 3 | Exact deterministic capability route | Registry and HTTP integration select `alpha` before `zeta`, preserve task/context/session/run fields, and return selected identity | Yes |
| 4 | Raw compatibility and typed route normalization | Existing named-agent transport tests remain green; typed malformed selected identity regression passes | Yes |
| 5 | Native adapter capability forwarding | `test_native_agent_remote_adapter_routes_by_capability` and adapter listing assertion pass | Yes |
| 6 | Documentation, security, regression, and package gates | Public docs, changelog, parity/release artifacts, targeted scans, and full suite are green; clean-archive package gate remains the final pending check | Pending |

## Regression

```text
python -m pytest tests/autonomy/test_server.py tests/autonomy/test_agent_transport.py -q --no-cov
56 passed in 21.28s

python -m pytest -q --no-cov
1649 passed, 1 skipped in 267.21s
```

The full run collected `1650` tests and completed without failures. The single
skip is pre-existing test-environment coverage; no test was weakened or
removed.

## Static and security gates

```text
python -m black --check maple/autonomy/server.py maple/autonomy/agent_transport.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_server.py tests/autonomy/test_agent_transport.py
6 files would be left unchanged.

python -m isort --check-only maple/autonomy/server.py maple/autonomy/agent_transport.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_server.py tests/autonomy/test_agent_transport.py
isort_exit=0

python -m ruff check maple/autonomy/server.py maple/autonomy/agent_transport.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_server.py tests/autonomy/test_agent_transport.py
All checks passed!

python -m mypy --follow-imports=skip maple/autonomy/server.py maple/autonomy/agent_transport.py maple/autonomy/__init__.py maple/__init__.py
Success: no issues found in 4 source files

python -m compileall -q maple/autonomy/server.py maple/autonomy/agent_transport.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_server.py tests/autonomy/test_agent_transport.py
compile_exit=0

slice170_secret_scan=passed
slice170_danger_scan=passed
```

No dependency was added. `gitleaks` and Bandit are unavailable in this
environment. The environment-wide `python -m pip_audit --local` baseline
remains a separate release-governance veto; this slice changes no dependency.

**Security verdict:** Pass for Slice-170-specific findings. The route is
authenticated, scope-checked, bounded, exact-match, and metadata-only for
discovery. It does not claim identity federation, distributed ownership,
push delivery, retries, failover, or exactly-once effects.

## Release disposition

Slice 170 is ready for clean-archive package verification. Publication,
deployment, cloud action, registry write, and website update were not
performed.
