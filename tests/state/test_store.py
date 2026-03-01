"""Tests for maple.state.store - StateStore with all backends."""

import os
import shutil
import tempfile
import pytest
from maple.state.store import StateStore, StorageBackend, ConsistencyLevel, StateEntry


# --- Memory backend ---

class TestMemoryBackend:
    """Test StateStore with memory backend."""

    @pytest.fixture
    def store(self):
        return StateStore(backend=StorageBackend.MEMORY, consistency=ConsistencyLevel.EVENTUAL)

    def test_get_nonexistent(self, store):
        result = store.get("missing")
        assert result.is_ok()
        assert result.unwrap() is None

    def test_set_and_get(self, store):
        store.set("key1", {"value": 42})
        result = store.get("key1")
        assert result.is_ok()
        assert result.unwrap() == {"value": 42}

    def test_overwrite(self, store):
        store.set("key1", "first")
        store.set("key1", "second")
        assert store.get("key1").unwrap() == "second"

    def test_delete(self, store):
        store.set("key1", "value")
        result = store.delete("key1")
        assert result.is_ok()
        assert result.unwrap() is True
        assert store.get("key1").unwrap() is None

    def test_delete_nonexistent(self, store):
        result = store.delete("missing")
        assert result.is_ok()
        assert result.unwrap() is False

    def test_list_keys(self, store):
        store.set("a", 1)
        store.set("b", 2)
        store.set("c", 3)
        result = store.list_keys()
        assert result.is_ok()
        assert sorted(result.unwrap()) == ["a", "b", "c"]

    def test_list_keys_with_prefix(self, store):
        store.set("user:1", "alice")
        store.set("user:2", "bob")
        store.set("task:1", "clean")
        result = store.list_keys(prefix="user:")
        assert result.is_ok()
        assert sorted(result.unwrap()) == ["user:1", "user:2"]

    def test_version_tracking(self, store):
        r1 = store.set("key", "v1")
        r2 = store.set("key", "v2")
        assert r1.unwrap().version < r2.unwrap().version

    def test_optimistic_locking_success(self, store):
        entry = store.set("key", "v1").unwrap()
        result = store.set("key", "v2", expected_version=entry.version)
        assert result.is_ok()

    def test_optimistic_locking_failure(self, store):
        store.set("key", "v1")
        store.set("key", "v2")  # bumps version
        result = store.set("key", "v3", expected_version=1)
        assert result.is_err()
        assert result.unwrap_err()['errorType'] == 'VERSION_MISMATCH'

    def test_delete_with_version_check(self, store):
        entry = store.set("key", "value").unwrap()
        result = store.delete("key", expected_version=entry.version)
        assert result.is_ok()
        assert result.unwrap() is True

    def test_delete_version_mismatch(self, store):
        store.set("key", "v1")
        store.set("key", "v2")
        result = store.delete("key", expected_version=1)
        assert result.is_err()

    def test_statistics(self, store):
        store.set("a", "1")
        store.set("b", "2")
        stats = store.get_statistics()
        assert stats['backend'] == 'memory'
        assert stats['keys_count'] == 2

    def test_listeners(self, store):
        changes = []
        store.add_listener(lambda k, e: changes.append((k, e.value)))
        store.set("key", "value")
        assert len(changes) == 1
        assert changes[0] == ("key", "value")

    def test_remove_listener(self, store):
        changes = []
        listener = lambda k, e: changes.append(k)
        store.add_listener(listener)
        store.set("a", 1)
        store.remove_listener(listener)
        store.set("b", 2)
        assert len(changes) == 1


# --- File backend ---

class TestFileBackend:
    """Test StateStore with file backend."""

    @pytest.fixture
    def store(self, tmp_path):
        return StateStore(
            backend=StorageBackend.FILE,
            consistency=ConsistencyLevel.EVENTUAL,
            config={'directory': str(tmp_path / 'state')}
        )

    def test_get_nonexistent(self, store):
        result = store.get("missing")
        assert result.is_ok()
        assert result.unwrap() is None

    def test_set_and_get(self, store):
        store.set("key1", {"value": 42})
        result = store.get("key1")
        assert result.is_ok()
        assert result.unwrap() == {"value": 42}

    def test_overwrite(self, store):
        store.set("key1", "first")
        store.set("key1", "second")
        assert store.get("key1").unwrap() == "second"

    def test_delete(self, store):
        store.set("key1", "value")
        result = store.delete("key1")
        assert result.is_ok()
        assert result.unwrap() is True
        assert store.get("key1").unwrap() is None

    def test_delete_nonexistent(self, store):
        result = store.delete("missing")
        assert result.is_ok()
        assert result.unwrap() is False

    def test_list_keys(self, store):
        store.set("a", 1)
        store.set("b", 2)
        result = store.list_keys()
        assert result.is_ok()
        assert sorted(result.unwrap()) == ["a", "b"]

    def test_list_keys_with_prefix(self, store):
        store.set("user_1", "alice")
        store.set("user_2", "bob")
        store.set("task_1", "clean")
        result = store.list_keys(prefix="user_")
        assert result.is_ok()
        assert len(result.unwrap()) == 2

    def test_version_check(self, store):
        entry = store.set("key", "v1").unwrap()
        result = store.set("key", "v2", expected_version=entry.version)
        assert result.is_ok()

    def test_version_mismatch(self, store):
        store.set("key", "v1")
        store.set("key", "v2")
        result = store.set("key", "v3", expected_version=1)
        assert result.is_err()

    def test_statistics(self, store):
        store.set("a", 1)
        stats = store.get_statistics()
        assert stats['backend'] == 'file'
        assert stats['keys_count'] == 1

    def test_persistence(self, store):
        """Data should survive across store instances."""
        store.set("persistent", "data")

        # Create new store pointing to same directory
        store2 = StateStore(
            backend=StorageBackend.FILE,
            config={'directory': store._file_dir}
        )
        result = store2.get("persistent")
        assert result.is_ok()
        assert result.unwrap() == "data"


