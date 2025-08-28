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


# maple/security/audit.py
# Creator: Mahesh Vaikri

"""
Security audit logging and compliance for MAPLE.
"""

import time
import json
import threading
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime
import uuid
from enum import Enum

class AuditEventType(Enum):
    """Types of security events to audit."""
    AUTHENTICATION_SUCCESS = "AUTHENTICATION_SUCCESS"
    AUTHENTICATION_FAILURE = "AUTHENTICATION_FAILURE"
    AUTHORIZATION_GRANTED = "AUTHORIZATION_GRANTED"
    AUTHORIZATION_DENIED = "AUTHORIZATION_DENIED"
    LINK_ESTABLISHED = "LINK_ESTABLISHED"
    LINK_FAILED = "LINK_FAILED"
    LINK_TERMINATED = "LINK_TERMINATED"
    MESSAGE_ENCRYPTED = "MESSAGE_ENCRYPTED"
    MESSAGE_DECRYPTED = "MESSAGE_DECRYPTED"
    ENCRYPTION_FAILURE = "ENCRYPTION_FAILURE"
    TOKEN_ISSUED = "TOKEN_ISSUED"
    TOKEN_REVOKED = "TOKEN_REVOKED"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    SECURITY_VIOLATION = "SECURITY_VIOLATION"
    CONFIGURATION_CHANGE = "CONFIGURATION_CHANGE"
    ACCESS_DENIED = "ACCESS_DENIED"

class AuditSeverity(Enum):
    """Severity levels for audit events."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

@dataclass
class AuditEvent:
    """Represents a security audit event."""
    event_id: str
    timestamp: float
    event_type: AuditEventType
    severity: AuditSeverity
    agent_id: Optional[str]
    principal: Optional[str]
    resource: Optional[str]
    action: Optional[str]
    result: str  # SUCCESS, FAILURE, DENIED
    details: Dict[str, Any]
    source_ip: Optional[str] = None
    session_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert audit event to dictionary."""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "iso_timestamp": datetime.fromtimestamp(self.timestamp).isoformat(),
            "event_type": self.event_type.value,
            "severity": self.severity.value,
            "agent_id": self.agent_id,
            "principal": self.principal,
            "resource": self.resource,
            "action": self.action,
            "result": self.result,
            "details": self.details,
            "source_ip": self.source_ip,
            "session_id": self.session_id
        }

