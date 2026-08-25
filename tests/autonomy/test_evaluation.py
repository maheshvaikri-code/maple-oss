"""Tests for deterministic agent evaluation."""

import pytest

from maple.autonomy.evaluation import (
    EvalCase,
    EvalObservation,
    EvaluationHarness,
    GroundednessEvalCase,
    GroundednessObservation,
    GroundingSource,
    RetrievalEvalCase,
)
from maple.autonomy.retrieval import (
    Document,
    DocumentChunk,
    InMemoryLexicalRetriever,
    SourceRef,
    VectorRetrievalHit,
)
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


def test_retrieval_evaluation_measures_source_precision_recall_and_f1():
    retriever = InMemoryLexicalRetriever()
    retriever.add_document(
        Document(
            "doc-one",
            "MAPLE provides resource aware messaging",
            SourceRef("urn:source:one"),
        )
    )
    retriever.add_document(
        Document(
            "doc-two",
            "A different topic with no matching terms",
            SourceRef("urn:source:two"),
        )
    )
    case = RetrievalEvalCase(
        "source-recall",
        "resource messaging",
        ("urn:source:one",),
        min_precision=1.0,
        min_recall=1.0,
    )

    report = EvaluationHarness().run_retrieval(
        [case], lambda query: retriever.search(query).unwrap()
    )

    assert report.is_ok()
    result = report.unwrap().results[0]
    assert result.passed
    assert result.score == 1.0
    assert result.actual_output["matched_source_uris"] == ["urn:source:one"]


def test_retrieval_evaluation_accepts_vector_hits_and_reports_low_recall():
    source = SourceRef("urn:source:vector")
    chunk = DocumentChunk(
        "doc:0",
        "doc",
        0,
        "vector result",
        0,
        13,
        source,
    )
    case = RetrievalEvalCase(
        "vector-recall",
        "vector query",
        ("urn:source:vector", "urn:source:missing"),
        min_recall=1.0,
    )

    report = EvaluationHarness().run_retrieval(
        [case], lambda query: [VectorRetrievalHit(chunk, 1.0)]
    )

    assert report.is_ok()
    result = report.unwrap().results[0]
    assert not result.passed
    assert result.score == pytest.approx(2 / 3)
    assert result.errors[0]["errorType"] == "RAG_RECALL_LOW"


def test_retrieval_evaluation_isolates_malformed_and_raising_runners():
    cases = [
        RetrievalEvalCase("pass", "good", ("urn:source:one",)),
        RetrievalEvalCase("malformed", "bad", ("urn:source:one",)),
        RetrievalEvalCase("exception", "crash", ("urn:source:one",)),
    ]
    source = SourceRef("urn:source:one")
    chunk = DocumentChunk("doc:0", "doc", 0, "good", 0, 4, source)

    def runner(query):
        if query == "bad":
            return {"not": "hits"}
        if query == "crash":
            raise RuntimeError("runner details")
        return [VectorRetrievalHit(chunk, 1.0)]

    report = EvaluationHarness().run_retrieval(cases, runner)

    assert report.is_ok()
    assert report.unwrap().passed == 1
    assert report.unwrap().results[1].errors[0]["errorType"] == (
        "RAG_OBSERVATION_INVALID"
    )
    assert report.unwrap().results[2].errors[0]["errorType"] == (
        "RAG_RUNNER_EXCEPTION"
    )


def test_retrieval_evaluation_rejects_invalid_golden_cases():
    invalid = RetrievalEvalCase(
        "invalid",
        "query",
        ("urn:source:one", "urn:source:one"),
        min_precision=1.1,
    )

    result = EvaluationHarness().run_retrieval([invalid], lambda query: [])

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "RAG_CASE_INVALID"


def test_retrieval_evaluation_rejects_unhashable_golden_uri_without_raising():
    invalid = RetrievalEvalCase("invalid-uri", "query", ([],))

    result = EvaluationHarness().run_retrieval([invalid], lambda query: [])

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "RAG_CASE_INVALID"


def test_retrieval_evaluation_bounds_runner_hit_count():
    source = SourceRef("urn:source:bounded")
    chunk = DocumentChunk("doc:0", "doc", 0, "bounded", 0, 7, source)
    hit = VectorRetrievalHit(chunk, 1.0)
    case = RetrievalEvalCase("bounded", "query", ("urn:source:bounded",))

    report = EvaluationHarness(max_retrieval_hits=1).run_retrieval(
        [case], lambda query: [hit, hit]
    )

    assert report.is_ok()
    assert report.unwrap().results[0].errors[0]["errorType"] == "RAG_HIT_LIMIT"


