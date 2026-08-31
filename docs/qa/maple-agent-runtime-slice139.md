# MAPLE Agent Runtime Slice 139 QA

Date: 2026-08-27

Scope: add bounded manager-style agent-as-tool delegation through
`create_agent_tool(...)`. The tool preserves caller orchestration ownership,
uses approval by default, bounds task/context/result data, supports explicitly
declared sync and async target methods, and sanitizes child failures.

Implementation commit: `5693545`
Documentation commit: `1834789`

## Acceptance evidence

- Focused agent-tool suite: `31 passed in 2.86s`
- Exact tracked committed-HEAD suite: `1373 passed, 1 skipped in 272.36s` across `1374` collected tests
- Whole-package mypy: `Success: no issues found in 97 source files`
- isort on changed Python files: passed
- Ruff: `All checks passed!`
- `python -m compileall -q maple tests`: passed
- `git diff --check`: passed
- Public export smoke: `agent_tool_exports=2`
- Project dependency audit: `No known vulnerabilities found`
- Source-only secret scan: `source_secret_high_confidence_matches=0`
- Source-only dangerous-construct scan: `source_dangerous_construct_matches=0`

## Behavioral coverage

- Normal invocation returns only bounded `agent_id`, `goal_id`, `status`, and `result` fields and does not create an ownership handoff record.
- Context keys are explicitly allowlisted and bounded; denied keys fail before target invocation.
- Missing context-aware target methods, malformed target results, target exceptions, and child `Result` errors become typed sanitized failures.
- Async execution uses the target's explicitly declared async method and preserves the same result/error boundary.
- Existing `Tool` validation covers empty and oversized task input before delegation.

## Package evidence

The clean ZIP-extracted committed archive built successfully. Wheel and source
distribution both passed Twine checks; the wheel contained `104` entries and
the source distribution contained `600` entries. The no-dependency wheel-target
smoke imported `create_agent_tool` successfully:
`clean_archive_import=create_agent_tool`.

SHA-256: wheel
`AA942D36AD64C699CD39FCA8B835DF175DC8CBEDB7C681D56F92ABEACF124639`;
source distribution
`1EAF8F3E2543A817C68F7AF9D537723915CAD5A350F839B03B1349723270B5E1`.

## Disposition

Local QA passes for this implementation, documentation, and committed package
artifacts. Environment-wide dependency governance remains a release veto from
the prior audit: `384` known vulnerabilities across `77` installed packages.
No publication, deployment, cloud action, or website update was performed.
