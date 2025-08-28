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


# mapl/error/types.py
# Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

from enum import Enum
from typing import Dict, Any, Optional

class ErrorType(Enum):
    """Common error types in MAPL."""
    # Communication errors
    NETWORK_ERROR = "NETWORK_ERROR"
    TIMEOUT = "TIMEOUT"
    ROUTING_ERROR = "ROUTING_ERROR"
    
    # Processing errors
    VALIDATION_ERROR = "VALIDATION_ERROR"
    RESOURCE_ERROR = "RESOURCE_ERROR"
    LOGIC_ERROR = "LOGIC_ERROR"
    
    # Security errors
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"
    INTEGRITY_ERROR = "INTEGRITY_ERROR"

    # Link-related errors
    INVALID_LINK = "INVALID_LINK"
    LINK_NOT_ESTABLISHED = "LINK_NOT_ESTABLISHED"
    EXPIRED_LINK = "EXPIRED_LINK"
    UNAUTHORIZED_LINK_USAGE = "UNAUTHORIZED_LINK_USAGE"
    LINK_ESTABLISHMENT_ERROR = "LINK_ESTABLISHMENT_ERROR"
    LINK_VERIFICATION_FAILED = "LINK_VERIFICATION_FAILED"
    LINK_TIMEOUT = "LINK_TIMEOUT"

class Severity(Enum):
    """Error severity levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class Error:
    """Represents a structured error in MAPL."""
    
    def __init__(
        self,
        error_type: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        severity: Severity = Severity.MEDIUM,
        recoverable: bool = False,
        suggestion: Optional[Dict[str, Any]] = None
    ):
        self.error_type = error_type
        self.message = message
        self.details = details or {}
        self.severity = severity
        self.recoverable = recoverable
        self.suggestion = suggestion or {}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Error':
        """Create an error from a dictionary."""
        return cls(
            error_type=data.get('errorType', 'UNKNOWN_ERROR'),
            message=data.get('message', ''),
            details=data.get('details', {}),
            severity=Severity(data.get('severity', 'MEDIUM')),
            recoverable=data.get('recoverable', False),
            suggestion=data.get('suggestion', {})
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the error to a dictionary."""
        return {
            'errorType': self.error_type,
            'message': self.message,
            'details': self.details,
            'severity': self.severity.value,
            'recoverable': self.recoverable,
            'suggestion': self.suggestion
        }
    
class SecurityError(Exception):
    """Exception raised for security-related errors."""
    pass