"""Deterministic local evaluation contracts for MAPLE agents."""

from __future__ import annotations

import inspect
import json
import math
import re
import time
from dataclasses import dataclass, field, replace
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Union,
)

from ..core.result import Result
from .contracts import validate_json_schema
from .events import RedactionPolicy
from .observability import TraceSpan
from .retrieval import RetrievalHit, VectorRetrievalHit

Error = Dict[str, Any]
_UNSET = object()
_GROUNDING_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)
_GROUNDING_MAX_CLAIMS = 256
_GROUNDING_MAX_SOURCES = 256
_EVAL_MAX_FIXTURE_VERSION = 32
_EVAL_MAX_TRAJECTORY_TOOLS = 256
_EVAL_MAX_TOOL_NAME_LENGTH = 256
_EVAL_MAX_TRAJECTORY_STEP_BYTES = 65_536
_EVAL_MAX_TRAJECTORY_DURATION_MS = 86_400_000.0
_EVAL_MAX_JUDGE_RATIONALE_BYTES = 4_096
_EVAL_MAX_TRACE_SPANS = 256
_EVAL_MAX_TRACE_NAME_LENGTH = 256
_TRACE_STATUSES = ("running", "ok", "error", "cancelled")
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
class EvalTrajectoryStep:
    """One bounded, JSON-safe tool step in an evaluation trajectory."""

    tool_name: str
    arguments: Any = field(default_factory=dict)
    result: Any = None
    status: str = "ok"
    duration_ms: float = 0.0

    def validate(self) -> Optional[Error]:
        if (
            not isinstance(self.tool_name, str)
            or not self.tool_name
            or len(self.tool_name) > _EVAL_MAX_TOOL_NAME_LENGTH
            or any(ord(char) < 32 for char in self.tool_name)
        ):
            return {
                "errorType": "EVAL_TRAJECTORY_STEP_INVALID",
                "message": "trajectory tool_name must be bounded text.",
            }
        if not isinstance(self.status, str) or self.status not in (
            "ok",
            "error",
            "cancelled",
        ):
            return {
                "errorType": "EVAL_TRAJECTORY_STEP_INVALID",
                "message": "trajectory status is invalid.",
            }
        try:
            duration_is_finite = math.isfinite(float(self.duration_ms))
        except (OverflowError, TypeError, ValueError):
            duration_is_finite = False
        if (
            not isinstance(self.duration_ms, (int, float))
            or isinstance(self.duration_ms, bool)
            or not duration_is_finite
            or self.duration_ms < 0.0
            or self.duration_ms > _EVAL_MAX_TRAJECTORY_DURATION_MS
        ):
            return {
                "errorType": "EVAL_TRAJECTORY_STEP_INVALID",
                "message": "trajectory duration_ms is invalid or too large.",
            }
        try:
            encoded = json.dumps(
                {"arguments": self.arguments, "result": self.result},
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8")
        except (TypeError, ValueError, OverflowError):
            return {
                "errorType": "EVAL_TRAJECTORY_STEP_INVALID",
                "message": "trajectory arguments and result must be JSON serializable.",
            }
        if len(encoded) > _EVAL_MAX_TRAJECTORY_STEP_BYTES:
            return {
                "errorType": "EVAL_TRAJECTORY_STEP_TOO_LARGE",
                "message": "trajectory arguments and result exceed the byte limit.",
            }
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Return the stable JSON-compatible fixture representation."""
        return {
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "result": self.result,
            "status": self.status,
            "duration_ms": self.duration_ms,
        }


@dataclass(frozen=True)
class TraceEvalSpan:
    """Identifier-free span shape used by deterministic trace fixtures."""

    name: str
    status: str = "ok"
    parent_index: Optional[int] = None

    def validate(self, *, index: Optional[int] = None) -> Optional[Error]:
        if (
            not isinstance(self.name, str)
            or not self.name
            or len(self.name) > _EVAL_MAX_TRACE_NAME_LENGTH
            or any(ord(char) < 32 for char in self.name)
        ):
            return {
                "errorType": "TRACE_SPAN_INVALID",
                "message": "trace span name must be bounded text.",
            }
        if not isinstance(self.status, str) or self.status not in _TRACE_STATUSES:
            return {
                "errorType": "TRACE_SPAN_INVALID",
                "message": "trace span status is invalid.",
            }
        if self.parent_index is not None and (
            not isinstance(self.parent_index, int)
            or isinstance(self.parent_index, bool)
            or self.parent_index < 0
            or self.parent_index >= _EVAL_MAX_TRACE_SPANS
            or (index is not None and self.parent_index >= index)
        ):
            return {
                "errorType": "TRACE_PARENT_INVALID",
                "message": "trace span parent_index must reference an earlier span.",
            }
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Return the stable identifier-free fixture representation."""
        return {
            "name": self.name,
            "status": self.status,
            "parent_index": self.parent_index,
        }


@dataclass(frozen=True)
class TraceEvalCase:
    """One bounded versioned fixture for deterministic trace scoring."""

    case_id: str
    input: Any
    expected_trace: Tuple[TraceEvalSpan, ...]
    min_score: float = 1.0
    metadata: Mapping[str, Any] = field(default_factory=dict)
    fixture_version: int = 1

    def validate(self) -> Optional[Error]:
        if (
            not isinstance(self.case_id, str)
            or not self.case_id
            or len(self.case_id) > 256
        ):
            return {
                "errorType": "TRACE_CASE_INVALID",
                "message": "case_id must be bounded and non-empty.",
            }
        if (
            not isinstance(self.fixture_version, int)
            or isinstance(self.fixture_version, bool)
            or self.fixture_version < 1
            or self.fixture_version > _EVAL_MAX_FIXTURE_VERSION
        ):
            return {
                "errorType": "TRACE_CASE_INVALID",
                "message": "fixture_version must be between 1 and 32.",
            }
        if (
            not isinstance(self.expected_trace, tuple)
            or not self.expected_trace
            or len(self.expected_trace) > _EVAL_MAX_TRACE_SPANS
            or not all(isinstance(span, TraceEvalSpan) for span in self.expected_trace)
        ):
            return {
                "errorType": "TRACE_CASE_INVALID",
                "message": "expected_trace must be a bounded non-empty tuple.",
            }
        for index, span in enumerate(self.expected_trace):
            span_error = span.validate(index=index)
            if span_error is not None:
                return span_error
        if (
            not isinstance(self.min_score, (int, float))
            or isinstance(self.min_score, bool)
            or not math.isfinite(float(self.min_score))
            or self.min_score < 0.0
            or self.min_score > 1.0
        ):
            return {
                "errorType": "TRACE_CASE_INVALID",
                "message": "min_score must be a finite number between 0 and 1.",
            }
        try:
            json.dumps(self.metadata, allow_nan=False)
        except (TypeError, ValueError, OverflowError):
            return {
                "errorType": "TRACE_CASE_INVALID",
                "message": "case metadata must be JSON serializable.",
            }
        return None


@dataclass(frozen=True)
class EvalCase:
    """One golden evaluation case with output and/or trajectory expectations."""

    case_id: str
    input: Any
    expected_output: Any = _UNSET
    output_schema: Optional[Mapping[str, Any]] = None
    expected_tool_names: Tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    fixture_version: int = 1
    expected_trajectory: Tuple[EvalTrajectoryStep, ...] = ()

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
            and not self.expected_trajectory
        ):
            return {
                "errorType": "EVAL_CASE_INVALID",
                "message": "case must define an output or trajectory expectation.",
            }
        if (
            not isinstance(self.fixture_version, int)
            or isinstance(self.fixture_version, bool)
            or self.fixture_version < 1
            or self.fixture_version > _EVAL_MAX_FIXTURE_VERSION
        ):
            return {
                "errorType": "EVAL_CASE_INVALID",
                "message": "fixture_version must be between 1 and 32.",
            }
        if not isinstance(self.expected_tool_names, tuple) or not all(
            isinstance(name, str)
            and name
            and len(name) <= _EVAL_MAX_TOOL_NAME_LENGTH
            and not any(ord(char) < 32 for char in name)
            for name in self.expected_tool_names
        ):
            return {
                "errorType": "EVAL_CASE_INVALID",
                "message": "expected_tool_names must be a tuple of names.",
            }
        if len(self.expected_tool_names) > _EVAL_MAX_TRAJECTORY_TOOLS:
            return {
                "errorType": "EVAL_CASE_INVALID",
                "message": "expected_tool_names exceeds the trajectory limit.",
            }
        if (
            not isinstance(self.expected_trajectory, tuple)
            or len(self.expected_trajectory) > _EVAL_MAX_TRAJECTORY_TOOLS
            or not all(
                isinstance(step, EvalTrajectoryStep)
                for step in self.expected_trajectory
            )
        ):
            return {
                "errorType": "EVAL_CASE_INVALID",
                "message": "expected_trajectory must be a bounded tuple of steps.",
            }
        for step in self.expected_trajectory:
            step_error = step.validate()
            if step_error is not None:
                return step_error
        if self.expected_trajectory and self.expected_tool_names:
            trajectory_names = tuple(
                step.tool_name for step in self.expected_trajectory
            )
            if trajectory_names != tuple(self.expected_tool_names):
                return {
                    "errorType": "EVAL_CASE_INVALID",
                    "message": "expected_tool_names must match expected_trajectory.",
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
            if not is_number or not finite or value < 0.0 or value > 1.0:
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
    """Optional runner result carrying output and a bounded tool trajectory."""

    output: Any
    tool_names: Tuple[str, ...] = ()
    trajectory: Tuple[EvalTrajectoryStep, ...] = ()


@dataclass(frozen=True)
class EvalJudgeResult:
    """Bounded result returned by an optional generation-quality judge."""

    score: float
    passed: bool
    rationale: str = ""

    def validate(self) -> Optional[Error]:
        if isinstance(self.score, (int, float)) and not isinstance(self.score, bool):
            try:
                finite_score = math.isfinite(self.score)
            except OverflowError:
                finite_score = False
        else:
            finite_score = False
        if not finite_score or self.score < 0.0 or self.score > 1.0:
            return {
                "errorType": "EVAL_JUDGE_RESULT_INVALID",
                "message": "judge score must be a finite number between 0 and 1.",
            }
        if not isinstance(self.passed, bool):
            return {
                "errorType": "EVAL_JUDGE_RESULT_INVALID",
                "message": "judge passed must be a boolean.",
            }
        if (
            not isinstance(self.rationale, str)
            or len(self.rationale.encode("utf-8")) > _EVAL_MAX_JUDGE_RATIONALE_BYTES
            or any(
                ord(char) < 32 and char not in ("\r", "\n", "\t")
                for char in self.rationale
            )
        ):
            return {
                "errorType": "EVAL_JUDGE_RESULT_INVALID",
                "message": "judge rationale must be bounded text.",
            }
        return None


EvalJudgeValue = Union[EvalJudgeResult, Result[EvalJudgeResult, Error]]
EvalJudge = Callable[[EvalCase, EvalObservation], EvalJudgeValue]
AsyncEvalJudge = Callable[
    [EvalCase, EvalObservation], Union[EvalJudgeValue, Awaitable[EvalJudgeValue]]
]


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
    fixture_version: int = 1
    judge_score: Optional[float] = None
    judge_rationale: Optional[str] = None
    actual_trajectory: Tuple[EvalTrajectoryStep, ...] = ()
    actual_tool_names: Tuple[str, ...] = ()
    actual_trace: Tuple[TraceEvalSpan, ...] = ()


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
                    "fixture_version": result.fixture_version,
                    "judge_score": result.judge_score,
                    "judge_rationale": result.judge_rationale,
                    "actual_tool_names": list(result.actual_tool_names),
                    "actual_trajectory": [
                        step.to_dict() for step in result.actual_trajectory
                    ],
                    "actual_trace": [span.to_dict() for span in result.actual_trace],
                }
                for result in self.results
            ],
        }


