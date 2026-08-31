# MAPLE Agent Runtime Slice 136 QA Record

Date: 2026-08-27

Scope: add `EvaluationHarness.run_async(...)` and `AsyncEvalJudge` for
sequential awaitable runners and host-owned judges. The path reuses existing
output/schema/trajectory validation, redaction, and size bounds; it does not
select providers, retry callbacks, persist raw observations, execute generated
code, or claim hosted evaluation.

Implementation commit: `bfd56b5`

## Evidence

- Focused async evaluation coverage: `4 passed, 22 deselected in 4.61s`
- Full evaluation suite: `26 passed in 0.28s`
- Exact tracked test manifest: `1359 passed, 1 skipped in 232.58s` across `108` tracked Python test files
- Whole-package mypy: `Success: no issues found in 97 source files`
- Black on changed Python files: `4 files would be left unchanged.`
- isort on changed Python files: passed
- Ruff: `All checks passed!`
- `python -m compileall -q maple tests`: passed
- `git diff --check`: passed
- Project dependency audit: `No known vulnerabilities found`
- Source-only secret scan: `source_secret_high_confidence_matches=0`
- Source-only dangerous-construct scan: `source_dangerous_construct_matches=0`
- Clean committed-candidate archive build: exit `0`
- Wheel: `104` entries
- Source distribution: `591` entries
- Twine checks: both artifacts `PASSED`
- Clean archive no-dependency async evaluation smoke: `passed`

## Disposition

Local QA passes for this slice. Async execution is sequential and deterministic;
provider choice, retries, calibration, trace scoring, hosted evaluation,
generated-code execution, and exactly-once semantics remain outside the
contract. A fresh independent verifier session was not available in this
environment, and the environment-wide dependency audit remains a
release-governance veto: `384` known vulnerabilities across `77` installed
packages. No publication, deployment, cloud action, or website update was
performed.
