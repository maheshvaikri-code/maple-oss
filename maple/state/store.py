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


# maple/state/store.py
# Creator: Mahesh Vaikri

"""
State Storage for MAPLE
Provides distributed state management with different storage backends
"""

import time
import threading
from typing import Any, Dict, Optional, List, Union, Callable
from dataclasses import dataclass
from enum import Enum
import json
import logging

from ..core.result import Result

logger = logging.getLogger(__name__)

class StorageBackend(Enum):
    """Available storage backends."""
    MEMORY = "memory"
    FILE = "file"
    REDIS = "redis"
    DATABASE = "database"

class ConsistencyLevel(Enum):
    """Consistency levels for state operations."""
    EVENTUAL = "eventual"     # Eventually consistent
    STRONG = "strong"         # Strongly consistent
    CAUSAL = "causal"         # Causally consistent

@dataclass
class StateEntry:
    """Represents a state entry."""
    key: str
    value: Any
    version: int
    timestamp: float
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'key': self.key,
            'value': self.value,
            'version': self.version,
            'timestamp': self.timestamp,
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StateEntry':
        """Create from dictionary."""
        return cls(
            key=data['key'],
            value=data['value'],
            version=data['version'],
            timestamp=data['timestamp'],
            metadata=data.get('metadata', {})
        )

