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


# maple/core/serialization.py
# Creator: Mahesh Vaikri

"""
Serialization utilities for MAPLE messages and data structures
Provides multiple serialization formats and efficient encoding/decoding
"""

import json
import pickle
import base64
from typing import Any, Dict, Union, Optional
from enum import Enum
import logging

from .result import Result

logger = logging.getLogger(__name__)

class SerializationFormat(Enum):
    """Supported serialization formats."""
    JSON = "json"
    PICKLE = "pickle"
    MSGPACK = "msgpack"
    PROTOBUF = "protobuf"

class Serializer:
    """
    Handles serialization and deserialization of MAPLE data structures.
    
    Supports multiple formats:
    - JSON: Human-readable, widely compatible
    - Pickle: Python-specific, supports complex objects
    - MessagePack: Binary, compact and fast
    - Protocol Buffers: Type-safe, cross-language
    """
    
    def __init__(self, default_format: SerializationFormat = SerializationFormat.JSON):
        """
        Initialize the serializer.
        
        Args:
            default_format: Default serialization format to use
        """
        self.default_format = default_format
        self._check_dependencies()
    
    def _check_dependencies(self):
        """Check availability of optional serialization libraries."""
        self.msgpack_available = False
        self.protobuf_available = False
        
        try:
            import msgpack
            self.msgpack_available = True
        except ImportError:
            pass
        
        try:
            import google.protobuf
            self.protobuf_available = True
        except ImportError:
            pass
    
    def serialize(
        self,
        data: Any,
        format: Optional[SerializationFormat] = None
    ) -> Result[bytes, Dict[str, Any]]:
        """
        Serialize data to bytes.
        
        Args:
            data: Data to serialize
            format: Serialization format (uses default if None)
            
        Returns:
            Result containing serialized bytes or error
        """
        format = format or self.default_format
        
        try:
            if format == SerializationFormat.JSON:
                return self._serialize_json(data)
            elif format == SerializationFormat.PICKLE:
                return self._serialize_pickle(data)
            elif format == SerializationFormat.MSGPACK:
                return self._serialize_msgpack(data)
            elif format == SerializationFormat.PROTOBUF:
                return self._serialize_protobuf(data)
            else:
                return Result.err({
                    'errorType': 'UNSUPPORTED_FORMAT',
                    'message': f'Unsupported serialization format: {format.value}'
                })
                
        except Exception as e:
            return Result.err({
                'errorType': 'SERIALIZATION_ERROR',
                'message': f'Failed to serialize data: {str(e)}',
                'details': {'format': format.value}
            })
    
    def deserialize(
        self,
        data: bytes,
        format: Optional[SerializationFormat] = None
    ) -> Result[Any, Dict[str, Any]]:
        """
        Deserialize bytes to data.
        
        Args:
            data: Bytes to deserialize
            format: Serialization format (uses default if None)
            
        Returns:
            Result containing deserialized data or error
        """
        format = format or self.default_format
        
        try:
            if format == SerializationFormat.JSON:
                return self._deserialize_json(data)
            elif format == SerializationFormat.PICKLE:
                return self._deserialize_pickle(data)
            elif format == SerializationFormat.MSGPACK:
                return self._deserialize_msgpack(data)
            elif format == SerializationFormat.PROTOBUF:
                return self._deserialize_protobuf(data)
            else:
                return Result.err({
                    'errorType': 'UNSUPPORTED_FORMAT',
                    'message': f'Unsupported deserialization format: {format.value}'
                })
                
        except Exception as e:
            return Result.err({
                'errorType': 'DESERIALIZATION_ERROR',
                'message': f'Failed to deserialize data: {str(e)}',
                'details': {'format': format.value}
            })
    
    def _serialize_json(self, data: Any) -> Result[bytes, Dict[str, Any]]:
        """Serialize data to JSON."""
        try:
            # Handle special types that JSON can't serialize by default
            json_data = self._prepare_for_json(data)
            json_str = json.dumps(json_data, separators=(',', ':'), ensure_ascii=False)
            return Result.ok(json_str.encode('utf-8'))
        except Exception as e:
            return Result.err({
                'errorType': 'JSON_SERIALIZATION_ERROR',
                'message': f'JSON serialization failed: {str(e)}'
            })
    
    def _deserialize_json(self, data: bytes) -> Result[Any, Dict[str, Any]]:
        """Deserialize JSON data."""
        try:
            json_str = data.decode('utf-8')
            parsed_data = json.loads(json_str)
            return Result.ok(self._restore_from_json(parsed_data))
        except Exception as e:
            return Result.err({
                'errorType': 'JSON_DESERIALIZATION_ERROR',
                'message': f'JSON deserialization failed: {str(e)}'
            })
    
    def _serialize_pickle(self, data: Any) -> Result[bytes, Dict[str, Any]]:
        """Serialize data using pickle."""
        try:
            pickled_data = pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)
            return Result.ok(pickled_data)
        except Exception as e:
            return Result.err({
                'errorType': 'PICKLE_SERIALIZATION_ERROR',
                'message': f'Pickle serialization failed: {str(e)}'
            })
    
    def _deserialize_pickle(self, data: bytes) -> Result[Any, Dict[str, Any]]:
        """Deserialize pickle data."""
        try:
            unpickled_data = pickle.loads(data)
            return Result.ok(unpickled_data)
        except Exception as e:
            return Result.err({
                'errorType': 'PICKLE_DESERIALIZATION_ERROR',
                'message': f'Pickle deserialization failed: {str(e)}'
            })
    
    def _serialize_msgpack(self, data: Any) -> Result[bytes, Dict[str, Any]]:
        """Serialize data using MessagePack."""
        if not self.msgpack_available:
            return Result.err({
                'errorType': 'MSGPACK_UNAVAILABLE',
                'message': 'MessagePack library not available. Install with: pip install msgpack'
            })
        
        try:
            import msgpack
            packed_data = msgpack.packb(data, use_bin_type=True)
            return Result.ok(packed_data)
        except Exception as e:
            return Result.err({
                'errorType': 'MSGPACK_SERIALIZATION_ERROR',
                'message': f'MessagePack serialization failed: {str(e)}'
            })
    
    def _deserialize_msgpack(self, data: bytes) -> Result[Any, Dict[str, Any]]:
        """Deserialize MessagePack data."""
        if not self.msgpack_available:
            return Result.err({
                'errorType': 'MSGPACK_UNAVAILABLE',
                'message': 'MessagePack library not available. Install with: pip install msgpack'
            })
        
        try:
            import msgpack
            unpacked_data = msgpack.unpackb(data, raw=False, strict_map_key=False)
            return Result.ok(unpacked_data)
        except Exception as e:
            return Result.err({
                'errorType': 'MSGPACK_DESERIALIZATION_ERROR',
                'message': f'MessagePack deserialization failed: {str(e)}'
            })
    
    def _serialize_protobuf(self, data: Any) -> Result[bytes, Dict[str, Any]]:
        """Serialize data using Protocol Buffers."""
        return Result.err({
            'errorType': 'PROTOBUF_NOT_IMPLEMENTED',
            'message': 'Protocol Buffers serialization not yet implemented'
        })
    
    def _deserialize_protobuf(self, data: bytes) -> Result[Any, Dict[str, Any]]:
        """Deserialize Protocol Buffers data."""
        return Result.err({
            'errorType': 'PROTOBUF_NOT_IMPLEMENTED',
            'message': 'Protocol Buffers deserialization not yet implemented'
        })
    
    def _prepare_for_json(self, data: Any) -> Any:
        """Prepare data for JSON serialization by handling special types."""
        if isinstance(data, dict):
            return {key: self._prepare_for_json(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self._prepare_for_json(item) for item in data]
        elif isinstance(data, tuple):
            return {'__tuple__': [self._prepare_for_json(item) for item in data]}
        elif isinstance(data, set):
            return {'__set__': [self._prepare_for_json(item) for item in data]}
        elif isinstance(data, bytes):
            return {'__bytes__': base64.b64encode(data).decode('ascii')}
        elif hasattr(data, '__dict__'):
            # Handle objects with __dict__
            return {
                '__object__': {
                    'class': f"{data.__class__.__module__}.{data.__class__.__name__}",
                    'data': self._prepare_for_json(data.__dict__)
                }
            }
        else:
            return data
    
    def _restore_from_json(self, data: Any) -> Any:
        """Restore data from JSON by reconstructing special types."""
        if isinstance(data, dict):
            if '__tuple__' in data:
                return tuple(self._restore_from_json(item) for item in data['__tuple__'])
            elif '__set__' in data:
                return set(self._restore_from_json(item) for item in data['__set__'])
            elif '__bytes__' in data:
                return base64.b64decode(data['__bytes__'].encode('ascii'))
            elif '__object__' in data:
                # For now, just return the data dict - full object reconstruction
                # would require importing the class
                return data['__object__']['data']
            else:
                return {key: self._restore_from_json(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self._restore_from_json(item) for item in data]
        else:
            return data
    
    def serialize_message(self, message) -> Result[bytes, Dict[str, Any]]:
        """
        Serialize a MAPLE message.
        
        Args:
            message: Message instance to serialize
            
        Returns:
            Result containing serialized message bytes or error
        """
        try:
            # Convert message to dictionary first
            message_dict = message.to_dict()
            return self.serialize(message_dict)
        except Exception as e:
            return Result.err({
                'errorType': 'MESSAGE_SERIALIZATION_ERROR',
                'message': f'Failed to serialize message: {str(e)}'
            })
    
    def deserialize_message(self, data: bytes) -> Result[Any, Dict[str, Any]]:
        """
        Deserialize bytes to a MAPLE message.
        
        Args:
            data: Serialized message bytes
            
        Returns:
            Result containing Message instance or error
        """
        try:
            # Deserialize to dictionary first
            dict_result = self.deserialize(data)
            if dict_result.is_err():
                return dict_result
            
            message_dict = dict_result.unwrap()
            
            # Import Message class and reconstruct
            from .message import Message
            message = Message.from_dict(message_dict)
            return Result.ok(message)
            
        except Exception as e:
            return Result.err({
                'errorType': 'MESSAGE_DESERIALIZATION_ERROR',
                'message': f'Failed to deserialize message: {str(e)}'
            })
    
    def get_format_info(self) -> Dict[str, Any]:
        """Get information about available serialization formats."""
        return {
            'default_format': self.default_format.value,
            'available_formats': {
                'json': True,
                'pickle': True,
                'msgpack': self.msgpack_available,
                'protobuf': self.protobuf_available
            },
            'recommendations': {
                'human_readable': 'json',
                'performance': 'msgpack' if self.msgpack_available else 'pickle',
                'cross_language': 'json',
                'binary': 'msgpack' if self.msgpack_available else 'pickle'
            }
        }

# Global serializer instance
default_serializer = Serializer()
