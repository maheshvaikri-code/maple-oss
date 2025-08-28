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


# mapl/resources/specification.py
# Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

from typing import Dict, Any, Optional, Union
from dataclasses import dataclass
import re
import json

from ..core.types import Size, Duration

@dataclass
class ResourceRange:
    """A range of resource values, with minimum, preferred, and maximum."""
    min: Any
    preferred: Optional[Any] = None
    max: Optional[Any] = None
    
    def __post_init__(self):
        # Set preferred to min if not specified
        if self.preferred is None:
            self.preferred = self.min
        
        # Set max to preferred if not specified
        if self.max is None:
            self.max = self.preferred
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to a dictionary."""
        return {
            'min': self.min,
            'preferred': self.preferred,
            'max': self.max
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ResourceRange':
        """Create from a dictionary."""
        return cls(
            min=data.get('min'),
            preferred=data.get('preferred'),
            max=data.get('max')
        )

@dataclass
class TimeConstraint:
    """Time constraints for a resource request."""
    deadline: Optional[str] = None
    timeout: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to a dictionary."""
        result = {}
        if self.deadline:
            result['deadline'] = self.deadline
        if self.timeout:
            result['timeout'] = self.timeout
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TimeConstraint':
        """Create from a dictionary."""
        return cls(
            deadline=data.get('deadline'),
            timeout=data.get('timeout')
        )

@dataclass
class ResourceRequest:
    """A request for resources."""
    compute: Optional[ResourceRange] = None
    memory: Optional[ResourceRange] = None
    bandwidth: Optional[ResourceRange] = None
    time: Optional[TimeConstraint] = None
    priority: str = "MEDIUM"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to a dictionary."""
        result = {'priority': self.priority}
        
        if self.compute:
            result['compute'] = self.compute.to_dict()
        if self.memory:
            result['memory'] = self.memory.to_dict()
        if self.bandwidth:
            result['bandwidth'] = self.bandwidth.to_dict()
        if self.time:
            result['time'] = self.time.to_dict()
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ResourceRequest':
        """Create from a dictionary."""
        return cls(
            compute=ResourceRange.from_dict(data['compute']) if 'compute' in data else None,
            memory=ResourceRange.from_dict(data['memory']) if 'memory' in data else None,
            bandwidth=ResourceRange.from_dict(data['bandwidth']) if 'bandwidth' in data else None,
            time=TimeConstraint.from_dict(data['time']) if 'time' in data else None,
            priority=data.get('priority', 'MEDIUM')
        )
    
    @classmethod
    def Range(cls, min: Any, preferred: Optional[Any] = None, max: Optional[Any] = None) -> ResourceRange:
        """Create a resource range."""
        return ResourceRange(min, preferred, max)
    
    @classmethod
    def TimeConstraint(cls, deadline: Optional[str] = None, timeout: Optional[str] = None) -> TimeConstraint:
        """Create a time constraint."""
        return TimeConstraint(deadline, timeout)