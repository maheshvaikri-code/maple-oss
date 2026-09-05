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


class TestTheNatsGate:
    """The NATS transport is the only part of MAPLE whose behaviour is not
    exercised on a developer machine - no nats-py, no server. That is how it
    came to be described rather than measured (ADR-161), so the one place it
    runs has to be a real gate rather than an informational job.
    """

    def _ci(self):
        import yaml

        return yaml.safe_load(_workflow("ci.yml"))

    def test_a_live_server_job_exists(self):
        jobs = self._ci()["jobs"]
        assert "nats" in jobs, "the only job that runs NATS code is gone"
        assert "nats" in jobs["nats"].get("services", {}), (
            "the job no longer starts a NATS service container, so it cannot "
            "be measuring anything"
        )

    def test_the_summary_gates_on_it(self):
        """A job nothing gates on is decoration."""
        summary = self._ci()["jobs"]["summary"]
        assert "nats" in summary["needs"]

        condition = summary["steps"][-1]["if"]
        assert (
            "needs.nats.result != 'success'" in condition
        ), "CI Summary would report success over a failed NATS job"

    def test_a_skipped_run_is_treated_as_a_failure(self):
        """Skipping is the failure mode that looks like success here: no
        server means the tests pass by not running."""
        steps = self._ci()["jobs"]["nats"]["steps"]
        guard = [s for s in steps if "skipped" in str(s.get("name", "")).lower()]
        assert guard, "nothing checks whether the NATS tests actually ran"
        assert "junitxml" in " ".join(
            str(s.get("run", "")) for s in steps
        ), "without a machine-readable result the guard cannot count skips"

    def test_the_marker_is_deselected_by_default(self):
        """Local runs stay hermetic; the suite is opt-in via -m nats."""
        pyproject = (WORKFLOW_ROOT.parents[1] / "pyproject.toml").read_text(
            encoding="utf-8"
        )
        assert "not nats" in pyproject
        assert "nats: needs a live NATS server" in pyproject
