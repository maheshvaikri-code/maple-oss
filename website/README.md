# MAPLE website assets

**Status: content aligned with MAPLE 2.1.0. Not deployed.**

This directory holds the static website source and the local website analysis.
The bundle carries the 2.1.0 capability index, the release-status language, the
framework comparison, and the public documentation set. Editing this directory
does not deploy or connect the site to any external service.

Documentation ships with a release, not after it: the site content is
reconciled against the tree *before* a version is tagged, so the moment a
release is published the site is already correct.

## Source of truth

The website's public content is consolidated in:

- [MAPLE 2.1.0 capability index](public_html/docs/maple-2.1.0.md) - current
- [MAPLE 2.0.0 capability index](public_html/docs/maple-2.0.0.md) - retained as
  a historical record, with a banner pointing at 2.1.0

The repository README and release documents remain authoritative for the
current runtime surface:

- [Root README](../README.md)
- [Changelog](../CHANGELOG.md)
- [Architecture decision records](../docs/adr/)
- [QA records](../docs/qa/)
- [External-phase plan](../docs/plans/maple-publication-website-cloud-registry.md)

The checked-in HTML and media are a separate presentation surface. The
existing logo, favicon, badges, and visual shell are preserved while copy and
links are reconciled with the 2.0.0 source-of-truth documents.

`public_html/` is the editable static source tree. `public_html.zip` is the
local generated bundle for a later website handoff.

Note that `website/` is listed in `.gitignore`; only this README is tracked.
Site content changes therefore live in the working tree and are not carried in
the repository's history. Treat that as deliberate, and keep this README as the
record of what the site currently claims.

## Website checklist

For a future website change:

1. Confirm the website repository/path, owner, target domain, and deployment
   authority.
2. Reconcile version, installation commands, capability claims, examples,
   links, accessibility, and security language with the root README and
   release evidence.
3. Run local HTML, link, accessibility, and copy checks.
4. Obtain explicit approval before any external deployment.

No external deployment, domain change, registry write, release tag, or
publication is implied by this directory. There is no
.openai/hosting.json in this repository.
