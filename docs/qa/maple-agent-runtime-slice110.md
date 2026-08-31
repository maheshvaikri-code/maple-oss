# Slice 110 QA — Bounded Model/Provider Retries

- Tested tree: `653d675`
- QA date: 2026-08-26
- Verdict: **PASS for behavior and local static gates**

## Functional evidence

Focused command:

```text
python -m pytest tests/autonomy/test_agent.py tests/llm/test_provider.py tests/llm/test_provider_native_streaming.py -q --no-cov -p no:dash -p no:benchmark --tb=short --no-header
```

Observed result: `48 passed in 0.52s`.

The focused coverage includes sync and async classified model retries,
stream-collector retry, fail-fast permanent failures, bounded backoff and
configuration validation, OpenAI/Anthropic adapter classification, and the
existing native-stream compatibility failure.

Tracked application regression command:

```text
python -m pytest tests -q --no-cov -p no:dash -p no:benchmark --tb=short --no-header --ignore=tests/test_doctrine_gold.py --ignore=tests/test_doctrine_lint.py --ignore=tests/test_doctrine_metrics.py --ignore=tests/test_doctrine_packaging.py --ignore=tests/test_doctrine_state.py
```

Observed result: `1273 passed, 1 skipped in 250.94s (0:04:10)`.

The five ignored files are user-owned untracked Doctrine tests, not skipped
tracked application coverage.

## Static and runtime gates

- Changed-boundary mypy: `Success: no issues found in 5 source files`.
- Changed-source Ruff: `All checks passed!`.
- Black: all seven changed Python files left unchanged after formatting.
- `compileall -q maple tests`: exit `0`.
- `git diff --check`: exit `0`.
- `python -m maple.cli doctor --json`: `ready: true`, all eight checks true,
  `network: false`.

## Release disposition

Behavioral QA passes. The clean committed-HEAD package candidate `1ff12ce`
rebuilt wheel/sdist `1.1.3`; both Twine checks passed, the sdist contains `516`
entries, all six checked public/slice files are present, and the workspace-only
audit is zero:

```text
source=git archive HEAD
head=1ff12ce
build_exit=0
twine_wheel=PASSED
twine_sdist=PASSED
sdist_entries=516
required_files=6/6
workspace_only_hits=0
present=README.md, LICENSE, CHANGELOG.md,
  docs/adr/056-bounded-model-provider-retries.md,
  docs/qa/maple-agent-runtime-slice110.md,
  docs/reviews/maple-agent-runtime-slice110.md
absent=AGENTS.md, CLAUDE.md, COMMERCIAL_LICENSE.md, Makefile,
  docs/brief.md, docs/maximus.md
```

The dependency-governance gate remains open because the current shared
interpreter reports `383 known vulnerabilities in 77 packages`, and
`gitleaks`/`bandit` are unavailable in the environment.
