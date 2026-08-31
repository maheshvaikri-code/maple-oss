# MAPLE 2.0.0 follow-up remediation plan

**Baseline:** MAPLE 2.0.0 local release candidate  
**Purpose:** track findings that are outside the closed release-blocker slice
without presenting them as complete. Adoption and license are excluded.

## Open follow-ups

| Priority | Finding | Planned correction | Exit evidence |
|---|---|---|---|
| P0 / external | Production publication can follow a published GitHub release when the external `pypi` environment permits it. | Require protected release tags and an externally configured environment reviewer, or move production publication behind a separately authorized manual workflow. | Protected-branch/ruleset and environment settings recorded; dry-run proves an unapproved release cannot publish. |
| P1 / API | `MUTUAL_TLS` and `OAUTH2` enum values return `NOT_IMPLEMENTED` while the manager name suggests broad production support. | Choose an API-compatible capability report or remove unsupported methods in a deliberately reviewed major/API change. | Contract tests, updated API/README, and no unsupported security claim. |
| P1 / security | API keys are retained as plaintext dictionary keys. | Add a keyed fingerprint/constant-time lookup design with rotation and revocation semantics; preserve typed failures and never serialize or log the raw key. | Security review, migration behavior, memory/log inspection tests, and rotation regression suite. |
| P1 / bounds | Direct JSON and MessagePack deserialization does not enforce the same byte/depth boundary as protected transport paths. | Add configurable serializer byte/depth/object limits with fail-closed typed errors and compatibility defaults chosen through the API review. | Oversized, deeply nested, and boundary-minus/at/plus tests; package and security gates. |
| P2 / public claims | Candidate metadata and executable demo copy still contain older stable/performance/comparison language. | Align the package classifier and every public demo/launcher with measured, reproducible, version-aware claims. | Demo smoke output, claim inventory, metadata test, and documentation review. |

## Sequencing

1. Resolve the external publication and protected-branch controls before any
   registry or tag action.
2. Agree the authentication API decision, then implement API-key protection
   without silently changing existing consumers.
3. Add serializer limits and adversarial regressions.
4. Sweep demo output and package metadata, then rerun the full release matrix.

These items remain intentionally separate from the completed blocker fix. No
website, cloud, registry, tag, or protected-branch action is authorized by this
plan.