class StateStore:
    """
    Distributed state store for MAPLE agents.
    
    Features:
    - Multiple storage backends
    - Versioning and conflict resolution
    - Consistency guarantees
    - Change notifications
    - Atomic operations
    """
    
    def __init__(
        self,
        backend: StorageBackend = StorageBackend.MEMORY,
        consistency: ConsistencyLevel = ConsistencyLevel.EVENTUAL,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the state store.
        
        Args:
            backend: Storage backend to use
            consistency: Consistency level
            config: Backend-specific configuration
        """
        self.backend = backend
        self.consistency = consistency
        self.config = config or {}
        
        # In-memory storage for MEMORY backend
        self._memory_store: Dict[str, StateEntry] = {}
        self._memory_lock = threading.RLock()
        
        # Change listeners
        self._listeners: List[Callable[[str, StateEntry], None]] = []
        self._listener_lock = threading.RLock()
        
        # Version tracking
        self._version_counter = 0
        self._version_lock = threading.Lock()
        
        logger.info(f"StateStore initialized with {backend.value} backend, {consistency.value} consistency")
    
    def get(self, key: str) -> Result[Optional[Any], Dict[str, Any]]:
        """
        Get a value from the state store.
        
        Args:
            key: Key to retrieve
            
        Returns:
            Result containing the value or None if not found
        """
        try:
            if self.backend == StorageBackend.MEMORY:
                return self._memory_get(key)
            elif self.backend == StorageBackend.FILE:
                return self._file_get(key)
            elif self.backend == StorageBackend.REDIS:
                return self._redis_get(key)
            elif self.backend == StorageBackend.DATABASE:
                return self._database_get(key)
            else:
                return Result.err({
                    'errorType': 'UNSUPPORTED_BACKEND',
                    'message': f'Backend {self.backend.value} not supported'
                })
                
        except Exception as e:
            return Result.err({
                'errorType': 'STATE_GET_ERROR',
                'message': f'Failed to get state for key {key}: {str(e)}',
                'details': {'key': key}
            })
    
    def set(
        self,
        key: str,
        value: Any,
        metadata: Optional[Dict[str, Any]] = None,
        expected_version: Optional[int] = None
    ) -> Result[StateEntry, Dict[str, Any]]:
        """
        Set a value in the state store.
        
        Args:
            key: Key to set
            value: Value to store
            metadata: Optional metadata
            expected_version: Expected current version for optimistic locking
            
        Returns:
            Result containing the new StateEntry or error
        """
        try:
            with self._version_lock:
                self._version_counter += 1
                new_version = self._version_counter
            
            entry = StateEntry(
                key=key,
                value=value,
                version=new_version,
                timestamp=time.time(),
                metadata=metadata or {}
            )
            
            if self.backend == StorageBackend.MEMORY:
                result = self._memory_set(entry, expected_version)
            elif self.backend == StorageBackend.FILE:
                result = self._file_set(entry, expected_version)
            elif self.backend == StorageBackend.REDIS:
                result = self._redis_set(entry, expected_version)
            elif self.backend == StorageBackend.DATABASE:
                result = self._database_set(entry, expected_version)
            else:
                return Result.err({
                    'errorType': 'UNSUPPORTED_BACKEND',
                    'message': f'Backend {self.backend.value} not supported'
                })
            
            # Notify listeners if successful
            if result.is_ok():
                self._notify_listeners(key, entry)
            
            return result
            
        except Exception as e:
            return Result.err({
                'errorType': 'STATE_SET_ERROR',
                'message': f'Failed to set state for key {key}: {str(e)}',
                'details': {'key': key}
            })
    
    def delete(self, key: str, expected_version: Optional[int] = None) -> Result[bool, Dict[str, Any]]:
        """
        Delete a key from the state store.
        
        Args:
            key: Key to delete
            expected_version: Expected current version for optimistic locking
            
        Returns:
            Result indicating whether the key was deleted
        """
        try:
            if self.backend == StorageBackend.MEMORY:
                return self._memory_delete(key, expected_version)
            elif self.backend == StorageBackend.FILE:
                return self._file_delete(key, expected_version)
            elif self.backend == StorageBackend.REDIS:
                return self._redis_delete(key, expected_version)
            elif self.backend == StorageBackend.DATABASE:
                return self._database_delete(key, expected_version)
            else:
                return Result.err({
                    'errorType': 'UNSUPPORTED_BACKEND',
                    'message': f'Backend {self.backend.value} not supported'
                })
                
        except Exception as e:
            return Result.err({
                'errorType': 'STATE_DELETE_ERROR',
                'message': f'Failed to delete state for key {key}: {str(e)}',
                'details': {'key': key}
            })
    
    def list_keys(self, prefix: Optional[str] = None) -> Result[List[str], Dict[str, Any]]:
        """
        List all keys in the state store.
        
        Args:
            prefix: Optional prefix filter
            
        Returns:
            Result containing list of keys
        """
        try:
            if self.backend == StorageBackend.MEMORY:
                return self._memory_list_keys(prefix)
            else:
                return Result.err({
                    'errorType': 'NOT_IMPLEMENTED',
                    'message': f'list_keys not implemented for {self.backend.value} backend'
                })
                
        except Exception as e:
            return Result.err({
                'errorType': 'STATE_LIST_ERROR',
                'message': f'Failed to list keys: {str(e)}'
            })
    
    def add_listener(self, listener: Callable[[str, StateEntry], None]) -> None:
        """
        Add a change listener.
        
        Args:
            listener: Function to call when state changes
        """
        with self._listener_lock:
            self._listeners.append(listener)
    
    def remove_listener(self, listener: Callable[[str, StateEntry], None]) -> None:
        """
        Remove a change listener.
        
        Args:
            listener: Listener function to remove
        """
        with self._listener_lock:
            if listener in self._listeners:
                self._listeners.remove(listener)
    
    def _notify_listeners(self, key: str, entry: StateEntry) -> None:
        """Notify all listeners of a state change."""
        with self._listener_lock:
            listeners = self._listeners.copy()
        
        for listener in listeners:
            try:
                listener(key, entry)
            except Exception as e:
                logger.error(f"Error in state change listener: {e}")
    
    # Memory backend implementation
    def _memory_get(self, key: str) -> Result[Optional[Any], Dict[str, Any]]:
        """Get value from memory backend."""
        with self._memory_lock:
            entry = self._memory_store.get(key)
            return Result.ok(entry.value if entry else None)
    
    def _memory_set(self, entry: StateEntry, expected_version: Optional[int]) -> Result[StateEntry, Dict[str, Any]]:
        """Set value in memory backend."""
        with self._memory_lock:
            # Check expected version
            if expected_version is not None:
                existing = self._memory_store.get(entry.key)
                if existing and existing.version != expected_version:
                    return Result.err({
                        'errorType': 'VERSION_MISMATCH',
                        'message': f'Expected version {expected_version}, found {existing.version}',
                        'details': {
                            'key': entry.key,
                            'expected_version': expected_version,
                            'current_version': existing.version
                        }
                    })
            
            self._memory_store[entry.key] = entry
            return Result.ok(entry)
    
    def _memory_delete(self, key: str, expected_version: Optional[int]) -> Result[bool, Dict[str, Any]]:
        """Delete value from memory backend."""
        with self._memory_lock:
            entry = self._memory_store.get(key)
            if not entry:
                return Result.ok(False)
            
            # Check expected version
            if expected_version is not None and entry.version != expected_version:
                return Result.err({
                    'errorType': 'VERSION_MISMATCH',
                    'message': f'Expected version {expected_version}, found {entry.version}',
                    'details': {
                        'key': key,
                        'expected_version': expected_version,
                        'current_version': entry.version
                    }
                })
            
            del self._memory_store[key]
            return Result.ok(True)
    
    def _memory_list_keys(self, prefix: Optional[str]) -> Result[List[str], Dict[str, Any]]:
        """List keys from memory backend."""
        with self._memory_lock:
            keys = list(self._memory_store.keys())
            if prefix:
                keys = [k for k in keys if k.startswith(prefix)]
            return Result.ok(keys)
    
    # File backend implementation (simplified)
    def _file_get(self, key: str) -> Result[Optional[Any], Dict[str, Any]]:
        """Get value from file backend."""
        return Result.err({
            'errorType': 'NOT_IMPLEMENTED',
            'message': 'File backend not yet implemented'
        })
    
    def _file_set(self, entry: StateEntry, expected_version: Optional[int]) -> Result[StateEntry, Dict[str, Any]]:
        """Set value in file backend."""
        return Result.err({
            'errorType': 'NOT_IMPLEMENTED',
            'message': 'File backend not yet implemented'
        })
    
    def _file_delete(self, key: str, expected_version: Optional[int]) -> Result[bool, Dict[str, Any]]:
        """Delete value from file backend."""
        return Result.err({
            'errorType': 'NOT_IMPLEMENTED',
            'message': 'File backend not yet implemented'
        })
    
    # Redis backend implementation (placeholder)
    def _redis_get(self, key: str) -> Result[Optional[Any], Dict[str, Any]]:
        """Get value from Redis backend."""
        return Result.err({
            'errorType': 'NOT_IMPLEMENTED',
            'message': 'Redis backend not yet implemented'
        })
    
    def _redis_set(self, entry: StateEntry, expected_version: Optional[int]) -> Result[StateEntry, Dict[str, Any]]:
        """Set value in Redis backend."""
        return Result.err({
            'errorType': 'NOT_IMPLEMENTED',
            'message': 'Redis backend not yet implemented'
        })
    
    def _redis_delete(self, key: str, expected_version: Optional[int]) -> Result[bool, Dict[str, Any]]:
        """Delete value from Redis backend."""
        return Result.err({
            'errorType': 'NOT_IMPLEMENTED',
            'message': 'Redis backend not yet implemented'
        })
    
    # Database backend implementation (placeholder)
    def _database_get(self, key: str) -> Result[Optional[Any], Dict[str, Any]]:
        """Get value from database backend."""
        return Result.err({
            'errorType': 'NOT_IMPLEMENTED',
            'message': 'Database backend not yet implemented'
        })
    
    def _database_set(self, entry: StateEntry, expected_version: Optional[int]) -> Result[StateEntry, Dict[str, Any]]:
        """Set value in database backend."""
        return Result.err({
            'errorType': 'NOT_IMPLEMENTED',
            'message': 'Database backend not yet implemented'
        })
    
    def _database_delete(self, key: str, expected_version: Optional[int]) -> Result[bool, Dict[str, Any]]:
        """Delete value from database backend."""
        return Result.err({
            'errorType': 'NOT_IMPLEMENTED',
            'message': 'Database backend not yet implemented'
        })
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get state store statistics."""
        stats = {
            'backend': self.backend.value,
            'consistency': self.consistency.value,
            'listeners_count': len(self._listeners)
        }
        
        if self.backend == StorageBackend.MEMORY:
            with self._memory_lock:
                stats.update({
                    'keys_count': len(self._memory_store),
                    'total_size_bytes': sum(
                        len(str(entry.value)) for entry in self._memory_store.values()
                    )
                })
        
        return stats
