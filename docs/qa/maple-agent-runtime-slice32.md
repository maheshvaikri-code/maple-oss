# QA evidence — MAPLE agent-runtime slice 32

## Results

- `python -m build --wheel --sdist` → `Successfully built
  maple_oss-1.1.3-py3-none-any.whl and maple_oss-1.1.3.tar.gz`.
- `python -m twine check dist\*` → wheel `PASSED`, sdist `PASSED`, exit 0.
- `python -m maple.cli doctor --json` → all checks true, `network: false`,
  `ready: true`, `status: SUCCESS`, version `1.1.3`.
- `python -m black --check maple` → pass.
- `python -m isort --check-only maple` → pass.
- `python -m ruff check tools tests` → pass.
- `python -m compileall -q maple` → pass.

## Open gates

The full repository pytest run remains incomplete. Aggregate explicit-target
mypy remains at `277 errors in 43 files`; the configured Python 3.8 target is
not accepted by installed mypy 2.3. Bandit is unavailable locally, dependency
audit disposition is open, and fresh-context independent verification is not
available. No package was uploaded or published.
