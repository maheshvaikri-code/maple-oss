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


# maple/adapters/s2_adapter.py
# Creator: Mahesh Vaikri

"""
S2.dev Integration Adapter for MAPLE

Bridges MAPLE's agent communication with S2's durable streaming platform
(https://s2.dev). S2 provides unlimited, durable, real-time streams that
are ideal for multi-agent message transport and persistent state storage.

Usage:
    pip install streamstore

    from maple.adapters.s2_adapter import S2Broker, S2StateBackend

    # As a message broker
    broker = S2Broker(access_token="your_s2_token", basin_name="maple-agents")
    await broker.connect()
    await broker.send("agent_a", "agent_b", message)

    # As a state backend
    state = S2StateBackend(access_token="your_s2_token", basin_name="maple-state")
    await state.connect()
    await state.set("key", {"value": 42})
"""

import asyncio
import json
import time
import logging
from typing import Any, Dict, List, Optional, Callable, AsyncIterator
from dataclasses import dataclass

from ..core.message import Message
from ..core.result import Result

try:
    from streamstore import (
        S2,
        Record,
        AppendInput,
        SeqNum,
        ReadLimit,
        StreamConfig,
        BasinConfig,
    )
    S2_AVAILABLE = True
except ImportError:
    S2_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class S2Config:
    """Configuration for S2.dev integration."""
    access_token: str
    basin_name: str = "maple-agents"
    endpoint: Optional[str] = None
    request_timeout: float = 5.0
    max_retries: int = 3
    enable_compression: bool = False
    create_basin_on_connect: bool = True
    create_streams_on_demand: bool = True


