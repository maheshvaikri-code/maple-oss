"""Tests for the autonomy memory system."""

import pytest
from maple.autonomy.memory import (
    WorkingMemory, EpisodicMemory, SemanticMemory, MemoryManager, MemoryEntry,
)
from maple.state.store import StateStore, StorageBackend
from maple.core.result import Result


class TestWorkingMemory:
    def test_add_and_retrieve(self):
        wm = WorkingMemory(max_tokens=1000)
        wm.add("key1", "hello world")
        ctx = wm.get_context()
        assert len(ctx) == 1
        assert ctx[0]["key"] == "key1"
        assert ctx[0]["content"] == "hello world"

    def test_size_and_tokens(self):
        wm = WorkingMemory(max_tokens=1000)
        wm.add("k1", "hello")
        wm.add("k2", "world")
        assert wm.size == 2
        assert wm.token_usage > 0

    def test_eviction_on_overflow(self):
        wm = WorkingMemory(max_tokens=10)  # Very small budget
        wm.add("old", "a" * 20)  # 5 tokens
        wm.add("new", "b" * 20)  # 5 tokens, should evict old
        ctx = wm.get_context()
        keys = [c["key"] for c in ctx]
        # At least the newest entry should be there
        assert "new" in keys

    def test_clear(self):
        wm = WorkingMemory()
        wm.add("k1", "data")
        wm.add("k2", "data")
        assert wm.size == 2
        wm.clear()
        assert wm.size == 0
        assert wm.token_usage == 0

    def test_relevance_score(self):
        wm = WorkingMemory()
        wm.add("important", "critical data", relevance=0.9)
        ctx = wm.get_context()
        assert ctx[0]["relevance"] == 0.9


class TestEpisodicMemory:
    def test_record_and_recall(self):
        store = StateStore(backend=StorageBackend.MEMORY)
        em = EpisodicMemory(store)
        em.record("task1", {"action": "search", "outcome": "found 3 results"})
        em.record("task1", {"action": "analyze", "outcome": "pattern detected"})

        result = em.recall("task1")
        assert result.is_ok()
        episodes = result.unwrap()
        assert len(episodes) == 2
        assert episodes[0]["action"] == "search"

    def test_recall_empty(self):
        store = StateStore(backend=StorageBackend.MEMORY)
        em = EpisodicMemory(store)
        result = em.recall("nonexistent")
        assert result.is_ok()
        assert result.unwrap() == []

    def test_search(self):
        store = StateStore(backend=StorageBackend.MEMORY)
        em = EpisodicMemory(store)
        em.record("task1", {"action": "search", "query": "python error"})
        em.record("task1", {"action": "fix", "result": "bug resolved"})
        em.record("task2", {"action": "search", "query": "database timeout"})

        result = em.search("error")
        assert result.is_ok()
        matches = result.unwrap()
        assert len(matches) >= 1
        assert any("error" in str(m).lower() for m in matches)


class TestSemanticMemory:
    def test_store_and_recall(self):
        store = StateStore(backend=StorageBackend.MEMORY)
        sm = SemanticMemory(store)
        sm.store_fact("agent_count", 5)
        result = sm.recall_fact("agent_count")
        assert result.is_ok()
        assert result.unwrap() == 5

    def test_recall_missing(self):
        store = StateStore(backend=StorageBackend.MEMORY)
        sm = SemanticMemory(store)
        result = sm.recall_fact("missing_key")
        # Should return ok with None or err
        if result.is_ok():
            assert result.unwrap() is None

    def test_store_with_metadata(self):
        store = StateStore(backend=StorageBackend.MEMORY)
        sm = SemanticMemory(store)
        result = sm.store_fact("fact1", {"value": True}, metadata={"source": "observation"})
        assert result.is_ok()

    def test_list_facts(self):
        store = StateStore(backend=StorageBackend.MEMORY)
        sm = SemanticMemory(store)
        sm.store_fact("python.version", "3.11")
        sm.store_fact("python.framework", "maple")
        sm.store_fact("system.os", "linux")

        result = sm.list_facts("python")
        assert result.is_ok()
        keys = result.unwrap()
        assert len(keys) >= 2


class TestMemoryManager:
    def test_creation(self):
        mm = MemoryManager()
        assert mm.working is not None
        assert mm.episodic is not None
        assert mm.semantic is not None

    def test_working_memory_integration(self):
        mm = MemoryManager(working_memory_tokens=4000)
        mm.working.add("test", "hello world")
        assert mm.working.size == 1

    def test_episodic_integration(self):
        mm = MemoryManager()
        mm.episodic.record("task1", {"event": "started"})
        result = mm.episodic.recall("task1")
        assert result.is_ok()
        assert len(result.unwrap()) == 1

    def test_semantic_integration(self):
        mm = MemoryManager()
        mm.semantic.store_fact("key", "value")
        result = mm.semantic.recall_fact("key")
        assert result.is_ok()
        assert result.unwrap() == "value"

    def test_summarize_no_llm(self):
        mm = MemoryManager()
        mm.working.add("k1", "data")
        result = mm.summarize_and_archive()
        assert result.is_err()
        assert "LLM" in result.unwrap_err()["message"]

    def test_summarize_empty_working_memory(self):
        mm = MemoryManager()
        # With no working memory, should return ok
        result = mm.summarize_and_archive(llm_provider="fake")
        assert result.is_ok()
        assert "nothing" in result.unwrap()


class TestMemoryEntry:
    def test_creation(self):
        entry = MemoryEntry(key="k", content="data", memory_type="working")
        assert entry.key == "k"
        assert entry.relevance_score == 1.0
        assert entry.timestamp > 0
