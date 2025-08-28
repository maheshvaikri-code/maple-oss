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


# mapl/resources/manager.py

from typing import Dict, Any, Optional, List, Union
import threading
import logging
from copy import deepcopy

from ..core.result import Result
from .specification import ResourceRequest, ResourceRange

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ResourceAllocation:
    """
    Represents allocated resources.
    """
    
    def __init__(self, allocation_id: str, resources: Dict[str, Any]):
        self.allocation_id = allocation_id
        self.resources = resources
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to a dictionary."""
        return {
            'allocation_id': self.allocation_id,
            'resources': self.resources
        }

class ResourceManager:
    """
    Manages resource allocation and tracking.
    """
    
    def __init__(self):
        self.available_resources: Dict[str, Any] = {}
        self.allocations: Dict[str, ResourceAllocation] = {}
        self._lock = threading.RLock()
        self._allocation_counter = 0
    
    def register_resource(self, resource_type: str, amount: Any) -> None:
        """
        Register available resources.
        
        Args:
            resource_type: The type of resource.
            amount: The amount of resource available.
        """
        with self._lock:
            self.available_resources[resource_type] = amount
            logger.info(f"Registered {amount} of {resource_type}")
    
    def get_available_resources(self) -> Dict[str, Any]:
        """
        Get the currently available resources.
        
        Returns:
            A dictionary of available resources.
        """
        with self._lock:
            return deepcopy(self.available_resources)
    
    def allocate(self, request: Union[ResourceRequest, Dict[str, Any]]) -> Result[ResourceAllocation, Dict[str, Any]]:
        """
        Allocate resources based on a request.
        
        Args:
            request: The resource request.
        
        Returns:
            A Result containing either the allocation or an error.
        """
        # Convert dictionary to ResourceRequest if needed
        if isinstance(request, dict):
            request = ResourceRequest.from_dict(request)
        
        with self._lock:
            # Check if we can satisfy the request
            satisfied, shortfall = self._can_satisfy(request)
            
            if not satisfied:
                return Result.err({
                    'errorType': 'RESOURCE_UNAVAILABLE',
                    'message': 'Insufficient resources to satisfy request',
                    'details': {
                        'shortfall': shortfall
                    }
                })
            
            # Create an allocation ID
            self._allocation_counter += 1
            allocation_id = f"alloc_{self._allocation_counter}"
            
            # Allocate the resources
            allocation = self._allocate_resources(allocation_id, request)
            
            logger.info(f"Allocated resources: {allocation.resources}")
            return Result.ok(allocation)
    
    def release(self, allocation: ResourceAllocation) -> None:
        """
        Release allocated resources.
        
        Args:
            allocation: The resource allocation to release.
        """
        with self._lock:
            if allocation.allocation_id in self.allocations:
                # Release the resources
                for resource_type, amount in self.allocations[allocation.allocation_id].resources.items():
                    # For resources that are added (like compute units)
                    if resource_type in ['compute', 'memory', 'bandwidth']:
                        if resource_type in self.available_resources:
                            self.available_resources[resource_type] += amount
                    
                    # For other resources, just remove from allocations
                
                # Remove the allocation
                del self.allocations[allocation.allocation_id]
                logger.info(f"Released allocation {allocation.allocation_id}")
    
    def _can_satisfy(self, request: ResourceRequest) -> tuple[bool, Dict[str, Any]]:
        """
        Check if a request can be satisfied with available resources.
        
        Args:
            request: The resource request.
        
        Returns:
            A tuple of (can_satisfy, shortfall).
        """
        shortfall = {}
        
        # Check compute
        if request.compute and 'compute' in self.available_resources:
            if request.compute.min > self.available_resources['compute']:
                shortfall['compute'] = {
                    'requested': request.compute.min,
                    'available': self.available_resources['compute']
                }
        
        # Check memory
        if request.memory and 'memory' in self.available_resources:
            from ..core.types import Size
            
            requested = Size.parse(request.memory.min) if isinstance(request.memory.min, str) else request.memory.min
            available = Size.parse(self.available_resources['memory']) if isinstance(self.available_resources['memory'], str) else self.available_resources['memory']
            
            if requested > available:
                shortfall['memory'] = {
                    'requested': request.memory.min,
                    'available': self.available_resources['memory']
                }
        
        # Check bandwidth
        if request.bandwidth and 'bandwidth' in self.available_resources:
            # Similar to memory, parsing might be needed
            # This is a simplified check
            if request.bandwidth.min > self.available_resources['bandwidth']:
                shortfall['bandwidth'] = {
                    'requested': request.bandwidth.min,
                    'available': self.available_resources['bandwidth']
                }
        
        # Return whether there's any shortfall
        return len(shortfall) == 0, shortfall
    
    def _allocate_resources(self, allocation_id: str, request: ResourceRequest) -> ResourceAllocation:
        """
        Allocate resources for a request.
        
        Args:
            allocation_id: The allocation ID.
            request: The resource request.
        
        Returns:
            A ResourceAllocation object.
        """
        resources = {}
        
        # Allocate compute
        if request.compute and 'compute' in self.available_resources:
            # Try to allocate preferred, but fall back to minimum
            amount = min(request.compute.preferred, self.available_resources['compute'])
            amount = max(amount, request.compute.min)  # But ensure at least minimum
            
            self.available_resources['compute'] -= amount
            resources['compute'] = amount
        
        # Allocate memory
        if request.memory and 'memory' in self.available_resources:
            from ..core.types import Size
            
            preferred = Size.parse(request.memory.preferred) if isinstance(request.memory.preferred, str) else request.memory.preferred
            available = Size.parse(self.available_resources['memory']) if isinstance(self.available_resources['memory'], str) else self.available_resources['memory']
            minimum = Size.parse(request.memory.min) if isinstance(request.memory.min, str) else request.memory.min
            
            amount = min(preferred, available)
            amount = max(amount, minimum)  # But ensure at least minimum
            
            self.available_resources['memory'] = available - amount
            resources['memory'] = amount
        
        # Allocate bandwidth
        if request.bandwidth and 'bandwidth' in self.available_resources:
            # Similar to memory
            amount = min(request.bandwidth.preferred, self.available_resources['bandwidth'])
            amount = max(amount, request.bandwidth.min)  # But ensure at least minimum
            
            self.available_resources['bandwidth'] -= amount
            resources['bandwidth'] = amount
        
        # Create and store the allocation
        allocation = ResourceAllocation(allocation_id, resources)
        self.allocations[allocation_id] = allocation
        
        return allocation