@dataclass(frozen=True)
class EvalCalibrationCase:
    """One human-labeled fixture used to calibrate a host-supplied judge."""

    case_id: str
    fixture: EvalCase
    observation: EvalObservation
    expected_passed: bool
    expected_score: Optional[float] = None

    def validate(self) -> Optional[Error]:
        if (
            not isinstance(self.case_id, str)
            or not self.case_id
            or len(self.case_id) > 256
            or any(ord(char) < 32 for char in self.case_id)
        ):
            return {
                "errorType": "EVAL_CALIBRATION_CASE_INVALID",
                "message": "calibration case_id must be bounded and non-empty.",
            }
        if not isinstance(self.fixture, EvalCase):
            return {
                "errorType": "EVAL_CALIBRATION_CASE_INVALID",
                "message": "calibration fixture must be an EvalCase.",
            }
        if self.fixture.validate() is not None:
            return {
                "errorType": "EVAL_CALIBRATION_CASE_INVALID",
                "message": "calibration fixture is invalid.",
            }
        if not isinstance(self.observation, EvalObservation):
            return {
                "errorType": "EVAL_CALIBRATION_CASE_INVALID",
                "message": "calibration observation must be an EvalObservation.",
            }
        if not isinstance(self.expected_passed, bool):
            return {
                "errorType": "EVAL_CALIBRATION_CASE_INVALID",
                "message": "expected_passed must be a boolean.",
            }
        if self.expected_score is not None:
            is_number = isinstance(
                self.expected_score, (int, float)
            ) and not isinstance(self.expected_score, bool)
            if is_number:
                try:
                    finite = math.isfinite(self.expected_score)
                except OverflowError:
                    finite = False
            else:
                finite = False
            if not is_number or not finite or not 0.0 <= self.expected_score <= 1.0:
                return {
                    "errorType": "EVAL_CALIBRATION_CASE_INVALID",
                    "message": "expected_score must be a finite number between 0 and 1.",
                }
        return None


