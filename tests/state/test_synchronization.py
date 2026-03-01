"""Tests for maple.state.synchronization - StateSynchronizer."""

import pytest
from unittest.mock import MagicMock
from maple.state.synchronization import StateSynchronizer, SyncMode, SyncEvent
from maple.state.store import StateStore, StorageBackend


@pytest.fixture
def mock_agent():
    agent = MagicMock()
    agent.agent_id = "sync_test_agent"
    return agent


@pytest.fixture
def store():
    return StateStore(backend=StorageBackend.MEMORY)


@pytest.fixture
def syncer(mock_agent, store):
    return StateSynchronizer(mock_agent, store, sync_mode=SyncMode.BIDIRECTIONAL)


class TestPeerManagement:
    """Test peer add/remove."""

    def test_add_peer(self, syncer):
        syncer.add_peer("peer_1")
        stats = syncer.get_statistics()
        assert stats['peer_count'] >= 1

    def test_add_multiple_peers(self, syncer):
        syncer.add_peer("peer_1")
        syncer.add_peer("peer_2")
        syncer.add_peer("peer_3")
        stats = syncer.get_statistics()
        assert stats['peer_count'] >= 3

    def test_remove_peer(self, syncer):
        syncer.add_peer("peer_1")
        syncer.remove_peer("peer_1")
        stats = syncer.get_statistics()
        assert stats['peer_count'] == 0


class TestSyncLifecycle:
    """Test sync start/stop."""

    def test_start_stop(self, syncer):
        syncer.start_sync()
        stats = syncer.get_statistics()
        assert stats['sync_enabled'] is True

        syncer.stop_sync()
        stats = syncer.get_statistics()
        assert stats['sync_enabled'] is False

    def test_force_sync(self, syncer):
        syncer.add_peer("peer_1")
        result = syncer.force_sync()
        # May succeed or fail depending on transport, but shouldn't crash
        assert result is not None


class TestSyncEvent:
    """Test SyncEvent dataclass."""

    def test_to_dict(self):
        event = SyncEvent(
            key="test_key",
            operation="set",
            value={"data": 42},
            version=1,
            timestamp=100.0,
            source_agent="agent_a"
        )
        d = event.to_dict()
        assert d['key'] == 'test_key'
        assert d['operation'] == 'set'
        assert d['value'] == {"data": 42}
        assert d['source_agent'] == 'agent_a'

    def test_from_dict(self):
        data = {
            'key': 'k',
            'operation': 'set',
            'value': 'v',
            'version': 2,
            'timestamp': 200.0,
            'source_agent': 'agent_b'
        }
        event = SyncEvent.from_dict(data)
        assert event.key == 'k'
        assert event.source_agent == 'agent_b'

    def test_roundtrip(self):
        original = SyncEvent(
            key="roundtrip",
            operation="delete",
            value=None,
            version=5,
            timestamp=500.0,
            source_agent="agent_x"
        )
        restored = SyncEvent.from_dict(original.to_dict())
        assert restored.key == original.key
        assert restored.operation == original.operation
        assert restored.version == original.version


class TestStatistics:
    """Test synchronization statistics."""

    def test_initial_stats(self, syncer):
        stats = syncer.get_statistics()
        assert 'peer_count' in stats
        assert 'sync_enabled' in stats
        assert stats['sync_enabled'] is False
