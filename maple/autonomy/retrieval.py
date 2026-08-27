"""Bounded document, chunk, and retrieval primitives for MAPLE agents."""

from __future__ import annotations

import json
import math
import re
import threading
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import (
    Any,
    Dict,
    List,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    Set,
    Tuple,
    Union,
    cast,
)

from ..core.result import Result

Error = Dict[str, Any]
_TOKEN_PATTERN = re.compile(r"\w+", re.UNICODE)
_MAX_RERANK_CANDIDATES = 100


def _error(error_type: str, message: str, **details: Any) -> Error:
    error: Error = {"errorType": error_type, "message": message}
    if details:
        error["details"] = details
    return error


def _json_size(value: Any) -> Result[int, Error]:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError):
        return Result.err(
            _error("RETRIEVAL_NON_JSON_METADATA", "Metadata must be JSON serializable.")
        )
    return Result.ok(len(encoded))


def _validate_identifier(
    value: Any, field_name: str, max_length: int = 256
) -> Optional[Error]:
    if not isinstance(value, str) or not value or len(value) > max_length:
        return _error(
            "RETRIEVAL_INPUT_INVALID",
            f"{field_name} must be a non-empty bounded string.",
        )
    if any(ord(char) < 32 for char in value):
        return _error(
            "RETRIEVAL_INPUT_INVALID",
            f"{field_name} must not contain control characters.",
        )
    return None


@dataclass(frozen=True)
class SourceRef:
    """Stable source identity attached to every document and retrieval hit."""

    uri: str
    title: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> Optional[Error]:
        error = _validate_identifier(self.uri, "source uri", max_length=2048)
        if error is not None:
            return error
        if self.title is not None and (
            not isinstance(self.title, str) or len(self.title) > 512
        ):
            return _error("RETRIEVAL_INPUT_INVALID", "source title is invalid.")
        if not isinstance(self.metadata, Mapping):
            return _error(
                "RETRIEVAL_INPUT_INVALID", "source metadata must be an object."
            )
        metadata_size = _json_size(dict(self.metadata))
        if metadata_size.is_err():
            return cast(Error, metadata_size.unwrap_err())
        if metadata_size.unwrap() > 65_536:
            return _error(
                "RETRIEVAL_METADATA_TOO_LARGE",
                "source metadata exceeds the byte limit.",
            )
        return None


@dataclass(frozen=True)
class Document:
    """Text plus identity and source metadata for ingestion."""

    document_id: str
    text: str
    source: SourceRef
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> Optional[Error]:
        error = _validate_identifier(self.document_id, "document_id")
        if error is not None:
            return error
        if not isinstance(self.text, str):
            return _error("RETRIEVAL_INPUT_INVALID", "document text must be a string.")
        source_error = self.source.validate()
        if source_error is not None:
            return source_error
        if not isinstance(self.metadata, Mapping):
            return _error(
                "RETRIEVAL_INPUT_INVALID", "document metadata must be an object."
            )
        metadata_size = _json_size(dict(self.metadata))
        if metadata_size.is_err():
            return cast(Error, metadata_size.unwrap_err())
        if metadata_size.unwrap() > 65_536:
            return _error(
                "RETRIEVAL_METADATA_TOO_LARGE",
                "document metadata exceeds the byte limit.",
            )
        return None


@dataclass(frozen=True)
class DocumentChunk:
    """A deterministic text span retaining its document source."""

    chunk_id: str
    document_id: str
    index: int
    text: str
    start_char: int
    end_char: int
    source: SourceRef
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievalHit:
    """A ranked chunk with a stable source reference and matched terms."""

    chunk: DocumentChunk
    score: float
    matched_terms: Tuple[str, ...]


@dataclass(frozen=True)
class VectorRetrievalHit:
    """A ranked source-bearing chunk returned by vector similarity search."""

    chunk: DocumentChunk
    score: float