@dataclass(frozen=True)
class EvalCalibrationResult:
    """One bounded comparison between a human label and a judge result."""

    case_id: str
    expected_passed: bool
    judge_passed: Optional[bool] = None
    agreed: bool = False
    expected_score: Optional[float] = None
    judge_score: Optional[float] = None
    absolute_score_error: Optional[float] = None
    rationale: Optional[str] = None
    errors: Tuple[Error, ...] = ()


@dataclass(frozen=True)
class EvalCalibrationReport:
    """Aggregate descriptive calibration metrics for a bounded fixture set."""

    results: Tuple[EvalCalibrationResult, ...]

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def agreement_count(self) -> int:
        return sum(1 for result in self.results if result.agreed)

    @property
    def agreement_rate(self) -> float:
        return self.agreement_count / self.total if self.total else 0.0

    @property
    def scored_cases(self) -> int:
        return sum(
            1 for result in self.results if result.absolute_score_error is not None
        )

    @property
    def mean_absolute_score_error(self) -> Optional[float]:
        errors = [
            result.absolute_score_error
            for result in self.results
            if result.absolute_score_error is not None
        ]
        return sum(errors) / len(errors) if errors else None

    def as_dict(self) -> Dict[str, Any]:
        """Return a JSON-compatible bounded calibration report mapping."""
        return {
            "total": self.total,
            "agreement_count": self.agreement_count,
            "agreement_rate": self.agreement_rate,
            "scored_cases": self.scored_cases,
            "mean_absolute_score_error": self.mean_absolute_score_error,
            "results": [
                {
                    "case_id": result.case_id,
                    "expected_passed": result.expected_passed,
                    "judge_passed": result.judge_passed,
                    "agreed": result.agreed,
                    "expected_score": result.expected_score,
                    "judge_score": result.judge_score,
                    "absolute_score_error": result.absolute_score_error,
                    "rationale": result.rationale,
                    "errors": list(result.errors),
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

    def _safe_trajectory(
        self, trajectory: Tuple[EvalTrajectoryStep, ...]
    ) -> Optional[Tuple[EvalTrajectoryStep, ...]]:
        """Redact and bound trajectory fields before report or judge exposure."""
        if not self._valid_trajectory(trajectory):
            return None
        safe_steps: List[EvalTrajectoryStep] = []
        for step in trajectory:
            safe = self._safe_output(step.to_dict())
            if not isinstance(safe, Mapping):
                return None
            tool_name = safe.get("tool_name")
            status = safe.get("status")
            duration_ms = safe.get("duration_ms")
            if (
                not isinstance(tool_name, str)
                or not isinstance(status, str)
                or not isinstance(duration_ms, (int, float))
                or isinstance(duration_ms, bool)
            ):
                return None
            normalized = EvalTrajectoryStep(
                tool_name=tool_name,
                arguments=safe.get("arguments"),
                result=safe.get("result"),
                status=status,
                duration_ms=duration_ms,
            )
            if normalized.validate() is not None:
                return None
            safe_steps.append(normalized)
        try:
            encoded = json.dumps(
                [step.to_dict() for step in safe_steps],
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8")
        except (TypeError, ValueError, OverflowError):
            return None
        if len(encoded) > self.max_value_bytes:
            return None
        return tuple(safe_steps)

    def _safe_judge_rationale(self, value: str) -> Optional[str]:
        safe = self._safe_output(value)
        return safe if isinstance(safe, str) else None

    @staticmethod
    def _normalize_judge_result(value: Any) -> Result[EvalJudgeResult, Error]:
        if isinstance(value, Result):
            if value.is_err():
                return Result.err(
                    {
                        "errorType": "EVAL_JUDGE_ERROR",
                        "message": "judge returned an error.",
                    }
                )
            candidate = value.unwrap()
            if isinstance(candidate, EvalJudgeResult):
                return Result.ok(candidate)
        elif isinstance(value, EvalJudgeResult):
            return Result.ok(value)
        return Result.err(
            {
                "errorType": "EVAL_JUDGE_RESULT_INVALID",
                "message": "judge must return an EvalJudgeResult.",
            }
        )

    @staticmethod
    def _valid_tool_names(value: Any) -> bool:
        return (
            isinstance(value, tuple)
            and len(value) <= _EVAL_MAX_TRAJECTORY_TOOLS
            and all(
                isinstance(name, str)
                and name
                and len(name) <= _EVAL_MAX_TOOL_NAME_LENGTH
                and not any(ord(char) < 32 for char in name)
                for name in value
            )
        )

    @staticmethod
    def _valid_trajectory(value: Any) -> bool:
        return (
            isinstance(value, tuple)
            and len(value) <= _EVAL_MAX_TRAJECTORY_TOOLS
            and all(
                isinstance(step, EvalTrajectoryStep) and step.validate() is None
                for step in value
            )
        )

    @staticmethod
    def _normalize_trace(value: Any) -> Result[Tuple[TraceEvalSpan, ...], Error]:
        """Project native spans to bounded identifier-free evaluation spans."""
        if not isinstance(value, (list, tuple)):
            return Result.err(
                {
                    "errorType": "TRACE_OBSERVATION_INVALID",
                    "message": "trace runner must return a span sequence.",
                }
            )
        if len(value) > _EVAL_MAX_TRACE_SPANS:
            return Result.err(
                {
                    "errorType": "TRACE_SPAN_LIMIT",
                    "message": "trace span count exceeds the limit.",
                }
            )

        normalized: List[TraceEvalSpan] = []
        native_span_indexes: Dict[str, int] = {}
        for index, candidate in enumerate(value):
            if isinstance(candidate, TraceEvalSpan):
                span = candidate
            elif isinstance(candidate, TraceSpan):
                parent_index: Optional[int] = None
                if candidate.parent_span_id is not None:
                    if candidate.parent_span_id not in native_span_indexes:
                        return Result.err(
                            {
                                "errorType": "TRACE_PARENT_NOT_FOUND",
                                "message": "native trace span parent is not in the sequence.",
                            }
                        )
                    parent_index = native_span_indexes[candidate.parent_span_id]
                span = TraceEvalSpan(
                    name=candidate.name,
                    status=candidate.status,
                    parent_index=parent_index,
                )
                if candidate.span_id in native_span_indexes:
                    return Result.err(
                        {
                            "errorType": "TRACE_OBSERVATION_INVALID",
                            "message": "native trace span IDs must be unique.",
                        }
                    )
                native_span_indexes[candidate.span_id] = index
            else:
                return Result.err(
                    {
                        "errorType": "TRACE_OBSERVATION_INVALID",
                        "message": "trace runner returned an unknown span type.",
                    }
                )
            span_error = span.validate(index=index)
            if span_error is not None:
                return Result.err(
                    {
                        "errorType": "TRACE_OBSERVATION_INVALID",
                        "message": span_error["message"],
                        "cause": span_error["errorType"],
                    }
                )
            normalized.append(span)
        return Result.ok(tuple(normalized))

    @staticmethod
    def _score_trace(
        expected: Tuple[TraceEvalSpan, ...], actual: Tuple[TraceEvalSpan, ...]
    ) -> Dict[str, float]:
        """Return deterministic positional component scores for two traces."""
        denominator = max(len(expected), len(actual), 1)
        name_matches = sum(
            index < len(actual) and expected[index].name == actual[index].name
            for index in range(len(expected))
        )
        status_matches = sum(
            index < len(actual) and expected[index].status == actual[index].status
            for index in range(len(expected))
        )
        parent_matches = sum(
            index < len(actual)
            and expected[index].parent_index == actual[index].parent_index
            for index in range(len(expected))
        )
        name_score = name_matches / denominator
        status_score = status_matches / denominator
        parent_score = parent_matches / denominator
        return {
            "name_score": name_score,
            "status_score": status_score,
            "parent_score": parent_score,
            "score": (name_score + status_score + parent_score) / 3.0,
        }

    def _trace_report_fits(self, trace: Tuple[TraceEvalSpan, ...]) -> bool:
        try:
            encoded = json.dumps(
                [span.to_dict() for span in trace],
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8")
        except (TypeError, ValueError, OverflowError):
            return False
        return len(encoded) <= self.max_value_bytes

    def _validate_run_inputs(
        self,
        cases: Sequence[EvalCase],
        runner: Callable[[Any], Any],
        judge: Optional[Callable[..., Any]],
    ) -> Optional[Error]:
        if (
            not isinstance(self.max_cases, int)
            or isinstance(self.max_cases, bool)
            or self.max_cases <= 0
        ):
            return {
                "errorType": "EVAL_CONFIG_INVALID",
                "message": "max_cases must be positive.",
            }
        if (
            not isinstance(self.max_value_bytes, int)
            or isinstance(self.max_value_bytes, bool)
            or self.max_value_bytes <= 0
        ):
            return {
                "errorType": "EVAL_CONFIG_INVALID",
                "message": "max_value_bytes must be positive.",
            }
        if not callable(runner):
            return {
                "errorType": "EVAL_INPUT_INVALID",
                "message": "runner must be callable.",
            }
        if judge is not None and not callable(judge):
            return {
                "errorType": "EVAL_INPUT_INVALID",
                "message": "judge must be callable.",
            }
        if len(cases) > self.max_cases:
            return {
                "errorType": "EVAL_CASE_LIMIT",
                "message": "case count exceeds the limit.",
            }
        return None

    def _validate_calibration_inputs(
        self,
        cases: Sequence[EvalCalibrationCase],
        judge: Callable[..., Any],
    ) -> Optional[Error]:
        if (
            not isinstance(self.max_cases, int)
            or isinstance(self.max_cases, bool)
            or self.max_cases <= 0
        ):
            return {
                "errorType": "EVAL_CONFIG_INVALID",
                "message": "max_cases must be positive.",
            }
        if (
            not isinstance(self.max_value_bytes, int)
            or isinstance(self.max_value_bytes, bool)
            or self.max_value_bytes <= 0
        ):
            return {
                "errorType": "EVAL_CONFIG_INVALID",
                "message": "max_value_bytes must be positive.",
            }
        if not isinstance(cases, (list, tuple)):
            return {
                "errorType": "EVAL_CALIBRATION_INPUT_INVALID",
                "message": "calibration cases must be a list or tuple.",
            }
        if not callable(judge):
            return {
                "errorType": "EVAL_CALIBRATION_INPUT_INVALID",
                "message": "calibration judge must be callable.",
            }
        if len(cases) > self.max_cases:
            return {
                "errorType": "EVAL_CALIBRATION_CASE_LIMIT",
                "message": "calibration case count exceeds the limit.",
            }
        return None

    def _prepare_calibration_observation(
        self, observation: EvalObservation
    ) -> Result[EvalObservation, Error]:
        if not isinstance(observation, EvalObservation):
            return Result.err(
                {
                    "errorType": "EVAL_CALIBRATION_CASE_INVALID",
                    "message": "calibration observation must be an EvalObservation.",
                }
            )
        if not self._valid_tool_names(observation.tool_names):
            return Result.err(
                {
                    "errorType": "EVAL_CALIBRATION_CASE_INVALID",
                    "message": "calibration observation tool names are invalid.",
                }
            )
        if not self._valid_trajectory(observation.trajectory):
            return Result.err(
                {
                    "errorType": "EVAL_CALIBRATION_CASE_INVALID",
                    "message": "calibration observation trajectory is invalid.",
                }
            )
        safe_trajectory = self._safe_trajectory(observation.trajectory)
        if safe_trajectory is None:
            return Result.err(
                {
                    "errorType": "EVAL_CALIBRATION_CASE_INVALID",
                    "message": "calibration observation exceeds the report bound.",
                }
            )
        tool_names = observation.tool_names
        if observation.trajectory:
            trajectory_names = tuple(step.tool_name for step in observation.trajectory)
            if tool_names and tuple(tool_names) != trajectory_names:
                return Result.err(
                    {
                        "errorType": "EVAL_CALIBRATION_CASE_INVALID",
                        "message": "tool_names must match trajectory tool names.",
                    }
                )
            tool_names = trajectory_names
        return Result.ok(
            EvalObservation(
                output=self._safe_output(observation.output),
                tool_names=tuple(tool_names),
                trajectory=tuple(safe_trajectory),
            )
        )

    def _prepare_calibration_cases(
        self, cases: Sequence[EvalCalibrationCase]
    ) -> Result[Tuple[Tuple[EvalCalibrationCase, EvalObservation], ...], Error]:
        prepared: List[Tuple[EvalCalibrationCase, EvalObservation]] = []
        seen_case_ids = set()
        for case in cases:
            if not isinstance(case, EvalCalibrationCase):
                return Result.err(
                    {
                        "errorType": "EVAL_CALIBRATION_CASE_INVALID",
                        "message": "calibration cases must use EvalCalibrationCase.",
                    }
                )
            try:
                case_error = case.validate()
            except Exception:
                case_error = {
                    "errorType": "EVAL_CALIBRATION_CASE_INVALID",
                    "message": "calibration case validation failed.",
                }
            if case_error is not None:
                return Result.err(case_error)
            if case.case_id in seen_case_ids:
                return Result.err(
                    {
                        "errorType": "EVAL_CALIBRATION_CASE_INVALID",
                        "message": "calibration case IDs must be unique.",
                    }
                )
            seen_case_ids.add(case.case_id)
            observation = self._prepare_calibration_observation(case.observation)
            if observation.is_err():
                return Result.err(observation.unwrap_err())
            prepared.append((case, observation.unwrap()))
        return Result.ok(tuple(prepared))

    def _calibration_error_result(
        self, case: EvalCalibrationCase, error: Error
    ) -> EvalCalibrationResult:
        return EvalCalibrationResult(
            case_id=case.case_id,
            expected_passed=case.expected_passed,
            expected_score=case.expected_score,
            errors=(error,),
        )

    def _calibration_result(
        self,
        case: EvalCalibrationCase,
        judged_value: Any,
    ) -> EvalCalibrationResult:
        normalized = self._normalize_judge_result(judged_value)
        if normalized.is_err():
            return self._calibration_error_result(case, normalized.unwrap_err())
        judged = normalized.unwrap()
        judge_error = judged.validate()
        if judge_error is not None:
            return self._calibration_error_result(case, judge_error)
        absolute_score_error = None
        if case.expected_score is not None:
            absolute_score_error = abs(judged.score - case.expected_score)
        return EvalCalibrationResult(
            case_id=case.case_id,
            expected_passed=case.expected_passed,
            judge_passed=judged.passed,
            agreed=judged.passed == case.expected_passed,
            expected_score=case.expected_score,
            judge_score=judged.score,
            absolute_score_error=absolute_score_error,
            rationale=self._safe_judge_rationale(judged.rationale),
        )

    def calibrate(
        self,
        cases: Sequence[EvalCalibrationCase],
        judge: EvalJudge,
    ) -> Result[EvalCalibrationReport, Error]:
        """Compare a local judge with bounded caller-supplied human labels.

        Calibration is descriptive only: MAPLE does not select or invoke a
        provider, train or tune a judge, or claim semantic validity. The
        callback receives only redacted and size-bounded observations.
        """
        input_error = self._validate_calibration_inputs(cases, judge)
        if input_error is not None:
            return Result.err(input_error)
        prepared = self._prepare_calibration_cases(cases)
        if prepared.is_err():
            return Result.err(prepared.unwrap_err())

        results: List[EvalCalibrationResult] = []
        for case, observation in prepared.unwrap():
            try:
                judged_value = judge(case.fixture, observation)
                results.append(self._calibration_result(case, judged_value))
            except Exception as exc:
                results.append(
                    self._calibration_error_result(
                        case,
                        {
                            "errorType": "EVAL_JUDGE_EXCEPTION",
                            "message": "judge raised an exception.",
                            "details": {"exception": type(exc).__name__},
                        },
                    )
                )
        return Result.ok(EvalCalibrationReport(results=tuple(results)))

    async def calibrate_async(
        self,
        cases: Sequence[EvalCalibrationCase],
        judge: AsyncEvalJudge,
    ) -> Result[EvalCalibrationReport, Error]:
        """Run bounded calibration sequentially with sync or async callbacks."""
        input_error = self._validate_calibration_inputs(cases, judge)
        if input_error is not None:
            return Result.err(input_error)
        prepared = self._prepare_calibration_cases(cases)
        if prepared.is_err():
            return Result.err(prepared.unwrap_err())

        results: List[EvalCalibrationResult] = []
        for case, observation in prepared.unwrap():
            try:
                judged_value = judge(case.fixture, observation)
                if inspect.isawaitable(judged_value):
                    judged_value = await judged_value
                results.append(self._calibration_result(case, judged_value))
            except Exception as exc:
                results.append(
                    self._calibration_error_result(
                        case,
                        {
                            "errorType": "EVAL_JUDGE_EXCEPTION",
                            "message": "judge raised an exception.",
                            "details": {"exception": type(exc).__name__},
                        },
                    )
                )
        return Result.ok(EvalCalibrationReport(results=tuple(results)))

    def run(
        self,
        cases: Sequence[EvalCase],
        runner: Callable[[Any], Any],
        judge: Optional[EvalJudge] = None,
    ) -> Result[EvalReport, Error]:
        """Run cases, returning per-case failures instead of aborting the set.

        ``judge`` is an optional local callback supplied by the host. It receives
        the validated case and bounded runner observation, and may return an
        ``EvalJudgeResult`` directly or through ``Result``. MAPLE does not
        select a provider, retry a judge, or claim semantic faithfulness.
        """
        input_error = self._validate_run_inputs(cases, runner, judge)
        if input_error is not None:
            return Result.err(input_error)

        results: List[EvalResult] = []
        for case in cases:
            case_error = case.validate()
            if case_error is not None:
                return Result.err(case_error)
            started = time.perf_counter()
            errors: List[Error] = []
            actual: Any = None
            tool_names: Tuple[str, ...] = ()
            trajectory: Tuple[EvalTrajectoryStep, ...] = ()
            safe_trajectory: Tuple[EvalTrajectoryStep, ...] = ()
            judge_score: Optional[float] = None
            judge_rationale: Optional[str] = None
            observation_valid = True
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
                        if not self._valid_tool_names(tool_names):
                            errors.append(
                                {
                                    "errorType": "EVAL_OBSERVATION_INVALID",
                                    "message": "observed tool names are invalid or unbounded.",
                                }
                            )
                            observation_valid = False
                        trajectory = observation.trajectory
                        if not self._valid_trajectory(trajectory):
                            errors.append(
                                {
                                    "errorType": "EVAL_OBSERVATION_INVALID",
                                    "message": "observed trajectory is invalid or unbounded.",
                                }
                            )
                            observation_valid = False
                        else:
                            safe_trajectory_result = self._safe_trajectory(trajectory)
                            if safe_trajectory_result is None:
                                errors.append(
                                    {
                                        "errorType": "EVAL_OBSERVATION_INVALID",
                                        "message": "observed trajectory exceeds the report bound.",
                                    }
                                )
                                observation_valid = False
                            else:
                                safe_trajectory = safe_trajectory_result
                            if trajectory:
                                trajectory_names = tuple(
                                    step.tool_name for step in trajectory
                                )
                                if tool_names and tuple(tool_names) != trajectory_names:
                                    errors.append(
                                        {
                                            "errorType": "EVAL_OBSERVATION_INVALID",
                                            "message": "tool_names must match trajectory tool names.",
                                        }
                                    )
                                    observation_valid = False
                                else:
                                    tool_names = trajectory_names
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
                    if case.expected_trajectory:
                        expected_checks += 1
                        observed_trajectory = (
                            trajectory if self._valid_trajectory(trajectory) else ()
                        )
                        if tuple(
                            step.to_dict() for step in observed_trajectory
                        ) == tuple(step.to_dict() for step in case.expected_trajectory):
                            passed_checks += 1
                        else:
                            errors.append(
                                {
                                    "errorType": "EVAL_TRAJECTORY_MISMATCH",
                                    "message": "structured tool trajectory did not match expected steps.",
                                }
                            )
                    if judge is not None and observation_valid:
                        expected_checks += 1
                        judge_observation = EvalObservation(
                            output=self._safe_output(actual),
                            tool_names=tuple(tool_names),
                            trajectory=tuple(safe_trajectory),
                        )
                        try:
                            judged_value = judge(case, judge_observation)
                            judged: Optional[EvalJudgeResult] = None
                            if isinstance(judged_value, Result):
                                if judged_value.is_err():
                                    errors.append(
                                        {
                                            "errorType": "EVAL_JUDGE_ERROR",
                                            "message": "judge returned an error.",
                                        }
                                    )
                                else:
                                    candidate = judged_value.unwrap()
                                    if isinstance(candidate, EvalJudgeResult):
                                        judged = candidate
                                    else:
                                        errors.append(
                                            {
                                                "errorType": "EVAL_JUDGE_RESULT_INVALID",
                                                "message": (
                                                    "judge must return an EvalJudgeResult."
                                                ),
                                            }
                                        )
                            elif isinstance(judged_value, EvalJudgeResult):
                                judged = judged_value
                            else:
                                errors.append(
                                    {
                                        "errorType": "EVAL_JUDGE_RESULT_INVALID",
                                        "message": (
                                            "judge must return an EvalJudgeResult."
                                        ),
                                    }
                                )
                            if judged is not None:
                                judge_error = judged.validate()
                                if judge_error is not None:
                                    errors.append(judge_error)
                                else:
                                    judge_score = judged.score
                                    judge_rationale = self._safe_judge_rationale(
                                        judged.rationale
                                    )
                                    if judged.passed:
                                        passed_checks += 1
                                    else:
                                        errors.append(
                                            {
                                                "errorType": "EVAL_JUDGE_FAILED",
                                                "message": "judge marked case as failed.",
                                            }
                                        )
                        except Exception as exc:
                            errors.append(
                                {
                                    "errorType": "EVAL_JUDGE_EXCEPTION",
                                    "message": "judge raised an exception.",
                                    "details": {"exception": type(exc).__name__},
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
                    fixture_version=case.fixture_version,
                    judge_score=judge_score,
                    judge_rationale=judge_rationale,
                    actual_trajectory=tuple(safe_trajectory),
                    actual_tool_names=tuple(tool_names),
                )
            )
        return Result.ok(EvalReport(results=tuple(results)))

    async def run_async(
        self,
        cases: Sequence[EvalCase],
        runner: Callable[[Any], Any],
        judge: Optional[AsyncEvalJudge] = None,
    ) -> Result[EvalReport, Error]:
        """Run bounded cases with awaitable runners and provider-neutral judges.

        The runner and judge may be synchronous or awaitable. Cases are
        evaluated sequentially to preserve deterministic fixture order. Runner
        results are passed through the same synchronous validation/redaction
        path, and a judge sees only the bounded redacted observation retained
        in the report. MAPLE does not select a provider, retry a callback, or
        claim hosted evaluation semantics.
        """
        input_error = self._validate_run_inputs(cases, runner, judge)
        if input_error is not None:
            return Result.err(input_error)
        for case in cases:
            case_error = case.validate()
            if case_error is not None:
                return Result.err(case_error)

        updated_results: List[EvalResult] = []
        for case in cases:
            try:
                value = runner(case.input)
                if inspect.isawaitable(value):
                    value = await value
                failure: Optional[Exception] = None
            except Exception as exc:
                value = None
                failure = exc

            def cached_runner(
                _: Any, value: Any = value, failure: Optional[Exception] = failure
            ) -> Any:
                if failure is not None:
                    raise failure
                return value

            base_result = self.run([case], cached_runner)
            if base_result.is_err():
                return Result.err(base_result.unwrap_err())
            result = base_result.unwrap().results[0]
            if judge is None:
                updated_results.append(result)
                continue
            if any(
                error.get("errorType")
                in {
                    "EVAL_RUNNER_ERROR",
                    "EVAL_RUNNER_EXCEPTION",
                    "EVAL_OBSERVATION_INVALID",
                }
                for error in result.errors
            ):
                updated_results.append(result)
                continue

            expected_checks = sum(
                (
                    case.expected_output is not _UNSET,
                    case.output_schema is not None,
                    bool(case.expected_tool_names),
                    bool(case.expected_trajectory),
                )
            )
            errors = list(result.errors)
            judge_score: Optional[float] = None
            judge_rationale: Optional[str] = None
            judge_passed = 0
            judge_observation = EvalObservation(
                output=result.actual_output,
                tool_names=result.actual_tool_names,
                trajectory=result.actual_trajectory,
            )
            try:
                judged_value = judge(case, judge_observation)
                if inspect.isawaitable(judged_value):
                    judged_value = await judged_value
                normalized = self._normalize_judge_result(judged_value)
                if normalized.is_err():
                    errors.append(normalized.unwrap_err())
                else:
                    judged = normalized.unwrap()
                    judge_error = judged.validate()
                    if judge_error is not None:
                        errors.append(judge_error)
                    else:
                        judge_score = judged.score
                        judge_rationale = self._safe_judge_rationale(judged.rationale)
                        if judged.passed:
                            judge_passed = 1
                        else:
                            errors.append(
                                {
                                    "errorType": "EVAL_JUDGE_FAILED",
                                    "message": "judge marked case as failed.",
                                }
                            )
            except Exception as exc:
                errors.append(
                    {
                        "errorType": "EVAL_JUDGE_EXCEPTION",
                        "message": "judge raised an exception.",
                        "details": {"exception": type(exc).__name__},
                    }
                )
            updated_results.append(
                replace(
                    result,
                    passed=not errors,
                    score=(result.score * expected_checks + judge_passed)
                    / (expected_checks + 1),
                    errors=tuple(errors),
                    judge_score=judge_score,
                    judge_rationale=judge_rationale,
                )
            )
        return Result.ok(EvalReport(results=tuple(updated_results)))

    def run_trace(
        self,
        cases: Sequence[TraceEvalCase],
        runner: Callable[[Any], Any],
    ) -> Result[EvalReport, Error]:
        """Score bounded trace structure using deterministic local fixtures.

        The runner may return native ``TraceSpan`` values or identifier-free
        ``TraceEvalSpan`` values. Native IDs, timestamps, and attributes are
        discarded before scoring; this method does not establish semantic,
        causal, provider, or hosted trace correctness.
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
            actual_trace: Tuple[TraceEvalSpan, ...] = ()
            actual: Any = None
            score = 0.0
            try:
                encoded_case = json.dumps(
                    {
                        "expected_trace": [
                            span.to_dict() for span in case.expected_trace
                        ],
                        "metadata": case.metadata,
                    },
                    ensure_ascii=False,
                    allow_nan=False,
                    separators=(",", ":"),
                ).encode("utf-8")
                if len(encoded_case) > self.max_value_bytes:
                    errors.append(
                        {
                            "errorType": "TRACE_CASE_SIZE",
                            "message": "trace case exceeds the value byte limit.",
                        }
                    )
                else:
                    observation = runner(case.input)
                    if isinstance(observation, Result):
                        if observation.is_err():
                            errors.append(
                                {
                                    "errorType": "TRACE_RUNNER_ERROR",
                                    "message": "trace runner returned an error.",
                                }
                            )
                        else:
                            observation = observation.unwrap()
                    if not errors:
                        normalized = self._normalize_trace(observation)
                        if normalized.is_err():
                            errors.append(normalized.unwrap_err())
                        else:
                            actual_trace = normalized.unwrap()
                            if not self._trace_report_fits(actual_trace):
                                errors.append(
                                    {
                                        "errorType": "TRACE_REPORT_SIZE",
                                        "message": "trace observation exceeds the value byte limit.",
                                    }
                                )
                            else:
                                components = self._score_trace(
                                    case.expected_trace, actual_trace
                                )
                                score = components["score"]
                                actual = {
                                    "expected_span_count": len(case.expected_trace),
                                    "actual_span_count": len(actual_trace),
                                    **components,
                                }
                                if score < case.min_score:
                                    errors.append(
                                        {
                                            "errorType": "TRACE_SCORE_LOW",
                                            "message": "trace score was below the threshold.",
                                        }
                                    )
            except Exception as exc:
                errors.append(
                    {
                        "errorType": "TRACE_RUNNER_EXCEPTION",
                        "message": "trace runner raised an exception.",
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
                    fixture_version=case.fixture_version,
                    actual_trace=actual_trace,
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