def test_groundedness_evaluation_scores_supported_claims_deterministically():
    case = GroundednessEvalCase(
        "grounded",
        "What does MAPLE provide?",
        (
            GroundingSource(
                "urn:source:maple",
                "MAPLE provides resource aware messaging for agents.",
            ),
        ),
    )

    report = EvaluationHarness().run_groundedness(
        [case],
        lambda query: GroundednessObservation(
            "MAPLE provides resource aware messaging for agents."
        ),
    )

    assert report.is_ok()
    result = report.unwrap().results[0]
    assert result.passed
    assert result.score == 1.0
    assert result.actual_output["evidence_source_uris"] == ["urn:source:maple"]


def test_groundedness_evaluation_reports_low_support_without_aborting():
    case = GroundednessEvalCase(
        "mixed",
        "What is supported?",
        (GroundingSource("urn:source:one", "MAPLE supports typed workflows."),),
        min_supported_ratio=1.0,
        min_claim_overlap=0.75,
    )

    report = EvaluationHarness().run_groundedness(
        [case],
        lambda query: GroundednessObservation(
            "MAPLE supports typed workflows. MAPLE has a browser sandbox."
        ),
    )

    assert report.is_ok()
    result = report.unwrap().results[0]
    assert not result.passed
    assert result.score == pytest.approx(0.5)
    assert result.errors[0]["errorType"] == "GROUNDING_SUPPORT_LOW"


def test_groundedness_evaluation_isolates_malformed_and_raising_runners():
    source = GroundingSource("urn:source:one", "MAPLE supports typed workflows.")
    cases = [
        GroundednessEvalCase("pass", "good", (source,)),
        GroundednessEvalCase("malformed", "bad", (source,)),
        GroundednessEvalCase("exception", "crash", (source,)),
    ]

    def runner(query):
        if query == "bad":
            return {"answer": "not typed"}
        if query == "crash":
            raise RuntimeError("runner details")
        return GroundednessObservation("MAPLE supports typed workflows.")

    report = EvaluationHarness().run_groundedness(cases, runner)

    assert report.is_ok()
    assert report.unwrap().passed == 1
    assert report.unwrap().results[1].errors[0]["errorType"] == (
        "GROUNDING_OBSERVATION_INVALID"
    )
    assert report.unwrap().results[2].errors[0]["errorType"] == (
        "GROUNDING_RUNNER_EXCEPTION"
    )


def test_groundedness_evaluation_rejects_duplicate_sources_and_non_finite_threshold():
    source = GroundingSource("urn:source:one", "MAPLE supports typed workflows.")
    duplicate_sources = GroundednessEvalCase(
        "invalid",
        "query",
        (source, source),
    )
    non_finite_threshold = GroundednessEvalCase(
        "invalid-threshold",
        "query",
        (source,),
        min_supported_ratio=float("nan"),
    )

    duplicate_result = EvaluationHarness().run_groundedness(
        [duplicate_sources],
        lambda query: GroundednessObservation("MAPLE supports workflows."),
    )
    threshold_result = EvaluationHarness().run_groundedness(
        [non_finite_threshold],
        lambda query: GroundednessObservation("MAPLE supports workflows."),
    )

    assert duplicate_result.is_err()
    assert duplicate_result.unwrap_err()["errorType"] == "GROUNDING_CASE_INVALID"
    assert threshold_result.is_err()
    assert threshold_result.unwrap_err()["errorType"] == "GROUNDING_CASE_INVALID"


def test_groundedness_evaluation_handles_runner_errors_and_answer_bounds():
    source = GroundingSource("urn:source:one", "MAPLE supports workflows.")
    error_case = GroundednessEvalCase("error", "error", (source,))
    normal_harness = EvaluationHarness()
    small_harness = EvaluationHarness(max_value_bytes=32)

    runner_error = normal_harness.run_groundedness(
        [error_case],
        lambda query: Result.err({"errorType": "MODEL_ERROR", "message": "offline"}),
    )
    oversized = small_harness.run_groundedness(
        [error_case],
        lambda query: GroundednessObservation("MAPLE supports workflows."),
    )

    assert runner_error.is_ok()
    assert runner_error.unwrap().results[0].errors[0]["errorType"] == (
        "GROUNDING_RUNNER_ERROR"
    )
    assert oversized.is_ok()
    assert oversized.unwrap().results[0].errors[0]["errorType"] == (
        "GROUNDING_CASE_SIZE"
    )
