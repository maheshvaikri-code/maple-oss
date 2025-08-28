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


# maple/state/__init__.py
# Creator: Mahesh Vaikri

"""
State Management Components for MAPLE
Provides distributed state storage, synchronization, and consistency management
"""

from .store import StateStore, StateEntry, StorageBackend, ConsistencyLevel
from .synchronization import StateSynchronizer, SyncEvent, SyncMode
from .consistency import ConsistencyManager, ConsistencyModel, ConsistencyConstraint

__all__ = [
    # State storage
    'StateStore', 'StateEntry', 'StorageBackend', 'ConsistencyLevel',
    
    # State synchronization
    'StateSynchronizer', 'SyncEvent', 'SyncMode',
    
    # Consistency management
    'ConsistencyManager', 'ConsistencyModel', 'ConsistencyConstraint'
]
