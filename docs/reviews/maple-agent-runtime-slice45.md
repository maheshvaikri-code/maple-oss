# Review — MAPLE agent-runtime slice 45

## Scope

Review the communication pattern typing changes in:

- `maple/communication/pubsub.py`
- `maple/communication/request_response.py`
- `maple/communication/streaming.py`
- `tests/communication/test_pubsub.py`

## Findings

- Constructor and state annotations make the three communication patterns
  explicit without changing their transport setup or delivery flow.
- Broker publication remains delegated to the injected broker. The static cast
  documents the existing broker contract at the untyped agent boundary.
- Direct publication now returns `str(message.message_id)`, matching the
  declared `Result[str, ...]` API and the message serialization convention.
- Pending request state is represented by a private `TypedDict`, preserving the
  existing event/response/error cleanup lifecycle while preventing mixed-value
  inference from leaking into the public result contract.
- Stream subscriber IDs are narrowed at the existing append boundary; no
  subscriber filtering or delivery behavior was changed.

## Verification

- Focused communication suite: `49 passed`.
- Changed-file mypy: clean for all three modules.
- Black, isort, and compile checks: pass.
- Aggregate audit: `152 errors in 22 files`; the remaining diagnostics are
  outside this slice.

## Disposition

Approved for the release-readiness branch as a behavior-preserving typing
slice. The remaining aggregate type debt and independent verification gates are
tracked in the release plan.
