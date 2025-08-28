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


# maple/state/consistency.py
# Creator: Mahesh Vaikri

"""
Consistency Management for MAPLE
Provides different consistency models for distributed state
"""

import time
import threading
from typing import Dict, Any, List, Optional, Callable, Set, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

from ..core.result import Result
from .store import StateStore, StateEntry

logger = logging.getLogger(__name__)

class ConsistencyModel(Enum):
    """Available consistency models."""
    STRONG = "strong"           # All nodes see the same data at the same time
    EVENTUAL = "eventual"       # Eventually all nodes will converge
    CAUSAL = "causal"          # Causally related operations are seen in order
    MONOTONIC_READ = "monotonic_read"    # Never read older values
    MONOTONIC_WRITE = "monotonic_write"  # Writes are ordered
    READ_YOUR_WRITES = "read_your_writes"  # Read your own writes immediately

@dataclass
class ConsistencyConstraint:
    """Represents a consistency constraint."""
    model: ConsistencyModel
    tolerance_ms: int  # Tolerance for eventual consistency
    quorum_size: Optional[int] = None  # For strong consistency
    max_staleness_ms: Optional[int] = None  # Maximum allowed staleness

class ConsistencyManager:
    """
    Manages consistency models for distributed state in MAPLE.
    
    Features:
    - Multiple consistency models
    - Quorum-based operations
    - Causality tracking
    - Consistency violation detection
    - Automatic repair mechanisms
    """
    
    def __init__(
        self,
        agent,
        state_store: StateStore,
        default_model: ConsistencyModel = ConsistencyModel.EVENTUAL
    ):
        """
        Initialize the consistency manager.
        
        Args:
            agent: The agent instance
            state_store: State store to manage consistency for
            default_model: Default consistency model
        """
        self.agent = agent
        self.state_store = state_store
        self.default_model = default_model
        
        # Track consistency constraints per key
        self.key_constraints: Dict[str, ConsistencyConstraint] = {}
        self.constraints_lock = threading.RLock()
        
        # Causality tracking
        self.vector_clock: Dict[str, int] = {}  # agent_id -> clock
        self.causal_history: Dict[str, List[Tuple[str, int]]] = {}  # key -> [(agent, clock)]
        self.causality_lock = threading.RLock()
        
        # Read/write tracking for monotonic guarantees
        self.read_timestamps: Dict[str, float] = {}  # key -> last_read_time
        self.write_timestamps: Dict[str, float] = {}  # key -> last_write_time
        self.timestamps_lock = threading.RLock()
        
        # Statistics
        self.consistency_stats = {
            'strong_operations': 0,
            'eventual_operations': 0,
            'causal_operations': 0,
            'violations_detected': 0,
            'repairs_performed': 0
        }
        
        logger.info(f"ConsistencyManager initialized with {default_model.value} model")
    
    def set_constraint(self, key: str, constraint: ConsistencyConstraint) -> None:
        """
        Set a consistency constraint for a specific key.
        
        Args:
            key: The state key
            constraint: Consistency constraint to apply
        """
        with self.constraints_lock:
            self.key_constraints[key] = constraint
        
        logger.info(f"Set {constraint.model.value} consistency for key {key}")
    
    def get_constraint(self, key: str) -> ConsistencyConstraint:
        """
        Get the consistency constraint for a key.
        
        Args:
            key: The state key
            
        Returns:
            Consistency constraint (default if none set)
        """
        with self.constraints_lock:
            return self.key_constraints.get(key, ConsistencyConstraint(
                model=self.default_model,
                tolerance_ms=1000
            ))
    
    def consistent_read(self, key: str) -> Result[Any, Dict[str, Any]]:
        """
        Perform a consistency-aware read operation.
        
        Args:
            key: Key to read
            
        Returns:
            Result containing the value with consistency guarantees
        """
        constraint = self.get_constraint(key)
        
        try:
            if constraint.model == ConsistencyModel.STRONG:
                return self._strong_read(key, constraint)
            elif constraint.model == ConsistencyModel.EVENTUAL:
                return self._eventual_read(key, constraint)
            elif constraint.model == ConsistencyModel.CAUSAL:
                return self._causal_read(key, constraint)
            elif constraint.model == ConsistencyModel.MONOTONIC_READ:
                return self._monotonic_read(key, constraint)
            elif constraint.model == ConsistencyModel.READ_YOUR_WRITES:
                return self._read_your_writes(key, constraint)
            else:
                return self._basic_read(key)
                
        except Exception as e:
            return Result.err({
                'errorType': 'CONSISTENCY_READ_ERROR',
                'message': f'Consistent read failed for key {key}: {str(e)}',
                'details': {'key': key, 'model': constraint.model.value}
            })
    
    def consistent_write(
        self,
        key: str,
        value: Any,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Result[StateEntry, Dict[str, Any]]:
        """
        Perform a consistency-aware write operation.
        
        Args:
            key: Key to write
            value: Value to write
            metadata: Optional metadata
            
        Returns:
            Result containing the state entry with consistency guarantees
        """
        constraint = self.get_constraint(key)
        
        try:
            if constraint.model == ConsistencyModel.STRONG:
                return self._strong_write(key, value, constraint, metadata)
            elif constraint.model == ConsistencyModel.EVENTUAL:
                return self._eventual_write(key, value, constraint, metadata)
            elif constraint.model == ConsistencyModel.CAUSAL:
                return self._causal_write(key, value, constraint, metadata)
            elif constraint.model == ConsistencyModel.MONOTONIC_WRITE:
                return self._monotonic_write(key, value, constraint, metadata)
            else:
                return self._basic_write(key, value, metadata)
                
        except Exception as e:
            return Result.err({
                'errorType': 'CONSISTENCY_WRITE_ERROR',
                'message': f'Consistent write failed for key {key}: {str(e)}',
                'details': {'key': key, 'model': constraint.model.value}
            })
    
    def _strong_read(self, key: str, constraint: ConsistencyConstraint) -> Result[Any, Dict[str, Any]]:
        """Perform a strongly consistent read."""
        # For strong consistency, we need to check with a quorum of nodes
        # This is a simplified implementation
        
        self.consistency_stats['strong_operations'] += 1
        
        # In a real implementation, this would:
        # 1. Contact a quorum of replicas
        # 2. Get the latest version from majority
        # 3. Return the value only if quorum agrees
        
        # For now, just do a local read with timestamp check
        result = self.state_store.get(key)
        if result.is_ok():
            # Update read timestamp
            with self.timestamps_lock:
                self.read_timestamps[key] = time.time()
        
        return result
    
    def _eventual_read(self, key: str, constraint: ConsistencyConstraint) -> Result[Any, Dict[str, Any]]:
        """Perform an eventually consistent read."""
        self.consistency_stats['eventual_operations'] += 1
        
        # For eventual consistency, we can read from local replica
        # but should check staleness
        result = self.state_store.get(key)
        
        if result.is_ok() and constraint.max_staleness_ms:
            # Check if data is too stale
            if hasattr(self.state_store, '_memory_store'):
                entry = self.state_store._memory_store.get(key)
                if entry:
                    age_ms = (time.time() - entry.timestamp) * 1000
                    if age_ms > constraint.max_staleness_ms:
                        return Result.err({
                            'errorType': 'DATA_TOO_STALE',
                            'message': f'Data is {age_ms}ms old, exceeds limit of {constraint.max_staleness_ms}ms',
                            'details': {'age_ms': age_ms, 'limit_ms': constraint.max_staleness_ms}
                        })
        
        if result.is_ok():
            with self.timestamps_lock:
                self.read_timestamps[key] = time.time()
        
        return result
    
    def _causal_read(self, key: str, constraint: ConsistencyConstraint) -> Result[Any, Dict[str, Any]]:
        """Perform a causally consistent read."""
        self.consistency_stats['causal_operations'] += 1
        
        # Check causal dependencies
        with self.causality_lock:
            if key in self.causal_history:
                # Verify we have seen all causally preceding writes
                for dep_agent, dep_clock in self.causal_history[key]:
                    our_clock = self.vector_clock.get(dep_agent, 0)
                    if our_clock < dep_clock:
                        return Result.err({
                            'errorType': 'CAUSAL_DEPENDENCY_VIOLATION',
                            'message': f'Missing causal dependency from {dep_agent}:{dep_clock}',
                            'details': {
                                'required_clock': dep_clock,
                                'our_clock': our_clock,
                                'agent': dep_agent
                            }
                        })
        
        result = self.state_store.get(key)
        if result.is_ok():
            with self.timestamps_lock:
                self.read_timestamps[key] = time.time()
        
        return result
    
    def _monotonic_read(self, key: str, constraint: ConsistencyConstraint) -> Result[Any, Dict[str, Any]]:
        """Perform a monotonic read (never read older values)."""
        # Check that we don't read a value older than previously read
        with self.timestamps_lock:
            last_read = self.read_timestamps.get(key, 0)
        
        result = self.state_store.get(key)
        
        if result.is_ok() and hasattr(self.state_store, '_memory_store'):
            entry = self.state_store._memory_store.get(key)
            if entry and entry.timestamp < last_read:
                self.consistency_stats['violations_detected'] += 1
                return Result.err({
                    'errorType': 'MONOTONIC_READ_VIOLATION',
                    'message': f'Value timestamp {entry.timestamp} is older than last read {last_read}',
                    'details': {
                        'value_timestamp': entry.timestamp,
                        'last_read_timestamp': last_read
                    }
                })
        
        if result.is_ok():
            with self.timestamps_lock:
                self.read_timestamps[key] = time.time()
        
        return result
    
    def _read_your_writes(self, key: str, constraint: ConsistencyConstraint) -> Result[Any, Dict[str, Any]]:
        """Ensure you can read your own writes."""
        # Check if we've written to this key recently
        with self.timestamps_lock:
            last_write = self.write_timestamps.get(key, 0)
        
        result = self.state_store.get(key)
        
        if result.is_ok() and last_write > 0:
            # Verify the read reflects our write
            if hasattr(self.state_store, '_memory_store'):
                entry = self.state_store._memory_store.get(key)
                if entry and entry.timestamp < last_write:
                    self.consistency_stats['violations_detected'] += 1
                    return Result.err({
                        'errorType': 'READ_YOUR_WRITES_VIOLATION',
                        'message': f'Read does not reflect recent write',
                        'details': {
                            'value_timestamp': entry.timestamp,
                            'write_timestamp': last_write
                        }
                    })
        
        if result.is_ok():
            with self.timestamps_lock:
                self.read_timestamps[key] = time.time()
        
        return result
    
    def _strong_write(
        self,
        key: str,
        value: Any,
        constraint: ConsistencyConstraint,
        metadata: Optional[Dict[str, Any]]
    ) -> Result[StateEntry, Dict[str, Any]]:
        """Perform a strongly consistent write."""
        self.consistency_stats['strong_operations'] += 1
        
        # For strong consistency, need quorum agreement
        # This is simplified - real implementation would:
        # 1. Propose write to quorum
        # 2. Wait for majority acceptance
        # 3. Commit only if quorum agrees
        
        result = self.state_store.set(key, value, metadata)
        
        if result.is_ok():
            with self.timestamps_lock:
                self.write_timestamps[key] = time.time()
            
            # Update vector clock
            self._update_vector_clock()
        
        return result
    
    def _eventual_write(
        self,
        key: str,
        value: Any,
        constraint: ConsistencyConstraint,
        metadata: Optional[Dict[str, Any]]
    ) -> Result[StateEntry, Dict[str, Any]]:
        """Perform an eventually consistent write."""
        self.consistency_stats['eventual_operations'] += 1
        
        # For eventual consistency, write locally and propagate asynchronously
        result = self.state_store.set(key, value, metadata)
        
        if result.is_ok():
            with self.timestamps_lock:
                self.write_timestamps[key] = time.time()
            
            self._update_vector_clock()
        
        return result
    
    def _causal_write(
        self,
        key: str,
        value: Any,
        constraint: ConsistencyConstraint,
        metadata: Optional[Dict[str, Any]]
    ) -> Result[StateEntry, Dict[str, Any]]:
        """Perform a causally consistent write."""
        self.consistency_stats['causal_operations'] += 1
        
        # Update vector clock before write
        self._update_vector_clock()
        
        # Add causal metadata
        if not metadata:
            metadata = {}
        
        with self.causality_lock:
            metadata['causal_context'] = {
                'vector_clock': self.vector_clock.copy(),
                'agent_id': self.agent.agent_id
            }
        
        result = self.state_store.set(key, value, metadata)
        
        if result.is_ok():
            # Update causal history
            with self.causality_lock:
                if key not in self.causal_history:
                    self.causal_history[key] = []
                
                self.causal_history[key].append((
                    self.agent.agent_id,
                    self.vector_clock[self.agent.agent_id]
                ))
            
            with self.timestamps_lock:
                self.write_timestamps[key] = time.time()
        
        return result
    
    def _monotonic_write(
        self,
        key: str,
        value: Any,
        constraint: ConsistencyConstraint,
        metadata: Optional[Dict[str, Any]]
    ) -> Result[StateEntry, Dict[str, Any]]:
        """Perform a monotonic write (writes are ordered)."""
        # Ensure this write is after previous writes
        with self.timestamps_lock:
            last_write = self.write_timestamps.get(key, 0)
            current_time = time.time()
            
            if current_time <= last_write:
                # Adjust timestamp to ensure ordering
                current_time = last_write + 0.001  # 1ms increment
        
        result = self.state_store.set(key, value, metadata)
        
        if result.is_ok():
            with self.timestamps_lock:
                self.write_timestamps[key] = current_time
            
            self._update_vector_clock()
        
        return result
    
    def _basic_read(self, key: str) -> Result[Any, Dict[str, Any]]:
        """Perform a basic read without consistency guarantees."""
        return self.state_store.get(key)
    
    def _basic_write(
        self,
        key: str,
        value: Any,
        metadata: Optional[Dict[str, Any]]
    ) -> Result[StateEntry, Dict[str, Any]]:
        """Perform a basic write without consistency guarantees."""
        return self.state_store.set(key, value, metadata)
    
    def _update_vector_clock(self) -> None:
        """Update the vector clock for this agent."""
        with self.causality_lock:
            agent_id = self.agent.agent_id
            self.vector_clock[agent_id] = self.vector_clock.get(agent_id, 0) + 1
    
    def handle_remote_update(self, key: str, entry: StateEntry, causal_context: Optional[Dict[str, Any]]) -> None:
        """
        Handle a remote state update with consistency checking.
        
        Args:
            key: The updated key
            entry: The new state entry
            causal_context: Causal context from the update
        """
        if causal_context:
            # Update vector clock based on remote context
            remote_clock = causal_context.get('vector_clock', {})
            remote_agent = causal_context.get('agent_id')
            
            with self.causality_lock:
                for agent, clock in remote_clock.items():
                    self.vector_clock[agent] = max(
                        self.vector_clock.get(agent, 0),
                        clock
                    )
                
                # Add to causal history
                if remote_agent and key not in self.causal_history:
                    self.causal_history[key] = []
                
                if remote_agent:
                    self.causal_history[key].append((
                        remote_agent,
                        remote_clock.get(remote_agent, 0)
                    ))
    
    def detect_violations(self) -> List[Dict[str, Any]]:
        """
        Detect consistency violations.
        
        Returns:
            List of detected violations
        """
        violations = []
        
        # Check for monotonic read violations
        with self.timestamps_lock:
            for key in self.read_timestamps:
                if hasattr(self.state_store, '_memory_store'):
                    entry = self.state_store._memory_store.get(key)
                    if entry:
                        last_read = self.read_timestamps.get(key, 0)
                        if entry.timestamp < last_read:
                            violations.append({
                                'type': 'MONOTONIC_READ_VIOLATION',
                                'key': key,
                                'value_timestamp': entry.timestamp,
                                'last_read_timestamp': last_read
                            })
        
        return violations
    
    def repair_violations(self, violations: List[Dict[str, Any]]) -> int:
        """
        Attempt to repair consistency violations.
        
        Args:
            violations: List of violations to repair
            
        Returns:
            Number of violations repaired
        """
        repaired = 0
        
        for violation in violations:
            try:
                # Simple repair: invalidate inconsistent reads
                if violation['type'] == 'MONOTONIC_READ_VIOLATION':
                    key = violation['key']
                    with self.timestamps_lock:
                        # Reset read timestamp to allow fresh reads
                        self.read_timestamps[key] = 0
                    repaired += 1
                    self.consistency_stats['repairs_performed'] += 1
            except Exception as e:
                logger.error(f"Error repairing violation: {e}")
        
        return repaired
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get consistency management statistics."""
        with self.constraints_lock:
            constraint_count = len(self.key_constraints)
        
        with self.causality_lock:
            vector_clock_size = len(self.vector_clock)
            causal_history_size = sum(len(hist) for hist in self.causal_history.values())
        
        return {
            'default_model': self.default_model.value,
            'key_constraints': constraint_count,
            'vector_clock_size': vector_clock_size,
            'causal_history_size': causal_history_size,
            'statistics': self.consistency_stats.copy()
        }
