"""Bounded document, chunk, and retrieval primitives for MAPLE agents."""

from __future__ import annotations

import json
import math
import os
import re
import tempfile
import threading
import time
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import (
    Any,
    Callable,
    Deque,
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
from .durable_leases import DurableRecordLease

Error = Dict[str, Any]
_TOKEN_PATTERN = re.compile(r"\w+", re.UNICODE)
_MAX_RERANK_CANDIDATES = 100
_MAX_CONNECTOR_BATCH_SIZE = 100
_MAX_CONNECTOR_DOCUMENTS = 10_000
_MAX_CONNECTOR_BATCHES = 100
_DEFAULT_MAX_CHECKPOINT_BYTES = 4_096
_CHECKPOINT_VERSION = 1
DEFAULT_MAX_LEXICAL_INDEX_BYTES = 16 * 1024 * 1024
_MAX_LEXICAL_INDEX_BYTES = 64 * 1024 * 1024
_LEXICAL_INDEX_VERSION = 1
DEFAULT_MAX_VECTOR_INDEX_BYTES = 16 * 1024 * 1024
_MAX_VECTOR_INDEX_BYTES = 64 * 1024 * 1024
_VECTOR_INDEX_VERSION = 1
_MAX_FILE_VECTOR_DOCUMENTS = 100_000
_MAX_FILE_VECTOR_COUNT = 1_000_000
_MAX_FILE_VECTOR_DIMENSIONS = 16_384
_MAX_FILE_VECTOR_RESULTS = 100_000


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
class DocumentBatch:
    """One bounded connector page of source-bearing documents."""

    documents: Tuple[Document, ...]
    next_cursor: Optional[str] = None

    def validate(
        self, *, max_documents: int = _MAX_CONNECTOR_BATCH_SIZE
    ) -> Optional[Error]:
        """Validate page shape, document identities, and cursor bounds."""
        if (
            not isinstance(max_documents, int)
            or isinstance(max_documents, bool)
            or not 0 < max_documents <= _MAX_CONNECTOR_BATCH_SIZE
        ):
            return _error(
                "RETRIEVAL_CONNECTOR_LIMIT",
                "max_documents must be between 1 and 100.",
            )
        if isinstance(self.documents, (str, bytes)) or not isinstance(
            self.documents, Sequence
        ):
            return _error(
                "RETRIEVAL_CONNECTOR_INVALID",
                "documents must be a bounded sequence.",
            )
        if len(self.documents) > max_documents:
            return _error(
                "RETRIEVAL_CONNECTOR_LIMIT",
                "connector batch exceeds the requested limit.",
            )
        if self.next_cursor is not None:
            cursor_error = _validate_identifier(self.next_cursor, "next_cursor")
            if cursor_error is not None:
                return _error(
                    "RETRIEVAL_CONNECTOR_INVALID",
                    "next_cursor must be a bounded string.",
                )
        if not self.documents and self.next_cursor is not None:
            return _error(
                "RETRIEVAL_CONNECTOR_INVALID",
                "an empty page must not advance the cursor.",
            )
        seen_document_ids: Set[str] = set()
        for index, document in enumerate(self.documents):
            if not isinstance(document, Document) or document.validate() is not None:
                return _error(
                    "RETRIEVAL_CONNECTOR_INVALID",
                    "connector returned an invalid document.",
                    index=index,
                )
            if document.document_id in seen_document_ids:
                return _error(
                    "RETRIEVAL_CONNECTOR_DUPLICATE_DOCUMENT",
                    "connector returned a duplicate document ID.",
                    index=index,
                )
            seen_document_ids.add(document.document_id)
        return None


class DocumentConnector(Protocol):
    """Host-owned cursor source for bounded document pages."""

    def fetch(
        self, cursor: Optional[str], *, limit: int
    ) -> Result[DocumentBatch, Error]:
        """Return one page and an optional opaque continuation cursor."""


class DocumentIngestor(Protocol):
    """Sink contract for adding one validated document to a retrieval index."""

    def add_document(self, document: Document) -> Result[List[DocumentChunk], Error]:
        """Add a document and return its generated chunks."""


@dataclass(frozen=True)
class DocumentCursorCheckpoint:
    """One bounded durable position for a document connector stream."""

    cursor: Optional[str] = None
    complete: bool = False
    revision: int = 0

    def validate(self) -> Optional[Error]:
        if self.cursor is not None and _validate_identifier(self.cursor, "cursor"):
            return _error(
                "RETRIEVAL_CHECKPOINT_INVALID",
                "checkpoint cursor must be a bounded string.",
            )
        if not isinstance(self.complete, bool):
            return _error(
                "RETRIEVAL_CHECKPOINT_INVALID",
                "checkpoint complete must be a boolean.",
            )
        if (
            not isinstance(self.revision, int)
            or isinstance(self.revision, bool)
            or self.revision < 0
        ):
            return _error(
                "RETRIEVAL_CHECKPOINT_INVALID",
                "checkpoint revision must be a non-negative integer.",
            )
        if self.complete and self.cursor is not None:
            return _error(
                "RETRIEVAL_CHECKPOINT_INVALID",
                "a complete checkpoint must not retain a cursor.",
            )
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Return the JSON-safe checkpoint representation."""
        return {
            "cursor": self.cursor,
            "complete": self.complete,
            "revision": self.revision,
        }

    @classmethod
    def from_dict(
        cls, data: Mapping[str, Any]
    ) -> Result["DocumentCursorCheckpoint", Error]:
        """Parse and validate a persisted checkpoint mapping."""
        if not isinstance(data, Mapping):
            return Result.err(
                _error("RETRIEVAL_CHECKPOINT_INVALID", "checkpoint record is invalid.")
            )
        checkpoint = cls(
            cursor=data.get("cursor"),
            complete=data.get("complete", False),
            revision=data.get("revision", 0),
        )
        error = checkpoint.validate()
        if error is not None:
            return Result.err(error)
        return Result.ok(checkpoint)


class DocumentCursorCheckpointStore(Protocol):
    """Host-owned durable position contract for connector ingestion."""

    def load(self) -> Result[DocumentCursorCheckpoint, Error]:
        """Load the latest checkpoint or an empty initial position."""

    def save(
        self, checkpoint: DocumentCursorCheckpoint
    ) -> Result[DocumentCursorCheckpoint, Error]:
        """Persist the next revision without allowing stale writers."""

    def clear(self) -> Result[DocumentCursorCheckpoint, Error]:
        """Reset the stream position while retaining fencing revision."""


class DocumentConnectorRateLimiter(Protocol):
    """Host-owned admission contract checked before each connector fetch."""

    def allow(self) -> Result[None, Error]:
        """Consume one bounded fetch allowance or return a typed denial."""


class InMemoryDocumentConnectorRateLimiter:
    """Thread-safe trailing-window limiter for one connector instance."""

    def __init__(
        self,
        max_calls: int,
        window_seconds: float,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if (
            not isinstance(max_calls, int)
            or isinstance(max_calls, bool)
            or not 1 <= max_calls <= 10_000
        ):
            raise ValueError("max_calls must be between 1 and 10000")
        if (
            not isinstance(window_seconds, (int, float))
            or isinstance(window_seconds, bool)
            or not math.isfinite(float(window_seconds))
            or not 0.001 <= float(window_seconds) <= 86_400.0
        ):
            raise ValueError("window_seconds must be between 0.001 and 86400")
        if not callable(clock):
            raise ValueError("clock must be callable")
        self.max_calls = max_calls
        self.window_seconds = float(window_seconds)
        self._clock = clock
        self._timestamps: Deque[float] = deque()
        self._lock = threading.RLock()

    def allow(self) -> Result[None, Error]:
        """Consume one allowance without sleeping or retrying."""
        try:
            now = float(self._clock())
        except Exception:
            return Result.err(
                _error(
                    "RETRIEVAL_CONNECTOR_RATE_LIMITER_ERROR",
                    "connector rate limiter clock failed.",
                )
            )
        if not math.isfinite(now):
            return Result.err(
                _error(
                    "RETRIEVAL_CONNECTOR_RATE_LIMITER_ERROR",
                    "connector rate limiter clock is invalid.",
                )
            )
        with self._lock:
            if self._timestamps and now < self._timestamps[-1]:
                return Result.err(
                    _error(
                        "RETRIEVAL_CONNECTOR_RATE_LIMITER_ERROR",
                        "connector rate limiter clock moved backwards.",
                    )
                )
            cutoff = now - self.window_seconds
            while self._timestamps and self._timestamps[0] <= cutoff:
                self._timestamps.popleft()
            if len(self._timestamps) >= self.max_calls:
                retry_after = min(
                    self.window_seconds,
                    max(0.0, self._timestamps[0] + self.window_seconds - now),
                )
                return Result.err(
                    _error(
                        "RETRIEVAL_CONNECTOR_RATE_LIMITED",
                        "connector rate limit exceeded.",
                        retry_after_seconds=retry_after,
                    )
                )
            self._timestamps.append(now)
            return Result.ok(None)


class InMemoryDocumentCursorCheckpointStore:
    """Thread-safe one-process checkpoint storage for a connector stream."""

    def __init__(self, checkpoint: Optional[DocumentCursorCheckpoint] = None) -> None:
        if checkpoint is not None and (
            not isinstance(checkpoint, DocumentCursorCheckpoint)
            or checkpoint.validate() is not None
        ):
            raise ValueError("checkpoint is invalid")
        self._checkpoint = checkpoint or DocumentCursorCheckpoint()
        self._lock = threading.RLock()

    def load(self) -> Result[DocumentCursorCheckpoint, Error]:
        """Return the current immutable checkpoint."""
        with self._lock:
            return Result.ok(self._checkpoint)

    def save(
        self, checkpoint: DocumentCursorCheckpoint
    ) -> Result[DocumentCursorCheckpoint, Error]:
        """Persist one strictly next revision."""
        if not isinstance(checkpoint, DocumentCursorCheckpoint):
            return Result.err(
                _error(
                    "RETRIEVAL_CHECKPOINT_INVALID",
                    "checkpoint must be a DocumentCursorCheckpoint.",
                )
            )
        error = checkpoint.validate()
        if error is not None:
            return Result.err(error)
        with self._lock:
            expected = self._checkpoint.revision + 1
            if checkpoint.revision != expected:
                return Result.err(
                    _error(
                        "RETRIEVAL_CHECKPOINT_CONFLICT",
                        "checkpoint revision is stale or skipped.",
                        expected_revision=expected,
                        requested_revision=checkpoint.revision,
                    )
                )
            self._checkpoint = checkpoint
            return Result.ok(checkpoint)

    def clear(self) -> Result[DocumentCursorCheckpoint, Error]:
        """Reset the cursor and advance the fencing revision."""
        with self._lock:
            self._checkpoint = DocumentCursorCheckpoint(
                revision=self._checkpoint.revision + 1
            )
            return Result.ok(self._checkpoint)


class FileDocumentCursorCheckpointStore:
    """Atomic, bounded, cross-process checkpoint storage for one stream."""

    _FILENAME = "checkpoint.json"
    _TEMP_PREFIX = ".maple-retrieval-checkpoint-"

    def __init__(
        self,
        directory: Union[str, Path],
        *,
        max_bytes: int = _DEFAULT_MAX_CHECKPOINT_BYTES,
        lease_ttl_seconds: float = 30.0,
    ) -> None:
        if (
            not isinstance(max_bytes, int)
            or isinstance(max_bytes, bool)
            or not 512 <= max_bytes <= 1_048_576
        ):
            raise ValueError("max_bytes must be between 512 and 1048576")
        self.max_bytes = max_bytes
        self.directory = Path(directory)
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ValueError("retrieval checkpoint directory is unavailable") from exc
        if not self.directory.is_dir():
            raise ValueError("retrieval checkpoint path must be a directory")
        self.path = self.directory / self._FILENAME
        self._lock = threading.RLock()
        try:
            self._lease = DurableRecordLease(
                self.directory,
                namespace="retrieval-connector",
                holder_label="document-checkpoint",
                lease_ttl_seconds=lease_ttl_seconds,
            )
        except (OSError, TypeError, ValueError) as exc:
            raise ValueError("retrieval checkpoint lease is unavailable") from exc

    def _read_unlocked(self) -> Result[DocumentCursorCheckpoint, Error]:
        if not self.path.exists():
            return Result.ok(DocumentCursorCheckpoint())
        try:
            if self.path.stat().st_size > self.max_bytes:
                return Result.err(
                    _error(
                        "RETRIEVAL_CHECKPOINT_LOAD_ERROR",
                        "retrieval checkpoint exceeds the byte limit.",
                    )
                )
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, TypeError, ValueError, json.JSONDecodeError):
            return Result.err(
                _error(
                    "RETRIEVAL_CHECKPOINT_LOAD_ERROR",
                    "retrieval checkpoint could not be loaded.",
                )
            )
        version = data.get("version") if isinstance(data, Mapping) else None
        if (
            not isinstance(version, int)
            or isinstance(version, bool)
            or version != _CHECKPOINT_VERSION
        ):
            return Result.err(
                _error(
                    "RETRIEVAL_CHECKPOINT_LOAD_ERROR",
                    "retrieval checkpoint version is invalid.",
                )
            )
        parsed = DocumentCursorCheckpoint.from_dict(data.get("checkpoint", {}))
        if parsed.is_err():
            return Result.err(
                _error(
                    "RETRIEVAL_CHECKPOINT_LOAD_ERROR",
                    "retrieval checkpoint record is invalid.",
                )
            )
        return parsed

    def _encode(self, checkpoint: DocumentCursorCheckpoint) -> Result[str, Error]:
        try:
            encoded = json.dumps(
                {"version": _CHECKPOINT_VERSION, "checkpoint": checkpoint.to_dict()},
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            )
        except (TypeError, ValueError, OverflowError):
            return Result.err(
                _error(
                    "RETRIEVAL_CHECKPOINT_SAVE_ERROR",
                    "retrieval checkpoint is not serializable.",
                )
            )
        if len(encoded.encode("utf-8")) > self.max_bytes:
            return Result.err(
                _error(
                    "RETRIEVAL_CHECKPOINT_SIZE",
                    "retrieval checkpoint exceeds the byte limit.",
                )
            )
        return Result.ok(encoded)

    def _write_unlocked(
        self, checkpoint: DocumentCursorCheckpoint
    ) -> Result[DocumentCursorCheckpoint, Error]:
        encoded = self._encode(checkpoint)
        if encoded.is_err():
            return Result.err(encoded.unwrap_err())
        temporary_path: Optional[Path] = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=str(self.directory),
                prefix=self._TEMP_PREFIX,
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary_path = Path(handle.name)
                handle.write(encoded.unwrap())
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(str(temporary_path), str(self.path))
            temporary_path = None
            return Result.ok(checkpoint)
        except (OSError, TypeError, ValueError) as exc:
            return Result.err(
                _error(
                    "RETRIEVAL_CHECKPOINT_SAVE_ERROR",
                    "retrieval checkpoint could not be saved.",
                    reason=type(exc).__name__,
                )
            )
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink()
                except OSError:
                    pass

    def _run(
        self,
        operation: str,
        callback: Callable[[], Result[Any, Error]],
    ) -> Result[Any, Error]:
        try:
            return self._lease.run(
                "checkpoint",
                operation,
                callback,
                acquire_error_type="RETRIEVAL_CHECKPOINT_LEASE_ERROR",
                acquire_error_message="retrieval checkpoint lease could not be acquired.",
                release_error_type="RETRIEVAL_CHECKPOINT_LEASE_RELEASE_ERROR",
                release_error_message="retrieval checkpoint lease could not be released.",
            )
        except Exception as exc:
            return Result.err(
                _error(
                    "RETRIEVAL_CHECKPOINT_ERROR",
                    "retrieval checkpoint operation failed.",
                    operation=operation,
                    reason=type(exc).__name__,
                )
            )

    def load(self) -> Result[DocumentCursorCheckpoint, Error]:
        """Load the checkpoint under a fencing lease."""
        with self._lock:
            result = self._run("load", self._read_unlocked)
        if result.is_err():
            return Result.err(result.unwrap_err())
        return Result.ok(result.unwrap())

    def save(
        self, checkpoint: DocumentCursorCheckpoint
    ) -> Result[DocumentCursorCheckpoint, Error]:
        """Atomically save one strictly next revision."""
        if not isinstance(checkpoint, DocumentCursorCheckpoint):
            return Result.err(
                _error(
                    "RETRIEVAL_CHECKPOINT_INVALID",
                    "checkpoint must be a DocumentCursorCheckpoint.",
                )
            )
        error = checkpoint.validate()
        if error is not None:
            return Result.err(error)

        def operation() -> Result[DocumentCursorCheckpoint, Error]:
            current = self._read_unlocked()
            if current.is_err():
                return Result.err(current.unwrap_err())
            expected = current.unwrap().revision + 1
            if checkpoint.revision != expected:
                return Result.err(
                    _error(
                        "RETRIEVAL_CHECKPOINT_CONFLICT",
                        "checkpoint revision is stale or skipped.",
                        expected_revision=expected,
                        requested_revision=checkpoint.revision,
                    )
                )
            return self._write_unlocked(checkpoint)

        with self._lock:
            result = self._run("save", operation)
        if result.is_err():
            return Result.err(result.unwrap_err())
        return Result.ok(result.unwrap())

    def clear(self) -> Result[DocumentCursorCheckpoint, Error]:
        """Reset the cursor and advance the fencing revision."""

        def operation() -> Result[DocumentCursorCheckpoint, Error]:
            current = self._read_unlocked()
            if current.is_err():
                return Result.err(current.unwrap_err())
            return self._write_unlocked(
                DocumentCursorCheckpoint(revision=current.unwrap().revision + 1)
            )

        with self._lock:
            result = self._run("clear", operation)
        if result.is_err():
            return Result.err(result.unwrap_err())
        return Result.ok(result.unwrap())


@dataclass(frozen=True)
class ConnectorIngestReport:
    """Bounded progress returned by one connector ingestion call."""

    documents_ingested: int
    batches_fetched: int
    next_cursor: Optional[str]
    complete: bool

    def to_dict(self) -> Dict[str, Any]:
        """Return the JSON-safe progress summary."""
        return {
            "documents_ingested": self.documents_ingested,
            "batches_fetched": self.batches_fetched,
            "next_cursor": self.next_cursor,
            "complete": self.complete,
        }


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


def ingest_documents(
    connector: DocumentConnector,
    sink: DocumentIngestor,
    *,
    cursor: Optional[str] = None,
    batch_size: int = _MAX_CONNECTOR_BATCH_SIZE,
    max_documents: int = 1_000,
    max_batches: int = _MAX_CONNECTOR_BATCHES,
    checkpoint_store: Optional[DocumentCursorCheckpointStore] = None,
    rate_limiter: Optional[DocumentConnectorRateLimiter] = None,
) -> Result[ConnectorIngestReport, Error]:
    """Ingest bounded connector pages into an explicit host-owned sink.

    The helper performs no retry, network operation, transaction, or rollback;
    connector and sink lifecycle policies remain with the host.
    """
    if (
        not isinstance(batch_size, int)
        or isinstance(batch_size, bool)
        or not 0 < batch_size <= _MAX_CONNECTOR_BATCH_SIZE
    ):
        return Result.err(
            _error(
                "RETRIEVAL_CONNECTOR_LIMIT",
                "batch_size must be between 1 and 100.",
            )
        )
    if (
        not isinstance(max_documents, int)
        or isinstance(max_documents, bool)
        or not 0 < max_documents <= _MAX_CONNECTOR_DOCUMENTS
    ):
        return Result.err(
            _error(
                "RETRIEVAL_CONNECTOR_LIMIT",
                "max_documents must be between 1 and 10000.",
            )
        )
    if (
        not isinstance(max_batches, int)
        or isinstance(max_batches, bool)
        or not 0 < max_batches <= _MAX_CONNECTOR_BATCHES
    ):
        return Result.err(
            _error(
                "RETRIEVAL_CONNECTOR_LIMIT",
                "max_batches must be between 1 and 100.",
            )
        )
    if cursor is not None and _validate_identifier(cursor, "cursor") is not None:
        return Result.err(
            _error("RETRIEVAL_CONNECTOR_INVALID", "cursor must be a bounded string.")
        )
    if checkpoint_store is not None and cursor is not None:
        return Result.err(
            _error(
                "RETRIEVAL_CHECKPOINT_INPUT_INVALID",
                "cursor cannot be combined with checkpoint_store.",
            )
        )
    fetch = getattr(connector, "fetch", None)
    add_document = getattr(sink, "add_document", None)
    if not callable(fetch):
        return Result.err(
            _error("RETRIEVAL_CONNECTOR_INVALID", "connector must expose fetch(...).")
        )
    if not callable(add_document):
        return Result.err(
            _error("RETRIEVAL_SINK_INVALID", "sink must expose add_document(...).")
        )
    allow_rate = None
    if rate_limiter is not None:
        allow_rate = getattr(rate_limiter, "allow", None)
        if not callable(allow_rate):
            return Result.err(
                _error(
                    "RETRIEVAL_CONNECTOR_RATE_LIMITER_INVALID",
                    "rate_limiter must expose allow(...).",
                )
            )
    allow_rate_method = cast(Callable[[], Any], allow_rate)

    checkpoint_revision = 0
    if checkpoint_store is not None:
        load_checkpoint = getattr(checkpoint_store, "load", None)
        save_checkpoint = getattr(checkpoint_store, "save", None)
        if not callable(load_checkpoint) or not callable(save_checkpoint):
            return Result.err(
                _error(
                    "RETRIEVAL_CHECKPOINT_INVALID",
                    "checkpoint_store must expose load(...) and save(...).",
                )
            )
        load_checkpoint_method = cast(Callable[[], Any], load_checkpoint)
        save_checkpoint_method = cast(Callable[..., Any], save_checkpoint)
        try:
            loaded_result = load_checkpoint_method()
        except Exception:
            return Result.err(
                _error(
                    "RETRIEVAL_CHECKPOINT_LOAD_ERROR",
                    "retrieval checkpoint could not be loaded.",
                )
            )
        if not isinstance(loaded_result, Result) or loaded_result.is_err():
            return Result.err(
                _error(
                    "RETRIEVAL_CHECKPOINT_LOAD_ERROR",
                    "retrieval checkpoint could not be loaded.",
                )
            )
        loaded_checkpoint = loaded_result.unwrap()
        if not isinstance(loaded_checkpoint, DocumentCursorCheckpoint):
            return Result.err(
                _error(
                    "RETRIEVAL_CHECKPOINT_LOAD_ERROR",
                    "retrieval checkpoint record is invalid.",
                )
            )
        checkpoint_error = loaded_checkpoint.validate()
        if checkpoint_error is not None:
            return Result.err(
                _error(
                    "RETRIEVAL_CHECKPOINT_LOAD_ERROR",
                    "retrieval checkpoint record is invalid.",
                )
            )
        if loaded_checkpoint.complete:
            return Result.ok(
                ConnectorIngestReport(
                    documents_ingested=0,
                    batches_fetched=0,
                    next_cursor=None,
                    complete=True,
                )
            )
        current_cursor = loaded_checkpoint.cursor
        checkpoint_revision = loaded_checkpoint.revision
    else:
        current_cursor = cursor

    def persist_checkpoint(next_cursor: Optional[str]) -> Optional[Error]:
        nonlocal checkpoint_revision
        if checkpoint_store is None:
            return None
        checkpoint = DocumentCursorCheckpoint(
            cursor=next_cursor,
            complete=next_cursor is None,
            revision=checkpoint_revision + 1,
        )
        try:
            saved_result = save_checkpoint_method(checkpoint)
        except Exception:
            return _error(
                "RETRIEVAL_CHECKPOINT_SAVE_ERROR",
                "retrieval checkpoint could not be saved.",
            )
        if (
            not isinstance(saved_result, Result)
            or saved_result.is_err()
            or saved_result.unwrap() != checkpoint
        ):
            return _error(
                "RETRIEVAL_CHECKPOINT_SAVE_ERROR",
                "retrieval checkpoint could not be saved.",
            )
        checkpoint_revision += 1
        return None

    documents_ingested = 0
    batches_fetched = 0
    seen_document_ids: Set[str] = set()
    while documents_ingested < max_documents and batches_fetched < max_batches:
        requested_limit = min(batch_size, max_documents - documents_ingested)
        if rate_limiter is not None:
            try:
                rate_result = allow_rate_method()
            except Exception:
                return Result.err(
                    _error(
                        "RETRIEVAL_CONNECTOR_RATE_LIMITER_ERROR",
                        "connector rate limiter failed.",
                        batch_index=batches_fetched,
                    )
                )
            if not isinstance(rate_result, Result):
                return Result.err(
                    _error(
                        "RETRIEVAL_CONNECTOR_RATE_LIMITER_ERROR",
                        "connector rate limiter returned an invalid result.",
                        batch_index=batches_fetched,
                    )
                )
            if rate_result.is_err():
                rate_error = rate_result.unwrap_err()
                if (
                    isinstance(rate_error, dict)
                    and rate_error.get("errorType")
                    == "RETRIEVAL_CONNECTOR_RATE_LIMITED"
                ):
                    retry_after = None
                    details = rate_error.get("details")
                    if isinstance(details, dict):
                        candidate = details.get("retry_after_seconds")
                        if (
                            isinstance(candidate, (int, float))
                            and not isinstance(candidate, bool)
                            and math.isfinite(float(candidate))
                            and 0.0 <= float(candidate) <= 86_400.0
                        ):
                            retry_after = float(candidate)
                    return Result.err(
                        _error(
                            "RETRIEVAL_CONNECTOR_RATE_LIMITED",
                            "connector rate limit exceeded.",
                            batch_index=batches_fetched,
                            **(
                                {"retry_after_seconds": retry_after}
                                if retry_after is not None
                                else {}
                            ),
                        )
                    )
                return Result.err(
                    _error(
                        "RETRIEVAL_CONNECTOR_RATE_LIMITER_ERROR",
                        "connector rate limiter returned an error.",
                        batch_index=batches_fetched,
                    )
                )
            if rate_result.unwrap() is not None:
                return Result.err(
                    _error(
                        "RETRIEVAL_CONNECTOR_RATE_LIMITER_ERROR",
                        "connector rate limiter returned an invalid value.",
                        batch_index=batches_fetched,
                    )
                )
        try:
            batch_result = fetch(current_cursor, limit=requested_limit)
        except Exception:
            return Result.err(
                _error(
                    "RETRIEVAL_CONNECTOR_ERROR",
                    "connector fetch failed.",
                    batch_index=batches_fetched,
                )
            )
        if not isinstance(batch_result, Result) or batch_result.is_err():
            return Result.err(
                _error(
                    "RETRIEVAL_CONNECTOR_ERROR",
                    "connector fetch returned an error.",
                    batch_index=batches_fetched,
                )
            )
        batch = batch_result.unwrap()
        if not isinstance(batch, DocumentBatch):
            return Result.err(
                _error(
                    "RETRIEVAL_CONNECTOR_INVALID",
                    "connector must return a DocumentBatch.",
                    batch_index=batches_fetched,
                )
            )
        batch_error = batch.validate(max_documents=requested_limit)
        if batch_error is not None:
            return Result.err(batch_error)
        if batch.next_cursor is not None and batch.next_cursor == current_cursor:
            return Result.err(
                _error(
                    "RETRIEVAL_CONNECTOR_CURSOR_STALLED",
                    "connector cursor did not advance.",
                    batch_index=batches_fetched,
                )
            )
        for index, document in enumerate(batch.documents):
            if document.document_id in seen_document_ids:
                return Result.err(
                    _error(
                        "RETRIEVAL_CONNECTOR_DUPLICATE_DOCUMENT",
                        "connector repeated a document ID.",
                        batch_index=batches_fetched,
                        document_index=index,
                    )
                )
        for index, document in enumerate(batch.documents):
            try:
                sink_result = add_document(document)
            except Exception:
                return Result.err(
                    _error(
                        "RETRIEVAL_SINK_ERROR",
                        "document sink failed.",
                        batch_index=batches_fetched,
                        document_index=index,
                        documents_ingested=documents_ingested,
                    )
                )
            if not isinstance(sink_result, Result) or sink_result.is_err():
                return Result.err(
                    _error(
                        "RETRIEVAL_SINK_ERROR",
                        "document sink returned an error.",
                        batch_index=batches_fetched,
                        document_index=index,
                        documents_ingested=documents_ingested,
                    )
                )
            seen_document_ids.add(document.document_id)
            documents_ingested += 1
        batches_fetched += 1
        checkpoint_error = persist_checkpoint(batch.next_cursor)
        if checkpoint_error is not None:
            return Result.err(checkpoint_error)
        if batch.next_cursor is None:
            return Result.ok(
                ConnectorIngestReport(
                    documents_ingested=documents_ingested,
                    batches_fetched=batches_fetched,
                    next_cursor=None,
                    complete=True,
                )
            )
        current_cursor = batch.next_cursor

    return Result.ok(
        ConnectorIngestReport(
            documents_ingested=documents_ingested,
            batches_fetched=batches_fetched,
            next_cursor=current_cursor,
            complete=False,
        )
    )


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


def _source_to_dict(source: SourceRef) -> Dict[str, Any]:
    return {
        "uri": source.uri,
        "title": source.title,
        "metadata": dict(source.metadata),
    }


def _document_to_dict(document: Document) -> Dict[str, Any]:
    return {
        "document_id": document.document_id,
        "text": document.text,
        "source": _source_to_dict(document.source),
        "metadata": dict(document.metadata),
    }


def _chunking_policy_to_dict(policy: ChunkingPolicy) -> Dict[str, int]:
    return {
        "max_chars": policy.max_chars,
        "overlap_chars": policy.overlap_chars,
        "max_chunks": policy.max_chunks,
        "max_document_bytes": policy.max_document_bytes,
    }


def _document_from_dict(value: Any) -> Result[Document, Error]:
    if not isinstance(value, Mapping):
        return Result.err(
            _error("RETRIEVAL_INDEX_LOAD_ERROR", "retrieval index document is invalid.")
        )
    source_value = value.get("source")
    if not isinstance(source_value, Mapping):
        return Result.err(
            _error("RETRIEVAL_INDEX_LOAD_ERROR", "retrieval index source is invalid.")
        )
    document = Document(
        document_id=cast(str, value.get("document_id")),
        text=cast(str, value.get("text")),
        source=SourceRef(
            uri=cast(str, source_value.get("uri")),
            title=cast(Optional[str], source_value.get("title")),
            metadata=cast(Mapping[str, Any], source_value.get("metadata", {})),
        ),
        metadata=cast(Mapping[str, Any], value.get("metadata", {})),
    )
    if document.validate() is not None:
        return Result.err(
            _error("RETRIEVAL_INDEX_LOAD_ERROR", "retrieval index document is invalid.")
        )
    return Result.ok(document)


class FileLexicalRetriever:
    """Bounded, atomic, cross-process durable lexical retrieval."""

    _FILENAME = "lexical-index.json"
    _TEMP_PREFIX = ".maple-lexical-index-"

    def __init__(
        self,
        directory: Union[str, Path],
        chunker: Optional[TextChunker] = None,
        *,
        max_documents: int = 1_000,
        max_chunks: int = 100_000,
        max_query_bytes: int = 16_384,
        max_results: int = 100,
        max_bytes: int = DEFAULT_MAX_LEXICAL_INDEX_BYTES,
        lease_ttl_seconds: float = 30.0,
    ) -> None:
        if chunker is not None and not isinstance(chunker, TextChunker):
            raise TypeError("chunker must be a TextChunker")
        self.chunker = chunker or TextChunker()
        limits = (
            ("max_documents", max_documents),
            ("max_chunks", max_chunks),
            ("max_query_bytes", max_query_bytes),
            ("max_results", max_results),
        )
        for name, value in limits:
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if (
            not isinstance(max_bytes, int)
            or isinstance(max_bytes, bool)
            or not 512 <= max_bytes <= _MAX_LEXICAL_INDEX_BYTES
        ):
            raise ValueError("max_bytes must be between 512 and 67108864")
        chunker_error = self.chunker.policy.validate()
        if chunker_error is not None:
            raise ValueError("chunker policy is invalid")

        self.max_documents = max_documents
        self.max_chunks = max_chunks
        self.max_query_bytes = max_query_bytes
        self.max_results = max_results
        self.max_bytes = max_bytes
        try:
            self.directory = Path(directory)
            self.directory.mkdir(parents=True, exist_ok=True)
        except (OSError, TypeError, ValueError) as exc:
            raise ValueError("retrieval index directory is unavailable") from exc
        if not self.directory.is_dir():
            raise ValueError("retrieval index path must be a directory")
        self.path = self.directory / self._FILENAME
        self._lock = threading.RLock()
        try:
            self._lease = DurableRecordLease(
                self.directory,
                namespace="retrieval-index",
                holder_label="lexical-index",
                lease_ttl_seconds=lease_ttl_seconds,
            )
        except (OSError, TypeError, ValueError) as exc:
            raise ValueError("retrieval index lease is unavailable") from exc

        self._index = self._new_index()
        loaded = self._run("load", self._load_index_unlocked)
        if loaded.is_err():
            raise ValueError("retrieval index state is invalid")
        self._index = loaded.unwrap()

    def _new_index(self) -> InMemoryLexicalRetriever:
        return InMemoryLexicalRetriever(
            self.chunker,
            max_documents=self.max_documents,
            max_chunks=self.max_chunks,
            max_query_bytes=self.max_query_bytes,
            max_results=self.max_results,
        )

    def _read_documents_unlocked(self) -> Result[List[Document], Error]:
        try:
            with self.path.open("rb") as handle:
                encoded = handle.read(self.max_bytes + 1)
        except FileNotFoundError:
            return Result.ok([])
        except OSError:
            return Result.err(
                _error(
                    "RETRIEVAL_INDEX_LOAD_ERROR",
                    "retrieval index could not be loaded.",
                )
            )
        if len(encoded) > self.max_bytes:
            return Result.err(
                _error(
                    "RETRIEVAL_INDEX_LOAD_ERROR",
                    "retrieval index exceeds the byte limit.",
                )
            )
        try:
            data = json.loads(encoded.decode("utf-8"))
        except (UnicodeError, TypeError, ValueError):
            return Result.err(
                _error(
                    "RETRIEVAL_INDEX_LOAD_ERROR",
                    "retrieval index could not be loaded.",
                )
            )
        if (
            not isinstance(data, Mapping)
            or data.get("version") != _LEXICAL_INDEX_VERSION
        ):
            return Result.err(
                _error(
                    "RETRIEVAL_INDEX_LOAD_ERROR",
                    "retrieval index version is invalid.",
                )
            )
        raw_policy = data.get("chunking_policy")
        expected_policy = _chunking_policy_to_dict(self.chunker.policy)
        if not isinstance(raw_policy, Mapping) or any(
            type(raw_policy.get(name)) is not type(expected)
            or raw_policy.get(name) != expected
            for name, expected in expected_policy.items()
        ):
            return Result.err(
                _error(
                    "RETRIEVAL_INDEX_CONFIG_MISMATCH",
                    "retrieval index chunking policy does not match.",
                )
            )
        raw_documents = data.get("documents")
        if (
            not isinstance(raw_documents, list)
            or len(raw_documents) > self.max_documents
        ):
            return Result.err(
                _error(
                    "RETRIEVAL_INDEX_LOAD_ERROR",
                    "retrieval index document list is invalid.",
                )
            )
        documents: List[Document] = []
        seen_ids: Set[str] = set()
        for value in raw_documents:
            parsed = _document_from_dict(value)
            if parsed.is_err():
                return Result.err(parsed.unwrap_err())
            document = parsed.unwrap()
            if document.document_id in seen_ids:
                return Result.err(
                    _error(
                        "RETRIEVAL_INDEX_LOAD_ERROR",
                        "retrieval index contains duplicate documents.",
                    )
                )
            seen_ids.add(document.document_id)
            documents.append(document)
        return Result.ok(documents)

    def _load_index_unlocked(self) -> Result[InMemoryLexicalRetriever, Error]:
        documents = self._read_documents_unlocked()
        if documents.is_err():
            return Result.err(documents.unwrap_err())
        index = self._new_index()
        for document in documents.unwrap():
            added = index.add_document(document)
            if added.is_err():
                return Result.err(
                    _error(
                        "RETRIEVAL_INDEX_LOAD_ERROR",
                        "retrieval index could not be rebuilt.",
                    )
                )
        return Result.ok(index)

    def _encode_documents(self, documents: Sequence[Document]) -> Result[str, Error]:
        try:
            encoded = json.dumps(
                {
                    "version": _LEXICAL_INDEX_VERSION,
                    "chunking_policy": _chunking_policy_to_dict(self.chunker.policy),
                    "documents": [
                        _document_to_dict(document) for document in documents
                    ],
                },
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            )
        except (TypeError, ValueError, OverflowError):
            return Result.err(
                _error(
                    "RETRIEVAL_INDEX_SAVE_ERROR",
                    "retrieval index is not JSON serializable.",
                )
            )
        if len(encoded.encode("utf-8")) > self.max_bytes:
            return Result.err(
                _error(
                    "RETRIEVAL_INDEX_SIZE",
                    "retrieval index exceeds the byte limit.",
                )
            )
        return Result.ok(encoded)

    def _write_documents_unlocked(
        self, documents: Sequence[Document]
    ) -> Result[None, Error]:
        encoded = self._encode_documents(documents)
        if encoded.is_err():
            return Result.err(encoded.unwrap_err())
        temporary_path: Optional[Path] = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=str(self.directory),
                prefix=self._TEMP_PREFIX,
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary_path = Path(handle.name)
                handle.write(encoded.unwrap())
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(str(temporary_path), str(self.path))
            temporary_path = None
            return Result.ok(None)
        except (OSError, TypeError, ValueError):
            return Result.err(
                _error(
                    "RETRIEVAL_INDEX_SAVE_ERROR",
                    "retrieval index could not be saved.",
                )
            )
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink()
                except OSError:
                    pass

    def _run(
        self,
        operation: str,
        callback: Callable[[], Result[Any, Error]],
    ) -> Result[Any, Error]:
        try:
            return self._lease.run(
                "index",
                operation,
                callback,
                acquire_error_type="RETRIEVAL_INDEX_LEASE_ERROR",
                acquire_error_message="retrieval index lease could not be acquired.",
                release_error_type="RETRIEVAL_INDEX_LEASE_RELEASE_ERROR",
                release_error_message="retrieval index lease could not be released.",
            )
        except Exception:
            return Result.err(
                _error(
                    "RETRIEVAL_INDEX_ERROR",
                    "retrieval index operation failed.",
                )
            )

    def add_document(self, document: Document) -> Result[List[DocumentChunk], Error]:
        """Persist one document and return its deterministic chunks."""
        if not isinstance(document, Document):
            return Result.err(
                _error("RETRIEVAL_INPUT_INVALID", "document must be a Document.")
            )
        with self._lock:

            def operation() -> Result[List[DocumentChunk], Error]:
                loaded = self._load_index_unlocked()
                if loaded.is_err():
                    return Result.err(loaded.unwrap_err())
                index = loaded.unwrap()
                added = index.add_document(document)
                if added.is_err():
                    return Result.err(added.unwrap_err())
                documents = list(index._documents.values())
                written = self._write_documents_unlocked(documents)
                if written.is_err():
                    return Result.err(written.unwrap_err())
                self._index = index
                return Result.ok(added.unwrap())

            result = self._run("add", operation)
        return result

    def remove_document(self, document_id: str) -> Result[bool, Error]:
        """Persist removal of one document, if present."""
        error = _validate_identifier(document_id, "document_id")
        if error is not None:
            return Result.err(error)
        with self._lock:

            def operation() -> Result[bool, Error]:
                loaded = self._load_index_unlocked()
                if loaded.is_err():
                    return Result.err(loaded.unwrap_err())
                current = loaded.unwrap()
                if document_id not in current._documents:
                    self._index = current
                    return Result.ok(False)
                documents = [
                    document
                    for identifier, document in current._documents.items()
                    if identifier != document_id
                ]
                candidate = self._new_index()
                for document in documents:
                    added = candidate.add_document(document)
                    if added.is_err():
                        return Result.err(
                            _error(
                                "RETRIEVAL_INDEX_SAVE_ERROR",
                                "retrieval index could not be rebuilt.",
                            )
                        )
                written = self._write_documents_unlocked(documents)
                if written.is_err():
                    return Result.err(written.unwrap_err())
                self._index = candidate
                return Result.ok(True)

            result = self._run("remove", operation)
        return result

    def search(
        self, query: str, *, top_k: int = 5, min_score: float = 0.0
    ) -> Result[List[RetrievalHit], Error]:
        """Refresh the durable index and return deterministic lexical hits."""
        with self._lock:
            loaded = self._run("search", self._load_index_unlocked)
            if loaded.is_err():
                return Result.err(loaded.unwrap_err())
            self._index = loaded.unwrap()
            return self._index.search(query, top_k=top_k, min_score=min_score)

    def stats(self) -> Dict[str, int]:
        """Refresh and return bounded durable-index counts."""
        with self._lock:
            loaded = self._run("stats", self._load_index_unlocked)
            if loaded.is_err():
                raise RuntimeError("retrieval index statistics unavailable")
            self._index = loaded.unwrap()
            return self._index.stats()


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
        try:
            converted = float(value)
        except (OverflowError, TypeError, ValueError):
            return Result.err(
                _error(
                    "RETRIEVAL_VECTOR_INVALID",
                    f"{field_name} contains a non-finite value.",
                    index=index,
                )
            )
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


class FileVectorRetriever:
    """Bounded, atomic, cross-process durable vector retrieval.

    The host supplies embeddings; MAPLE persists the source documents and
    vectors locally, then rebuilds the tested in-memory cosine index on each
    operation. This class does not select an embedding model or call a
    provider.
    """

    _FILENAME = "vector-index.json"
    _TEMP_PREFIX = ".maple-vector-index-"

    def __init__(
        self,
        directory: Union[str, Path],
        chunker: Optional[TextChunker] = None,
        *,
        max_documents: int = 1_000,
        max_vectors: int = 100_000,
        max_dimensions: int = 4_096,
        max_results: int = 100,
        max_bytes: int = DEFAULT_MAX_VECTOR_INDEX_BYTES,
        lease_ttl_seconds: float = 30.0,
    ) -> None:
        if chunker is not None and not isinstance(chunker, TextChunker):
            raise TypeError("chunker must be a TextChunker")
        self.chunker = chunker or TextChunker()
        limits = (
            ("max_documents", max_documents, _MAX_FILE_VECTOR_DOCUMENTS),
            ("max_vectors", max_vectors, _MAX_FILE_VECTOR_COUNT),
            ("max_dimensions", max_dimensions, _MAX_FILE_VECTOR_DIMENSIONS),
            ("max_results", max_results, _MAX_FILE_VECTOR_RESULTS),
        )
        for name, value, maximum in limits:
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or not 1 <= value <= maximum
            ):
                raise ValueError(f"{name} must be between 1 and {maximum}")
        if (
            not isinstance(max_bytes, int)
            or isinstance(max_bytes, bool)
            or not 512 <= max_bytes <= _MAX_VECTOR_INDEX_BYTES
        ):
            raise ValueError("max_bytes must be between 512 and 67108864")
        if (
            not isinstance(lease_ttl_seconds, (int, float))
            or isinstance(lease_ttl_seconds, bool)
            or not math.isfinite(float(lease_ttl_seconds))
            or not 0.001 <= float(lease_ttl_seconds) <= 86_400.0
        ):
            raise ValueError("lease_ttl_seconds must be between 0.001 and 86400")
        chunker_error = self.chunker.policy.validate()
        if chunker_error is not None:
            raise ValueError("chunker policy is invalid")

        self.max_documents = max_documents
        self.max_vectors = max_vectors
        self.max_dimensions = max_dimensions
        self.max_results = max_results
        self.max_bytes = max_bytes
        try:
            self.directory = Path(directory)
            self.directory.mkdir(parents=True, exist_ok=True)
        except (OSError, TypeError, ValueError) as exc:
            raise ValueError("vector index directory is unavailable") from exc
        if not self.directory.is_dir():
            raise ValueError("vector index path must be a directory")
        self.path = self.directory / self._FILENAME
        self._lock = threading.RLock()
        try:
            self._lease = DurableRecordLease(
                self.directory,
                namespace="retrieval-vector-index",
                holder_label="vector-index",
                lease_ttl_seconds=lease_ttl_seconds,
            )
        except (OSError, TypeError, ValueError) as exc:
            raise ValueError("vector index lease is unavailable") from exc

        self._index = self._new_index()
        loaded = self._run("load", self._load_index_unlocked)
        if loaded.is_err():
            raise ValueError("vector index state is invalid")
        self._index = loaded.unwrap()

    def _new_index(self) -> InMemoryVectorRetriever:
        return InMemoryVectorRetriever(
            self.chunker,
            max_documents=self.max_documents,
            max_vectors=self.max_vectors,
            max_dimensions=self.max_dimensions,
            max_results=self.max_results,
        )

    def _read_records_unlocked(
        self,
    ) -> Result[List[Tuple[Document, List[Tuple[float, ...]]]], Error]:
        try:
            with self.path.open("rb") as handle:
                encoded = handle.read(self.max_bytes + 1)
        except FileNotFoundError:
            return Result.ok([])
        except OSError:
            return Result.err(
                _error(
                    "RETRIEVAL_VECTOR_INDEX_LOAD_ERROR",
                    "vector index could not be loaded.",
                )
            )
        if len(encoded) > self.max_bytes:
            return Result.err(
                _error(
                    "RETRIEVAL_VECTOR_INDEX_LOAD_ERROR",
                    "vector index exceeds the byte limit.",
                )
            )
        try:
            data = json.loads(encoded.decode("utf-8"))
        except (UnicodeError, TypeError, ValueError):
            return Result.err(
                _error(
                    "RETRIEVAL_VECTOR_INDEX_LOAD_ERROR",
                    "vector index could not be loaded.",
                )
            )
        if (
            not isinstance(data, Mapping)
            or type(data.get("version")) is not int
            or data.get("version") != _VECTOR_INDEX_VERSION
        ):
            return Result.err(
                _error(
                    "RETRIEVAL_VECTOR_INDEX_LOAD_ERROR",
                    "vector index version is invalid.",
                )
            )
        raw_policy = data.get("chunking_policy")
        expected_policy = _chunking_policy_to_dict(self.chunker.policy)
        if not isinstance(raw_policy, Mapping) or any(
            type(raw_policy.get(name)) is not type(expected)
            or raw_policy.get(name) != expected
            for name, expected in expected_policy.items()
        ):
            return Result.err(
                _error(
                    "RETRIEVAL_VECTOR_INDEX_CONFIG_MISMATCH",
                    "vector index chunking policy does not match.",
                )
            )
        raw_documents = data.get("documents")
        if (
            not isinstance(raw_documents, list)
            or len(raw_documents) > self.max_documents
        ):
            return Result.err(
                _error(
                    "RETRIEVAL_VECTOR_INDEX_LOAD_ERROR",
                    "vector index document list is invalid.",
                )
            )

        records: List[Tuple[Document, List[Tuple[float, ...]]]] = []
        seen_ids: Set[str] = set()
        vector_count = 0
        for value in raw_documents:
            if not isinstance(value, Mapping):
                return Result.err(
                    _error(
                        "RETRIEVAL_VECTOR_INDEX_LOAD_ERROR",
                        "vector index document record is invalid.",
                    )
                )
            parsed_document = _document_from_dict(value.get("document"))
            if parsed_document.is_err():
                return Result.err(
                    _error(
                        "RETRIEVAL_VECTOR_INDEX_LOAD_ERROR",
                        "vector index document is invalid.",
                    )
                )
            document = parsed_document.unwrap()
            if document.document_id in seen_ids:
                return Result.err(
                    _error(
                        "RETRIEVAL_VECTOR_INDEX_LOAD_ERROR",
                        "vector index contains duplicate documents.",
                    )
                )
            raw_embeddings = value.get("embeddings")
            if isinstance(raw_embeddings, (str, bytes)) or not isinstance(
                raw_embeddings, list
            ):
                return Result.err(
                    _error(
                        "RETRIEVAL_VECTOR_INDEX_LOAD_ERROR",
                        "vector index embeddings are invalid.",
                    )
                )
            if vector_count + len(raw_embeddings) > self.max_vectors:
                return Result.err(
                    _error(
                        "RETRIEVAL_VECTOR_INDEX_LOAD_ERROR",
                        "vector index vector limit is invalid.",
                    )
                )
            embeddings: List[Tuple[float, ...]] = []
            for index, embedding in enumerate(raw_embeddings):
                parsed_vector = _validate_vector(
                    embedding,
                    max_dimensions=self.max_dimensions,
                    field_name=f"embedding[{index}]",
                )
                if parsed_vector.is_err():
                    return Result.err(
                        _error(
                            "RETRIEVAL_VECTOR_INDEX_LOAD_ERROR",
                            "vector index contains an invalid vector.",
                        )
                    )
                embeddings.append(parsed_vector.unwrap())
            seen_ids.add(document.document_id)
            vector_count += len(embeddings)
            records.append((document, embeddings))
        return Result.ok(records)

    def _load_index_unlocked(self) -> Result[InMemoryVectorRetriever, Error]:
        records = self._read_records_unlocked()
        if records.is_err():
            return Result.err(records.unwrap_err())
        index = self._new_index()
        for document, embeddings in records.unwrap():
            added = index.add_document(document, embeddings)
            if added.is_err():
                return Result.err(
                    _error(
                        "RETRIEVAL_VECTOR_INDEX_LOAD_ERROR",
                        "vector index could not be rebuilt.",
                    )
                )
        return Result.ok(index)

    @staticmethod
    def _records_from_index(
        index: InMemoryVectorRetriever,
    ) -> List[Tuple[Document, List[Tuple[float, ...]]]]:
        records: List[Tuple[Document, List[Tuple[float, ...]]]] = []
        for document_id, document in index._documents.items():
            chunks = sorted(
                (
                    chunk
                    for chunk in index._chunks.values()
                    if chunk.document_id == document_id
                ),
                key=lambda chunk: chunk.index,
            )
            records.append(
                (
                    document,
                    [index._vectors[chunk.chunk_id] for chunk in chunks],
                )
            )
        return records

    def _encode_records(
        self,
        records: Sequence[Tuple[Document, Sequence[Sequence[float]]]],
    ) -> Result[str, Error]:
        try:
            encoded = json.dumps(
                {
                    "version": _VECTOR_INDEX_VERSION,
                    "chunking_policy": _chunking_policy_to_dict(self.chunker.policy),
                    "documents": [
                        {
                            "document": _document_to_dict(document),
                            "embeddings": [list(vector) for vector in embeddings],
                        }
                        for document, embeddings in records
                    ],
                },
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            )
        except (TypeError, ValueError, OverflowError):
            return Result.err(
                _error(
                    "RETRIEVAL_VECTOR_INDEX_SAVE_ERROR",
                    "vector index is not JSON serializable.",
                )
            )
        if len(encoded.encode("utf-8")) > self.max_bytes:
            return Result.err(
                _error(
                    "RETRIEVAL_VECTOR_INDEX_SIZE",
                    "vector index exceeds the byte limit.",
                )
            )
        return Result.ok(encoded)

    def _write_records_unlocked(
        self,
        records: Sequence[Tuple[Document, Sequence[Sequence[float]]]],
    ) -> Result[None, Error]:
        encoded = self._encode_records(records)
        if encoded.is_err():
            return Result.err(encoded.unwrap_err())
        temporary_path: Optional[Path] = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=str(self.directory),
                prefix=self._TEMP_PREFIX,
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary_path = Path(handle.name)
                handle.write(encoded.unwrap())
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(str(temporary_path), str(self.path))
            temporary_path = None
            return Result.ok(None)
        except (OSError, TypeError, ValueError):
            return Result.err(
                _error(
                    "RETRIEVAL_VECTOR_INDEX_SAVE_ERROR",
                    "vector index could not be saved.",
                )
            )
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink()
                except OSError:
                    pass

    def _run(
        self,
        operation: str,
        callback: Callable[[], Result[Any, Error]],
    ) -> Result[Any, Error]:
        try:
            return self._lease.run(
                "index",
                operation,
                callback,
                acquire_error_type="RETRIEVAL_VECTOR_INDEX_LEASE_ERROR",
                acquire_error_message="vector index lease could not be acquired.",
                release_error_type="RETRIEVAL_VECTOR_INDEX_LEASE_RELEASE_ERROR",
                release_error_message="vector index lease could not be released.",
            )
        except Exception:
            return Result.err(
                _error(
                    "RETRIEVAL_VECTOR_INDEX_ERROR",
                    "vector index operation failed.",
                )
            )

    def add_document(
        self, document: Document, embeddings: Sequence[Sequence[float]]
    ) -> Result[List[DocumentChunk], Error]:
        """Persist one document and its caller-supplied chunk embeddings."""
        if not isinstance(document, Document):
            return Result.err(
                _error("RETRIEVAL_INPUT_INVALID", "document must be a Document.")
            )
        with self._lock:

            def operation() -> Result[List[DocumentChunk], Error]:
                loaded = self._load_index_unlocked()
                if loaded.is_err():
                    return Result.err(loaded.unwrap_err())
                index = loaded.unwrap()
                added = index.add_document(document, embeddings)
                if added.is_err():
                    return Result.err(added.unwrap_err())
                records = self._records_from_index(index)
                written = self._write_records_unlocked(records)
                if written.is_err():
                    return Result.err(written.unwrap_err())
                self._index = index
                return Result.ok(added.unwrap())

            return self._run("add", operation)

    def remove_document(self, document_id: str) -> Result[bool, Error]:
        """Persist removal of one document, if present."""
        error = _validate_identifier(document_id, "document_id")
        if error is not None:
            return Result.err(error)
        with self._lock:

            def operation() -> Result[bool, Error]:
                loaded = self._load_index_unlocked()
                if loaded.is_err():
                    return Result.err(loaded.unwrap_err())
                current = loaded.unwrap()
                if document_id not in current._documents:
                    self._index = current
                    return Result.ok(False)
                records = [
                    record
                    for record in self._records_from_index(current)
                    if record[0].document_id != document_id
                ]
                candidate = self._new_index()
                for document, embeddings in records:
                    added = candidate.add_document(document, embeddings)
                    if added.is_err():
                        return Result.err(
                            _error(
                                "RETRIEVAL_VECTOR_INDEX_SAVE_ERROR",
                                "vector index could not be rebuilt.",
                            )
                        )
                written = self._write_records_unlocked(records)
                if written.is_err():
                    return Result.err(written.unwrap_err())
                self._index = candidate
                return Result.ok(True)

            return self._run("remove", operation)

    def search(
        self,
        query_vector: Sequence[float],
        *,
        top_k: int = 5,
        min_score: float = 0.0,
    ) -> Result[List[VectorRetrievalHit], Error]:
        """Refresh the durable index and return deterministic vector hits."""
        with self._lock:
            loaded = self._run("search", self._load_index_unlocked)
            if loaded.is_err():
                return Result.err(loaded.unwrap_err())
            self._index = loaded.unwrap()
            return self._index.search(query_vector, top_k=top_k, min_score=min_score)

    def stats(self) -> Dict[str, int]:
        """Refresh and return bounded durable-vector counts."""
        with self._lock:
            loaded = self._run("stats", self._load_index_unlocked)
            if loaded.is_err():
                raise RuntimeError("vector index statistics unavailable")
            self._index = loaded.unwrap()
            return self._index.stats()
