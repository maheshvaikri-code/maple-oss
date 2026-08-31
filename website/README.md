# MAPLE website assets

**Status: IN STANDING - held for a later website pass.**

This directory contains the tracked static website assets and the local
website analysis. The website is intentionally not being updated, deployed,
or connected to a hosting provider in the MAPLE 2.0.0 repository release work.

## Source of truth

The repository README and release documents are authoritative for the current
2.0.0 runtime surface:

- [Root README](../README.md)
- [Release checklist](../docs/releases/v2.0.0.md)
- [Release QA record](../docs/qa/maple-agent-runtime-release-2.0.0.md)
- [External-phase plan](../docs/plans/maple-publication-website-cloud-registry.md)

The checked-in HTML and media are a separate presentation surface. They may
contain historical copy, links, screenshots, or examples that need review
against the source-of-truth documents before any public update.

## Standing checklist

Before a future website change:

1. Confirm the website repository/path, owner, target domain, and deployment
   authority.
2. Reconcile version, installation commands, capability claims, examples,
   links, accessibility, and security language with the root README and
   release checklist.
3. Run local HTML, link, accessibility, and copy checks.
4. Obtain explicit approval before any deployment or external hosting action.

No website deployment, cloud SDK call, domain change, registry write, release
tag, or publication is implied by this directory. There is no
.openai/hosting.json in this repository.
