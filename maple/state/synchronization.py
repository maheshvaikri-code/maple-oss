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


# maple/state/synchronization.py
# Creator: Mahesh Vaikri

"""
State Synchronization for MAPLE
Provides distributed state synchronization between agents
"""

import time
import threading
from typing import Dict, Any, List, Optional, Callable, Set
from dataclasses import dataclass
from enum import Enum
import logging

from ..core.result import Result
from ..core.message import Message
from .store import StateStore, StateEntry

logger = logging.getLogger(__name__)

class SyncMode(Enum):
    """Synchronization modes."""
    PUSH = "push"       # Push changes to others
    PULL = "pull"       # Pull changes from others
    BIDIRECTIONAL = "bidirectional"  # Both push and pull

@dataclass
class SyncEvent:
    """Represents a synchronization event."""
    key: str
    operation: str  # "set", "delete"
    value: Any
    version: int
    timestamp: float
    source_agent: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'key': self.key,
            'operation': self.operation,
            'value': self.value,
            'version': self.version,
            'timestamp': self.timestamp,
            'source_agent': self.source_agent
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SyncEvent':
        """Create from dictionary."""
        return cls(
            key=data['key'],
            operation=data['operation'],
            value=data['value'],
            version=data['version'],
            timestamp=data['timestamp'],
            source_agent=data['source_agent']
        )