class S2Broker:
    """
    MAPLE message broker backed by S2.dev durable streams.

    Each agent gets its own S2 stream within a shared basin.
    Messages are appended as JSON-encoded records, and agents
    read from their stream to receive messages.

    Features:
    - Durable message delivery (messages survive restarts)
    - Real-time streaming via S2 read sessions
    - Per-agent message streams with sequence tracking
    - Topic-based pub/sub via dedicated topic streams
    """

    def __init__(self, config: S2Config):
        if not S2_AVAILABLE:
            raise ImportError(
                "S2 SDK not available. Install with: pip install streamstore"
            )
        self.config = config
        self._client: Optional[S2] = None
        self._basin = None
        self._streams: Dict[str, Any] = {}  # agent_id -> stream
        self._read_positions: Dict[str, int] = {}  # agent_id -> last seq_num
        self._handlers: Dict[str, List[Callable]] = {}
        self._running = False

    async def connect(self) -> Result[None, Dict[str, Any]]:
        """Connect to S2 and initialize the basin."""
        try:
            kwargs = {
                'access_token': self.config.access_token,
                'request_timeout': self.config.request_timeout,
                'max_retries': self.config.max_retries,
                'enable_compression': self.config.enable_compression,
            }
            if self.config.endpoint:
                kwargs['endpoints'] = self.config.endpoint

            self._client = S2(**kwargs)

            if self.config.create_basin_on_connect:
                try:
                    await self._client.create_basin(
                        self.config.basin_name,
                        BasinConfig(create_stream_on_append=True)
                    )
                    logger.info(f"Created S2 basin: {self.config.basin_name}")
                except Exception:
                    # Basin may already exist
                    pass

            self._basin = self._client.basin(self.config.basin_name)
            self._running = True

            logger.info(f"S2Broker connected to basin: {self.config.basin_name}")
            return Result.ok(None)

        except Exception as e:
            return Result.err({
                'errorType': 'S2_CONNECTION_ERROR',
                'message': f'Failed to connect to S2: {str(e)}'
            })

    async def disconnect(self) -> None:
        """Disconnect from S2."""
        self._running = False
        if self._client:
            await self._client.close()
            self._client = None
        logger.info("S2Broker disconnected")

    async def _ensure_stream(self, stream_name: str):
        """Get or create a stream for an agent."""
        if stream_name not in self._streams:
            if self.config.create_streams_on_demand:
                try:
                    await self._basin.create_stream(stream_name)
                except Exception:
                    pass  # Stream may already exist
            self._streams[stream_name] = self._basin.stream(stream_name)
        return self._streams[stream_name]

    async def send(
        self,
        sender: str,
        receiver: str,
        message: Message
    ) -> Result[str, Dict[str, Any]]:
        """
        Send a MAPLE message to a receiver via S2 stream.

        The message is serialized as JSON and appended to the
        receiver's stream.
        """
        try:
            stream = await self._ensure_stream(f"agent-{receiver}")

            # Serialize message to JSON bytes
            msg_dict = message.to_dict()
            msg_dict['_maple_sender'] = sender
            msg_dict['_maple_timestamp'] = time.time()
            body = json.dumps(msg_dict).encode('utf-8')

            record = Record(body=body, headers=[
                (b'sender', sender.encode()),
                (b'type', message.message_type.encode()),
                (b'priority', (message.priority.value if hasattr(message.priority, 'value') else str(message.priority)).encode()),
            ])

            result = await stream.append(AppendInput(records=[record]))

            msg_id = f"s2_{result.start_seq_num}"
            logger.debug(f"Message sent to {receiver} at seq {result.start_seq_num}")
            return Result.ok(msg_id)

        except Exception as e:
            return Result.err({
                'errorType': 'S2_SEND_ERROR',
                'message': f'Failed to send message via S2: {str(e)}',
                'details': {'sender': sender, 'receiver': receiver}
            })

    async def receive(
        self,
        agent_id: str,
        timeout: float = 5.0
    ) -> Result[Message, Dict[str, Any]]:
        """
        Receive the next message for an agent from their S2 stream.

        Reads from the last known position forward.
        """
        try:
            stream = await self._ensure_stream(f"agent-{agent_id}")
            start = self._read_positions.get(agent_id, 0)

            records = await stream.read(
                start=SeqNum(start),
                limit=ReadLimit(count=1)
            )

            if hasattr(records, 'next_seq_num'):
                # Got a Tail response - no new records
                return Result.err({
                    'errorType': 'NO_MESSAGES',
                    'message': 'No new messages available'
                })

            if records and len(records) > 0:
                record = records[0]
                msg_data = json.loads(record.body.decode('utf-8'))

                # Update read position
                self._read_positions[agent_id] = record.seq_num + 1

                # Reconstruct MAPLE Message
                message = Message.from_dict(msg_data)
                return Result.ok(message)

            return Result.err({
                'errorType': 'NO_MESSAGES',
                'message': 'No new messages available'
            })

        except Exception as e:
            return Result.err({
                'errorType': 'S2_RECEIVE_ERROR',
                'message': f'Failed to receive from S2: {str(e)}'
            })

    async def publish(
        self,
        topic: str,
        message: Message
    ) -> Result[str, Dict[str, Any]]:
        """Publish a message to a topic stream."""
        try:
            stream = await self._ensure_stream(f"topic-{topic}")

            body = json.dumps(message.to_dict()).encode('utf-8')
            record = Record(body=body, headers=[
                (b'topic', topic.encode()),
                (b'type', message.message_type.encode()),
            ])

            result = await stream.append(AppendInput(records=[record]))
            return Result.ok(f"s2_topic_{result.start_seq_num}")

        except Exception as e:
            return Result.err({
                'errorType': 'S2_PUBLISH_ERROR',
                'message': f'Failed to publish to topic {topic}: {str(e)}'
            })

    async def subscribe_stream(
        self,
        agent_id: str,
        topic: str,
        handler: Callable[[Message], None]
    ) -> Result[None, Dict[str, Any]]:
        """
        Subscribe to a topic stream. Messages are delivered to the handler
        via a background read session.
        """
        try:
            stream = await self._ensure_stream(f"topic-{topic}")

            key = f"{agent_id}:{topic}"
            if key not in self._handlers:
                self._handlers[key] = []
            self._handlers[key].append(handler)

            # Start background reader for this subscription
            asyncio.create_task(self._topic_reader(stream, key))

            return Result.ok(None)
        except Exception as e:
            return Result.err({
                'errorType': 'S2_SUBSCRIBE_ERROR',
                'message': f'Failed to subscribe to topic {topic}: {str(e)}'
            })

    async def _topic_reader(self, stream, handler_key: str):
        """Background task that reads from a topic stream and dispatches messages."""
        position = 0
        while self._running:
            try:
                async for record in stream.read_session(start=SeqNum(position)):
                    msg_data = json.loads(record.body.decode('utf-8'))
                    message = Message.from_dict(msg_data)
                    position = record.seq_num + 1

                    for handler in self._handlers.get(handler_key, []):
                        try:
                            handler(message)
                        except Exception as e:
                            logger.error(f"Handler error: {e}")
            except Exception as e:
                logger.error(f"Topic reader error: {e}")
                await asyncio.sleep(1)

    def to_maple_config(self) -> Dict[str, Any]:
        """
        Generate a MAPLE-compatible config dictionary for this broker.

        Usage:
            config = Config(
                agent_id="my_agent",
                broker_url=f"s2://{basin_name}",
                **broker.to_maple_config()
            )
        """
        return {
            's2_broker': {
                'basin': self.config.basin_name,
                'endpoint': self.config.endpoint,
                'compression': self.config.enable_compression,
            }
        }


