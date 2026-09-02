"""Contract tests for release-critical workflow failure semantics."""

from pathlib import Path


WORKFLOW_ROOT = Path(__file__).parents[1] / ".github" / "workflows"


def _workflow(name: str) -> str:
    return (WORKFLOW_ROOT / name).read_text(encoding="utf-8")


def test_quality_workflows_do_not_mask_required_checks() -> None:
    # quality.yml and test.yml were folded into ci.yml (ADR-158): they fired on
    # the same triggers and re-ran the same matrix, so every push paid for the
    # full suite roughly twice.
    content = _workflow("ci.yml")
    assert "contents: read" in content
    assert "continue-on-error: true" not in content


def test_ci_summary_cannot_report_success_over_a_failed_job() -> None:
    """The summary job runs with `if: always()`.

    Without an explicit gate it would report success even when lint, test, or
    build failed, and branch protection requiring "CI Summary" would wave a red
    build through. Regression guard for that hole (ADR-158).
    """
    content = _workflow("ci.yml")

    assert "needs.lint.result != 'success'" in content
    assert "needs.test.result != 'success'" in content
    assert "needs.build.result != 'success'" in content
    assert "exit 1" in content


def test_ci_retains_the_checks_absorbed_from_quality_workflow() -> None:
    """Folding quality.yml in must not quietly drop what it enforced."""
    content = _workflow("ci.yml")

    assert "black --check" in content
    assert "isort --check-only" in content
    assert "tools/check_license_headers.py" in content
    assert "tools/check_readme_sections.py" in content


def test_ci_lint_does_not_suppress_defect_detecting_rules() -> None:
    """F401/F811/F841 catch real defects and the tree is clean without them.

    Asserted against the --extend-ignore values specifically, not the file
    text: the workflow explains in a comment *why* those codes are not
    suppressed, and a naive substring search would match the explanation.
    """
    content = _workflow("ci.yml")

    suppressed = [
        line.split("--extend-ignore=", 1)[1].split()[0].rstrip("\\")
        for line in content.splitlines()
        if "--extend-ignore=" in line
    ]
    assert suppressed, "expected at least one flake8 invocation"
    for codes in suppressed:
        for rule in ("F401", "F811", "F841"):
            assert rule not in codes.split(","), f"{rule} suppressed in: {codes}"


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
