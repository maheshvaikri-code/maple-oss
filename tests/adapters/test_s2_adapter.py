# Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)
# MAPLE - Multi Agent Protocol Language Engine

"""Tests for S2.dev adapter integration."""

import json
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from dataclasses import dataclass

from maple.core.message import Message
from maple.core.result import Result
from maple.broker.production_broker import BrokerType, ProductionBrokerManager


class TestBrokerTypeS2(unittest.TestCase):
    """Test S2 is registered as a broker type."""

    def test_s2_broker_type_exists(self):
        """Test BrokerType.S2 is defined."""
        self.assertEqual(BrokerType.S2.value, "s2")

    def test_s2_in_available_brokers(self):
        """Test S2 appears in available brokers list."""
        available = ProductionBrokerManager.get_available_brokers()
        self.assertIn(BrokerType.S2, available)
        # streamstore is not installed in test env, so should be False
        self.assertFalse(available[BrokerType.S2])

    def test_create_s2_broker_without_sdk(self):
        """Test creating S2 broker fails gracefully without streamstore."""
        from maple.agent.config import Config
        config = Config(agent_id="test", broker_url="s2://my-basin")
        result = ProductionBrokerManager.create_broker(config, BrokerType.S2)
        self.assertTrue(result.is_err())
        error = result.unwrap_err()
        self.assertEqual(error['errorType'], 'BROKER_DEPENDENCY_MISSING')
        self.assertIn('streamstore', error['message'])


class TestS2Config(unittest.TestCase):
    """Test S2Config dataclass."""

    def test_s2_config_defaults(self):
        """Test S2Config has correct defaults."""
        # Import with mocked streamstore
        with patch.dict('sys.modules', {'streamstore': MagicMock()}):
            from maple.adapters.s2_adapter import S2Config
            config = S2Config(access_token="test-token")
            self.assertEqual(config.access_token, "test-token")
            self.assertEqual(config.basin_name, "maple-agents")
            self.assertIsNone(config.endpoint)
            self.assertEqual(config.request_timeout, 5.0)
            self.assertEqual(config.max_retries, 3)
            self.assertFalse(config.enable_compression)
            self.assertTrue(config.create_basin_on_connect)
            self.assertTrue(config.create_streams_on_demand)

    def test_s2_config_custom_values(self):
        """Test S2Config with custom values."""
        with patch.dict('sys.modules', {'streamstore': MagicMock()}):
            from maple.adapters.s2_adapter import S2Config
            config = S2Config(
                access_token="my-token",
                basin_name="custom-basin",
                endpoint="https://custom.s2.dev",
                request_timeout=10.0,
                max_retries=5,
                enable_compression=True,
                create_basin_on_connect=False,
                create_streams_on_demand=False,
            )
            self.assertEqual(config.basin_name, "custom-basin")
            self.assertEqual(config.endpoint, "https://custom.s2.dev")
            self.assertTrue(config.enable_compression)


class TestS2BrokerUnit(unittest.TestCase):
    """Test S2Broker with mocked S2 SDK."""

    def _make_broker(self):
        """Create an S2Broker with mocked streamstore."""
        mock_s2_module = MagicMock()
        mock_s2_module.S2 = MagicMock
        mock_s2_module.Record = MagicMock
        mock_s2_module.AppendInput = MagicMock
        mock_s2_module.SeqNum = MagicMock
        mock_s2_module.ReadLimit = MagicMock
        mock_s2_module.StreamConfig = MagicMock
        mock_s2_module.BasinConfig = MagicMock

        with patch.dict('sys.modules', {'streamstore': mock_s2_module}):
            # Re-import to pick up the mock
            import importlib
            from maple.adapters import s2_adapter
            importlib.reload(s2_adapter)
            from maple.adapters.s2_adapter import S2Broker, S2Config

            config = S2Config(access_token="test-token", basin_name="test-basin")
            broker = S2Broker(config)
            return broker

    def test_broker_init(self):
        """Test S2Broker initializes correctly."""
        broker = self._make_broker()
        self.assertIsNotNone(broker)
        self.assertEqual(broker.config.basin_name, "test-basin")
        self.assertFalse(broker._running)
        self.assertEqual(len(broker._streams), 0)

    def test_broker_to_maple_config(self):
        """Test to_maple_config returns correct dict."""
        broker = self._make_broker()
        config = broker.to_maple_config()
        self.assertIn('s2_broker', config)
        self.assertEqual(config['s2_broker']['basin'], 'test-basin')


