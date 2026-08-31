# Review - MAPLE agent-runtime slice 64

## Scope

Review the blocking security findings from the isolated Bandit audit and the
resulting transport and serialization changes.

## Findings

- A2A registry registration now has the same bounded 30-second timeout as
  outbound A2A execution.
- MCP's dependency-free transport already rejects non-absolute `http(s)`
  URLs; regression coverage now proves rejection of `file:`, `ftp:`, embedded
  credentials, and fragments. The narrow Bandit annotation documents that
  validated boundary rather than disabling the transport check globally.
- Pickle input is bounded to 1 MiB and deserialized through an allowlist of
  inert built-in scalar/container types. Callable/module globals are rejected;
  round-trip compatibility for the existing built-in test data remains green.
- No new dependency or runtime network behavior was introduced.

## Verification

- Security regression: `37 passed`.
- Cross-surface regression: `621 passed, 1 skipped`.
- Isolated `pip check`: clean.
- Isolated `pip-audit`: no known vulnerabilities.
- Bandit `-ll`: exit 0, zero medium/high findings.
- Mypy, Ruff, Black, isort, and compile checks: pass.

## Disposition

Approved for the release-readiness branch. The medium/high security gate is
closed. Thirty-five low-severity legacy findings remain explicitly tracked;
they do not pass the CI `-ll` threshold. Full-suite completion and independent
fresh verification remain release gates.
