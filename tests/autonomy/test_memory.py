"""Tests for the autonomy memory system."""

import pytest

from maple.autonomy.memory import (
    EpisodicMemory,
    MemoryEntry,
    MemoryManager,
    SemanticMemory,
    WorkingMemory,
)
from maple.core.result import Result
from maple.llm.types import LLMResponse
from maple.state.store import StateStore, StorageBackend


class TestWorkingMemory:
    @pytest.mark.parametrize("max_tokens", [0, -1, True, 1.5, 1_000_001])
    def test_invalid_budget_fails_fast(self, max_tokens):
        with pytest.raises(ValueError):
            WorkingMemory(max_tokens=max_tokens)

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

    def test_unicode_token_accounting_uses_utf8_bytes(self):
        wm = WorkingMemory(max_tokens=2)

        result = wm.add("unicode", "é" * 3)

        assert result.is_ok()
        assert wm.token_usage == 2

    def test_oversized_entry_rejected_without_eviction(self):
        wm = WorkingMemory(max_tokens=2)
        wm.add("existing", "kept")

        result = wm.add("too-large", "x" * 9)

        assert result.is_err()
        assert result.unwrap_err()["errorType"] == "MEMORY_ENTRY_TOO_LARGE"
        assert [entry["key"] for entry in wm.get_context()] == ["existing"]
        assert wm.token_usage == 1

    def test_entry_count_is_bounded_with_empty_content(self):
        wm = WorkingMemory(max_tokens=1_000_000)
        for index in range(4_096):
            assert wm.add(str(index), "").is_ok()

        result = wm.add("new", "")

        assert result.is_ok()
        assert wm.size == 4_096
        assert wm.get_context()[0]["key"] == "1"

    def test_invalid_entry_metadata_rejected_without_mutation(self):
        wm = WorkingMemory(max_tokens=4)

        invalid_key = wm.add("bad\nkey", "value")
        invalid_unicode_control_key = wm.add("bad\x7fkey", "value")
        oversized_key = wm.add("k" * 257, "value")
        invalid_unicode_key = wm.add("\ud800", "value")
        invalid_content = wm.add("content", 123)
        invalid_unicode_content = wm.add("unicode", "\ud800")
        invalid_relevance = wm.add("relevance", "value", relevance=2.0)
        non_finite_relevance = wm.add("non-finite", "value", relevance=float("nan"))

        assert invalid_key.unwrap_err()["errorType"] == "MEMORY_KEY_INVALID"
        assert (
            invalid_unicode_control_key.unwrap_err()["errorType"]
            == "MEMORY_KEY_INVALID"
        )
        assert oversized_key.unwrap_err()["errorType"] == "MEMORY_KEY_INVALID"
        assert invalid_unicode_key.unwrap_err()["errorType"] == "MEMORY_KEY_INVALID"
        assert invalid_content.unwrap_err()["errorType"] == "MEMORY_CONTENT_INVALID"
        assert (
            invalid_unicode_content.unwrap_err()["errorType"]
            == "MEMORY_CONTENT_INVALID"
        )
        assert invalid_relevance.unwrap_err()["errorType"] == "MEMORY_RELEVANCE_INVALID"
        assert (
            non_finite_relevance.unwrap_err()["errorType"] == "MEMORY_RELEVANCE_INVALID"
        )
        assert wm.size == 0
        assert wm.token_usage == 0


class TestEpisodicMemory:
    @pytest.mark.parametrize(
        "kwargs",
        [
            {"max_events_per_task": 0},
            {"max_events_per_task": True},
            {"max_events_per_task": 1_025},
            {"max_event_bytes": 0},
            {"max_event_bytes": True},
            {"max_event_bytes": 65 * 1024},
        ],
    )
    def test_invalid_bounds_fail_fast(self, kwargs):
        store = StateStore(backend=StorageBackend.MEMORY)

        with pytest.raises(ValueError):
            EpisodicMemory(store, **kwargs)

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
        result = sm.store_fact(
            "fact1", {"value": True}, metadata={"source": "observation"}
        )
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

    def test_record_keeps_newest_bounded_event_window(self):
        store = StateStore(backend=StorageBackend.MEMORY)
        em = EpisodicMemory(store, max_events_per_task=2)

        assert em.record("task1", {"event": "first"}).is_ok()
        assert em.record("task1", {"event": "second"}).is_ok()
        assert em.record("task1", {"event": "third"}).is_ok()

        recalled = em.recall("task1")

        assert recalled.is_ok()
        assert [episode["event"] for episode in recalled.unwrap()] == [
            "second",
            "third",
        ]

    def test_oversized_event_rejected_without_write(self):
        store = StateStore(backend=StorageBackend.MEMORY)
        em = EpisodicMemory(store, max_event_bytes=128)

        result = em.record("task1", {"payload": "x" * 256})

        assert result.is_err()
        assert result.unwrap_err()["errorType"] == "EPISODIC_EVENT_TOO_LARGE"
        assert em.recall("task1").unwrap() == []

    def test_invalid_event_and_task_id_rejected_without_write(self):
        store = StateStore(backend=StorageBackend.MEMORY)
        em = EpisodicMemory(store)

        invalid_event = em.record("task1", {"value": float("nan")})
        invalid_task = em.record("bad\x7ftask", {"event": "ignored"})
        invalid_unicode = em.record("\ud800", {"event": "ignored"})

        assert invalid_event.unwrap_err()["errorType"] == "EPISODIC_EVENT_INVALID"
        assert invalid_task.unwrap_err()["errorType"] == "EPISODIC_TASK_ID_INVALID"
        assert invalid_unicode.unwrap_err()["errorType"] == "EPISODIC_TASK_ID_INVALID"
        assert em.recall("task1").unwrap() == []

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

    def test_summarize_preserves_working_memory_when_archive_fails(self, monkeypatch):
        mm = MemoryManager()
        mm.working.add("k1", "retain this context")

        class FakeProvider:
            def complete(self, messages):
                return Result.ok(LLMResponse(content="summary"))

        archive_error = {
            "errorType": "MEMORY_ARCHIVE_FAILED",
            "message": "persist failed",
        }
        monkeypatch.setattr(
            mm.episodic,
            "record",
            lambda task_id, event: Result.err(archive_error),
        )

        result = mm.summarize_and_archive(llm_provider=FakeProvider())

        assert result.is_err()
        assert result.unwrap_err() == archive_error
        assert [entry["key"] for entry in mm.working.get_context()] == ["k1"]
        assert mm.working.token_usage > 0


class TestMemoryEntry:
    def test_creation(self):
        entry = MemoryEntry(key="k", content="data", memory_type="working")
        assert entry.key == "k"
        assert entry.relevance_score == 1.0
        assert entry.timestamp > 0
