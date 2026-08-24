"""Tests for deterministic agent evaluation."""

from maple.autonomy.evaluation import EvalCase, EvalObservation, EvaluationHarness
from maple.core.result import Result


def test_evaluation_checks_output_schema_and_tool_trajectory():
    cases = [
        EvalCase(
            "answer",
            {"question": "2+2"},
            expected_output={"answer": 4},
            output_schema={
                "type": "object",
                "required": ["answer"],
                "properties": {"answer": {"type": "integer"}},
            },
            expected_tool_names=("calculator",),
        )
    ]

    report = EvaluationHarness().run(
        cases,
        lambda value: EvalObservation({"answer": 4}, ("calculator",)),
    )

    assert report.is_ok()
    assert report.unwrap().passed == 1
    assert report.unwrap().pass_rate == 1.0


def test_evaluation_returns_case_failures_without_aborting_suite():
    cases = [
        EvalCase("pass", "one", expected_output="ONE"),
        EvalCase("fail", "two", expected_output="TWO"),
        EvalCase("runner-error", "three", expected_output="THREE"),
    ]

    def runner(value):
        if value == "three":
            return Result.err({"errorType": "MODEL_ERROR", "message": "unavailable"})
        return value.upper() if value == "one" else "wrong"

    report = EvaluationHarness().run(cases, runner)

    assert report.is_ok()
    results = report.unwrap().results
    assert report.unwrap().passed == 1
    assert results[1].errors[0]["errorType"] == "EVAL_OUTPUT_MISMATCH"
    assert results[2].errors[0]["errorType"] == "EVAL_RUNNER_ERROR"


def test_evaluation_redacts_actual_output_and_bounds_case_count():
    harness = EvaluationHarness(max_cases=1)
    case = EvalCase("secret", "input", expected_output={"status": "ok"})

    report = harness.run(
        [case],
        lambda value: {"status": "wrong", "api_key": "hidden"},
    )
    limited = harness.run([case, case], lambda value: {"status": "ok"})

    assert report.is_ok()
    assert report.unwrap().results[0].actual_output["api_key"] == "[REDACTED]"
    assert limited.is_err()
    assert limited.unwrap_err()["errorType"] == "EVAL_CASE_LIMIT"


def test_invalid_case_and_runner_exception_fail_closed():
    invalid_case = EvalCase("no-expectation", "input")
    invalid = EvaluationHarness().run([invalid_case], lambda value: value)
    exception = EvaluationHarness().run(
        [EvalCase("exception", "input", expected_output="ok")],
        lambda value: (_ for _ in ()).throw(RuntimeError("secret details")),
    )

    assert invalid.is_err()
    assert invalid.unwrap_err()["errorType"] == "EVAL_CASE_INVALID"
    assert exception.is_ok()
    assert (
        exception.unwrap().results[0].errors[0]["errorType"] == "EVAL_RUNNER_EXCEPTION"
    )
