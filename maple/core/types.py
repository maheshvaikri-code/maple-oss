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


# maple/core/types.py
# Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

from enum import Enum
from typing import Any, Dict, List, Optional, Set, TypeVar, Generic, Union, Type
from datetime import datetime
import uuid

# Type variables for generic types
T = TypeVar('T')
K = TypeVar('K')
V = TypeVar('V')
E = TypeVar('E')

# Primitive type definitions
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

class Float:
    @staticmethod
    def validate(value: Any) -> float:
        if not isinstance(value, (float, int)) or isinstance(value, bool):
            raise TypeError(f"Expected float, got {type(value).__name__}")
        return float(value)

class String:
    @staticmethod
    def validate(value: Any) -> str:
        if not isinstance(value, str):
            raise TypeError(f"Expected string, got {type(value).__name__}")
        return value

class Timestamp:
    @staticmethod
    def validate(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace('Z', '+00:00'))
            except ValueError:
                raise ValueError(f"Invalid timestamp format: {value}")
        raise TypeError(f"Expected timestamp, got {type(value).__name__}")

class UUID:
    @staticmethod
    def validate(value: Any) -> uuid.UUID:
        if isinstance(value, uuid.UUID):
            return value
        if isinstance(value, str):
            try:
                return uuid.UUID(value)
            except ValueError:
                raise ValueError(f"Invalid UUID format: {value}")
        raise TypeError(f"Expected UUID, got {type(value).__name__}")

class Byte:
    @staticmethod
    def validate(value: Any) -> int:
        if isinstance(value, int):
            if 0 <= value <= 255:
                return value
            raise ValueError(f"Byte value must be between 0 and 255, got {value}")
        raise TypeError(f"Expected byte, got {type(value).__name__}")

# Collection types
class Array(Generic[T]):
    def __init__(self, item_type):
        self.item_type = item_type
    
    def validate(self, value: Any) -> List[T]:
        if not isinstance(value, list):
            raise TypeError(f"Expected array, got {type(value).__name__}")
        return [self.item_type.validate(item) for item in value]

class Map(Generic[K, V]):
    def __init__(self, key_type, value_type):
        self.key_type = key_type
        self.value_type = value_type
    
    def validate(self, value: Any) -> Dict[K, V]:
        if not isinstance(value, dict):
            raise TypeError(f"Expected map, got {type(value).__name__}")
        return {
            self.key_type.validate(k): self.value_type.validate(v)
            for k, v in value.items()
        }

class Set(Generic[T]):
    def __init__(self, item_type):
        self.item_type = item_type
    
    def validate(self, value: Any) -> Set[T]:
        if isinstance(value, list):
            value = set(value)
        if not isinstance(value, set):
            raise TypeError(f"Expected set, got {type(value).__name__}")
        return {self.item_type.validate(item) for item in value}

# Special types
class Option(Generic[T]):
    def __init__(self, item_type):
        self.item_type = item_type
    
    def validate(self, value: Any) -> Optional[T]:
        if value is None:
            return None
        return self.item_type.validate(value)

