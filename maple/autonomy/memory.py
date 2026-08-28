"""
Copyright (C) 2025 Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

This file is part of MAPLE - Multi Agent Protocol Language Engine.

MAPLE - Multi Agent Protocol Language Engine is free software: you can redistribute it and/or
modify it under the terms of the GNU Affero General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later version.
MAPLE - Multi Agent Protocol Language Engine is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE. See the GNU Affero General Public License for more details. You should have
received a copy of the GNU Affero General Public License along with MAPLE - Multi Agent Protocol
Language Engine. If not, see <https://www.gnu.org/licenses/>.
"""

# Memory system for autonomous agents, built on existing StateStore.

import json
import logging
import math
import time
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, cast

from ..core.result import Result
from ..state.store import StateStore, StorageBackend

logger = logging.getLogger(__name__)

_MAX_WORKING_MEMORY_TOKENS = 1_000_000
_MAX_WORKING_MEMORY_ENTRIES = 4_096
_MAX_WORKING_MEMORY_KEY_BYTES = 256


@dataclass
class MemoryEntry:
    """A single memory entry."""

    key: str
    content: Any
    memory_type: str
    timestamp: float = field(default_factory=time.time)
    relevance_score: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class WorkingMemory:
    """
    Current context window management.
    Manages what the agent is 'thinking about right now'.
    Has a max token budget and evicts oldest entries when full.
    """

    def __init__(self, max_tokens: int = 8000) -> None:
        if (
            isinstance(max_tokens, bool)
            or not isinstance(max_tokens, int)
            or not 1 <= max_tokens <= _MAX_WORKING_MEMORY_TOKENS
        ):
            raise ValueError(
                "max_tokens must be an integer from 1 to "
                f"{_MAX_WORKING_MEMORY_TOKENS}"
            )
        self.max_tokens = max_tokens
        self.entries: List[MemoryEntry] = []
        self._current_tokens = 0

    def add(
        self, key: str, content: str, relevance: float = 1.0
    ) -> Result[None, Dict[str, Any]]:
        """Add content to working memory, evicting old entries if needed."""
        if (
            not isinstance(key, str)
            or not key
            or any(unicodedata.category(character) == "Cc" for character in key)
        ):
            return Result.err(
                {
                    "errorType": "MEMORY_KEY_INVALID",
                    "message": "Working-memory keys must be bounded text.",
                }
            )
        try:
            key_bytes = key.encode("utf-8")
        except UnicodeEncodeError:
            return Result.err(
                {
                    "errorType": "MEMORY_KEY_INVALID",
                    "message": "Working-memory keys must be bounded text.",
                }
            )
        if len(key_bytes) > _MAX_WORKING_MEMORY_KEY_BYTES:
            return Result.err(
                {
                    "errorType": "MEMORY_KEY_INVALID",
                    "message": "Working-memory keys must be bounded text.",
                }
            )
        if not isinstance(content, str):
            return Result.err(
                {
                    "errorType": "MEMORY_CONTENT_INVALID",
                    "message": "Working-memory content must be text.",
                }
            )
        if (
            isinstance(relevance, bool)
            or not isinstance(relevance, (int, float))
            or not math.isfinite(float(relevance))
            or not 0.0 <= relevance <= 1.0
        ):
            return Result.err(
                {
                    "errorType": "MEMORY_RELEVANCE_INVALID",
                    "message": "Working-memory relevance must be between 0 and 1.",
                }
            )
        try:
            tokens = self._estimate_tokens(content)
        except UnicodeEncodeError:
            return Result.err(
                {
                    "errorType": "MEMORY_CONTENT_INVALID",
                    "message": "Working-memory content must be valid UTF-8 text.",
                }
            )
        if tokens > self.max_tokens:
            return Result.err(
                {
                    "errorType": "MEMORY_ENTRY_TOO_LARGE",
                    "message": "Working-memory content exceeds the token budget.",
                    "details": {
                        "entry_tokens": tokens,
                        "max_tokens": self.max_tokens,
                    },
                }
            )
        while (
            self._current_tokens + tokens > self.max_tokens
            or len(self.entries) >= _MAX_WORKING_MEMORY_ENTRIES
        ) and self.entries:
            evicted = self.entries.pop(0)
            self._current_tokens -= self._estimate_tokens(str(evicted.content))

        entry = MemoryEntry(
            key=key, content=content, memory_type="working", relevance_score=relevance
        )
        self.entries.append(entry)
        self._current_tokens += tokens
        return Result.ok(None)

    @staticmethod
    def _estimate_tokens(content: str) -> int:
        """Estimate tokens conservatively from UTF-8 bytes for local bounds."""
        if not content:
            return 0
        return max(1, (len(content.encode("utf-8")) + 3) // 4)

    def get_context(self) -> List[Dict[str, Any]]:
        """Get all working memory as context for LLM."""
        return [
            {"key": e.key, "content": e.content, "relevance": e.relevance_score}
            for e in self.entries
        ]

    def clear(self) -> None:
        """Clear all working memory."""
        self.entries.clear()
        self._current_tokens = 0

    @property
    def size(self) -> int:
        return len(self.entries)

    @property
    def token_usage(self) -> int:
        return self._current_tokens


class EpisodicMemory:
    """
    Past interactions and outcomes, keyed by task.
    Uses StateStore for persistence.
    """

    def __init__(self, store: StateStore) -> None:
        self.store = store
        self._prefix = "episodic:"

    def record(
        self, task_id: str, event: Dict[str, Any]
    ) -> Result[None, Dict[str, Any]]:
        """Record an episode (action + outcome) for a task."""
        key = f"{self._prefix}{task_id}"
        existing = self.store.get(key)
        episodes_value = existing.unwrap() if existing.is_ok() else None
        episodes = cast(List[Dict[str, Any]], episodes_value) if episodes_value else []
        episodes.append({**event, "timestamp": time.time()})
        return self.store.set(key, episodes).map(lambda _: None)

    def recall(self, task_id: str) -> Result[List[Dict[str, Any]], Dict[str, Any]]:
        """Recall all episodes for a task."""
        key = f"{self._prefix}{task_id}"
        result = self.store.get(key)
        if result.is_ok():
            return Result.ok(result.unwrap() or [])
        return Result.ok([])

    def search(
        self, query: str, limit: int = 10
    ) -> Result[List[Dict[str, Any]], Dict[str, Any]]:
        """Search episodic memory by keyword."""
        keys_result = self.store.list_keys(prefix=self._prefix)
        if keys_result.is_err():
            return Result.ok([])

        matches: List[Dict[str, Any]] = []
        for key in keys_result.unwrap():
            episodes = self.store.get(key)
            episodes_value = episodes.unwrap() if episodes.is_ok() else None
            if episodes_value:
                for ep in cast(List[Dict[str, Any]], episodes_value):
                    if query.lower() in str(ep).lower():
                        matches.append(ep)
                        if len(matches) >= limit:
                            return Result.ok(matches)
        return Result.ok(matches)


class SemanticMemory:
    """
    Learned facts, agent capabilities, world knowledge.
    Uses StateStore for persistence.
    """

    def __init__(self, store: StateStore):
        self.store = store
        self._prefix = "semantic:"

    def store_fact(
        self, key: str, fact: Any, metadata: Optional[Dict] = None
    ) -> Result[None, Dict]:
        """Store a fact in semantic memory."""
        return self.store.set(f"{self._prefix}{key}", fact, metadata=metadata).map(
            lambda _: None
        )

    def recall_fact(self, key: str) -> Result[Any, Dict]:
        """Recall a fact from semantic memory."""
        return self.store.get(f"{self._prefix}{key}")

    def list_facts(self, prefix: Optional[str] = None) -> Result[List[str], Dict]:
        """List all fact keys."""
        search_prefix = f"{self._prefix}{prefix}" if prefix else self._prefix
        return self.store.list_keys(prefix=search_prefix)


class MemoryManager:
    """
    Unified memory interface for autonomous agents.
    Coordinates working, episodic, and semantic memory.
    """

    def __init__(
        self,
        backend: StorageBackend = StorageBackend.MEMORY,
        working_memory_tokens: int = 8000,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.store = StateStore(backend=backend, config=config)
        self.working = WorkingMemory(max_tokens=working_memory_tokens)
        self.episodic = EpisodicMemory(self.store)
        self.semantic = SemanticMemory(self.store)

    def summarize_and_archive(
        self, llm_provider: Optional[Any] = None
    ) -> Result[str, Dict[str, Any]]:
        """
        Summarize working memory and store in episodic memory.
        Requires an LLM provider for summarization.
        """
        if not llm_provider:
            return Result.err(
                {
                    "errorType": "NO_LLM",
                    "message": "LLM provider required for summarization",
                }
            )

        context = self.working.get_context()
        if not context:
            return Result.ok("nothing to summarize")

        from ..llm.types import ChatMessage, ChatRole

        messages = [
            ChatMessage(
                role=ChatRole.SYSTEM,
                content="Summarize the following working memory into key facts and outcomes. Be concise.",
            ),
            ChatMessage(role=ChatRole.USER, content=json.dumps(context, default=str)),
        ]

        result = llm_provider.complete(messages)
        if result.is_err():
            return Result.err(result.unwrap_err())

        summary = result.unwrap().content or ""
        self.episodic.record(
            "memory_summary", {"summary": summary, "entries_count": len(context)}
        )
        self.working.clear()
        return Result.ok(summary)
