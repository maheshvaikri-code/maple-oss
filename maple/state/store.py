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

import os
import re
import time
import threading
import sqlite3
import tempfile
from typing import Any, Dict, Optional, List, Callable
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
    - Multiple storage backends (memory, file, SQLite database)
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

        # File backend state
        self._file_dir: Optional[str] = None
        if backend == StorageBackend.FILE:
            self._file_dir = self.config.get('directory', os.path.join(tempfile.gettempdir(), 'maple_state'))
            os.makedirs(self._file_dir, exist_ok=True)

        # Database backend state
        self._db_path: Optional[str] = None
        self._db_lock = threading.RLock()
        if backend == StorageBackend.DATABASE:
            self._db_path = self.config.get('database_path', os.path.join(tempfile.gettempdir(), 'maple_state.db'))
            self._init_database()

        logger.info(f"StateStore initialized with {backend.value} backend, {consistency.value} consistency")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, key: str) -> Result[Optional[Any], Dict[str, Any]]:
        """Get a value from the state store."""
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
        """Set a value in the state store."""
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
        """Delete a key from the state store."""
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
        """List all keys in the state store."""
        try:
            if self.backend == StorageBackend.MEMORY:
                return self._memory_list_keys(prefix)
            elif self.backend == StorageBackend.FILE:
                return self._file_list_keys(prefix)
            elif self.backend == StorageBackend.DATABASE:
                return self._database_list_keys(prefix)
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
        """Add a change listener."""
        with self._listener_lock:
            self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[str, StateEntry], None]) -> None:
        """Remove a change listener."""
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
        elif self.backend == StorageBackend.FILE:
            if self._file_dir and os.path.isdir(self._file_dir):
                files = [f for f in os.listdir(self._file_dir) if f.endswith('.json')]
                stats['keys_count'] = len(files)
        elif self.backend == StorageBackend.DATABASE:
            with self._db_lock:
                try:
                    conn = sqlite3.connect(self._db_path)
                    cursor = conn.execute("SELECT COUNT(*) FROM state_entries")
                    stats['keys_count'] = cursor.fetchone()[0]
                    conn.close()
                except Exception:
                    stats['keys_count'] = 0

        return stats

    # ------------------------------------------------------------------
    # Memory backend
    # ------------------------------------------------------------------

    def _memory_get(self, key: str) -> Result[Optional[Any], Dict[str, Any]]:
        with self._memory_lock:
            entry = self._memory_store.get(key)
            return Result.ok(entry.value if entry else None)

    def _memory_set(self, entry: StateEntry, expected_version: Optional[int]) -> Result[StateEntry, Dict[str, Any]]:
        with self._memory_lock:
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
        with self._memory_lock:
            entry = self._memory_store.get(key)
            if not entry:
                return Result.ok(False)
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
        with self._memory_lock:
            keys = list(self._memory_store.keys())
            if prefix:
                keys = [k for k in keys if k.startswith(prefix)]
            return Result.ok(keys)

    # ------------------------------------------------------------------
    # File backend
    # ------------------------------------------------------------------

    @staticmethod
    def _sanitize_filename(key: str) -> str:
        """Convert a key to a safe filename."""
        return re.sub(r'[^a-zA-Z0-9_\-]', '_', key) + '.json'

    def _file_path_for(self, key: str) -> str:
        return os.path.join(self._file_dir, self._sanitize_filename(key))

    def _file_get(self, key: str) -> Result[Optional[Any], Dict[str, Any]]:
        path = self._file_path_for(key)
        if not os.path.exists(path):
            return Result.ok(None)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            entry = StateEntry.from_dict(data)
            return Result.ok(entry.value)
        except Exception as e:
            return Result.err({
                'errorType': 'FILE_READ_ERROR',
                'message': f'Failed to read state file for key {key}: {str(e)}'
            })

    def _file_set(self, entry: StateEntry, expected_version: Optional[int]) -> Result[StateEntry, Dict[str, Any]]:
        path = self._file_path_for(entry.key)

        # Check expected version
        if expected_version is not None and os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
                if existing['version'] != expected_version:
                    return Result.err({
                        'errorType': 'VERSION_MISMATCH',
                        'message': f"Expected version {expected_version}, found {existing['version']}",
                        'details': {
                            'key': entry.key,
                            'expected_version': expected_version,
                            'current_version': existing['version']
                        }
                    })
            except Exception:
                pass  # file unreadable, proceed with write

        # Atomic write via temp file + rename
        tmp_fd, tmp_path = tempfile.mkstemp(dir=self._file_dir, suffix='.tmp')
        try:
            with os.fdopen(tmp_fd, 'w', encoding='utf-8') as f:
                json.dump(entry.to_dict(), f, default=str)
            # On Windows os.rename fails if destination exists, so remove first
            if os.path.exists(path):
                os.remove(path)
            os.rename(tmp_path, path)
            return Result.ok(entry)
        except Exception as e:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            return Result.err({
                'errorType': 'FILE_WRITE_ERROR',
                'message': f'Failed to write state file for key {entry.key}: {str(e)}'
            })

    def _file_delete(self, key: str, expected_version: Optional[int]) -> Result[bool, Dict[str, Any]]:
        path = self._file_path_for(key)
        if not os.path.exists(path):
            return Result.ok(False)

        if expected_version is not None:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
                if existing['version'] != expected_version:
                    return Result.err({
                        'errorType': 'VERSION_MISMATCH',
                        'message': f"Expected version {expected_version}, found {existing['version']}",
                        'details': {
                            'key': key,
                            'expected_version': expected_version,
                            'current_version': existing['version']
                        }
                    })
            except Exception:
                pass

        try:
            os.remove(path)
            return Result.ok(True)
        except Exception as e:
            return Result.err({
                'errorType': 'FILE_DELETE_ERROR',
                'message': f'Failed to delete state file for key {key}: {str(e)}'
            })

    def _file_list_keys(self, prefix: Optional[str]) -> Result[List[str], Dict[str, Any]]:
        if not self._file_dir or not os.path.isdir(self._file_dir):
            return Result.ok([])

        keys = []
        for filename in os.listdir(self._file_dir):
            if not filename.endswith('.json'):
                continue
            try:
                with open(os.path.join(self._file_dir, filename), 'r', encoding='utf-8') as f:
                    data = json.load(f)
                keys.append(data['key'])
            except Exception:
                continue

        if prefix:
            keys = [k for k in keys if k.startswith(prefix)]
        return Result.ok(keys)

    # ------------------------------------------------------------------
    # Redis backend (placeholder - requires external dependency)
    # ------------------------------------------------------------------

    def _redis_get(self, key: str) -> Result[Optional[Any], Dict[str, Any]]:
        return Result.err({
            'errorType': 'NOT_IMPLEMENTED',
            'message': 'Redis backend requires the redis library. Install with: pip install redis'
        })

    def _redis_set(self, entry: StateEntry, expected_version: Optional[int]) -> Result[StateEntry, Dict[str, Any]]:
        return Result.err({
            'errorType': 'NOT_IMPLEMENTED',
            'message': 'Redis backend requires the redis library. Install with: pip install redis'
        })

    def _redis_delete(self, key: str, expected_version: Optional[int]) -> Result[bool, Dict[str, Any]]:
        return Result.err({
            'errorType': 'NOT_IMPLEMENTED',
            'message': 'Redis backend requires the redis library. Install with: pip install redis'
        })

    # ------------------------------------------------------------------
    # SQLite database backend
    # ------------------------------------------------------------------

    def _init_database(self) -> None:
        """Create the state_entries table if it doesn't exist."""
        with self._db_lock:
            conn = sqlite3.connect(self._db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS state_entries (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    updated_at REAL NOT NULL
                )
            """)
            conn.commit()
            conn.close()

    def _database_get(self, key: str) -> Result[Optional[Any], Dict[str, Any]]:
        with self._db_lock:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.execute(
                    "SELECT value, version, metadata, updated_at FROM state_entries WHERE key = ?",
                    (key,)
                )
                row = cursor.fetchone()
                conn.close()
                if row is None:
                    return Result.ok(None)
                value = json.loads(row[0])
                return Result.ok(value)
            except Exception as e:
                return Result.err({
                    'errorType': 'DATABASE_READ_ERROR',
                    'message': f'Failed to read key {key} from database: {str(e)}'
                })

    def _database_set(self, entry: StateEntry, expected_version: Optional[int]) -> Result[StateEntry, Dict[str, Any]]:
        with self._db_lock:
            try:
                conn = sqlite3.connect(self._db_path)

                if expected_version is not None:
                    cursor = conn.execute(
                        "SELECT version FROM state_entries WHERE key = ?",
                        (entry.key,)
                    )
                    row = cursor.fetchone()
                    if row and row[0] != expected_version:
                        conn.close()
                        return Result.err({
                            'errorType': 'VERSION_MISMATCH',
                            'message': f'Expected version {expected_version}, found {row[0]}',
                            'details': {
                                'key': entry.key,
                                'expected_version': expected_version,
                                'current_version': row[0]
                            }
                        })

                value_json = json.dumps(entry.value, default=str)
                metadata_json = json.dumps(entry.metadata, default=str)

                conn.execute(
                    """INSERT OR REPLACE INTO state_entries (key, value, version, metadata, updated_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (entry.key, value_json, entry.version, metadata_json, entry.timestamp)
                )
                conn.commit()
                conn.close()
                return Result.ok(entry)
            except Exception as e:
                return Result.err({
                    'errorType': 'DATABASE_WRITE_ERROR',
                    'message': f'Failed to write key {entry.key} to database: {str(e)}'
                })

    def _database_delete(self, key: str, expected_version: Optional[int]) -> Result[bool, Dict[str, Any]]:
        with self._db_lock:
            try:
                conn = sqlite3.connect(self._db_path)

                if expected_version is not None:
                    cursor = conn.execute(
                        "SELECT version FROM state_entries WHERE key = ?",
                        (key,)
                    )
                    row = cursor.fetchone()
                    if row is None:
                        conn.close()
                        return Result.ok(False)
                    if row[0] != expected_version:
                        conn.close()
                        return Result.err({
                            'errorType': 'VERSION_MISMATCH',
                            'message': f'Expected version {expected_version}, found {row[0]}',
                            'details': {
                                'key': key,
                                'expected_version': expected_version,
                                'current_version': row[0]
                            }
                        })

                cursor = conn.execute("DELETE FROM state_entries WHERE key = ?", (key,))
                deleted = cursor.rowcount > 0
                conn.commit()
                conn.close()
                return Result.ok(deleted)
            except Exception as e:
                return Result.err({
                    'errorType': 'DATABASE_DELETE_ERROR',
                    'message': f'Failed to delete key {key} from database: {str(e)}'
                })

    def _database_list_keys(self, prefix: Optional[str]) -> Result[List[str], Dict[str, Any]]:
        with self._db_lock:
            try:
                conn = sqlite3.connect(self._db_path)
                if prefix:
                    cursor = conn.execute(
                        "SELECT key FROM state_entries WHERE key LIKE ?",
                        (prefix + '%',)
                    )
                else:
                    cursor = conn.execute("SELECT key FROM state_entries")
                keys = [row[0] for row in cursor.fetchall()]
                conn.close()
                return Result.ok(keys)
            except Exception as e:
                return Result.err({
                    'errorType': 'DATABASE_LIST_ERROR',
                    'message': f'Failed to list keys from database: {str(e)}'
                })
