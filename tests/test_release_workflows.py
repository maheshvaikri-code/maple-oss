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
            re.findall(r"uses:\s+([^#\s]+)", workflow.read_text(encoding="utf-8"))
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


def test_publish_workflow_requires_confirmation_for_testpypi():
    workflow = _workflow("publish.yml")

    assert "github.event.inputs.confirmation == 'I AUTHORIZE THIS PUBLISH'" in workflow
    assert "environment: testpypi" in workflow
    assert "github.event_name == 'release'" in workflow
    assert "github.event.inputs.target == 'pypi'" not in workflow
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
