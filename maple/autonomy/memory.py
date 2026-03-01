"""Memory system for autonomous agents, built on existing StateStore."""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..core.result import Result
from ..state.store import StateStore, StorageBackend

logger = logging.getLogger(__name__)


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

    def __init__(self, max_tokens: int = 8000):
        self.max_tokens = max_tokens
        self.entries: List[MemoryEntry] = []
        self._current_tokens = 0

    def add(self, key: str, content: str, relevance: float = 1.0) -> Result[None, Dict[str, Any]]:
        """Add content to working memory, evicting old entries if needed."""
        tokens = len(content) // 4
        while self._current_tokens + tokens > self.max_tokens and self.entries:
            evicted = self.entries.pop(0)
            self._current_tokens -= len(str(evicted.content)) // 4

        entry = MemoryEntry(key=key, content=content, memory_type="working", relevance_score=relevance)
        self.entries.append(entry)
        self._current_tokens += tokens
        return Result.ok(None)

    def get_context(self) -> List[Dict[str, Any]]:
        """Get all working memory as context for LLM."""
        return [{'key': e.key, 'content': e.content, 'relevance': e.relevance_score} for e in self.entries]

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

    def __init__(self, store: StateStore):
        self.store = store
        self._prefix = "episodic:"

    def record(self, task_id: str, event: Dict[str, Any]) -> Result[None, Dict[str, Any]]:
        """Record an episode (action + outcome) for a task."""
        key = f"{self._prefix}{task_id}"
        existing = self.store.get(key)
        episodes = existing.unwrap() if existing.is_ok() and existing.unwrap() else []
        episodes.append({**event, 'timestamp': time.time()})
        return self.store.set(key, episodes).map(lambda _: None)

    def recall(self, task_id: str) -> Result[List[Dict], Dict[str, Any]]:
        """Recall all episodes for a task."""
        key = f"{self._prefix}{task_id}"
        result = self.store.get(key)
        if result.is_ok():
            return Result.ok(result.unwrap() or [])
        return Result.ok([])

    def search(self, query: str, limit: int = 10) -> Result[List[Dict], Dict[str, Any]]:
        """Search episodic memory by keyword."""
        keys_result = self.store.list_keys(prefix=self._prefix)
        if keys_result.is_err():
            return Result.ok([])

        matches = []
        for key in keys_result.unwrap():
            episodes = self.store.get(key)
            if episodes.is_ok() and episodes.unwrap():
                for ep in episodes.unwrap():
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

    def store_fact(self, key: str, fact: Any, metadata: Optional[Dict] = None) -> Result[None, Dict]:
        """Store a fact in semantic memory."""
        return self.store.set(f"{self._prefix}{key}", fact, metadata=metadata).map(lambda _: None)

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
    ):
        self.store = StateStore(backend=backend, config=config)
        self.working = WorkingMemory(max_tokens=working_memory_tokens)
        self.episodic = EpisodicMemory(self.store)
        self.semantic = SemanticMemory(self.store)

    def summarize_and_archive(self, llm_provider=None) -> Result[str, Dict]:
        """
        Summarize working memory and store in episodic memory.
        Requires an LLM provider for summarization.
        """
        if not llm_provider:
            return Result.err({'errorType': 'NO_LLM', 'message': 'LLM provider required for summarization'})

        context = self.working.get_context()
        if not context:
            return Result.ok("nothing to summarize")

        from ..llm.types import ChatMessage, ChatRole
        messages = [
            ChatMessage(role=ChatRole.SYSTEM, content="Summarize the following working memory into key facts and outcomes. Be concise."),
            ChatMessage(role=ChatRole.USER, content=json.dumps(context, default=str))
        ]

        result = llm_provider.complete(messages)
        if result.is_err():
            return result

        summary = result.unwrap().content
        self.episodic.record("memory_summary", {"summary": summary, "entries_count": len(context)})
        self.working.clear()
        return Result.ok(summary)