class S2StateBackend:
    """
    MAPLE state backend powered by S2.dev streams.

    Uses a single S2 stream as an append-only log for state changes.
    The current state is reconstructed by replaying the log. This provides
    durable, distributed state with full audit history.

    The stream stores JSON records with key, value, version, and operation
    type (set/delete).
    """

    def __init__(self, config: S2Config):
        if not S2_AVAILABLE:
            raise ImportError(
                "S2 SDK not available. Install with: pip install streamstore"
            )
        self.config = config
        self._client: Optional[S2] = None
        self._stream = None
        self._state_cache: Dict[str, Dict[str, Any]] = {}
        self._version_counter = 0
        self._listeners: List[Callable] = []

    async def connect(self) -> Result[None, Dict[str, Any]]:
        """Connect and replay the state log to rebuild cache."""
        try:
            self._client = S2(
                access_token=self.config.access_token,
                request_timeout=self.config.request_timeout,
            )

            try:
                await self._client.create_basin(
                    self.config.basin_name,
                    BasinConfig(create_stream_on_append=True)
                )
            except Exception:
                pass

            basin = self._client.basin(self.config.basin_name)

            try:
                await basin.create_stream("state-log")
            except Exception:
                pass

            self._stream = basin.stream("state-log")

            # Replay log to rebuild state
            await self._replay_log()

            logger.info(f"S2StateBackend connected, replayed {self._version_counter} entries")
            return Result.ok(None)

        except Exception as e:
            return Result.err({
                'errorType': 'S2_STATE_CONNECTION_ERROR',
                'message': f'Failed to connect S2 state backend: {str(e)}'
            })

    async def disconnect(self) -> None:
        """Disconnect from S2."""
        if self._client:
            await self._client.close()
            self._client = None

    async def _replay_log(self):
        """Replay the state log to rebuild the in-memory cache."""
        try:
            records = await self._stream.read(
                start=SeqNum(0),
                limit=ReadLimit(count=100000)
            )

            if hasattr(records, 'next_seq_num'):
                return  # Empty stream

            for record in records:
                entry = json.loads(record.body.decode('utf-8'))
                op = entry.get('operation', 'set')
                key = entry['key']

                if op == 'delete':
                    self._state_cache.pop(key, None)
                else:
                    self._state_cache[key] = entry
                    self._version_counter = max(
                        self._version_counter, entry.get('version', 0)
                    )
        except Exception as e:
            logger.warning(f"State log replay error: {e}")

    async def get(self, key: str) -> Result[Optional[Any], Dict[str, Any]]:
        """Get a value from the state cache."""
        entry = self._state_cache.get(key)
        if entry:
            return Result.ok(entry.get('value'))
        return Result.ok(None)

    async def set(
        self,
        key: str,
        value: Any,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Result[Dict[str, Any], Dict[str, Any]]:
        """Set a value by appending to the state log."""
        try:
            self._version_counter += 1
            entry = {
                'operation': 'set',
                'key': key,
                'value': value,
                'version': self._version_counter,
                'timestamp': time.time(),
                'metadata': metadata or {}
            }

            body = json.dumps(entry, default=str).encode('utf-8')
            record = Record(body=body, headers=[
                (b'key', key.encode()),
                (b'op', b'set'),
            ])

            await self._stream.append(AppendInput(records=[record]))
            self._state_cache[key] = entry

            # Notify listeners
            for listener in self._listeners:
                try:
                    listener(key, entry)
                except Exception as e:
                    logger.error(f"State listener error: {e}")

            return Result.ok(entry)

        except Exception as e:
            return Result.err({
                'errorType': 'S2_STATE_SET_ERROR',
                'message': f'Failed to set state via S2: {str(e)}'
            })

    async def delete(self, key: str) -> Result[bool, Dict[str, Any]]:
        """Delete a key by appending a delete marker to the log."""
        try:
            if key not in self._state_cache:
                return Result.ok(False)

            entry = {
                'operation': 'delete',
                'key': key,
                'timestamp': time.time()
            }

            body = json.dumps(entry).encode('utf-8')
            record = Record(body=body, headers=[
                (b'key', key.encode()),
                (b'op', b'delete'),
            ])

            await self._stream.append(AppendInput(records=[record]))
            self._state_cache.pop(key, None)

            return Result.ok(True)

        except Exception as e:
            return Result.err({
                'errorType': 'S2_STATE_DELETE_ERROR',
                'message': f'Failed to delete state via S2: {str(e)}'
            })

    async def list_keys(self, prefix: Optional[str] = None) -> Result[List[str], Dict[str, Any]]:
        """List all keys in the state cache."""
        keys = list(self._state_cache.keys())
        if prefix:
            keys = [k for k in keys if k.startswith(prefix)]
        return Result.ok(keys)

    def add_listener(self, listener: Callable) -> None:
        """Add a state change listener."""
        self._listeners.append(listener)

    def get_statistics(self) -> Dict[str, Any]:
        """Get state backend statistics."""
        return {
            'backend': 's2',
            'basin': self.config.basin_name,
            'keys_count': len(self._state_cache),
            'version_counter': self._version_counter,
            'listeners_count': len(self._listeners)
        }
