# QA Record - MAPLE v2.0.0 local candidate

## Final repository gate closure

**Exact final commit:** `aca5a751b2af8e543623f8e351afa8f7c0176c92`
(`docs(release): record final CI gate closure`)

The final hosted workflows passed on this commit:

| Workflow | Run | Result |
|---|---:|---|
| Security Scan | `33341517061` | success |
| Code Quality | `33341517056` | success |
| Tests | `33341517046` | success; Python 3.9/3.10/3.11/3.12 and Windows/Linux/macOS jobs |
| CI | `33341517051` | success; preflight, lint/type check, test matrix, package build, summary |

The final local targeted regression gate reported `11 passed in 1.16s` for
the durable lease, Windows concurrency, Doctrine lint, and installer checks.
The four concurrent durable-store tests were then repeated ten times with
`repetitions_failed=0`. A complete local suite at the immediately preceding
commit `fc52b3d` reported `1906 passed, 1 skipped in 781.02s`; the final
commit's complete cross-platform suites are the hosted evidence above.

Gitleaks `8.30.1` scanned a clean Git archive of this exact commit
(`~7.74 MB`) and reported `no leaks found`. The explicit full-history scan
covered `743 commits` and reported only the three previously reviewed
synthetic historical findings; no credentials, allowlist, or history rewrite
is claimed.

GitHub reports `main` as `protected: false`; the branch-protection endpoint
returned HTTP `404 Branch not protected`, and repository rulesets count is
`0`. The independent fresh-context reviewer session remains unavailable, so
this remains an author-run QA record pending that human-controlled gate.

**Quality candidate commit:** `b4afc0c` (`chore(release): promote MAPLE to 2.0.0`)
**Final repository candidate:** `aca5a75` (`docs(release): record final CI gate closure`)
**Security remediation candidate:** `b86b724` (`fix(security): neutralize scanner false-positive fixtures`)
**Verification date:** 2026-08-29
**Scope:** MAPLE source quality gates, version promotion, full test suite, and
clean-archive package smoke checks.

## Repository quality gates

The following commands were run against the candidate source tree:

| Check | Result |
|---|---|
| `python -m pytest -q --no-cov` | `1904 passed, 1 skipped in 466.09s (0:07:46)` |
| `python -m flake8 maple/ --max-line-length=88 --extend-ignore=E203,W503,W291,W293,E302,E402,F401,F811,F841 --count --statistics` | exit `0`, `0` findings |
| Workflow-equivalent author scan | `103` modules checked, `0` missing notices |
| `python -m black maple --check --quiet` | exit `0` |
| `python -m isort maple --check-only --diff` | exit `0` |
| `python -m ruff check maple` | `All checks passed!` |
| `python -m mypy maple/ --ignore-missing-imports` | `Success: no issues found in 103 source files` |
| `python -m compileall -q maple` | exit `0` |
| `python -m bandit -r maple -ll -q` | exit `0` |
| `python -m pip_audit --strict --progress-spinner off --timeout 30 .` | exit `0`, `No known vulnerabilities found` |
| `git diff --check -- maple README.md CHANGELOG.md VERSION docs` | exit `0` |

The original CI baseline of `610` line-length findings and `20` header-policy
findings is now `0` and `0`. The workflow policy itself was not weakened.

## Package smoke gates

The package was built from a clean `git archive` of the exact candidate commit,
excluding the user's unrelated working-tree changes:

```text
python -m build --no-isolation --wheel --sdist
Successfully built maple_oss-2.0.0-py3-none-any.whl and maple-oss-2.0.0.tar.gz

python -m twine check dist\\maple_oss-2.0.0-py3-none-any.whl dist\\maple_oss-2.0.0.tar.gz
wheel: PASSED
sdist: PASSED

python -m pip install --no-deps --target install dist\\maple_oss-2.0.0-py3-none-any.whl
Successfully installed maple-oss-2.0.0
```

The isolated import/doctor smoke reported:

```text
import_version=2.0.0
agent_registry=AgentRegistry
evaluation_harness=EvaluationHarness
{"checks": {"core": true, "evaluation": true, "events": true, "execution": true, "interop": true, "retrieval": true, "server": true, "sessions": true}, "network": false, "ready": true, "status": "SUCCESS", "version": "2.0.0"}
twine_exit=0
install_exit=0
import_exit=0
doctor_exit=0
```

Archive audit results:

```text
wheel_entries=110
sdist_entries=914
wheel_excluded_demo=0
sdist_excluded_demo=0
sdist_has_release=True
```

Candidate artifact SHA-256 values:

