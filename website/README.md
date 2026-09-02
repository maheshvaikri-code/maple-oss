# MAPLE website assets

**Status: content aligned with MAPLE 2.1.0. Not deployed.**

This directory holds the static website source and the local website analysis.
The bundle carries the 2.1.0 capability index, the release-status language, the
framework comparison, and the public documentation set. Editing this directory
does not deploy or connect the site to any external service.

Documentation ships with a release, not after it: the site content is
reconciled against the tree *before* a version is tagged, so the moment a
release is published the site is already correct.

## Documentation page

`public_html/docs.html` is **generated**. Do not edit it:

```bash
python website/build_docs_page.py
```

It assembles 19 pages into seven sections and embeds them in the page, so the
viewer needs no network call and works from `file://` as well as from a host.

Content comes from two places, and the split is deliberate:

- **Narrative pages** live in `website/docs-src/` - the introduction,
  architecture, delivery guarantees, scopes, security, autonomy, and production
  pages. These are written for the site.
- **Reference pages** are read straight from the repository's own `docs/`
  directory at build time - the API reference, type system, best practices,
  troubleshooting, comparisons, and use cases. Each carries a "source of truth"
  line pointing at the file it came from.

Reference pages are pulled rather than copied because copies drift. The site
previously carried its own abridged versions and ended up advertising a test
count that was two releases out of date, alongside a 100-line "API reference"
against the repository's 4,238-line one.

The tree is defined in `TREE` at the top of the generator; add a page there.

### Superseded files

These remain in `public_html/docs/` but are no longer served - the viewer now
reads their canonical counterparts from `docs/`:

`api-reference.md`, `best-practices.md`, `details_Result_Type.md`,
`getting-started.md`, `industry-applications.md`, `mapl-use-cases.md`,
`protocol-comparison.md`, `troubleshooting.md`, `type-system.md`

They are safe to delete. They are kept only because this directory is
gitignored, so removing them is not recoverable from history.

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
