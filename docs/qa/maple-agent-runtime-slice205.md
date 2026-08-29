# Slice 205 QA - Durable local lexical retrieval

**Status:** PASS for the bounded local contract; conditional for repository
publication.

## Acceptance evidence

| Area | Evidence | Result |
|---|---|---|
| Configuration and state bounds | Invalid limits, corrupt JSON, oversized bytes, unsupported version, and chunking-policy mismatch tests | Pass |
| Restart persistence | `test_file_lexical_retriever_persists_and_reloads_documents` | Pass |
| Atomic mutation | Failed remove write preserves file bytes and searchable state | Pass |
| Shared-instance fencing | Two retrievers mutate one directory concurrently | Pass |
| External refresh and query bounds | Fresh search/stats reload the durable source; query limits remain typed | Pass |
| Input and storage redaction | Non-JSON metadata and raised storage failure tests | Pass |
| Focused retrieval regression | `python -m pytest -q tests/autonomy/test_retrieval.py` | `35 passed in 4.50s` |
| Repository regression | `python -m pytest -q --no-cov` | `1838 passed, 1 skipped in 372.71s` |
| Static quality | Black, Ruff, mypy, compileall | All pass |
| Dependency audit | `python -m pip_audit --strict .` | No known vulnerabilities found |
| Clean package smoke | Fresh `git archive` of `b9843d7`; build, Twine, install, import, doctor | All pass |

## Adversarial matrix

Covered inputs include invalid constructor bounds and chunkers, corrupt and
oversized state, unsupported versions, invalid document/source records,
duplicate IDs, policy mismatch, non-JSON metadata, atomic writer failure,
raised storage failure with secret-like text, concurrent writers, restart
reload, external-instance refresh, oversized queries, invalid result bounds,
missing state, and persisted removal.

## Release boundary

The clean package smoke confirms the new public export is present in the
version `1.1.3` wheel and sdist. It does not make the v1.1.4 release ready:
the repository still has preserved user-owned dirty files, CI policy findings,
environment-wide editable-distribution audit limitations, unavailable fresh
independent verifier tooling, and human-gated HTTP/hosted/execution decisions.
No publication, cloud action, or website update is authorized by this slice.
