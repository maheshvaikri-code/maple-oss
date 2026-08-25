"""Deterministic local evaluation contracts for MAPLE agents."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from ..core.result import Result
from .contracts import validate_json_schema
from .events import RedactionPolicy
from .retrieval import RetrievalHit, VectorRetrievalHit

Error = Dict[str, Any]
_UNSET = object()


@dataclass(frozen=True)
class EvalCase:
    """One golden evaluation case with output and/or trajectory expectations."""

    case_id: str
    input: Any
    expected_output: Any = _UNSET
    output_schema: Optional[Mapping[str, Any]] = None
    expected_tool_names: Tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> Optional[Error]:
        if (
            not isinstance(self.case_id, str)
            or not self.case_id
            or len(self.case_id) > 256
        ):
            return {
                "errorType": "EVAL_CASE_INVALID",
                "message": "case_id must be bounded and non-empty.",
            }
        if (
            self.expected_output is _UNSET
            and self.output_schema is None
            and not self.expected_tool_names
        ):
            return {
                "errorType": "EVAL_CASE_INVALID",
                "message": "case must define an output or trajectory expectation.",
            }
        if not isinstance(self.expected_tool_names, tuple) or not all(
            isinstance(name, str) and name for name in self.expected_tool_names
        ):
            return {
                "errorType": "EVAL_CASE_INVALID",
                "message": "expected_tool_names must be a tuple of names.",
            }
        try:
            json.dumps(self.metadata, allow_nan=False)
        except (TypeError, ValueError):
            return {
                "errorType": "EVAL_CASE_INVALID",
                "message": "case metadata must be JSON serializable.",
            }
        return None


@dataclass(frozen=True)
class RetrievalEvalCase:
    """One deterministic source-coverage evaluation case."""

    case_id: str
    query: str
    expected_source_uris: Tuple[str, ...]
    min_precision: float = 0.0
    min_recall: float = 1.0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> Optional[Error]:
        if (
            not isinstance(self.case_id, str)
            or not self.case_id
            or len(self.case_id) > 256
        ):
            return {
                "errorType": "RAG_CASE_INVALID",
                "message": "case_id must be bounded and non-empty.",
            }
        if (
            not isinstance(self.query, str)
            or not self.query.strip()
            or len(self.query.encode("utf-8")) > 16_384
        ):
            return {
                "errorType": "RAG_CASE_INVALID",
                "message": "query must be non-empty and bounded.",
            }
        if (
            not isinstance(self.expected_source_uris, tuple)
            or not self.expected_source_uris
        ):
            return {
                "errorType": "RAG_CASE_INVALID",
                "message": "expected_source_uris must be a non-empty tuple.",
            }
        for uri in self.expected_source_uris:
            if (
                not isinstance(uri, str)
                or not uri
                or len(uri) > 2_048
                or any(ord(char) < 32 for char in uri)
            ):
                return {
                    "errorType": "RAG_CASE_INVALID",
                    "message": "expected source URIs must be bounded text.",
                }
        if len(set(self.expected_source_uris)) != len(self.expected_source_uris):
            return {
                "errorType": "RAG_CASE_INVALID",
                "message": "expected_source_uris must not contain duplicates.",
            }
        for name, value in (
            ("min_precision", self.min_precision),
            ("min_recall", self.min_recall),
        ):
            if (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or value < 0.0
                or value > 1.0
            ):
                return {
                    "errorType": "RAG_CASE_INVALID",
                    "message": f"{name} must be between 0 and 1.",
                }
        try:
            json.dumps(self.metadata, allow_nan=False)
        except (TypeError, ValueError):
            return {
                "errorType": "RAG_CASE_INVALID",
                "message": "case metadata must be JSON serializable.",
            }
        return None


@dataclass(frozen=True)
class EvalObservation:
    """Optional runner result carrying output and ordered tool names."""

    output: Any
    tool_names: Tuple[str, ...] = ()


@dataclass(frozen=True)
class EvalResult:
    """Outcome for one evaluation case."""

    case_id: str
    passed: bool
    score: float
    actual_output: Any = None
    errors: Tuple[Error, ...] = ()
    duration_ms: float = 0.0


@dataclass(frozen=True)
class EvalReport:
    """Aggregate evaluation outcome."""

    results: Tuple[EvalResult, ...]

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(1 for result in self.results if result.passed)

    @property
    def failed(self) -> int:
        return self.total - self.passed

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0

    def as_dict(self) -> Dict[str, Any]:
        """Return a JSON-compatible bounded report mapping."""
        return {
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "pass_rate": self.pass_rate,
            "results": [
                {
                    "case_id": result.case_id,
                    "passed": result.passed,
                    "score": result.score,
                    "actual_output": result.actual_output,
                    "errors": list(result.errors),
                    "duration_ms": result.duration_ms,
                }
                for result in self.results
            ],
        }


class EvaluationHarness:
    """Run deterministic cases against a local callable or scripted agent."""

    def __init__(
        self,
        *,
        max_cases: int = 1_000,
        max_value_bytes: int = 1_048_576,
        max_retrieval_hits: int = 1_000,
        redaction: Optional[RedactionPolicy] = None,
    ) -> None:
        self.max_cases = max_cases
        self.max_value_bytes = max_value_bytes
        self.max_retrieval_hits = max_retrieval_hits
        self.redaction = redaction or RedactionPolicy()

    def _safe_output(self, value: Any) -> Any:
        redacted = self.redaction.redact(value)
        if redacted.is_err():
            return None
        try:
            encoded = json.dumps(redacted.unwrap(), allow_nan=False).encode("utf-8")
        except (TypeError, ValueError, OverflowError):
            return None
        if len(encoded) > self.max_value_bytes:
            return None
        return redacted.unwrap()

    def run(
        self,
        cases: Sequence[EvalCase],
        runner: Callable[[Any], Any],
    ) -> Result[EvalReport, Error]:
        """Run cases, returning per-case failures instead of aborting the set."""
        if (
            not isinstance(self.max_cases, int)
            or isinstance(self.max_cases, bool)
            or self.max_cases <= 0
        ):
            return Result.err(
                {
                    "errorType": "EVAL_CONFIG_INVALID",
                    "message": "max_cases must be positive.",
                }
            )
        if (
            not isinstance(self.max_value_bytes, int)
            or isinstance(self.max_value_bytes, bool)
            or self.max_value_bytes <= 0
        ):
            return Result.err(
                {
                    "errorType": "EVAL_CONFIG_INVALID",
                    "message": "max_value_bytes must be positive.",
                }
            )
        if not callable(runner):
            return Result.err(
                {
                    "errorType": "EVAL_INPUT_INVALID",
                    "message": "runner must be callable.",
                }
            )
        if len(cases) > self.max_cases:
            return Result.err(
                {
                    "errorType": "EVAL_CASE_LIMIT",
                    "message": "case count exceeds the limit.",
                }
            )

        results: List[EvalResult] = []
        for case in cases:
            case_error = case.validate()
            if case_error is not None:
                return Result.err(case_error)
            started = time.perf_counter()
            errors: List[Error] = []
            actual: Any = None
            tool_names: Tuple[str, ...] = ()
            try:
                observation = runner(case.input)
                if isinstance(observation, Result):
                    if observation.is_err():
                        errors.append(
                            {
                                "errorType": "EVAL_RUNNER_ERROR",
                                "message": "runner returned an error.",
                            }
                        )
                    else:
                        observation = observation.unwrap()
                if not errors:
                    if isinstance(observation, EvalObservation):
                        actual = observation.output
                        tool_names = observation.tool_names
                    else:
                        actual = observation
                    expected_checks = 0
                    passed_checks = 0
                    if case.expected_output is not _UNSET:
                        expected_checks += 1
                        if actual == case.expected_output:
                            passed_checks += 1
                        else:
                            errors.append(
                                {
                                    "errorType": "EVAL_OUTPUT_MISMATCH",
                                    "message": (
                                        "actual output did not match expected output."
                                    ),
                                }
                            )
                    if case.output_schema is not None:
                        expected_checks += 1
                        schema_result = validate_json_schema(actual, case.output_schema)
                        if schema_result.is_ok():
                            passed_checks += 1
                        else:
                            errors.append(
                                {
                                    "errorType": "EVAL_SCHEMA_MISMATCH",
                                    "message": (
                                        "actual output failed the expected schema."
                                    ),
                                }
                            )
                    if case.expected_tool_names:
                        expected_checks += 1
                        if tuple(tool_names) == tuple(case.expected_tool_names):
                            passed_checks += 1
                        else:
                            errors.append(
                                {
                                    "errorType": "EVAL_TRAJECTORY_MISMATCH",
                                    "message": (
                                        "tool trajectory did not match expected names."
                                    ),
                                }
                            )
                    score = passed_checks / expected_checks if expected_checks else 0.0
                else:
                    score = 0.0
            except Exception as exc:
                errors.append(
                    {
                        "errorType": "EVAL_RUNNER_EXCEPTION",
                        "message": "runner raised an exception.",
                        "details": {"exception": type(exc).__name__},
                    }
                )
                score = 0.0
            results.append(
                EvalResult(
                    case_id=case.case_id,
                    passed=not errors,
                    score=score,
                    actual_output=self._safe_output(actual),
                    errors=tuple(errors),
                    duration_ms=(time.perf_counter() - started) * 1000,
                )
            )
        return Result.ok(EvalReport(results=tuple(results)))

    def run_retrieval(
        self,
        cases: Sequence[RetrievalEvalCase],
        runner: Callable[[str], Any],
    ) -> Result[EvalReport, Error]:
        """Evaluate source precision/recall for lexical or vector retrieval."""
        if (
            not isinstance(self.max_cases, int)
            or isinstance(self.max_cases, bool)
            or self.max_cases <= 0
        ):
            return Result.err(
                {
                    "errorType": "EVAL_CONFIG_INVALID",
                    "message": "max_cases must be positive.",
                }
            )
        if (
            not isinstance(self.max_value_bytes, int)
            or isinstance(self.max_value_bytes, bool)
            or self.max_value_bytes <= 0
        ):
            return Result.err(
                {
                    "errorType": "EVAL_CONFIG_INVALID",
                    "message": "max_value_bytes must be positive.",
                }
            )
        if (
            not isinstance(self.max_retrieval_hits, int)
            or isinstance(self.max_retrieval_hits, bool)
            or self.max_retrieval_hits <= 0
        ):
            return Result.err(
                {
                    "errorType": "EVAL_CONFIG_INVALID",
                    "message": "max_retrieval_hits must be positive.",
                }
            )
        if not callable(runner):
            return Result.err(
                {
                    "errorType": "EVAL_INPUT_INVALID",
                    "message": "runner must be callable.",
                }
            )
        if len(cases) > self.max_cases:
            return Result.err(
                {
                    "errorType": "EVAL_CASE_LIMIT",
                    "message": "case count exceeds the limit.",
                }
            )

        results: List[EvalResult] = []
        for case in cases:
            case_error = case.validate()
            if case_error is not None:
                return Result.err(case_error)
            started = time.perf_counter()
            errors: List[Error] = []
            actual: Any = None
            score = 0.0
            try:
                observation = runner(case.query)
                if isinstance(observation, Result):
                    if observation.is_err():
                        errors.append(
                            {
                                "errorType": "RAG_RUNNER_ERROR",
                                "message": "retrieval runner returned an error.",
                            }
                        )
                    else:
                        observation = observation.unwrap()
                if not errors:
                    if not isinstance(observation, (list, tuple)):
                        errors.append(
                            {
                                "errorType": "RAG_OBSERVATION_INVALID",
                                "message": (
                                    "retrieval runner must return a hit sequence."
                                ),
                            }
                        )
                    else:
                        if len(observation) > self.max_retrieval_hits:
                            errors.append(
                                {
                                    "errorType": "RAG_HIT_LIMIT",
                                    "message": "retrieval hit count exceeds the limit.",
                                }
                            )
                        retrieved_uris: List[str] = []
                        seen_uris = set()
                        for hit in observation:
                            if errors:
                                break
                            if not isinstance(hit, (RetrievalHit, VectorRetrievalHit)):
                                errors.append(
                                    {
                                        "errorType": "RAG_OBSERVATION_INVALID",
                                        "message": (
                                            "retrieval runner returned an unknown "
                                            "hit type."
                                        ),
                                    }
                                )
                                break
                            uri = hit.chunk.source.uri
                            if (
                                not isinstance(uri, str)
                                or not uri
                                or len(uri) > 2_048
                                or any(ord(char) < 32 for char in uri)
                            ):
                                errors.append(
                                    {
                                        "errorType": "RAG_OBSERVATION_INVALID",
                                        "message": (
                                            "retrieval hit source URI is invalid."
                                        ),
                                    }
                                )
                                break
                            if uri not in seen_uris:
                                seen_uris.add(uri)
                                retrieved_uris.append(uri)
                        if not errors:
                            expected = set(case.expected_source_uris)
                            matched = expected.intersection(seen_uris)
                            precision = (
                                len(matched) / len(seen_uris) if seen_uris else 0.0
                            )
                            recall = len(matched) / len(expected)
                            score = (
                                2.0 * precision * recall / (precision + recall)
                                if precision + recall
                                else 0.0
                            )
                            actual = {
                                "retrieved_source_uris": retrieved_uris,
                                "matched_source_uris": sorted(matched),
                                "precision": precision,
                                "recall": recall,
                                "f1": score,
                            }
                            if precision < case.min_precision:
                                errors.append(
                                    {
                                        "errorType": "RAG_PRECISION_LOW",
                                        "message": (
                                            "retrieved source precision was below "
                                            "the threshold."
                                        ),
                                    }
                                )
                            if recall < case.min_recall:
                                errors.append(
                                    {
                                        "errorType": "RAG_RECALL_LOW",
                                        "message": (
                                            "retrieved source recall was below the "
                                            "threshold."
                                        ),
                                    }
                                )
            except Exception as exc:
                errors.append(
                    {
                        "errorType": "RAG_RUNNER_EXCEPTION",
                        "message": "retrieval runner raised an exception.",
                        "details": {"exception": type(exc).__name__},
                    }
                )
            results.append(
                EvalResult(
                    case_id=case.case_id,
                    passed=not errors,
                    score=score,
                    actual_output=self._safe_output(actual),
                    errors=tuple(errors),
                    duration_ms=(time.perf_counter() - started) * 1000,
                )
            )
        return Result.ok(EvalReport(results=tuple(results)))
