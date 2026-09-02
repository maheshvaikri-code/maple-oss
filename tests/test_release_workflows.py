"""Regression coverage for release workflow safety invariants."""

import re
from pathlib import Path

import maple
import tests

REPO = Path(__file__).resolve().parent.parent


def _workflow(name):
    return (REPO / ".github" / "workflows" / name).read_text(encoding="utf-8")


def _action_refs():
    refs = []
    for workflow in (REPO / ".github" / "workflows").glob("*.yml"):
        refs.extend(
            ref
            for ref in re.findall(
                r"uses:\s+([^#\s]+)", workflow.read_text(encoding="utf-8")
            )
            if not ref.startswith("./")
        )
    return refs


def test_release_workflow_is_tag_driven_and_does_not_mutate_main():
    workflow = _workflow("release.yml")

    assert 'tags:\n      - "v*"' in workflow
    assert "workflow_dispatch:" not in workflow
    assert "bump2version" not in workflow
    assert "git push origin main" not in workflow
    assert "Verify tag matches package and changelog" in workflow
    assert "GITHUB_REF_NAME#v" in workflow
    assert "maple.__version__" in workflow
    assert 'Path("CHANGELOG.md")' in workflow
    assert 'gh release create "$RELEASE_TAG"' in workflow
    assert 'gh release create "${{ github.ref_name }}"' not in workflow
    assert "Release tag has an invalid format" in workflow


def test_release_workflow_hands_off_to_publish_workflow():
    workflow = _workflow("release.yml")

    assert "publish-to-pypi:" in workflow
    assert "needs: release-from-tag" in workflow
    assert "uses: ./.github/workflows/publish.yml" in workflow
    assert "target: pypi" in workflow
    assert 'confirmation: "I AUTHORIZE THIS PUBLISH"' in workflow
    assert "release_tag: ${{ github.ref_name }}" in workflow
    assert "source_ref: ${{ github.ref_name }}" in workflow
    assert "secrets: inherit" in workflow


def test_publish_workflow_supports_explicit_pypi_dispatch():
    workflow = _workflow("publish.yml")

    assert "- testpypi" in workflow
    assert "- pypi" in workflow
    assert "inputs.confirmation == 'I AUTHORIZE THIS PUBLISH'" in workflow
    assert "environment: testpypi" in workflow
    assert "environment: pypi" in workflow
    assert "github.event_name == 'release'" in workflow
    assert "github.event_name == 'workflow_dispatch'" in workflow
    assert "github.event_name == 'workflow_call'" in workflow
    assert "inputs.target == 'pypi'" in workflow
    assert "release_tag:" in workflow
    assert "source_ref:" in workflow
    assert "Manual PyPI publication must run from main" in workflow
    assert "Verify release tag matches package and changelog" in workflow


def test_release_asset_upload_treats_release_tag_as_quoted_data():
    workflow = _workflow("publish.yml")

    assert "RELEASE_TAG: ${{ github.event.release.tag_name }}" in workflow
    assert 'gh release upload "$RELEASE_TAG" dist/*' in workflow
    assert "gh release upload ${{ github.ref_name }} dist/*" not in workflow
    assert "Release tag has an invalid format" in workflow


def test_ci_summary_does_not_advertise_stale_version():
    workflow = _workflow("ci.yml")

    assert "MAPLE v1.1.1" not in workflow
    assert "MAPLE release gates" in workflow


def test_all_workflow_actions_are_pinned_to_verified_commits():
    refs = _action_refs()
    expected = {
        "actions/checkout": "11bd71901bbe5b1630ceea73d27597364c9af683",
        "actions/setup-python": "a26af69be951a213d495a4c3e4e4022e16d87065",
        "actions/upload-artifact": "ea165f8d65b6e75b540449e92b4886f43607fa02",
        "actions/download-artifact": "d3f86a106a0bac45b974a628896c90dbdf5c8093",
        "codecov/codecov-action": "0f8570b1a125f4937846a11fcfa3bcd548bd8c97",
        "pypa/gh-action-pypi-publish": "dc37677b2e1c63e2034f94d8a5b11f265b73ba33",
    }

    assert refs
    assert all(re.fullmatch(r"[^@]+@[0-9a-f]{40}", ref) for ref in refs)
    for action, commit in expected.items():
        assert f"{action}@{commit}" in refs


