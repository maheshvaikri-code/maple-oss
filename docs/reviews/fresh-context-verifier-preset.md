# Code Review Report — Fresh-Context Verifier Preset

**Gate:** G4 (Code Review) · **Class:** M · **Method:** fresh-context verifier
(a subagent seeing only the diff + contract, not the author's narrative —
the exact discipline this feature enforces).

## Verdict

SHIP-WITH-FIXES → **all findings resolved**; re-verified by tests. The
direct-`send()` sender allowlist was airtight and well-tested from the start;
the defects were in the paths *around* it, two of which defeated the
"runtime guarantee instead of a convention" claim.

## Findings and resolution

| ID | Sev | Finding | Resolution |
|----|-----|---------|-----------|
| H1 | HIGH | `broker.publish()` bypassed the policy entirely — a verifier could reach a builder via a topic. | `publish()` now validates the sender against every subscriber (and the payload policy) and rejects the whole publish on any violation. Test: `test_publish_verifier_to_builder_topic_rejected`. |
| H2 | HIGH | `MessageBroker` singleton read the policy only on first construction; fleet construction order could silently drop it. | `__init__` calls `_refresh_separation_policy()` on re-init (adopts a newly-supplied policy, never clears an active one, logs on replace); added explicit `set_separation_policy()`. Test: `test_singleton_adopts_policy_from_later_config`. |
| M1 | MED | Prose could be smuggled in a ref's unbounded `path` field. | A ref's `path` is now subject to `max_prose_chars`; `is_artifact_ref` also rejects newlines in `path`. Tests: `test_long_ref_path_is_rejected_as_prose`, `test_ref_path_with_newline_is_not_a_valid_ref`. |
| M2 | MED | Lowercase custom `guarded_types` silently disabled the payload guard (`Message` upper-cases types). | `SeparationOfDutiesPolicy.__post_init__` upper-cases `guarded_types`. Test: `test_lowercase_guarded_type_still_guards`. |
| L1 | LOW | Prose in dict **keys** was never checked. | `_find_prose` now checks keys too. Test: `test_long_dict_key_is_rejected_as_prose`. |
| L2 | LOW | `receiver=None` was fail-open for a listed sender. | A listed sender with no receiver is now denied (fail-closed). Test: `test_listed_sender_without_receiver_denied`. |
| L3 | LOW | Unbounded recursion on cyclic/deeply-nested payloads (raw `RecursionError`, cheap DoS). | Traversal is depth-capped (`_MAX_PAYLOAD_DEPTH=100`); over-limit → clean `PAYLOAD_TOO_DEEP` error. Tests: `test_deeply_nested_payload_rejected`, `test_cyclic_payload_rejected`, `test_deep_payload_without_ref_rejected`. |
| N1 | NIT | `_collect_refs` walked the whole payload when only presence was needed. | Replaced with short-circuiting `_has_artifact_ref`. |
| N2 | NIT | Guarantee holds only for the in-memory broker; `nats_broker`/S2 unenforced. | Documented as scoped in the module docstring, plan, and CHANGELOG. Follow-up if those transports are adopted. |
| N3 | NIT | String sentinel in `_find_prose` could theoretically collide with a field name. | Removed; `_find_prose` now builds the field path top-down (no sentinel). |

## Checks that came back clean (verifier's words)

- `Result<T,E>` idiom and error shapes consistent with the rest of `maple/`;
  allowlist details are not leaked in the raised `SecurityError`.
- Enforcement order (SoD before link/authz) is sensible and intentional.
- Policy helpers are read-only/pure — safe to share across delivery threads;
  the only concurrency hazard was the singleton lifecycle (H2), now fixed.

## Evidence

`tests/security/test_separation.py`: **52 passed**, `maple/security/separation.py`
at **100%** line coverage. Broader regression subset: see `docs/qa/`.