```text
maple_oss-2.0.0-py3-none-any.whl  B7FF615A7CCDCCA21138CA83B45D9CD87DAD0AEEFFFD916DB4A543BECFFA7453
maple_oss-2.0.0.tar.gz            57F6D6EF04C25152BA8EE12BC405E785ACA192750C32EF37E6CF8C841628B83E
```

The release evidence documents were then committed in `5c22057`. A final
clean-archive rebuild of that commit also passed:

```text
archive_head=5c2205783fddccae349394f3d3f1b32ca52578c
Successfully built maple_oss-2.0.0-py3-none-any.whl and maple_oss-2.0.0.tar.gz
wheel: PASSED
sdist: PASSED
import_version=2.0.0
{"checks": {"core": true, "evaluation": true, "events": true, "execution": true, "interop": true, "retrieval": true, "server": true, "sessions": true}, "network": false, "ready": true, "status": "SUCCESS", "version": "2.0.0"}
wheel_entries=110
sdist_entries=917
wheel_excluded_demo=0
sdist_excluded_demo=0
sdist_has_release=True
```

Final archive SHA-256 values:

```text
maple_oss-2.0.0-py3-none-any.whl  94A5382D5F23C53B37FD35C2F1A18CDD87F313FD312311E61C37B4F52283153B
maple_oss-2.0.0.tar.gz            8EB1D2499C173EBBC8F5737A59613444DA3B7E901945B74A2047BCF6D61F17DC
```

The pending repository updates were committed in `e8e2faa`. A post-commit
clean-archive rebuild of that exact commit passed all package gates:

```text
archive_head=e8e2faabf45f7f30f3e76210fc5321d50bd06219
Successfully built maple_oss-2.0.0-py3-none-any.whl and maple_oss-2.0.0.tar.gz
twine_exit=0
install_exit=0
import_version=2.0.0
import_exit=0
{"checks": {"core": true, "evaluation": true, "events": true, "execution": true, "interop": true, "retrieval": true, "server": true, "sessions": true}, "network": false, "ready": true, "status": "SUCCESS", "version": "2.0.0"}
doctor_exit=0
wheel_entries=110
sdist_entries=923
wheel_excluded_demo=0
sdist_excluded_demo=0
sdist_has_release=True
```

Post-commit artifact SHA-256 values:

```text
maple_oss-2.0.0-py3-none-any.whl  1785E812C08F911339EF7E48D00DF2C008BFC7D99FF605E7CD1FFAD9350A3B65
maple_oss-2.0.0.tar.gz            4F702096A8B2701359CA57678A9978FB6612202EFB051A2542ECD9633A044370
```

The security remediation was committed in `b86b724`. A final clean-archive
rebuild of that exact commit passed:

```text
archive_head=b86b724357c882c1cdbb2060e08bb229ac989300
Successfully built maple_oss-2.0.0-py3-none-any.whl and maple_oss-2.0.0.tar.gz
twine_exit=0
install_exit=0
import_version=2.0.0
import_exit=0
{"checks": {"core": true, "evaluation": true, "events": true, "execution": true, "interop": true, "retrieval": true, "server": true, "sessions": true}, "network": false, "ready": true, "status": "SUCCESS", "version": "2.0.0"}
doctor_exit=0
wheel_entries=110
sdist_entries=923
wheel_excluded_demo=0
sdist_excluded_demo=0
sdist_has_release=True
```

Security-remediated artifact SHA-256 values:

```text
maple_oss-2.0.0-py3-none-any.whl  3A7110AFA3990BB9691C16F6515E45989C43056D0BA9AE98D1C0DA115EECFDC7
maple_oss-2.0.0.tar.gz            3C92491D64F6784975A1C73B23C92A35E28CA79F8D3CF2F4DECC6984B8C1C203
```

## Limitations and handoff

- Gitleaks `8.30.1` was downloaded temporarily from the official release and
  its Windows x64 archive SHA-256 was verified before execution.
- The full-history scan inspected `735` commits and found three fixture/document
  false positives. The current secret-like test marker, the idempotency-key
  fixture, and the n8n JWT placeholder are not credentials; the current files
  are now scanner-clean. No allowlist or history rewrite was used.
- A clean-tree Gitleaks directory scan inspected approximately `7.36 MB` and
  returned `no leaks found` with exit `0`.
- An independent fresh verifier session was not available in this execution
  context, so this file is an author-run QA record, not an independent sign-off.
- The working tree contains pre-existing user changes. The release artifact
  above came from a clean archive of the candidate commit and did not include
  those changes.
- No tag, registry write, cloud call, website deployment, or external
  publication was performed.
