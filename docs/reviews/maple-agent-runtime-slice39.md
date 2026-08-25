# Review — MAPLE agent-runtime slice 39

## Scope

Close the public CLI and package-validation type boundary without changing
doctor, validation, or banner behavior.

## Review findings

- `doctor_report` and `main` now expose explicit return contracts.
- `validate_installation` and `print_banner` now expose explicit return
  contracts.
- The public CLI and package smoke paths remain behaviorally unchanged.
- Optional provider and broker typing remains isolated for later slices.

## Decision

Slice accepted. The change is limited to public return annotations and does
not alter validation, output, or exit-code semantics.
