# Slice 205 Review - Durable local lexical retrieval

**Reviewer role:** Code Reviewer
**Review basis:** Slice 205 brief, ADR-149, implementation plan, and
committed implementation `b9843d7` plus bounded-read hardening `5135877`

## Verdict

PASS for the bounded local contract. `FileLexicalRetriever` reuses the
existing validated document/chunk and deterministic lexical contracts, stores
only JSON-safe source records plus the chunking policy, and rebuilds derived
state after restart. Mutations reload under the existing durable file lease,
write prospective state through a same-directory temporary file with flush,
fsync, and atomic replacement, and publish the new in-memory index only after
the write succeeds.

The backend is explicitly local-only. It does not add a dependency, fetch
documents, generate embeddings, provide a managed vector store, execute
retrieved content, or claim distributed consensus or exactly-once effects.

This is a local self-review. A fresh independent verifier session was
unavailable in this environment, so this artifact is not independent security
or release sign-off.

## Findings and disposition

- Persisting the chunking policy closes a restart-consistency gap: reopening a
  store with a different policy fails closed instead of silently changing
  chunk boundaries. Covered by
  `test_file_lexical_retriever_rejects_chunking_policy_mismatch`.
- Candidate add/remove operations rebuild and validate before persistence;
  writer failures leave the prior file bytes and searchable state unchanged.
- Corrupt, oversized, unsupported-version, duplicate, invalid-UTF-8, and
  unrebuildable state is rejected without exposing raw storage details.
- Shared local instances reload under `DurableRecordLease`; the concurrency
  regression confirmed both peer updates survive.
- No open findings remain within Slice 205's stated scope.

## Verification evidence

```text
focused_retrieval=35 passed in 4.92s
full_suite=1838 passed, 1 skipped in 372.71s
mypy=Success: no issues found in 102 source files
black=4 files would be left unchanged
ruff=All checks passed
compileall=exit 0
pip_audit=No known vulnerabilities found
```

Clean archive package smoke from committed `b9843d7`:

```text
source_archive_entries=960
wheel_entries=109
sdist_entries=874
build_exit=0
twine_exit=0
install_exit=0
import_exit=0
import_output=1.1.3 FileLexicalRetriever
doctor_exit=0
doctor_output={"checks": {"core": true, "evaluation": true, "events": true, "execution": true, "interop": true, "retrieval": true, "server": true, "sessions": true}, "network": false, "ready": true, "status": "SUCCESS", "version": "1.1.3"}
required_slice205_files_present=True
excluded_wheel_entries=0
excluded_sdist_entries=0
wheel_sha256=B54BD391021ACB519216D10E774CD158652BF7FBA69C8A1C35FD526BB6D706F5
sdist_sha256=7C5E8CEBCFD8F7F2524826A94219758573267471DDEC817F81AF57C15BF13388
```

The candidate remains version `1.1.3`; no tag, registry write, publication,
cloud action, or website update was performed.