@dataclass(frozen=True)
class RerankedRetrievalHit:
    """A host-reranked hit retaining its retrieval score and source."""

    chunk: DocumentChunk
    score: float
    original_score: float


class RetrievalReranker(Protocol):
    """Host-owned provider-neutral score seam for retrieval candidates."""

    def score(self, query: str, chunk: DocumentChunk) -> Result[float, Error]:
        """Return one finite score for a bounded candidate chunk."""


class EmbeddingProvider(Protocol):
    """Optional host seam for producing vectors outside the MAPLE core."""

    def embed(self, text: str) -> Result[Sequence[float], Error]:
        """Return one bounded embedding vector for text."""


@dataclass(frozen=True)
class ChunkingPolicy:
    """Bounds for deterministic character-based text chunking."""

    max_chars: int = 1_200
    overlap_chars: int = 200
    max_chunks: int = 10_000
    max_document_bytes: int = 5 * 1024 * 1024

    def validate(self) -> Optional[Error]:
        for name, value in (
            ("max_chars", self.max_chars),
            ("max_chunks", self.max_chunks),
            ("max_document_bytes", self.max_document_bytes),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                return _error("RETRIEVAL_CONFIG_INVALID", f"{name} must be positive.")
        if (
            not isinstance(self.overlap_chars, int)
            or isinstance(self.overlap_chars, bool)
            or self.overlap_chars < 0
            or self.overlap_chars >= self.max_chars
        ):
            return _error(
                "RETRIEVAL_CONFIG_INVALID",
                "overlap_chars must be non-negative and smaller than max_chars.",
            )
        return None


class TextChunker:
    """Split documents at bounded whitespace-aware character windows."""

    def __init__(self, policy: Optional[ChunkingPolicy] = None) -> None:
        self.policy = policy or ChunkingPolicy()

    def chunk(self, document: Document) -> Result[List[DocumentChunk], Error]:
        policy_error = self.policy.validate()
        if policy_error is not None:
            return Result.err(policy_error)
        document_error = document.validate()
        if document_error is not None:
            return Result.err(document_error)
        if not document.text:
            return Result.ok([])
        if len(document.text.encode("utf-8")) > self.policy.max_document_bytes:
            return Result.err(
                _error(
                    "RETRIEVAL_DOCUMENT_TOO_LARGE", "document exceeds the byte limit."
                )
            )

        chunks: List[DocumentChunk] = []
        position = 0
        text_length = len(document.text)
        while position < text_length:
            if len(chunks) >= self.policy.max_chunks:
                return Result.err(
                    _error("RETRIEVAL_CHUNK_LIMIT", "document exceeds the chunk limit.")
                )
            window_end = min(position + self.policy.max_chars, text_length)
            cut_end = window_end
            if window_end < text_length:
                lower_bound = position + max(1, self.policy.max_chars // 2)
                for candidate in range(window_end, lower_bound, -1):
                    if document.text[candidate - 1].isspace():
                        cut_end = candidate - 1
                        break
            raw = document.text[position:cut_end]
            leading = len(raw) - len(raw.lstrip())
            trailing = len(raw.rstrip())
            start_char = position + leading
            end_char = position + trailing
            if start_char >= end_char:
                position = max(position + 1, window_end)
                continue
            chunk_index = len(chunks)
            chunks.append(
                DocumentChunk(
                    chunk_id=f"{document.document_id}:{chunk_index}",
                    document_id=document.document_id,
                    index=chunk_index,
                    text=document.text[start_char:end_char],
                    start_char=start_char,
                    end_char=end_char,
                    source=document.source,
                    metadata=dict(document.metadata),
                )
            )
            if end_char >= text_length:
                break
            position = max(position + 1, end_char - self.policy.overlap_chars)
        return Result.ok(chunks)


class RetrievalBackend(Protocol):
    """Backend contract for retrieval adapters."""

    def add_document(self, document: Document) -> Result[List[DocumentChunk], Error]:
        """Ingest a document and return its chunks."""

    def remove_document(self, document_id: str) -> Result[bool, Error]:
        """Remove a document and its chunks."""

    def search(
        self, query: str, *, top_k: int = 5, min_score: float = 0.0
    ) -> Result[List[RetrievalHit], Error]:
        """Return ranked source-bearing hits."""


def _tokens(value: str) -> List[str]:
    return [token.casefold() for token in _TOKEN_PATTERN.findall(value)]


def rerank_hits(
    query: str,
    candidates: Sequence[Union[RetrievalHit, VectorRetrievalHit]],
    reranker: RetrievalReranker,
    *,
    top_k: int = 5,
    max_candidates: int = 100,
) -> Result[List[RerankedRetrievalHit], Error]:
    """Apply a bounded host-owned reranker to lexical or vector hits.

    MAPLE validates the callback boundary and ordering but does not select a
    model, make network calls, or claim that a score measures faithfulness.
    """
    if (
        not isinstance(max_candidates, int)
        or isinstance(max_candidates, bool)
        or not 0 < max_candidates <= _MAX_RERANK_CANDIDATES
    ):
        return Result.err(
            _error(
                "RETRIEVAL_RERANK_CONFIG_INVALID",
                "max_candidates must be between 1 and 100.",
            )
        )
    if not isinstance(query, str) or not query.strip():
        return Result.err(_error("RETRIEVAL_QUERY_INVALID", "query must not be empty."))
    if len(query.encode("utf-8")) > 16_384:
        return Result.err(
            _error("RETRIEVAL_QUERY_TOO_LARGE", "query exceeds the byte limit.")
        )
    if (
        not isinstance(top_k, int)
        or isinstance(top_k, bool)
        or not 1 <= top_k <= max_candidates
    ):
        return Result.err(
            _error("RETRIEVAL_RERANK_LIMIT", "top_k is outside the allowed range.")
        )
    if isinstance(candidates, (str, bytes)) or not isinstance(candidates, Sequence):
        return Result.err(
            _error("RETRIEVAL_CANDIDATE_INVALID", "candidates must be a sequence.")
        )
    if len(candidates) > max_candidates:
        return Result.err(_error("RETRIEVAL_RERANK_LIMIT", "candidate limit exceeded."))
    scorer = getattr(reranker, "score", None)
    if not callable(scorer):
        return Result.err(
            _error("RETRIEVAL_RERANKER_INVALID", "reranker must expose score(...).")
        )

    ranked: List[RerankedRetrievalHit] = []
    seen_chunk_ids: Set[str] = set()
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, (RetrievalHit, VectorRetrievalHit)):
            return Result.err(
                _error(
                    "RETRIEVAL_CANDIDATE_INVALID",
                    "candidates must be retrieval hit values.",
                    index=index,
                )
            )
        if not isinstance(candidate.chunk, DocumentChunk):
            return Result.err(
                _error(
                    "RETRIEVAL_CANDIDATE_INVALID",
                    "candidate chunks must be DocumentChunk values.",
                    index=index,
                )
            )
        chunk_id = candidate.chunk.chunk_id
        if _validate_identifier(chunk_id, "chunk_id") is not None:
            return Result.err(
                _error(
                    "RETRIEVAL_CANDIDATE_INVALID",
                    "candidate chunk IDs must be bounded strings.",
                    index=index,
                )
            )
        if chunk_id in seen_chunk_ids:
            return Result.err(
                _error(
                    "RETRIEVAL_CANDIDATE_INVALID",
                    "candidate chunk IDs must be unique.",
                    index=index,
                )
            )
        seen_chunk_ids.add(chunk_id)
        if (
            isinstance(candidate.score, bool)
            or not isinstance(candidate.score, (int, float))
            or not math.isfinite(float(candidate.score))
        ):
            return Result.err(
                _error(
                    "RETRIEVAL_CANDIDATE_INVALID",
                    "candidate scores must be finite numbers.",
                    index=index,
                )
            )
        try:
            score_result = scorer(query, candidate.chunk)
        except Exception:
            return Result.err(
                _error(
                    "RETRIEVAL_RERANKER_ERROR",
                    "reranker callback failed.",
                    index=index,
                )
            )
        if not isinstance(score_result, Result) or score_result.is_err():
            return Result.err(
                _error(
                    "RETRIEVAL_RERANKER_ERROR",
                    "reranker callback returned an error.",
                    index=index,
                )
            )
        score = score_result.unwrap()
        if (
            isinstance(score, bool)
            or not isinstance(score, (int, float))
            or not math.isfinite(float(score))
        ):
            return Result.err(
                _error(
                    "RETRIEVAL_RERANKER_RESULT_INVALID",
                    "reranker scores must be finite numbers.",
                    index=index,
                )
            )
        ranked.append(
            RerankedRetrievalHit(
                chunk=candidate.chunk,
                score=float(score),
                original_score=float(candidate.score),
            )
        )
    ranked.sort(key=lambda hit: (-hit.score, hit.chunk.chunk_id))
    return Result.ok(ranked[:top_k])


class InMemoryLexicalRetriever:
    """Small deterministic lexical retriever for local use and contract tests."""

    def __init__(
        self,
        chunker: Optional[TextChunker] = None,
        *,
        max_documents: int = 1_000,
        max_chunks: int = 100_000,
        max_query_bytes: int = 16_384,
        max_results: int = 100,
    ) -> None:
        self.chunker = chunker or TextChunker()
        self.max_documents = max_documents
        self.max_chunks = max_chunks
        self.max_query_bytes = max_query_bytes
        self.max_results = max_results
        self._documents: Dict[str, Document] = {}
        self._chunks: Dict[str, DocumentChunk] = {}
        self._term_counts: Dict[str, Counter[str]] = {}
        self._term_index: Dict[str, Set[str]] = defaultdict(set)
        self._lock = threading.RLock()

    def _validate_limits(self) -> Optional[Error]:
        for name, value in (
            ("max_documents", self.max_documents),
            ("max_chunks", self.max_chunks),
            ("max_query_bytes", self.max_query_bytes),
            ("max_results", self.max_results),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                return _error("RETRIEVAL_CONFIG_INVALID", f"{name} must be positive.")
        return None

    def add_document(self, document: Document) -> Result[List[DocumentChunk], Error]:
        limits_error = self._validate_limits()
        if limits_error is not None:
            return Result.err(limits_error)
        with self._lock:
            if document.document_id in self._documents:
                return Result.err(
                    _error(
                        "RETRIEVAL_DUPLICATE_DOCUMENT",
                        "document_id is already indexed.",
                    )
                )
            if len(self._documents) >= self.max_documents:
                return Result.err(
                    _error("RETRIEVAL_DOCUMENT_LIMIT", "document limit reached.")
                )
        chunks_result = self.chunker.chunk(document)
        if chunks_result.is_err():
            return Result.err(chunks_result.unwrap_err())
        chunks = chunks_result.unwrap()
        with self._lock:
            if len(self._chunks) + len(chunks) > self.max_chunks:
                return Result.err(
                    _error("RETRIEVAL_CHUNK_LIMIT", "retriever chunk limit reached.")
                )
            self._documents[document.document_id] = document
            for chunk in chunks:
                counts = Counter(_tokens(chunk.text))
                self._chunks[chunk.chunk_id] = chunk
                self._term_counts[chunk.chunk_id] = counts
                for term in counts:
                    self._term_index[term].add(chunk.chunk_id)
        return Result.ok(chunks)

    def remove_document(self, document_id: str) -> Result[bool, Error]:
        error = _validate_identifier(document_id, "document_id")
        if error is not None:
            return Result.err(error)
        with self._lock:
            document = self._documents.pop(document_id, None)
            if document is None:
                return Result.ok(False)
            chunk_ids = [
                chunk_id
                for chunk_id, chunk in self._chunks.items()
                if chunk.document_id == document_id
            ]
            for chunk_id in chunk_ids:
                counts = self._term_counts.pop(chunk_id, Counter())
                for term in counts:
                    ids = self._term_index[term]
                    ids.discard(chunk_id)
                    if not ids:
                        del self._term_index[term]
                del self._chunks[chunk_id]
        return Result.ok(True)

    def search(
        self, query: str, *, top_k: int = 5, min_score: float = 0.0
    ) -> Result[List[RetrievalHit], Error]:
        limits_error = self._validate_limits()
        if limits_error is not None:
            return Result.err(limits_error)
        if not isinstance(query, str) or not query.strip():
            return Result.err(
                _error("RETRIEVAL_QUERY_INVALID", "query must not be empty.")
            )
        if len(query.encode("utf-8")) > self.max_query_bytes:
            return Result.err(
                _error("RETRIEVAL_QUERY_TOO_LARGE", "query exceeds the byte limit.")
            )
        if (
            not isinstance(top_k, int)
            or isinstance(top_k, bool)
            or not 1 <= top_k <= self.max_results
        ):
            return Result.err(
                _error("RETRIEVAL_QUERY_INVALID", "top_k is outside the allowed range.")
            )
        if (
            not isinstance(min_score, (int, float))
            or isinstance(min_score, bool)
            or not math.isfinite(min_score)
            or min_score < 0
        ):
            return Result.err(
                _error(
                    "RETRIEVAL_QUERY_INVALID",
                    "min_score must be finite and non-negative.",
                )
            )
        query_terms = set(_tokens(query))
        if not query_terms:
            return Result.ok([])
        with self._lock:
            candidate_ids = set().union(
                *(self._term_index.get(term, set()) for term in query_terms)
            )
            total_chunks = max(1, len(self._chunks))
            scored: List[RetrievalHit] = []
            for chunk_id in candidate_ids:
                counts = self._term_counts[chunk_id]
                matched = tuple(sorted(term for term in query_terms if term in counts))
                score = 0.0
                for term in matched:
                    document_frequency = len(self._term_index[term])
                    inverse_frequency = (
                        math.log((total_chunks + 1) / (document_frequency + 1)) + 1.0
                    )
                    score += (1.0 + math.log(counts[term])) * inverse_frequency
                score /= max(1.0, math.sqrt(sum(counts.values())))
                if score >= min_score:
                    scored.append(
                        RetrievalHit(
                            chunk=self._chunks[chunk_id],
                            score=score,
                            matched_terms=matched,
                        )
                    )
        scored.sort(key=lambda hit: (-hit.score, hit.chunk.chunk_id))
        return Result.ok(scored[:top_k])

    def stats(self) -> Dict[str, int]:
        """Return bounded index counts for observability."""
        with self._lock:
            return {
                "documents": len(self._documents),
                "chunks": len(self._chunks),
                "terms": len(self._term_index),
            }


def _validate_vector(
    vector: Any,
    *,
    max_dimensions: int,
    field_name: str,
) -> Result[Tuple[float, ...], Error]:
    if isinstance(vector, (str, bytes)) or not isinstance(vector, Sequence):
        return Result.err(
            _error(
                "RETRIEVAL_VECTOR_INVALID",
                f"{field_name} must be a numeric sequence.",
            )
        )
    if not vector or len(vector) > max_dimensions:
        return Result.err(
            _error(
                "RETRIEVAL_VECTOR_INVALID",
                f"{field_name} dimensions are outside the allowed range.",
                max_dimensions=max_dimensions,
            )
        )
    values: List[float] = []
    for index, value in enumerate(vector):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return Result.err(
                _error(
                    "RETRIEVAL_VECTOR_INVALID",
                    f"{field_name} contains a non-numeric value.",
                    index=index,
                )
            )
        converted = float(value)
        if not math.isfinite(converted):
            return Result.err(
                _error(
                    "RETRIEVAL_VECTOR_INVALID",
                    f"{field_name} contains a non-finite value.",
                    index=index,
                )
            )
        values.append(converted)
    if math.sqrt(sum(value * value for value in values)) <= 0.0:
        return Result.err(
            _error("RETRIEVAL_VECTOR_INVALID", f"{field_name} must not be zero.")
        )
    return Result.ok(tuple(values))


class InMemoryVectorRetriever:
    """Bounded cosine-similarity index over caller-supplied embeddings.

    MAPLE validates and indexes vectors but does not select an embedding model
    or call a hosted provider. Hosts can connect an ``EmbeddingProvider`` and
    retain the same source-bearing chunk contract.
    """

    def __init__(
        self,
        chunker: Optional[TextChunker] = None,
        *,
        max_documents: int = 1_000,
        max_vectors: int = 100_000,
        max_dimensions: int = 4_096,
        max_results: int = 100,
    ) -> None:
        self.chunker = chunker or TextChunker()
        self.max_documents = max_documents
        self.max_vectors = max_vectors
        self.max_dimensions = max_dimensions
        self.max_results = max_results
        self._documents: Dict[str, Document] = {}
        self._chunks: Dict[str, DocumentChunk] = {}
        self._vectors: Dict[str, Tuple[float, ...]] = {}
        self._dimension: Optional[int] = None
        self._lock = threading.RLock()

    def _validate_limits(self) -> Optional[Error]:
        for name, value in (
            ("max_documents", self.max_documents),
            ("max_vectors", self.max_vectors),
            ("max_dimensions", self.max_dimensions),
            ("max_results", self.max_results),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                return _error("RETRIEVAL_CONFIG_INVALID", f"{name} must be positive.")
        return None

    def add_document(
        self, document: Document, embeddings: Sequence[Sequence[float]]
    ) -> Result[List[DocumentChunk], Error]:
        limits_error = self._validate_limits()
        if limits_error is not None:
            return Result.err(limits_error)
        if isinstance(embeddings, (str, bytes)) or not isinstance(embeddings, Sequence):
            return Result.err(
                _error(
                    "RETRIEVAL_VECTOR_INVALID",
                    "embeddings must be a bounded sequence of vectors.",
                )
            )
        document_error = document.validate()
        if document_error is not None:
            return Result.err(document_error)
        chunks_result = self.chunker.chunk(document)
        if chunks_result.is_err():
            return Result.err(chunks_result.unwrap_err())
        chunks = chunks_result.unwrap()
        if len(embeddings) != len(chunks):
            return Result.err(
                _error(
                    "RETRIEVAL_VECTOR_COUNT_MISMATCH",
                    "One embedding is required for each document chunk.",
                    chunks=len(chunks),
                    embeddings=len(embeddings),
                )
            )
        vectors: List[Tuple[float, ...]] = []
        local_dimension: Optional[int] = None
        for index, embedding in enumerate(embeddings):
            vector_result = _validate_vector(
                embedding,
                max_dimensions=self.max_dimensions,
                field_name=f"embedding[{index}]",
            )
            if vector_result.is_err():
                return Result.err(vector_result.unwrap_err())
            vector = vector_result.unwrap()
            if local_dimension is None:
                local_dimension = len(vector)
            if len(vector) != local_dimension:
                return Result.err(
                    _error(
                        "RETRIEVAL_VECTOR_DIMENSION_MISMATCH",
                        "Embeddings in one document must share dimensions.",
                    )
                )
            vectors.append(vector)
        with self._lock:
            if document.document_id in self._documents:
                return Result.err(
                    _error(
                        "RETRIEVAL_DUPLICATE_DOCUMENT",
                        "document_id is already indexed.",
                    )
                )
            if len(self._documents) >= self.max_documents:
                return Result.err(
                    _error("RETRIEVAL_DOCUMENT_LIMIT", "document limit reached.")
                )
            if len(self._vectors) + len(vectors) > self.max_vectors:
                return Result.err(
                    _error("RETRIEVAL_VECTOR_LIMIT", "vector limit reached.")
                )
            if (
                local_dimension is not None
                and self._dimension is not None
                and local_dimension != self._dimension
            ):
                return Result.err(
                    _error(
                        "RETRIEVAL_VECTOR_DIMENSION_MISMATCH",
                        "All indexed embeddings must share dimensions.",
                        expected=self._dimension,
                        actual=local_dimension,
                    )
                )
            self._documents[document.document_id] = document
            if local_dimension is not None:
                self._dimension = local_dimension
            for chunk, vector in zip(chunks, vectors):
                self._chunks[chunk.chunk_id] = chunk
                self._vectors[chunk.chunk_id] = vector
        return Result.ok(chunks)

    def remove_document(self, document_id: str) -> Result[bool, Error]:
        error = _validate_identifier(document_id, "document_id")
        if error is not None:
            return Result.err(error)
        with self._lock:
            document = self._documents.pop(document_id, None)
            if document is None:
                return Result.ok(False)
            chunk_ids = [
                chunk_id
                for chunk_id, chunk in self._chunks.items()
                if chunk.document_id == document_id
            ]
            for chunk_id in chunk_ids:
                del self._chunks[chunk_id]
                del self._vectors[chunk_id]
            if not self._vectors:
                self._dimension = None
        return Result.ok(True)

    def search(
        self,
        query_vector: Sequence[float],
        *,
        top_k: int = 5,
        min_score: float = 0.0,
    ) -> Result[List[VectorRetrievalHit], Error]:
        limits_error = self._validate_limits()
        if limits_error is not None:
            return Result.err(limits_error)
        if (
            not isinstance(top_k, int)
            or isinstance(top_k, bool)
            or not 1 <= top_k <= self.max_results
        ):
            return Result.err(
                _error("RETRIEVAL_QUERY_INVALID", "top_k is outside the allowed range.")
            )
        if (
            not isinstance(min_score, (int, float))
            or isinstance(min_score, bool)
            or not math.isfinite(min_score)
            or not -1.0 <= min_score <= 1.0
        ):
            return Result.err(
                _error(
                    "RETRIEVAL_QUERY_INVALID",
                    "min_score must be finite and between -1 and 1.",
                )
            )
        vector_result = _validate_vector(
            query_vector,
            max_dimensions=self.max_dimensions,
            field_name="query_vector",
        )
        if vector_result.is_err():
            return Result.err(vector_result.unwrap_err())
        query = vector_result.unwrap()
        with self._lock:
            if self._dimension is not None and len(query) != self._dimension:
                return Result.err(
                    _error(
                        "RETRIEVAL_VECTOR_DIMENSION_MISMATCH",
                        "Query dimensions do not match the index.",
                        expected=self._dimension,
                        actual=len(query),
                    )
                )
            query_norm = math.sqrt(sum(value * value for value in query))
            scored: List[VectorRetrievalHit] = []
            for chunk_id, vector in self._vectors.items():
                score = sum(left * right for left, right in zip(query, vector))
                score /= query_norm * math.sqrt(sum(value * value for value in vector))
                if score >= min_score:
                    scored.append(
                        VectorRetrievalHit(
                            chunk=self._chunks[chunk_id],
                            score=score,
                        )
                    )
        scored.sort(key=lambda hit: (-hit.score, hit.chunk.chunk_id))
        return Result.ok(scored[:top_k])

    def stats(self) -> Dict[str, int]:
        """Return bounded vector-index counts for observability."""
        with self._lock:
            return {
                "documents": len(self._documents),
                "vectors": len(self._vectors),
                "dimensions": self._dimension or 0,
            }
