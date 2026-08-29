# MAPLE 2.0.0 publication, website, cloud, and registry plan

**Status:** prepared; no external action taken
**Prerequisite:** local 2.0.0 quality and package gates are complete, subject to
the open limitations in the release QA record.

## Workstreams

### 1. Website

- Confirm the website repository/path and intended domain.
- Update current version, release notes, install instructions, and capability
  language to match MAPLE 2.0.0.
- Publish the parity boundary plainly: local runtime capabilities are shipped;
  hosted identity, distributed scheduling, managed stores, sandboxing,
  browser/computer control, and hosted operations remain planned follow-ups.
- Run link, static HTML, accessibility, and copy checks locally.
- Obtain explicit deployment authorization, then preview and deploy through the
  approved hosting target.

### 2. Cloud

- Human selects and records exactly one initial provider in `docs/brief.md`:
  `Cloud target: aws`, `Cloud target: azure`, or `Cloud target: gcp`.
- Build the local emulator/parity ledger first for the selected provider's
  identity, secrets, storage, queue, observability, and deployment contracts.
- Add provider-specific infrastructure only after the provider is recorded and
  the local contract tests are green.
- Require explicit approval before any real cloud SDK call, account mutation,
  paid resource, or deployment.

### 3. External registry and release

- Select the approved targets: Test PyPI, PyPI, GitHub release, or another
  named registry.
- Run the missing secret scan and record provenance for the exact final
  artifacts.
- Confirm protected-branch state and obtain explicit approval to create/push
  `v2.0.0`.
- Upload first to the approved test target, run install/import/doctor/quickstart
  smoke tests, then obtain separate approval for production publication.
- Record URLs, artifact hashes, and rollback/withdrawal instructions after
  publication.

## Go/no-go criteria

The external phase may begin only when the following are explicit:

- project reviewer sign-off is filed;
- final secret scan is clean;
- cloud provider is recorded, if cloud work is in scope;
- website target/domain and deployment authority are named;
- registry targets are named;
- tag and publication approvals are separately confirmed.

Until those decisions are supplied, the repository remains a local 2.0.0
candidate and no website, cloud, registry, tag, or publication action is
claimed.