class StateSynchronizer:
    """
    Handles distributed state synchronization between MAPLE agents.
    
    Features:
    - Push/pull synchronization modes
    - Conflict resolution strategies
    - Change propagation
    - Version vector tracking
    - Synchronization events
    """
    
    def __init__(
        self,
        agent,
        state_store: StateStore,
        sync_mode: SyncMode = SyncMode.BIDIRECTIONAL,
        sync_interval: float = 5.0
    ):
        """
        Initialize the state synchronizer.
        
        Args:
            agent: The agent instance
            state_store: State store to synchronize
            sync_mode: Synchronization mode
            sync_interval: Interval between sync operations in seconds
        """
        self.agent = agent
        self.state_store = state_store
        self.sync_mode = sync_mode
        self.sync_interval = sync_interval
        
        # Track peer agents
        self.peer_agents: Set[str] = set()
        self.peer_lock = threading.RLock()
        
        # Sync state
        self.sync_enabled = False
        self.sync_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        
        # Version vectors for conflict resolution
        self.version_vectors: Dict[str, Dict[str, int]] = {}  # agent_id -> {key -> version}
        self.vv_lock = threading.RLock()
        
        # Statistics
        self.sync_stats = {
            'sync_operations': 0,
            'conflicts_resolved': 0,
            'changes_sent': 0,
            'changes_received': 0
        }
        
        # Set up message handlers
        self._setup_handlers()
        
        # Listen for state changes
        self.state_store.add_listener(self._on_state_change)
        
        logger.info(f"StateSynchronizer initialized with {sync_mode.value} mode")
    
    def add_peer(self, agent_id: str) -> None:
        """
        Add a peer agent for synchronization.
        
        Args:
            agent_id: ID of the peer agent
        """
        with self.peer_lock:
            self.peer_agents.add(agent_id)
        
        logger.info(f"Added peer agent: {agent_id}")
    
    def remove_peer(self, agent_id: str) -> None:
        """
        Remove a peer agent.
        
        Args:
            agent_id: ID of the peer agent to remove
        """
        with self.peer_lock:
            self.peer_agents.discard(agent_id)
        
        logger.info(f"Removed peer agent: {agent_id}")
    
    def start_sync(self) -> None:
        """Start the synchronization process."""
        if self.sync_enabled:
            return
        
        self.sync_enabled = True
        self.stop_event.clear()
        
        self.sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
        self.sync_thread.start()
        
        logger.info("State synchronization started")
    
    def stop_sync(self) -> None:
        """Stop the synchronization process."""
        if not self.sync_enabled:
            return
        
        self.sync_enabled = False
        self.stop_event.set()
        
        if self.sync_thread:
            self.sync_thread.join(timeout=5.0)
        
        logger.info("State synchronization stopped")
    
    def force_sync(self) -> Result[None, Dict[str, Any]]:
        """
        Force an immediate synchronization with all peers.
        
        Returns:
            Result indicating success or failure
        """
        try:
            if self.sync_mode in [SyncMode.PUSH, SyncMode.BIDIRECTIONAL]:
                self._push_changes()
            
            if self.sync_mode in [SyncMode.PULL, SyncMode.BIDIRECTIONAL]:
                self._request_changes()
            
            self.sync_stats['sync_operations'] += 1
            return Result.ok(None)
            
        except Exception as e:
            return Result.err({
                'errorType': 'SYNC_ERROR',
                'message': f'Force sync failed: {str(e)}'
            })
    
    def _setup_handlers(self) -> None:
        """Set up message handlers for synchronization."""
        @self.agent.handler("STATE_SYNC_EVENT")
        def handle_sync_event(message: Message) -> Optional[Message]:
            """Handle incoming synchronization events."""
            try:
                event_data = message.payload
                sync_event = SyncEvent.from_dict(event_data)
                
                self._apply_sync_event(sync_event)
                self.sync_stats['changes_received'] += 1
                
                return None  # No response needed
                
            except Exception as e:
                logger.error(f"Error handling sync event: {e}")
                return Message.error(
                    error_type="SYNC_EVENT_ERROR",
                    message=f"Failed to process sync event: {str(e)}"
                )
        
        @self.agent.handler("STATE_SYNC_REQUEST")
        def handle_sync_request(message: Message) -> Optional[Message]:
            """Handle requests for state synchronization."""
            try:
                # Send our current state to the requester
                keys = message.payload.get('keys', [])
                if not keys:
                    # Send all keys if none specified
                    keys_result = self.state_store.list_keys()
                    if keys_result.is_ok():
                        keys = keys_result.unwrap()
                
                changes = []
                for key in keys:
                    value_result = self.state_store.get(key)
                    if value_result.is_ok() and value_result.unwrap() is not None:
                        # Get the full state entry for version info
                        if hasattr(self.state_store, '_memory_store'):
                            entry = self.state_store._memory_store.get(key)
                            if entry:
                                sync_event = SyncEvent(
                                    key=key,
                                    operation="set",
                                    value=entry.value,
                                    version=entry.version,
                                    timestamp=entry.timestamp,
                                    source_agent=self.agent.agent_id
                                )
                                changes.append(sync_event.to_dict())
                
                return Message(
                    message_type="STATE_SYNC_RESPONSE",
                    payload={'changes': changes}
                )
                
            except Exception as e:
                logger.error(f"Error handling sync request: {e}")
                return Message.error(
                    error_type="SYNC_REQUEST_ERROR",
                    message=f"Failed to process sync request: {str(e)}"
                )
    
    def _sync_loop(self) -> None:
        """Main synchronization loop."""
        logger.info("State synchronization loop started")
        
        while self.sync_enabled and not self.stop_event.is_set():
            try:
                # Perform synchronization
                if self.sync_mode in [SyncMode.PUSH, SyncMode.BIDIRECTIONAL]:
                    self._push_changes()
                
                if self.sync_mode in [SyncMode.PULL, SyncMode.BIDIRECTIONAL]:
                    self._request_changes()
                
                self.sync_stats['sync_operations'] += 1
                
                # Wait for next sync interval
                if self.stop_event.wait(self.sync_interval):
                    break
                    
            except Exception as e:
                logger.error(f"Error in sync loop: {e}")
                time.sleep(1.0)  # Brief pause on error
    
    def _push_changes(self) -> None:
        """Push local changes to peer agents."""
        with self.peer_lock:
            peers = self.peer_agents.copy()
        
        if not peers:
            return
        
        # Get all local state keys
        keys_result = self.state_store.list_keys()
        if keys_result.is_err():
            return
        
        keys = keys_result.unwrap()
        
        # Create sync events for each key
        changes = []
        for key in keys:
            if hasattr(self.state_store, '_memory_store'):
                entry = self.state_store._memory_store.get(key)
                if entry:
                    sync_event = SyncEvent(
                        key=key,
                        operation="set",
                        value=entry.value,
                        version=entry.version,
                        timestamp=entry.timestamp,
                        source_agent=self.agent.agent_id
                    )
                    changes.append(sync_event.to_dict())
        
        # Send changes to peers
        for peer_id in peers:
            try:
                sync_message = Message(
                    message_type="STATE_SYNC_EVENT",
                    receiver=peer_id,
                    payload=changes[0] if changes else {}  # Send one change at a time for simplicity
                )
                
                self.agent.send(sync_message)
                self.sync_stats['changes_sent'] += len(changes)
                
            except Exception as e:
                logger.error(f"Error pushing changes to {peer_id}: {e}")
    
    def _request_changes(self) -> None:
        """Request changes from peer agents."""
        with self.peer_lock:
            peers = self.peer_agents.copy()
        
        for peer_id in peers:
            try:
                request_message = Message(
                    message_type="STATE_SYNC_REQUEST",
                    receiver=peer_id,
                    payload={'keys': []}  # Request all keys
                )
                
                # Send request (fire and forget for now)
                self.agent.send(request_message)
                
            except Exception as e:
                logger.error(f"Error requesting changes from {peer_id}: {e}")
    
    def _apply_sync_event(self, event: SyncEvent) -> None:
        """
        Apply a synchronization event to the local state.
        
        Args:
            event: The synchronization event to apply
        """
        try:
            if event.operation == "set":
                # Check for conflicts using version vectors
                conflict_resolved = self._resolve_conflict(event)
                
                if conflict_resolved:
                    # Apply the change
                    result = self.state_store.set(
                        key=event.key,
                        value=event.value,
                        metadata={
                            'sync_source': event.source_agent,
                            'sync_timestamp': event.timestamp
                        }
                    )
                    
                    if result.is_err():
                        logger.error(f"Failed to apply sync event: {result.unwrap_err()}")
                
            elif event.operation == "delete":
                result = self.state_store.delete(event.key)
                if result.is_err():
                    logger.error(f"Failed to delete key {event.key}: {result.unwrap_err()}")
            
            # Update version vector
            self._update_version_vector(event.source_agent, event.key, event.version)
            
        except Exception as e:
            logger.error(f"Error applying sync event: {e}")
    
    def _resolve_conflict(self, event: SyncEvent) -> bool:
        """
        Resolve conflicts using version vectors and timestamps.
        
        Args:
            event: The sync event to check for conflicts
            
        Returns:
            True if the event should be applied, False otherwise
        """
        with self.vv_lock:
            # Get current version for this key from this agent
            current_version = self.version_vectors.get(
                event.source_agent, {}
            ).get(event.key, 0)
            
            # Simple conflict resolution: accept if newer version or newer timestamp
            if event.version > current_version:
                return True
            elif event.version == current_version:
                # Use timestamp as tiebreaker
                current_value = self.state_store.get(event.key)
                if current_value.is_ok() and hasattr(self.state_store, '_memory_store'):
                    local_entry = self.state_store._memory_store.get(event.key)
                    if local_entry and event.timestamp > local_entry.timestamp:
                        self.sync_stats['conflicts_resolved'] += 1
                        return True
            
            return False
    
    def _update_version_vector(self, agent_id: str, key: str, version: int) -> None:
        """Update the version vector for conflict resolution."""
        with self.vv_lock:
            if agent_id not in self.version_vectors:
                self.version_vectors[agent_id] = {}
            
            self.version_vectors[agent_id][key] = max(
                self.version_vectors[agent_id].get(key, 0),
                version
            )
    
    def _on_state_change(self, key: str, entry: StateEntry) -> None:
        """
        Handle local state changes.
        
        Args:
            key: The key that changed
            entry: The new state entry
        """
        # Update our own version vector
        self._update_version_vector(self.agent.agent_id, key, entry.version)
        
        # If we're in push mode and sync is enabled, propagate immediately
        if (self.sync_enabled and 
            self.sync_mode in [SyncMode.PUSH, SyncMode.BIDIRECTIONAL]):
            
            try:
                sync_event = SyncEvent(
                    key=key,
                    operation="set",
                    value=entry.value,
                    version=entry.version,
                    timestamp=entry.timestamp,
                    source_agent=self.agent.agent_id
                )
                
                with self.peer_lock:
                    peers = self.peer_agents.copy()
                
                for peer_id in peers:
                    sync_message = Message(
                        message_type="STATE_SYNC_EVENT",
                        receiver=peer_id,
                        payload=sync_event.to_dict()
                    )
                    
                    self.agent.send(sync_message)
                
                self.sync_stats['changes_sent'] += len(peers)
                
            except Exception as e:
                logger.error(f"Error propagating state change: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get synchronization statistics."""
        with self.peer_lock:
            peer_count = len(self.peer_agents)
        
        with self.vv_lock:
            vv_size = sum(len(versions) for versions in self.version_vectors.values())
        
        return {
            'sync_mode': self.sync_mode.value,
            'sync_enabled': self.sync_enabled,
            'peer_count': peer_count,
            'version_vector_size': vv_size,
            'statistics': self.sync_stats.copy()
        }
