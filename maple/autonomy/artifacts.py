"""Bounded content-addressed artifacts and non-executing code-block parsing."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Tuple, Union

from ..core.result import Result

Error = Dict[str, Any]
BytesLike = Union[bytes, bytearray, memoryview]

DEFAULT_MAX_ARTIFACT_BYTES = 8 * 1024 * 1024
DEFAULT_MAX_STORE_BYTES = 64 * 1024 * 1024
DEFAULT_MAX_SOURCE_BYTES = 1024 * 1024
DEFAULT_MAX_CODE_BLOCKS = 64
DEFAULT_MAX_CODE_BLOCK_BYTES = 128 * 1024
_MAX_CODE_BLOCK_INDEX = 1_000_000
_ARTIFACT_ID = re.compile(r"^sha256:[0-9a-f]{64}$")
_LANGUAGE = re.compile(r"^[A-Za-z0-9_+.#-]{1,32}$")


def _error(error_type: str, message: str, **details: Any) -> Error:
    error: Error = {"errorType": error_type, "message": message}
    if details:
        error["details"] = details
    return error


@dataclass(frozen=True)
class Artifact:
    """Immutable metadata for content addressed by SHA-256."""

    artifact_id: str
    name: str
    media_type: str
    size: int
    sha256: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifactId": self.artifact_id,
            "name": self.name,
            "mediaType": self.media_type,
            "size": self.size,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class CodeBlock:
    """Code extracted from a Markdown fence; it is never executed here."""

    index: int
    language: str
    code: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.index, int)
            or isinstance(self.index, bool)
            or not 0 <= self.index <= _MAX_CODE_BLOCK_INDEX
        ):
            raise ValueError("code-block index is invalid")
        if not isinstance(self.language, str) or not _LANGUAGE.fullmatch(self.language):
            raise ValueError("code-block language is invalid")
        if not isinstance(self.code, str):
            raise ValueError("code-block code must be text")

    @property
    def byte_size(self) -> int:
        return len(self.code.encode("utf-8"))

    @property
    def sha256(self) -> str:
        """Return the digest of the exact UTF-8 code bytes."""
        return hashlib.sha256(self.code.encode("utf-8")).hexdigest()


class ArtifactStore(Protocol):
    """Storage contract for immutable artifact bytes."""

    def put(
        self,
        data: BytesLike,
        *,
        name: str = "artifact",
        media_type: str = "application/octet-stream",
    ) -> Result[Artifact, Error]:
        """Store bytes and return their stable metadata."""

    def get(self, artifact_id: str) -> Result[bytes, Error]:
        """Read bytes after validating the content-addressed identity."""

    def describe(self, artifact_id: str) -> Result[Artifact, Error]:
        """Return metadata without exposing unbounded content."""


def _normalize_payload(
    data: BytesLike,
    *,
    name: str,
    media_type: str,
    max_artifact_bytes: int,
) -> Result[Tuple[bytes, str, str, str], Error]:
    if not isinstance(data, (bytes, bytearray, memoryview)):
        return Result.err(
            _error("ARTIFACT_INPUT_INVALID", "Artifact data must be bytes-like")
        )
    payload = bytes(data)
    if len(payload) > max_artifact_bytes:
        return Result.err(
            _error(
                "ARTIFACT_TOO_LARGE",
                "Artifact exceeds the configured byte limit",
                maxBytes=max_artifact_bytes,
            )
        )
    if not isinstance(name, str) or not name or len(name) > 128:
        return Result.err(_error("ARTIFACT_NAME_INVALID", "Artifact name is invalid"))
    if name in {".", ".."} or "/" in name or "\\" in name:
        return Result.err(
            _error(
                "ARTIFACT_NAME_INVALID",
                "Artifact name must not contain path separators",
            )
        )
    if any(ord(char) < 32 or ord(char) == 127 for char in name):
        return Result.err(
            _error(
                "ARTIFACT_NAME_INVALID",
                "Artifact name contains a control character",
            )
        )
    if not isinstance(media_type, str) or not media_type or len(media_type) > 128:
        return Result.err(
            _error("ARTIFACT_MEDIA_TYPE_INVALID", "Artifact media type is invalid")
        )
    if any(ord(char) < 32 or ord(char) == 127 for char in media_type):
        return Result.err(
            _error(
                "ARTIFACT_MEDIA_TYPE_INVALID",
                "Artifact media type contains a control character",
            )
        )
    digest = hashlib.sha256(payload).hexdigest()
    return Result.ok((payload, name, media_type, digest))


def _metadata(artifact_id: str, name: str, media_type: str, payload: bytes) -> Artifact:
    digest = artifact_id.split(":", 1)[1]
    return Artifact(
        artifact_id=artifact_id,
        name=name,
        media_type=media_type,
        size=len(payload),
        sha256=digest,
    )


class InMemoryArtifactStore:
    """Bounded immutable artifact store for tests and short-lived agents."""

    def __init__(
        self,
        *,
        max_artifact_bytes: int = DEFAULT_MAX_ARTIFACT_BYTES,
        max_store_bytes: int = DEFAULT_MAX_STORE_BYTES,
    ):
        if max_artifact_bytes <= 0 or max_store_bytes <= 0:
            raise ValueError("artifact limits must be positive")
        if max_artifact_bytes > max_store_bytes:
            raise ValueError("max_artifact_bytes cannot exceed max_store_bytes")
        self.max_artifact_bytes = max_artifact_bytes
        self.max_store_bytes = max_store_bytes
        self._items: Dict[str, Tuple[Artifact, bytes]] = {}
        self._used_bytes = 0

    def put(
        self,
        data: BytesLike,
        *,
        name: str = "artifact",
        media_type: str = "application/octet-stream",
    ) -> Result[Artifact, Error]:
        normalized = _normalize_payload(
            data,
            name=name,
            media_type=media_type,
            max_artifact_bytes=self.max_artifact_bytes,
        )
        if normalized.is_err():
            return Result.err(normalized.unwrap_err())
        payload, safe_name, safe_media_type, digest = normalized.unwrap()
        artifact_id = f"sha256:{digest}"
        existing = self._items.get(artifact_id)
        if existing is not None:
            return Result.ok(existing[0])
        if self._used_bytes + len(payload) > self.max_store_bytes:
            return Result.err(
                _error(
                    "ARTIFACT_STORE_FULL",
                    "Artifact store exceeds the configured byte limit",
                    maxBytes=self.max_store_bytes,
                )
            )
        artifact = _metadata(artifact_id, safe_name, safe_media_type, payload)
        self._items[artifact_id] = (artifact, payload)
        self._used_bytes += len(payload)
        return Result.ok(artifact)

    def get(self, artifact_id: str) -> Result[bytes, Error]:
        if not _ARTIFACT_ID.fullmatch(str(artifact_id)):
            return Result.err(_error("ARTIFACT_ID_INVALID", "Artifact id is invalid"))
        item = self._items.get(artifact_id)
        if item is None:
            return Result.err(_error("ARTIFACT_NOT_FOUND", "Artifact was not found"))
        artifact, payload = item
        if hashlib.sha256(payload).hexdigest() != artifact.sha256:
            return Result.err(
                _error("ARTIFACT_CORRUPT", "Artifact hash verification failed")
            )
        return Result.ok(payload)

    def describe(self, artifact_id: str) -> Result[Artifact, Error]:
        if not _ARTIFACT_ID.fullmatch(str(artifact_id)):
            return Result.err(_error("ARTIFACT_ID_INVALID", "Artifact id is invalid"))
        item = self._items.get(artifact_id)
        if item is None:
            return Result.err(_error("ARTIFACT_NOT_FOUND", "Artifact was not found"))
        return Result.ok(item[0])


class FileArtifactStore:
    """Bounded file-backed artifact store with hash-verified reads."""

    def __init__(
        self,
        root: Union[str, os.PathLike],
        *,
        max_artifact_bytes: int = DEFAULT_MAX_ARTIFACT_BYTES,
        max_store_bytes: int = DEFAULT_MAX_STORE_BYTES,
    ):
        if max_artifact_bytes <= 0 or max_store_bytes <= 0:
            raise ValueError("artifact limits must be positive")
        if max_artifact_bytes > max_store_bytes:
            raise ValueError("max_artifact_bytes cannot exceed max_store_bytes")
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_artifact_bytes = max_artifact_bytes
        self.max_store_bytes = max_store_bytes
        self._used_bytes = 0
        for path in self.root.glob("sha256-*.bin"):
            if path.is_file():
                self._used_bytes += path.stat().st_size
        if self._used_bytes > max_store_bytes:
            raise ValueError("existing artifact store exceeds max_store_bytes")

    def _path(self, artifact_id: str, suffix: str) -> Result[Path, Error]:
        if not _ARTIFACT_ID.fullmatch(str(artifact_id)):
            return Result.err(_error("ARTIFACT_ID_INVALID", "Artifact id is invalid"))
        digest = artifact_id.split(":", 1)[1]
        path = self.root / f"sha256-{digest}{suffix}"
        try:
            if path.exists() and path.resolve().parent != self.root:
                return Result.err(
                    _error("ARTIFACT_PATH_INVALID", "Artifact path is unsafe")
                )
        except OSError as exc:
            return Result.err(_error("ARTIFACT_PATH_INVALID", str(exc)))
        return Result.ok(path)

    def put(
        self,
        data: BytesLike,
        *,
        name: str = "artifact",
        media_type: str = "application/octet-stream",
    ) -> Result[Artifact, Error]:
        normalized = _normalize_payload(
            data,
            name=name,
            media_type=media_type,
            max_artifact_bytes=self.max_artifact_bytes,
        )
        if normalized.is_err():
            return Result.err(normalized.unwrap_err())
        payload, safe_name, safe_media_type, digest = normalized.unwrap()
        artifact_id = f"sha256:{digest}"
        data_path_result = self._path(artifact_id, ".bin")
        metadata_path_result = self._path(artifact_id, ".json")
        if data_path_result.is_err() or metadata_path_result.is_err():
            return Result.err(
                (
                    data_path_result
                    if data_path_result.is_err()
                    else metadata_path_result
                ).unwrap_err()
            )
        data_path = data_path_result.unwrap()
        metadata_path = metadata_path_result.unwrap()
        data_already_exists = data_path.exists()
        if data_already_exists:
            existing = self.get(artifact_id)
            if existing.is_err():
                return Result.err(existing.unwrap_err())
            described = self.describe(artifact_id)
            if described.is_err():
                return Result.err(described.unwrap_err())
            return Result.ok(described.unwrap())
        elif self._used_bytes + len(payload) > self.max_store_bytes:
            return Result.err(
                _error(
                    "ARTIFACT_STORE_FULL",
                    "Artifact store exceeds the configured byte limit",
                    maxBytes=self.max_store_bytes,
                )
            )
        artifact = _metadata(artifact_id, safe_name, safe_media_type, payload)
        write_result = self._atomic_write(data_path, payload)
        if write_result.is_err():
            return Result.err(write_result.unwrap_err())
        metadata = json.dumps(artifact.to_dict(), ensure_ascii=False).encode("utf-8")
        write_result = self._atomic_write(metadata_path, metadata)
        if write_result.is_err():
            if not data_already_exists:
                try:
                    data_path.unlink()
                except OSError:
                    pass
            return Result.err(write_result.unwrap_err())
        if not data_already_exists:
            self._used_bytes += len(payload)
        return Result.ok(artifact)

    def _atomic_write(self, path: Path, payload: bytes) -> Result[None, Error]:
        temporary = None
        try:
            fd, temporary = tempfile.mkstemp(
                prefix=".maple-artifact-", dir=str(self.root)
            )
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            return Result.ok(None)
        except OSError as exc:
            return Result.err(_error("ARTIFACT_WRITE_ERROR", str(exc)))
        finally:
            if temporary is not None and os.path.exists(temporary):
                try:
                    os.unlink(temporary)
                except OSError:
                    pass

    def get(self, artifact_id: str) -> Result[bytes, Error]:
        path_result = self._path(artifact_id, ".bin")
        if path_result.is_err():
            return Result.err(path_result.unwrap_err())
        path = path_result.unwrap()
        if not path.is_file():
            return Result.err(_error("ARTIFACT_NOT_FOUND", "Artifact was not found"))
        try:
            payload = path.read_bytes()
        except OSError as exc:
            return Result.err(_error("ARTIFACT_READ_ERROR", str(exc)))
        if len(payload) > self.max_artifact_bytes:
            return Result.err(
                _error(
                    "ARTIFACT_TOO_LARGE",
                    "Artifact exceeds the configured byte limit",
                )
            )
        digest = artifact_id.split(":", 1)[1]
        if hashlib.sha256(payload).hexdigest() != digest:
            return Result.err(
                _error("ARTIFACT_CORRUPT", "Artifact hash verification failed")
            )
        return Result.ok(payload)

    def describe(self, artifact_id: str) -> Result[Artifact, Error]:
        path_result = self._path(artifact_id, ".json")
        if path_result.is_err():
            return Result.err(path_result.unwrap_err())
        path = path_result.unwrap()
        if not path.is_file():
            return Result.err(_error("ARTIFACT_NOT_FOUND", "Artifact was not found"))
        try:
            raw = path.read_bytes()
            if len(raw) > 16 * 1024:
                return Result.err(
                    _error(
                        "ARTIFACT_METADATA_INVALID",
                        "Artifact metadata is too large",
                    )
                )
            value = json.loads(raw.decode("utf-8"))
            artifact = Artifact(
                artifact_id=value["artifactId"],
                name=value["name"],
                media_type=value["mediaType"],
                size=value["size"],
                sha256=value["sha256"],
            )
        except (
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            return Result.err(_error("ARTIFACT_METADATA_INVALID", str(exc)))
        if (
            artifact.artifact_id != artifact_id
            or artifact.sha256 != artifact_id.split(":", 1)[1]
        ):
            return Result.err(
                _error(
                    "ARTIFACT_METADATA_INVALID",
                    "Artifact metadata identity mismatch",
                )
            )
        payload_result = self.get(artifact_id)
        if payload_result.is_err():
            return Result.err(payload_result.unwrap_err())
        if artifact.size != len(payload_result.unwrap()):
            return Result.err(
                _error("ARTIFACT_METADATA_INVALID", "Artifact metadata size mismatch")
            )
        return Result.ok(artifact)


def extract_code_blocks(
    source: str,
    *,
    max_source_bytes: int = DEFAULT_MAX_SOURCE_BYTES,
    max_blocks: int = DEFAULT_MAX_CODE_BLOCKS,
    max_block_bytes: int = DEFAULT_MAX_CODE_BLOCK_BYTES,
) -> Result[List[CodeBlock], Error]:
    """Extract bounded fenced code as data; never evaluate or write it."""
    if not isinstance(source, str):
        return Result.err(
            _error("CODE_SOURCE_INVALID", "Code-block source must be text")
        )
    if max_source_bytes <= 0 or max_blocks <= 0 or max_block_bytes <= 0:
        return Result.err(
            _error("CODE_LIMIT_INVALID", "Code-block limits must be positive")
        )
    source_bytes = source.encode("utf-8")
    if len(source_bytes) > max_source_bytes:
        return Result.err(
            _error(
                "CODE_SOURCE_TOO_LARGE",
                "Code-block source exceeds the configured byte limit",
            )
        )

    blocks: List[CodeBlock] = []
    active_language: Optional[str] = None
    active_lines: List[str] = []
    active_bytes = 0
    for line in source.splitlines(keepends=True):
        marker = line.rstrip("\r\n")
        if active_language is None:
            if not marker.startswith("```"):
                continue
            info = marker[3:].strip()
            language = info.split()[0] if info else "text"
            if not _LANGUAGE.fullmatch(language):
                return Result.err(
                    _error("CODE_LANGUAGE_INVALID", "Code-block language is invalid")
                )
            if len(blocks) >= max_blocks:
                return Result.err(
                    _error("CODE_BLOCK_LIMIT_EXCEEDED", "Too many code blocks")
                )
            active_language = language
            active_lines = []
            active_bytes = 0
            continue
        if marker.strip() == "```":
            code = "".join(active_lines)
            blocks.append(CodeBlock(len(blocks), active_language, code))
            active_language = None
            active_lines = []
            active_bytes = 0
            continue
        active_lines.append(line)
        active_bytes += len(line.encode("utf-8"))
        if active_bytes > max_block_bytes:
            return Result.err(
                _error(
                    "CODE_BLOCK_TOO_LARGE",
                    "Code block exceeds the configured byte limit",
                )
            )
    if active_language is not None:
        return Result.err(
            _error("CODE_FENCE_UNCLOSED", "Code block fence is not closed")
        )
    return Result.ok(blocks)


def materialize_code_block(
    store: ArtifactStore,
    block: CodeBlock,
    *,
    name: Optional[str] = None,
) -> Result[Artifact, Error]:
    """Store one bounded code block as an immutable, non-executable artifact.

    The default name retains the block index and language for inspection while
    the artifact ID is derived from the exact UTF-8 bytes. The existing store
    remains responsible for quota enforcement, persistence, and hash checks.
    """
    if not isinstance(block, CodeBlock):
        return Result.err(
            _error("CODE_BLOCK_INVALID", "Code block must be a CodeBlock instance")
        )
    if block.byte_size > DEFAULT_MAX_CODE_BLOCK_BYTES:
        return Result.err(
            _error(
                "CODE_BLOCK_TOO_LARGE",
                "Code block exceeds the materialization byte limit",
                maxBytes=DEFAULT_MAX_CODE_BLOCK_BYTES,
            )
        )
    artifact_name = (
        f"code-block-{block.index}.{block.language}" if name is None else name
    )
    if (
        not isinstance(artifact_name, str)
        or not artifact_name
        or len(artifact_name) > 128
        or artifact_name in {".", ".."}
        or "/" in artifact_name
        or "\\" in artifact_name
        or any(ord(char) < 32 or ord(char) == 127 for char in artifact_name)
    ):
        return Result.err(
            _error(
                "CODE_ARTIFACT_NAME_INVALID",
                "Code block artifact name is invalid",
            )
        )
    put = getattr(store, "put", None)
    if not callable(put):
        return Result.err(
            _error(
                "CODE_ARTIFACT_STORE_INVALID",
                "Code block artifact store must implement put",
            )
        )
    try:
        result = put(
            block.code.encode("utf-8"),
            name=artifact_name,
            media_type="text/plain",
        )
    except Exception as exc:
        return Result.err(
            _error(
                "CODE_ARTIFACT_STORE_ERROR",
                "Code block artifact store failed",
                exception=type(exc).__name__,
            )
        )
    if not isinstance(result, Result):
        return Result.err(
            _error(
                "CODE_ARTIFACT_STORE_INVALID",
                "Code block artifact store returned an invalid result",
            )
        )
    return result


__all__ = [
    "Artifact",
    "ArtifactStore",
    "CodeBlock",
    "FileArtifactStore",
    "InMemoryArtifactStore",
    "extract_code_blocks",
    "materialize_code_block",
]
