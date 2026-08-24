"""Bounded document, chunk, and retrieval primitives for MAPLE agents."""

from __future__ import annotations

import json
import math
import re
import threading
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Protocol, Set, Tuple

from ..core.result import Result

Error = Dict[str, Any]
_TOKEN_PATTERN = re.compile(r"\w+", re.UNICODE)


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
            return metadata_size.unwrap_err()
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
            return metadata_size.unwrap_err()
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
