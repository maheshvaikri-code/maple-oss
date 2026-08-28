"""Regression coverage for release workflow safety invariants."""

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _workflow(name):
    return (REPO / ".github" / "workflows" / name).read_text(encoding="utf-8")


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


def test_publish_workflow_requires_confirmation_for_testpypi():
    workflow = _workflow("publish.yml")

    assert "github.event.inputs.confirmation == 'I AUTHORIZE THIS PUBLISH'" in workflow
    assert "environment: testpypi" in workflow
    assert "github.event_name == 'release'" in workflow
    assert "github.event.inputs.target == 'pypi'" not in workflow
    assert "Verify release tag matches package and changelog" in workflow


def test_ci_summary_does_not_advertise_stale_version():
    workflow = _workflow("ci.yml")

    assert "MAPLE v1.1.1" not in workflow
    assert "MAPLE release gates" in workflow


def test_next_release_checklist_is_explicitly_conditional():
    checklist = (REPO / "docs" / "releases" / "v1.1.4.md").read_text(encoding="utf-8")

    assert "CONDITIONAL / NOT PUBLISH-READY" in checklist
    assert "Human’s explicit go for publishing" in checklist
    assert (
        "No tag, registry write, external publication, cloud action, or website update"
        in checklist
    )