def test_next_release_checklist_is_explicitly_conditional():
    checklist = (REPO / "docs" / "releases" / "v1.1.4.md").read_text(encoding="utf-8")

    assert "CONDITIONAL / NOT PUBLISH-READY" in checklist
    assert "Human’s explicit go for publishing" in checklist
    assert (
        "No tag, registry write, external publication, cloud action, or website update"
        in checklist
    )


def test_core_distribution_manifest_scope_and_version_are_explicit():
    manifest = (REPO / "MANIFEST.in").read_text(encoding="utf-8")
    version = (REPO / "VERSION").read_text(encoding="utf-8").strip()

    assert version == maple.__version__
    assert tests.__version__ == maple.__version__
    assert "recursive-include maple *.py" in manifest
    assert "recursive-include docs" in manifest
    assert "recursive-include examples" in manifest
    assert "recursive-include tests" in manifest
    assert "demo_package" not in manifest
    assert "n8n-integration" not in manifest


def test_project_license_uses_a_setuptools_compatible_file_form():
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")

    assert 'license = {file = "LICENSE"}' in pyproject
    assert (REPO / "LICENSE").is_file()


def _changelog_heading_matches(heading_line: str, version: str) -> bool:
    """Mirror of the verifier embedded in publish.yml.

    Kept in step with that shell-embedded Python deliberately: the release
    path is the one place a mismatch is only discovered at publish time, with
    the tag already pushed.
    """
    heading = heading_line[3:].strip()
    if heading.startswith("Version "):
        heading = heading[8:]
    if heading.startswith("["):
        heading = heading[1:].replace("]", " ", 1)
    heading = heading.strip()
    return heading == version or heading.startswith(version + " ")


def test_changelog_has_a_heading_the_release_verifier_accepts():
    """Regression: normalising headings to Keep a Changelog broke publication.

    `publish.yml` refuses to publish unless CHANGELOG.md carries a heading for
    the version being released. Reformatting `## 2.1.0 - date` into
    `## [2.1.0] - date` left the verifier unable to find it, and the failure
    surfaced only after the tag had been pushed:

        CHANGELOG.md has no heading for version 2.1.0
    """
    version = (REPO / "VERSION").read_text(encoding="utf-8").strip()
    headings = [
        line
        for line in (REPO / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
        if line.startswith("## ")
    ]

    assert any(_changelog_heading_matches(h, version) for h in headings), (
        f"CHANGELOG.md has no heading publish.yml would accept for {version}. "
        f"Headings present: {headings[:4]}"
    )


def test_release_verifier_accepts_every_heading_form_in_use():
    for line, version in [
        ("## [2.1.0] - 2026-09-01", "2.1.0"),
        ("## 2.0.0 - 2026-08-29", "2.0.0"),
        ("## Version 1.1.3 - Downstream integration improvements", "1.1.3"),
        ("## [1.1.3] - August 2026 - Downstream integration improvements", "1.1.3"),
    ]:
        assert _changelog_heading_matches(line, version), line

    # and must not match a different version or the unreleased section
    assert not _changelog_heading_matches("## [Unreleased]", "2.1.0")
    assert not _changelog_heading_matches("## [2.0.0] - 2026-08-29", "2.1.0")


def test_tag_push_grants_the_permissions_the_called_workflow_needs():
    """Regression: the tag-push publish path failed with `startup_failure`.

    The repository's default workflow permission is `read`. publish.yml's
    release-assets job requests `contents: write`, and a called workflow
    cannot exceed what the calling job holds, so GitHub rejected the run
    before creating any job - with no log explaining why.
    """
    release = _workflow("release.yml")
    publish = _workflow("publish.yml")

    assert "uses: ./.github/workflows/publish.yml" in release

    caller = release.split("publish-to-pypi:", 1)[1].split("uses:", 1)[0]
    assert "permissions:" in caller and "contents: write" in caller, (
        "the publish-to-pypi job must grant contents: write, or the reusable "
        "workflow call fails at startup"
    )

    # the grant has to cover what the called workflow actually asks for
    assert "contents: write" in publish