# Protocol-specific types
class Priority(Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class AgentID:
    @staticmethod
    def validate(value: Any) -> str:
        return String.validate(value)

class MessageID:
    @staticmethod
    def validate(value: Any) -> str:
        return String.validate(value)

class Size:
    @staticmethod
    def parse(size_str: str) -> int:
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
        
        # Convert to string and strip whitespace
        size_str = str(size_str).strip().upper()
        
        # Check each unit (ordered by length to match TB before B)
        for unit, multiplier in units.items():
            if size_str.endswith(unit):
                try:
                    # Extract the numeric part
                    numeric_part = size_str[:-len(unit)].strip()
                    if not numeric_part:
                        raise ValueError(f"No numeric value found in: {size_str}")
                    value = float(numeric_part)
                    return int(value * multiplier)
                except ValueError as e:
                    if "could not convert" in str(e):
                        raise ValueError(f"Invalid numeric value in size format: {size_str}")
                    else:
                        raise
        
        # If no unit found, try to parse as plain number (assume bytes)
        try:
            return int(float(size_str))
        except ValueError:
            raise ValueError(f"Unknown size format: {size_str}. Expected format like '4GB', '1024MB', etc.")
    
    @staticmethod
    def validate(value: Any) -> int:
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            return Size.parse(value)
        raise TypeError(f"Expected size, got {type(value).__name__}")

class Duration:
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

# Type validator for validating data against type definitions
class TypeValidator:
    @staticmethod
    def validate(data: Any, type_def: Any) -> Any:
        """Validate data against a type definition."""
        if hasattr(type_def, 'validate'):
            return type_def.validate(data)
        
        # For simple type checks
        if isinstance(type_def, type):
            if not isinstance(data, type_def):
                raise TypeError(f"Expected {type_def.__name__}, got {type(data).__name__}")
            return data
        
        # For dictionaries representing structs
        if isinstance(type_def, dict):
            if not isinstance(data, dict):
                raise TypeError(f"Expected dict, got {type(data).__name__}")
            
            result = {}
            for key, field_type in type_def.items():
                if key not in data:
                    raise ValueError(f"Missing required field: {key}")
                result[key] = TypeValidator.validate(data[key], field_type)
            
            return result
        
        raise ValueError(f"Unknown type definition: {type_def}")

class LinkRequest:
    @staticmethod
    def validate(value: Any) -> Dict[str, Any]:
        if not isinstance(value, dict):
            raise TypeError(f"Expected dict, got {type(value).__name__}")
        
        if 'publicKey' not in value:
            raise ValueError("Missing required field: publicKey")
        if 'nonce' not in value:
            raise ValueError("Missing required field: nonce")
        
        return {
            'publicKey': String.validate(value['publicKey']),
            'nonce': String.validate(value['nonce']),
            'supportedCiphers': Array(String).validate(value.get('supportedCiphers', []))
        }

class LinkChallenge:
    @staticmethod
    def validate(value: Any) -> Dict[str, Any]:
        if not isinstance(value, dict):
            raise TypeError(f"Expected dict, got {type(value).__name__}")
        
        if 'linkId' not in value:
            raise ValueError("Missing required field: linkId")
        if 'publicKey' not in value:
            raise ValueError("Missing required field: publicKey")
        if 'encryptedNonce' not in value:
            raise ValueError("Missing required field: encryptedNonce")
        if 'nonce' not in value:
            raise ValueError("Missing required field: nonce")
        
        return {
            'linkId': String.validate(value['linkId']),
            'publicKey': String.validate(value['publicKey']),
            'encryptedNonce': String.validate(value['encryptedNonce']),
            'nonce': String.validate(value['nonce'])
        }

class LinkConfirm:
    @staticmethod
    def validate(value: Any) -> Dict[str, Any]:
        if not isinstance(value, dict):
            raise TypeError(f"Expected dict, got {type(value).__name__}")
        
        if 'linkId' not in value:
            raise ValueError("Missing required field: linkId")
        if 'encryptedNonce' not in value:
            raise ValueError("Missing required field: encryptedNonce")
        if 'linkParams' not in value:
            raise ValueError("Missing required field: linkParams")
        
        return {
            'linkId': String.validate(value['linkId']),
            'encryptedNonce': String.validate(value['encryptedNonce']),
            'linkParams': Map(String, Any).validate(value['linkParams'])
        }

class LinkEstablished:
    @staticmethod
    def validate(value: Any) -> Dict[str, Any]:
        if not isinstance(value, dict):
            raise TypeError(f"Expected dict, got {type(value).__name__}")
        
        if 'linkId' not in value:
            raise ValueError("Missing required field: linkId")
        if 'encryptedParams' not in value:
            raise ValueError("Missing required field: encryptedParams")
        
        return {
            'linkId': String.validate(value['linkId']),
            'encryptedParams': String.validate(value['encryptedParams'])
        }