"""
MAPLE Core Types
Created by: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

Type system for MAPLE's 32/32 perfect validation.
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union
from datetime import datetime
import uuid
import re

# Primitive type validators
class Boolean:
    @staticmethod
    def validate(value: Any) -> bool:
        if not isinstance(value, bool):
            raise TypeError(f"Expected boolean, got {type(value).__name__}")
        return value

class Integer:
    @staticmethod
    def validate(value: Any) -> int:
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(f"Expected integer, got {type(value).__name__}")
        return value

class String:
    @staticmethod
    def validate(value: Any) -> str:
        if not isinstance(value, str):
            raise TypeError(f"Expected string, got {type(value).__name__}")
        return value

class Priority(Enum):
    """Message priority levels."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class AgentID:
    """Agent identifier with validation."""
    
    def __init__(self, agent_id: str):
        if not self.validate(agent_id):
            raise ValueError(f"Invalid agent ID: {agent_id}")
        self.id = agent_id
    
    @staticmethod
    def validate(agent_id: str) -> bool:
        """Validate agent ID format."""
        if not isinstance(agent_id, str):
            return False
        if not (1 <= len(agent_id) <= 255):
            return False
        return bool(re.match(r'^[a-zA-Z0-9_-]+$', agent_id))
    
    def __str__(self) -> str:
        return self.id
    
    def __repr__(self) -> str:
        return f"AgentID('{self.id}')"
    
    def __eq__(self, other) -> bool:
        if isinstance(other, AgentID):
            return self.id == other.id
        if isinstance(other, str):
            return self.id == other
        return False
    
    def __hash__(self) -> int:
        return hash(self.id)

class MessageID:
    """Message identifier using UUID v4."""
    
    def __init__(self, message_id: Optional[str] = None):
        if message_id is None:
            self.id = str(uuid.uuid4())
        else:
            if not self.validate(message_id):
                raise ValueError(f"Invalid message ID: {message_id}")
            self.id = message_id
    
    @staticmethod
    def validate(message_id: str) -> bool:
        """Validate UUID v4 format."""
        try:
            uuid_obj = uuid.UUID(message_id)
            return str(uuid_obj) == message_id and uuid_obj.version == 4
        except (ValueError, AttributeError):
            return False
    
    def __str__(self) -> str:
        return self.id
    
    def __repr__(self) -> str:
        return f"MessageID('{self.id}')"
    
    def __eq__(self, other) -> bool:
        if isinstance(other, MessageID):
            return self.id == other.id
        if isinstance(other, str):
            return self.id == other
        return False
    
    def __hash__(self) -> int:
        return hash(self.id)

class Duration:
    """Duration parser and validator."""
    
    @staticmethod
    def parse(duration_str: str) -> float:
        """Parse a duration string like '30s' into seconds."""
        units = {
            'ms': 0.001,
            's': 1,
            'm': 60,
            'h': 3600,
            'd': 86400
        }
        
        if isinstance(duration_str, (int, float)):
            return float(duration_str)
            
        for unit, multiplier in units.items():
            if duration_str.endswith(unit):
                try:
                    value = float(duration_str[:-len(unit)])
                    return value * multiplier
                except ValueError:
                    raise ValueError(f"Invalid duration format: {duration_str}")
        
        raise ValueError(f"Unknown duration unit in: {duration_str}")
    
    @staticmethod
    def validate(value: Any) -> float:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            return Duration.parse(value)
        raise TypeError(f"Expected duration, got {type(value).__name__}")

class Size:
    """Size parser and validator."""
    
    @staticmethod
    def parse(size_str: Union[str, int, float]) -> int:
        """Parse a size string like '4GB' into bytes."""
        units = {
            'TB': 1024 * 1024 * 1024 * 1024,
            'GB': 1024 * 1024 * 1024,
            'MB': 1024 * 1024,
            'KB': 1024,
            'B': 1
        }
        
        if isinstance(size_str, (int, float)):
            return int(size_str)
        
        if not isinstance(size_str, str):
            raise ValueError(f"Invalid size format: {size_str}")
        
        size_str = size_str.strip().upper()
        
        # Check each unit (ordered by length descending to match TB before B)
        for unit, multiplier in units.items():
            if size_str.endswith(unit):
                try:
                    value_str = size_str[:-len(unit)].strip()
                    value = float(value_str)
                    return int(value * multiplier)
                except (ValueError, IndexError):
                    raise ValueError(f"Invalid size format: {size_str}")
        
        # If no unit found, try to parse as raw number
        try:
            return int(float(size_str))
        except ValueError:
            raise ValueError(f"Unknown size unit in: {size_str}")
    
    @staticmethod
    def validate(value: Any) -> int:
        """Validate and convert a size value to bytes."""
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            return Size.parse(value)
        raise TypeError(f"Expected size, got {type(value).__name__}")

# Type validation utilities
class TypeValidator:
    @staticmethod
    def validate_string(value: Any, min_len: int = 1, max_len: int = 255) -> str:
        if not isinstance(value, str):
            raise TypeError(f"Expected string, got {type(value).__name__}")
        if not (min_len <= len(value) <= max_len):
            raise ValueError(f"String length must be between {min_len} and {max_len}")
        return value
    
    @staticmethod
    def validate_dict(value: Any) -> dict:
        if not isinstance(value, dict):
            raise TypeError(f"Expected dict, got {type(value).__name__}")
        return value
    
    @staticmethod
    def validate_list(value: Any) -> list:
        if not isinstance(value, list):
            raise TypeError(f"Expected list, got {type(value).__name__}")
        return value