# --- SQLite database backend ---

class TestDatabaseBackend:
    """Test StateStore with SQLite database backend."""

    @pytest.fixture
    def store(self, tmp_path):
        return StateStore(
            backend=StorageBackend.DATABASE,
            consistency=ConsistencyLevel.STRONG,
            config={'database_path': str(tmp_path / 'test_state.db')}
        )

    def test_get_nonexistent(self, store):
        result = store.get("missing")
        assert result.is_ok()
        assert result.unwrap() is None

    def test_set_and_get(self, store):
        store.set("key1", {"value": 42})
        result = store.get("key1")
        assert result.is_ok()
        assert result.unwrap() == {"value": 42}

    def test_set_string(self, store):
        store.set("key", "hello")
        assert store.get("key").unwrap() == "hello"

    def test_set_number(self, store):
        store.set("key", 3.14)
        assert store.get("key").unwrap() == 3.14

    def test_set_list(self, store):
        store.set("key", [1, 2, 3])
        assert store.get("key").unwrap() == [1, 2, 3]

    def test_overwrite(self, store):
        store.set("key", "first")
        store.set("key", "second")
        assert store.get("key").unwrap() == "second"

    def test_delete(self, store):
        store.set("key", "value")
        result = store.delete("key")
        assert result.is_ok()
        assert result.unwrap() is True
        assert store.get("key").unwrap() is None

    def test_delete_nonexistent(self, store):
        result = store.delete("missing")
        assert result.is_ok()
        assert result.unwrap() is False

    def test_list_keys(self, store):
        store.set("a", 1)
        store.set("b", 2)
        store.set("c", 3)
        result = store.list_keys()
        assert result.is_ok()
        assert sorted(result.unwrap()) == ["a", "b", "c"]

    def test_list_keys_with_prefix(self, store):
        store.set("user:1", "alice")
        store.set("user:2", "bob")
        store.set("task:1", "clean")
        result = store.list_keys(prefix="user:")
        assert result.is_ok()
        assert sorted(result.unwrap()) == ["user:1", "user:2"]

    def test_optimistic_locking_success(self, store):
        entry = store.set("key", "v1").unwrap()
        result = store.set("key", "v2", expected_version=entry.version)
        assert result.is_ok()

    def test_optimistic_locking_failure(self, store):
        store.set("key", "v1")
        store.set("key", "v2")
        result = store.set("key", "v3", expected_version=1)
        assert result.is_err()
        assert result.unwrap_err()['errorType'] == 'VERSION_MISMATCH'

    def test_delete_with_version_check(self, store):
        entry = store.set("key", "value").unwrap()
        result = store.delete("key", expected_version=entry.version)
        assert result.is_ok()

    def test_delete_version_mismatch(self, store):
        store.set("key", "v1")
        store.set("key", "v2")
        result = store.delete("key", expected_version=1)
        assert result.is_err()

    def test_statistics(self, store):
        store.set("a", 1)
        store.set("b", 2)
        stats = store.get_statistics()
        assert stats['backend'] == 'database'
        assert stats['keys_count'] == 2

    def test_persistence(self, store):
        """Data should survive across store instances."""
        store.set("persistent", {"data": True})

        store2 = StateStore(
            backend=StorageBackend.DATABASE,
            config={'database_path': store._db_path}
        )
        result = store2.get("persistent")
        assert result.is_ok()
        assert result.unwrap() == {"data": True}

    def test_metadata(self, store):
        store.set("key", "value", metadata={"source": "test"})
        # Just verify it doesn't crash - metadata is stored in DB


# --- StateEntry ---

class TestStateEntry:
    """Test StateEntry serialization."""

    def test_to_dict(self):
        entry = StateEntry(key="k", value="v", version=1, timestamp=100.0, metadata={})
        d = entry.to_dict()
        assert d['key'] == 'k'
        assert d['value'] == 'v'
        assert d['version'] == 1

    def test_from_dict(self):
        data = {'key': 'k', 'value': 'v', 'version': 1, 'timestamp': 100.0, 'metadata': {}}
        entry = StateEntry.from_dict(data)
        assert entry.key == 'k'
        assert entry.value == 'v'

    def test_roundtrip(self):
        original = StateEntry(key="test", value={"data": [1, 2]}, version=5, timestamp=999.0, metadata={"m": 1})
        restored = StateEntry.from_dict(original.to_dict())
        assert restored.key == original.key
        assert restored.value == original.value
        assert restored.version == original.version


# --- Redis backend (stub) ---

class TestRedisBackend:
    """Test that Redis backend returns NOT_IMPLEMENTED."""

    @pytest.fixture
    def store(self):
        # We can't actually create a Redis store without the lib,
        # but we can test the error paths directly
        s = StateStore(backend=StorageBackend.MEMORY)
        s.backend = StorageBackend.REDIS
        return s

    def test_get_not_implemented(self, store):
        result = store.get("key")
        assert result.is_err()
        assert 'NOT_IMPLEMENTED' in result.unwrap_err()['errorType']

    def test_set_not_implemented(self, store):
        result = store.set("key", "value")
        assert result.is_err()

    def test_delete_not_implemented(self, store):
        result = store.delete("key")
        assert result.is_err()