class AuditLogger:
    """
    Security audit logger for MAPLE.
    Provides compliance logging for security events.
    """
    
    def __init__(self, 
                 log_file: Optional[str] = None,
                 max_events_memory: int = 1000,
                 enable_console: bool = False):
        self.log_file = log_file
        self.max_events_memory = max_events_memory
        self.enable_console = enable_console
        
        # In-memory event storage
        self.events = []
        self.events_lock = threading.RLock()
        
        # Statistics
        self.event_counts = {}
        self.last_cleanup = time.time()
    
    def log_event(self,
                  event_type: AuditEventType,
                  severity: AuditSeverity,
                  result: str,
                  agent_id: Optional[str] = None,
                  principal: Optional[str] = None,
                  resource: Optional[str] = None,
                  action: Optional[str] = None,
                  details: Optional[Dict[str, Any]] = None,
                  source_ip: Optional[str] = None,
                  session_id: Optional[str] = None) -> str:
        """
        Log a security audit event.
        
        Returns:
            The event ID for tracking purposes.
        """
        event_id = str(uuid.uuid4())
        
        event = AuditEvent(
            event_id=event_id,
            timestamp=time.time(),
            event_type=event_type,
            severity=severity,
            agent_id=agent_id,
            principal=principal,
            resource=resource,
            action=action,
            result=result,
            details=details or {},
            source_ip=source_ip,
            session_id=session_id
        )
        
        with self.events_lock:
            # Add to in-memory storage
            self.events.append(event)
            
            # Update statistics
            event_type_str = event_type.value
            if event_type_str not in self.event_counts:
                self.event_counts[event_type_str] = 0
            self.event_counts[event_type_str] += 1
            
            # Cleanup old events if necessary
            if len(self.events) > self.max_events_memory:
                self.events = self.events[-self.max_events_memory:]
            
            # Write to file if configured
            if self.log_file:
                self._write_to_file(event)
            
            # Print to console if enabled
            if self.enable_console:
                self._print_to_console(event)
        
        return event_id
    
    def log_authentication_success(self, principal: str, agent_id: str, method: str, session_id: str):
        """Log successful authentication."""
        return self.log_event(
            event_type=AuditEventType.AUTHENTICATION_SUCCESS,
            severity=AuditSeverity.LOW,
            result="SUCCESS",
            principal=principal,
            agent_id=agent_id,
            action="authenticate",
            details={"method": method, "authentication_method": method},
            session_id=session_id
        )
    
    def log_authentication_failure(self, principal: str, agent_id: str, reason: str, source_ip: str = None):
        """Log failed authentication attempt."""
        return self.log_event(
            event_type=AuditEventType.AUTHENTICATION_FAILURE,
            severity=AuditSeverity.MEDIUM,
            result="FAILURE",
            principal=principal,
            agent_id=agent_id,
            action="authenticate",
            details={"failure_reason": reason, "failure_details": reason},
            source_ip=source_ip
        )
    
    def log_authorization_granted(self, principal: str, resource: str, action: str, agent_id: str):
        """Log successful authorization."""
        return self.log_event(
            event_type=AuditEventType.AUTHORIZATION_GRANTED,
            severity=AuditSeverity.LOW,
            result="SUCCESS",
            principal=principal,
            resource=resource,
            action=action,
            agent_id=agent_id,
            details={"authorized_action": action, "authorized_resource": resource}
        )
    
    def log_authorization_denied(self, principal: str, resource: str, action: str, reason: str, agent_id: str):
        """Log denied authorization attempt."""
        return self.log_event(
            event_type=AuditEventType.AUTHORIZATION_DENIED,
            severity=AuditSeverity.HIGH,
            result="DENIED",
            principal=principal,
            resource=resource,
            action=action,
            agent_id=agent_id,
            details={"denial_reason": reason, "attempted_action": action}
        )
    
    def log_link_established(self, agent_a: str, agent_b: str, link_id: str, encryption_params: Dict[str, Any]):
        """Log link establishment."""
        return self.log_event(
            event_type=AuditEventType.LINK_ESTABLISHED,
            severity=AuditSeverity.MEDIUM,
            result="SUCCESS",
            agent_id=agent_a,
            resource=f"link_{link_id}",
            action="establish_link",
            details={
                "link_id": link_id,
                "peer_agent": agent_b,
                "encryption_suite": encryption_params.get("cipher_suite"),
                "key_length": encryption_params.get("key_length")
            }
        )
    
    def log_link_failed(self, agent_a: str, agent_b: str, reason: str):
        """Log link establishment failure."""
        return self.log_event(
            event_type=AuditEventType.LINK_FAILED,
            severity=AuditSeverity.HIGH,
            result="FAILURE",
            agent_id=agent_a,
            action="establish_link",
            details={
                "peer_agent": agent_b,
                "failure_reason": reason
            }
        )
    
    def log_security_violation(self, agent_id: str, violation_type: str, details: Dict[str, Any]):
        """Log security violation."""
        return self.log_event(
            event_type=AuditEventType.SECURITY_VIOLATION,
            severity=AuditSeverity.CRITICAL,
            result="VIOLATION",
            agent_id=agent_id,
            action="security_check",
            details={
                "violation_type": violation_type,
                **details
            }
        )
    
    def log_token_issued(self, principal: str, token_type: str, expires_in: int, permissions: List[str]):
        """Log token issuance."""
        return self.log_event(
            event_type=AuditEventType.TOKEN_ISSUED,
            severity=AuditSeverity.LOW,
            result="SUCCESS",
            principal=principal,
            action="issue_token",
            details={
                "token_type": token_type,
                "expires_in_seconds": expires_in,
                "permissions": permissions
            }
        )
    
    def log_token_revoked(self, principal: str, token_id: str, reason: str):
        """Log token revocation."""
        return self.log_event(
            event_type=AuditEventType.TOKEN_REVOKED,
            severity=AuditSeverity.MEDIUM,
            result="SUCCESS",
            principal=principal,
            action="revoke_token",
            details={
                "token_id": token_id,
                "revocation_reason": reason
            }
        )
    
    def get_events(self, 
                   event_type: Optional[AuditEventType] = None,
                   severity: Optional[AuditSeverity] = None,
                   principal: Optional[str] = None,
                   since: Optional[float] = None,
                   limit: Optional[int] = None) -> List[AuditEvent]:
        """
        Retrieve audit events with optional filtering.
        """
        with self.events_lock:
            filtered_events = self.events.copy()
            
            # Apply filters
            if event_type:
                filtered_events = [e for e in filtered_events if e.event_type == event_type]
            
            if severity:
                filtered_events = [e for e in filtered_events if e.severity == severity]
            
            if principal:
                filtered_events = [e for e in filtered_events if e.principal == principal]
            
            if since:
                filtered_events = [e for e in filtered_events if e.timestamp >= since]
            
            # Sort by timestamp (newest first)
            filtered_events.sort(key=lambda e: e.timestamp, reverse=True)
            
            # Apply limit
            if limit:
                filtered_events = filtered_events[:limit]
            
            return filtered_events
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get audit statistics."""
        with self.events_lock:
            total_events = len(self.events)
            
            if total_events == 0:
                return {"total_events": 0}
            
            # Count by severity
            severity_counts = {}
            for event in self.events:
                severity = event.severity.value
                severity_counts[severity] = severity_counts.get(severity, 0) + 1
            
            # Count by result
            result_counts = {}
            for event in self.events:
                result = event.result
                result_counts[result] = result_counts.get(result, 0) + 1
            
            # Recent activity (last hour)
            one_hour_ago = time.time() - 3600
            recent_events = [e for e in self.events if e.timestamp >= one_hour_ago]
            
            return {
                "total_events": total_events,
                "event_type_counts": self.event_counts.copy(),
                "severity_counts": severity_counts,
                "result_counts": result_counts,
                "recent_events_count": len(recent_events),
                "oldest_event_timestamp": min(e.timestamp for e in self.events),
                "newest_event_timestamp": max(e.timestamp for e in self.events)
            }
    
    def _write_to_file(self, event: AuditEvent):
        """Write audit event to file."""
        try:
            with open(self.log_file, "a") as f:
                f.write(json.dumps(event.to_dict()) + "\n")
                f.flush()  # Ensure immediate write
        except Exception as e:
            # Log to console if file writing fails
            print(f"Audit log file write error: {e}")
    
    def flush_to_file(self):
        """Flush any pending file operations."""
        # This method exists for API compatibility
        # File writes are already flushed in _write_to_file
        pass
    
    def _print_to_console(self, event: AuditEvent):
        """Print audit event to console."""
        timestamp_str = datetime.fromtimestamp(event.timestamp).strftime("%Y-%m-%d %H:%M:%S")
        severity_icon = {
            AuditSeverity.LOW: "ℹ️",
            AuditSeverity.MEDIUM: "[WARN]",
            AuditSeverity.HIGH: "🚨",
            AuditSeverity.CRITICAL: "💀"
        }.get(event.severity, "📝")
        
        print(f"{severity_icon} [{timestamp_str}] {event.event_type.value}: {event.result}")
        if event.principal:
            print(f"    Principal: {event.principal}")
        if event.agent_id:
            print(f"    Agent: {event.agent_id}")
        if event.resource:
            print(f"    Resource: {event.resource}")
        if event.details:
            print(f"    Details: {event.details}")

# Global audit logger instance
_audit_logger = None

def get_audit_logger() -> AuditLogger:
    """Get the global audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger(
            log_file="maple_security_audit.log",
            enable_console=False
        )
    return _audit_logger

def configure_audit_logger(log_file: Optional[str] = None, 
                          enable_console: bool = False,
                          max_events_memory: int = 1000):
    """Configure the global audit logger."""
    global _audit_logger
    _audit_logger = AuditLogger(
        log_file=log_file,
        enable_console=enable_console,
        max_events_memory=max_events_memory
    )
