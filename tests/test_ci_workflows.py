"""Contract tests for release-critical workflow failure semantics."""

from pathlib import Path


WORKFLOW_ROOT = Path(__file__).parents[1] / ".github" / "workflows"


def _workflow(name: str) -> str:
    return (WORKFLOW_ROOT / name).read_text(encoding="utf-8")


def test_quality_workflows_do_not_mask_required_checks() -> None:
    for name in ("ci.yml", "quality.yml"):
        content = _workflow(name)
        assert "contents: read" in content
        assert "continue-on-error: true" not in content


def test_security_workflow_fails_after_recording_audit_reports() -> None:
    content = _workflow("security.yml")

    assert "pip-audit --format=json --output=audit-report.json" in content
    assert "bandit -r maple/ -f json -o bandit-report.json" in content
    assert "if: always()" in content
    assert "pip-audit || true" not in content
    assert "bandit -r maple/ -ll || true" not in content


def test_dependency_audit_is_gating_but_outdated_inventory_is_informational() -> None:
    content = _workflow("dependencies.yml")

    assert "contents: read" in content
    assert "contents: write" not in content
    assert "pull-requests: write" not in content
    assert "pip list --outdated --format=json > outdated.json || true" in content
    assert "pip-audit\n" in content
    assert "pip-audit || true" not in content
