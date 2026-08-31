# Ultra Review - MAPLE 2.0.0 public release candidate

- Review target: 67c988fb3347e98ed5e46caf7004ba06c33db0d9
- Review date: 2026-08-30
- Reviewer hats: Code Reviewer, Tech Writer, Release Manager
**Scope:** full repository release-readiness review with emphasis on public
documentation, README coverage, security boundaries, package evidence, and
website standing.

## Verdict

**No open blocker found in the reviewed local scope.** The repository remains
a **conditional local 2.0.0 candidate**, not a published release. The
independent fresh-context reviewer gate, protected-branch configuration,
release tag authorization, registry publication, cloud target, and website
deployment remain human-controlled gates.

The website is **in standing**. Only a status README was added under the
ignored website directory; the static website assets were not changed and no
deployment or hosting action was performed.

## Review method

The review read the current release checklist, external-phase plan, parity
ledger, release QA/review records, package metadata, public exports, workflows,
README surfaces, and the current source tree. It then performed:

- correctness and boundary review of the public documentation;
- stale-claim and broken-link sweeps;
- Python README code-block syntax and execution checks;
- full Python regression tests;
- formatter, lint, type, compilation, Doctrine, package, and security gates;
- exact-commit clean-archive and full-history Gitleaks scans;
- working-tree, branch, and release-boundary checks.

The repository has no available mechanism in this execution context for the
fresh serial Code Reviewer, Security Reviewer, and QA Engineer sessions
required by the doctrine. This report is therefore author-run evidence, not
independent sign-off.

## Findings and disposition

### Resolved before this report

1. **[MAJOR, resolved] Unsafe quickstart guidance.** The former root
   quickstart used Python eval on tool input. It was replaced with a bounded
   AST example that accepts only integer addition/multiplication and reads
   provider credentials from the environment.
2. **[MAJOR, resolved] Stale public release language.** The root README and
   demo package contained 1.1.x markers, unverified throughput claims,
   production/compliance claims, and links to paths that are not present.
   The public docs now identify 2.0.0 as an unpublished local candidate and
   state the local/hosted limitations.
3. **[MAJOR, resolved] Broken n8n links and scope ambiguity.** The n8n README
   and detailed guide now resolve locally, describe the three declared nodes
   and sample workflows, and distinguish the companion npm package from the
   Python 2.0.0 release.
4. **[MINOR, resolved] README discoverability.** README entry points now exist
   for the core, examples, legacy example, focused demos, external demo
   package, launch helpers, n8n integration, and website standing. Legacy
   installation/summary documents were reduced to truthful redirects.
5. **[MINOR, resolved] Review artifact drift.** The release QA and review
   records now point their final repository verification to the documentation
   closure commit 9db830b and the current hosted run IDs.

### Remaining, explicitly accepted as release conditions

- **[MAJOR] Independent review is unavailable.** Human or fresh-session
  Code/Security/QA verification is still required before a final release
  decision.
- **[MAJOR] The default branch is unprotected.** GitHub reports main as
  protected false, the protection endpoint returns HTTP 404, and repository
  rulesets count is zero. This was not changed by the review.
- **[MAJOR] External publication is not authorized.** No tag, registry write,
  cloud call, website deployment, or external publication occurred.
- **[MINOR] Website content is not synchronized.** The static website remains
  held for a separate copy, link, accessibility, security-language, and
  deployment review. The repository-level standing decision is documented in
  website/README.md and the external-phase plan.
- **[MINOR] Full-history Gitleaks findings remain historical fixtures.** The
  current exact archive is clean. The three full-history matches are the
  previously reviewed synthetic test/documentation markers, an idempotency
  fixture, and an n8n JWT placeholder; none is a credential, and no allowlist
  or history rewrite was used.
- **[MINOR] The Python package is the release artifact.** The demo and n8n
  directories remain companion surfaces outside the core wheel/sdist. Their
  separate package or external-service release decisions are not implied by
  MAPLE 2.0.0.

## Evidence

### Documentation and examples

~~~text
README surfaces audited: 8
README link audit: all checked files returned missing_links=[]
Python README blocks: 3 parsed successfully
Python README blocks: 3 executed successfully
Typed messaging quickstart: send_ok=True
~~~

The root README now documents the agent loop, tools, workflows, sessions,
human control, memory, retrieval, events, evaluation, task management,
protocol adapters, framework parity boundary, installation extras, code-block
artifact behavior, release evidence, and website standing. It explicitly
does not claim sandboxing, hosted services, distributed scheduling, or
exactly-once external effects.

### Runtime and quality

~~~text
20 passed in 1.10s
1906 passed, 1 skipped in 1166.27s (0:19:26)
Success: no issues found in 103 source files
103 files would be left unchanged.
compileall exit=0
doctrine_lint: corpus clean
~~~

The exact Flake8 command returned exit 0 with zero findings. Black, isort,
mypy, Bandit, pip-audit, compileall, and Doctrine lint returned success.
pip-audit reported: No known vulnerabilities found.

### Package

~~~text
Successfully built maple_oss-2.0.0-py3-none-any.whl and maple-oss-2.0.0.tar.gz
build_exit=0
~~~

The package metadata and offline doctor remain version-aligned to 2.0.0.
The core distribution boundary excludes the demo package and n8n integration.

### Security

~~~text
gitleaks 8.30.1 clean archive:
scanned ~7651778 bytes (7.65 MB)
no leaks found
gitleaks_clean_archive_exit=0
archive_commit=67c988fb3347e98ed5e46caf7004ba06c33db0d9

gitleaks full history:
745 commits scanned
scanned ~8820511 bytes (8.82 MB)
leaks found: 3
~~~

The historical findings match the existing disposition in the release QA
record. The reviewed runtime uses a restricted built-in-only unpickler for its
bounded pickle compatibility path; no untrusted-code execution boundary is
claimed. No new dependency was introduced by the documentation commit.
The existing requests adapter extra remains opt-in and is covered by the
dependency policy and pip-audit result.

### Hosted and repository state

The final hosted release workflows recorded for the preceding implementation
closure are all green: Security Scan 33341517061, Code Quality 33341517056,
Tests 33341517046, and CI 33341517051. The exact current documentation commit
is 67c988f; pushing it will require the normal hosted CI rerun.

The branch was clean before the documentation commit, and the documentation
commit contains no source behavior changes. The website assets, cloud state,
external registries, tags, and protected-branch settings were not mutated.

## Follow-up plan

1. Obtain fresh independent Code Reviewer, Security Reviewer, and QA sessions.
2. Decide and configure protected-branch required checks.
3. If cloud work enters scope, record one provider in docs/brief.md before any
   SDK or deployment action.
4. Authorize a separate website reconciliation and deployment review.
5. Select registry targets, authorize the v2.0.0 tag, and authorize publication
   separately.
6. Rerun the exact release, package, and clean-archive security gates on the
   final human-approved commit.