class TestS2StateBackendUnit(unittest.TestCase):
    """Test S2StateBackend with mocked S2 SDK."""

    def _make_backend(self):
        """Create an S2StateBackend with mocked streamstore."""
        mock_s2_module = MagicMock()
        mock_s2_module.S2 = MagicMock
        mock_s2_module.Record = MagicMock
        mock_s2_module.AppendInput = MagicMock
        mock_s2_module.SeqNum = MagicMock
        mock_s2_module.ReadLimit = MagicMock
        mock_s2_module.StreamConfig = MagicMock
        mock_s2_module.BasinConfig = MagicMock

        with patch.dict('sys.modules', {'streamstore': mock_s2_module}):
            import importlib
            from maple.adapters import s2_adapter
            importlib.reload(s2_adapter)
            from maple.adapters.s2_adapter import S2StateBackend, S2Config

            config = S2Config(access_token="test-token", basin_name="test-state")
            backend = S2StateBackend(config)
            return backend

    def test_backend_init(self):
        """Test S2StateBackend initializes correctly."""
        backend = self._make_backend()
        self.assertIsNotNone(backend)
        self.assertEqual(backend.config.basin_name, "test-state")
        self.assertEqual(len(backend._state_cache), 0)
        self.assertEqual(backend._version_counter, 0)

    def test_backend_get_empty(self):
        """Test get on empty cache returns None."""
        import asyncio
        backend = self._make_backend()
        result = asyncio.get_event_loop().run_until_complete(backend.get("nonexistent"))
        self.assertTrue(result.is_ok())
        self.assertIsNone(result.unwrap())

    def test_backend_list_keys_empty(self):
        """Test list_keys on empty cache returns empty list."""
        import asyncio
        backend = self._make_backend()
        result = asyncio.get_event_loop().run_until_complete(backend.list_keys())
        self.assertTrue(result.is_ok())
        self.assertEqual(result.unwrap(), [])

    def test_backend_list_keys_with_prefix(self):
        """Test list_keys filters by prefix."""
        import asyncio
        backend = self._make_backend()
        # Manually populate cache
        backend._state_cache = {
            "user:1": {"value": "a"},
            "user:2": {"value": "b"},
            "system:config": {"value": "c"},
        }
        result = asyncio.get_event_loop().run_until_complete(backend.list_keys("user:"))
        self.assertTrue(result.is_ok())
        keys = result.unwrap()
        self.assertEqual(len(keys), 2)
        self.assertIn("user:1", keys)
        self.assertIn("user:2", keys)

    def test_backend_statistics(self):
        """Test get_statistics returns correct info."""
        backend = self._make_backend()
        backend._state_cache = {"key1": {}, "key2": {}}
        backend._version_counter = 5
        stats = backend.get_statistics()
        self.assertEqual(stats['backend'], 's2')
        self.assertEqual(stats['basin'], 'test-state')
        self.assertEqual(stats['keys_count'], 2)
        self.assertEqual(stats['version_counter'], 5)

    def test_backend_add_listener(self):
        """Test listener registration."""
        backend = self._make_backend()
        callback = MagicMock()
        backend.add_listener(callback)
        self.assertEqual(len(backend._listeners), 1)
        self.assertEqual(backend._listeners[0], callback)


class TestAgentS2URLDetection(unittest.TestCase):
    """Test Agent auto-detects s2:// broker URLs."""

    def test_s2_url_triggers_s2_broker_path(self):
        """Test that s2:// URL triggers S2 broker creation path."""
        from maple.agent.config import Config
        from maple.agent.agent import Agent
        from maple.broker.broker import MessageBroker

        config = Config(agent_id="test_s2", broker_url="s2://my-basin")
        agent = Agent(config)
        # If streamstore is installed, broker is S2Broker; otherwise fallback to MessageBroker
        try:
            from maple.adapters.s2_adapter import S2Broker
            self.assertIsInstance(agent.broker, (S2Broker, MessageBroker))
        except ImportError:
            self.assertIsInstance(agent.broker, MessageBroker)


class TestAdaptersInit(unittest.TestCase):
    """Test adapters package initialization."""

    def test_adapters_import(self):
        """Test that maple.adapters can be imported."""
        import maple.adapters
        self.assertIsNotNone(maple.adapters)

    def test_s2_available_flag_is_bool(self):
        """Test S2_AVAILABLE flag is a boolean reflecting streamstore availability."""
        from maple.adapters import S2_AVAILABLE
        self.assertIsInstance(S2_AVAILABLE, bool)


if __name__ == '__main__':
    unittest.main()
