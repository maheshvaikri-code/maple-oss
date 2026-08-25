"""Deterministic local evaluation contracts for MAPLE agents."""

from __future__ import annotations

import json
import math
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from ..core.result import Result
from .contracts import validate_json_schema
from .events import RedactionPolicy
from .retrieval import RetrievalHit, VectorRetrievalHit

Error = Dict[str, Any]
_UNSET = object()
_GROUNDING_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)
_GROUNDING_MAX_CLAIMS = 256
_GROUNDING_MAX_SOURCES = 256
_GROUNDING_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "that",
        "the",
        "to",
        "was",
        "were",
        "with",
    }
)


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
class GroundingSource:
    """Bounded source text used by deterministic groundedness evaluation."""

    uri: str
    text: str

    def validate(self) -> Optional[Error]:
        if (
            not isinstance(self.uri, str)
            or not self.uri
            or len(self.uri) > 2_048
            or any(ord(char) < 32 for char in self.uri)
        ):
            return {
                "errorType": "GROUNDING_CASE_INVALID",
                "message": "source URI must be bounded text.",
            }
        if (
            not isinstance(self.text, str)
            or not self.text.strip()
            or len(self.text.encode("utf-8")) > 262_144
        ):
            return {
                "errorType": "GROUNDING_CASE_INVALID",
                "message": "source text must be non-empty and bounded.",
            }
        return None


@dataclass(frozen=True)
class GroundednessEvalCase:
    """One lexical claim-support evaluation case."""

    case_id: str
    query: str
    sources: Tuple[GroundingSource, ...]
    min_supported_ratio: float = 1.0
    min_claim_overlap: float = 0.5
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> Optional[Error]:
        if (
            not isinstance(self.case_id, str)
            or not self.case_id
            or len(self.case_id) > 256
        ):
            return {
                "errorType": "GROUNDING_CASE_INVALID",
                "message": "case_id must be bounded and non-empty.",
            }
        if (
            not isinstance(self.query, str)
            or not self.query.strip()
            or len(self.query.encode("utf-8")) > 16_384
        ):
            return {
                "errorType": "GROUNDING_CASE_INVALID",
                "message": "query must be non-empty and bounded.",
            }
        if (
            not isinstance(self.sources, tuple)
            or not self.sources
            or len(self.sources) > _GROUNDING_MAX_SOURCES
        ):
            return {
                "errorType": "GROUNDING_CASE_INVALID",
                "message": "sources must be a non-empty bounded tuple.",
            }
        source_uris = []
        for source in self.sources:
            if not isinstance(source, GroundingSource):
                return {
                    "errorType": "GROUNDING_CASE_INVALID",
                    "message": "sources must contain GroundingSource values.",
                }
            source_error = source.validate()
            if source_error:
                return source_error
            source_uris.append(source.uri)
        if len(set(source_uris)) != len(source_uris):
            return {
                "errorType": "GROUNDING_CASE_INVALID",
                "message": "source URIs must not contain duplicates.",
            }
        for name, value in (
            ("min_supported_ratio", self.min_supported_ratio),
            ("min_claim_overlap", self.min_claim_overlap),
        ):
            is_number = isinstance(value, (int, float)) and not isinstance(value, bool)
            if is_number:
                try:
                    finite = math.isfinite(value)
                except OverflowError:
                    finite = False
            else:
                finite = False
            if (
                not is_number
                or not finite
                or value < 0.0
                or value > 1.0
            ):
                return {
                    "errorType": "GROUNDING_CASE_INVALID",
                    "message": f"{name} must be a finite number between 0 and 1.",
                }
        try:
            json.dumps(self.metadata, allow_nan=False)
        except (TypeError, ValueError):
            return {
                "errorType": "GROUNDING_CASE_INVALID",
                "message": "case metadata must be JSON serializable.",
            }
        return None


@dataclass(frozen=True)
class EvalObservation:
    """Optional runner result carrying output and ordered tool names."""

    output: Any
    tool_names: Tuple[str, ...] = ()


@dataclass(frozen=True)
class GroundednessObservation:
    """Runner result for one generated answer."""

    answer: str


def _grounding_terms(text: str) -> set:
    return {
        token.casefold()
        for token in _GROUNDING_TOKEN.findall(text)
        if token.casefold() not in _GROUNDING_STOPWORDS
    }


def _grounding_claims(answer: str) -> List[str]:
    return [
        claim.strip()
        for claim in re.split(r"(?<=[.!?])\s+|\r?\n+", answer.strip())
        if claim.strip()
    ]


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

    def run_groundedness(
        self,
        cases: Sequence[GroundednessEvalCase],
        runner: Callable[[str], Any],
    ) -> Result[EvalReport, Error]:
        """Score bounded lexical claim support against supplied source text.

        This is a deterministic lexical proxy. It does not establish
        semantic entailment, factuality, or citation faithfulness.
        """
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
            score = 0.0
            try:
                encoded_case = json.dumps(
                    {
                        "query": case.query,
                        "sources": [
                            {"uri": source.uri, "text": source.text}
                            for source in case.sources
                        ],
                    },
                    ensure_ascii=False,
                    allow_nan=False,
                    separators=(",", ":"),
                ).encode("utf-8")
                if len(encoded_case) > self.max_value_bytes:
                    errors.append(
                        {
                            "errorType": "GROUNDING_CASE_SIZE",
                            "message": "grounding case exceeds the value byte limit.",
                        }
                    )
                else:
                    observation = runner(case.query)
                    if isinstance(observation, Result):
                        if observation.is_err():
                            errors.append(
                                {
                                    "errorType": "GROUNDING_RUNNER_ERROR",
                                    "message": "grounding runner returned an error.",
                                }
                            )
                        else:
                            observation = observation.unwrap()
                    if not errors:
                        if not isinstance(observation, GroundednessObservation):
                            errors.append(
                                {
                                    "errorType": "GROUNDING_OBSERVATION_INVALID",
                                    "message": (
                                        "grounding runner must return a "
                                        "GroundednessObservation."
                                    ),
                                }
                            )
                        elif (
                            not isinstance(observation.answer, str)
                            or not observation.answer.strip()
                        ):
                            errors.append(
                                {
                                    "errorType": "GROUNDING_ANSWER_INVALID",
                                    "message": "grounding answer must be non-empty text.",
                                }
                            )
                        elif (
                            len(observation.answer.encode("utf-8"))
                            > self.max_value_bytes
                        ):
                            errors.append(
                                {
                                    "errorType": "GROUNDING_ANSWER_SIZE",
                                    "message": "grounding answer exceeds the value byte limit.",
                                }
                            )
                        else:
                            claims = _grounding_claims(observation.answer)
                            if not claims:
                                errors.append(
                                    {
                                        "errorType": "GROUNDING_CLAIM_INVALID",
                                        "message": "grounding answer contains no claims.",
                                    }
                                )
                            elif len(claims) > _GROUNDING_MAX_CLAIMS:
                                errors.append(
                                    {
                                        "errorType": "GROUNDING_CLAIM_LIMIT",
                                        "message": "grounding claim count exceeds the limit.",
                                    }
                                )
                            else:
                                source_terms = {
                                    source.uri: _grounding_terms(source.text)
                                    for source in case.sources
                                }
                                supported_indexes: List[int] = []
                                evidence_uris = set()
                                for index, claim in enumerate(claims):
                                    claim_terms = _grounding_terms(claim)
                                    if not claim_terms:
                                        errors.append(
                                            {
                                                "errorType": "GROUNDING_CLAIM_INVALID",
                                                "message": "grounding claim has no comparable terms.",
                                            }
                                        )
                                        break
                                    best_ratio = -1.0
                                    best_uri = ""
                                    for uri, terms in source_terms.items():
                                        overlap = len(claim_terms.intersection(terms))
                                        ratio = overlap / len(claim_terms)
                                        if ratio > best_ratio or (
                                            ratio == best_ratio
                                            and (not best_uri or uri < best_uri)
                                        ):
                                            best_ratio = ratio
                                            best_uri = uri
                                    if best_ratio >= case.min_claim_overlap:
                                        supported_indexes.append(index)
                                        evidence_uris.add(best_uri)
                                if not errors:
                                    score = len(supported_indexes) / len(claims)
                                    actual = {
                                        "claim_count": len(claims),
                                        "supported_claim_count": len(supported_indexes),
                                        "unsupported_claim_count": len(claims)
                                        - len(supported_indexes),
                                        "supported_claim_indexes": supported_indexes,
                                        "supported_ratio": score,
                                        "evidence_source_uris": sorted(evidence_uris),
                                    }
                                    if score < case.min_supported_ratio:
                                        errors.append(
                                            {
                                                "errorType": "GROUNDING_SUPPORT_LOW",
                                                "message": (
                                                    "supported claim ratio was below "
                                                    "the threshold."
                                                ),
                                            }
                                        )
            except Exception as exc:
                errors.append(
                    {
                        "errorType": "GROUNDING_RUNNER_EXCEPTION",
                        "message": "grounding runner raised an exception.",
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
