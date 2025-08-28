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


# maple/security/authorization.py
# Creator: Mahesh Vaikri

"""
Authorization Manager for MAPLE
Provides role-based access control and permission management
"""

import time
import threading
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass
from enum import Enum
import logging

from ..core.result import Result

logger = logging.getLogger(__name__)

class Permission(Enum):
    """Standard permissions in MAPLE."""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"
    SEND_MESSAGE = "send_message"
    RECEIVE_MESSAGE = "receive_message"
    CREATE_LINK = "create_link"
    MANAGE_RESOURCES = "manage_resources"
    VIEW_STATS = "view_stats"

@dataclass
class Role:
    """Represents a role with permissions."""
    name: str
    permissions: Set[str]
    description: Optional[str] = None
    
    def has_permission(self, permission: str) -> bool:
        """Check if this role has a specific permission."""
        return permission in self.permissions or "admin" in self.permissions
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'name': self.name,
            'permissions': list(self.permissions),
            'description': self.description
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Role':
        """Create from dictionary."""
        return cls(
            name=data['name'],
            permissions=set(data.get('permissions', [])),
            description=data.get('description')
        )

@dataclass
class AccessPolicy:
    """Represents an access control policy."""
    resource_pattern: str  # Resource pattern (supports wildcards)
    required_permissions: Set[str]
    allowed_roles: Optional[Set[str]] = None
    denied_principals: Optional[Set[str]] = None
    
    def matches_resource(self, resource: str) -> bool:
        """Check if this policy applies to a resource."""
        if self.resource_pattern == "*":
            return True
        elif self.resource_pattern.endswith("*"):
            prefix = self.resource_pattern[:-1]
            return resource.startswith(prefix)
        else:
            return self.resource_pattern == resource
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'resource_pattern': self.resource_pattern,
            'required_permissions': list(self.required_permissions),
            'allowed_roles': list(self.allowed_roles) if self.allowed_roles else None,
            'denied_principals': list(self.denied_principals) if self.denied_principals else None
        }

class AuthorizationManager:
    """
    Handles authorization and access control for MAPLE agents.
    
    Features:
    - Role-based access control (RBAC)
    - Fine-grained permissions
    - Resource-based policies
    - Dynamic policy updates
    - Audit logging
    """
    
    def __init__(self, config=None):
        """
        Initialize the authorization manager.
        
        Args:
            config: Configuration object
        """
        self.config = config
        
        # Role and permission management
        self.roles: Dict[str, Role] = {}
        self.principal_roles: Dict[str, Set[str]] = {}  # principal -> roles
        self.policies: List[AccessPolicy] = []
        
        # Locks for thread safety
        self.roles_lock = threading.RLock()
        self.policies_lock = threading.RLock()
        
        # Statistics
        self.authz_stats = {
            'authorization_checks': 0,
            'access_granted': 0,
            'access_denied': 0,
            'policy_violations': 0
        }
        self.stats_lock = threading.RLock()
        
        # Initialize default roles
        self._create_default_roles()
        
        logger.info("AuthorizationManager initialized")
    
    def _create_default_roles(self) -> None:
        """Create default system roles."""
        default_roles = [
            Role(
                name="admin",
                permissions={p.value for p in Permission},
                description="Full administrative access"
            ),
            Role(
                name="agent",
                permissions={
                    Permission.READ.value,
                    Permission.WRITE.value,
                    Permission.SEND_MESSAGE.value,
                    Permission.RECEIVE_MESSAGE.value,
                    Permission.CREATE_LINK.value,
                    Permission.VIEW_STATS.value
                },
                description="Standard agent permissions"
            ),
            Role(
                name="readonly",
                permissions={
                    Permission.READ.value,
                    Permission.RECEIVE_MESSAGE.value,
                    Permission.VIEW_STATS.value
                },
                description="Read-only access"
            ),
            Role(
                name="guest",
                permissions={
                    Permission.READ.value
                },
                description="Minimal guest access"
            )
        ]
        
        with self.roles_lock:
            for role in default_roles:
                self.roles[role.name] = role
    
    def create_role(self, name: str, permissions: List[str], description: Optional[str] = None) -> Result[Role, Dict[str, Any]]:
        """
        Create a new role.
        
        Args:
            name: Role name
            permissions: List of permissions
            description: Optional role description
            
        Returns:
            Result containing the created role or error
        """
        try:
            # Validate permissions
            valid_permissions = {p.value for p in Permission}
            invalid_perms = set(permissions) - valid_permissions
            
            if invalid_perms:
                return Result.err({
                    'errorType': 'INVALID_PERMISSIONS',
                    'message': f'Invalid permissions: {invalid_perms}',
                    'details': {'invalid_permissions': list(invalid_perms)}
                })
            
            role = Role(
                name=name,
                permissions=set(permissions),
                description=description
            )
            
            with self.roles_lock:
                if name in self.roles:
                    return Result.err({
                        'errorType': 'ROLE_EXISTS',
                        'message': f'Role {name} already exists'
                    })
                
                self.roles[name] = role
            
            logger.info(f"Created role: {name} with permissions: {permissions}")
            return Result.ok(role)
            
        except Exception as e:
            return Result.err({
                'errorType': 'ROLE_CREATION_ERROR',
                'message': f'Failed to create role: {str(e)}'
            })
    
    def assign_role(self, principal: str, role_name: str) -> Result[None, Dict[str, Any]]:
        """
        Assign a role to a principal.
        
        Args:
            principal: Principal identifier (agent ID, user ID, etc.)
            role_name: Name of the role to assign
            
        Returns:
            Result indicating success or failure
        """
        try:
            with self.roles_lock:
                if role_name not in self.roles:
                    return Result.err({
                        'errorType': 'ROLE_NOT_FOUND',
                        'message': f'Role {role_name} does not exist'
                    })
                
                if principal not in self.principal_roles:
                    self.principal_roles[principal] = set()
                
                self.principal_roles[principal].add(role_name)
            
            logger.info(f"Assigned role {role_name} to principal {principal}")
            return Result.ok(None)
            
        except Exception as e:
            return Result.err({
                'errorType': 'ROLE_ASSIGNMENT_ERROR',
                'message': f'Failed to assign role: {str(e)}'
            })
    
    def revoke_role(self, principal: str, role_name: str) -> Result[None, Dict[str, Any]]:
        """
        Revoke a role from a principal.
        
        Args:
            principal: Principal identifier
            role_name: Name of the role to revoke
            
        Returns:
            Result indicating success or failure
        """
        try:
            with self.roles_lock:
                if principal in self.principal_roles:
                    self.principal_roles[principal].discard(role_name)
                    
                    # Remove principal if no roles left
                    if not self.principal_roles[principal]:
                        del self.principal_roles[principal]
            
            logger.info(f"Revoked role {role_name} from principal {principal}")
            return Result.ok(None)
            
        except Exception as e:
            return Result.err({
                'errorType': 'ROLE_REVOCATION_ERROR',
                'message': f'Failed to revoke role: {str(e)}'
            })
    
    def authorize(self, principal: str, action: str, resource: str) -> Result[bool, Dict[str, Any]]:
        """
        Check if a principal is authorized to perform an action on a resource.
        
        Args:
            principal: Principal requesting access
            action: Action to perform (maps to permission)
            resource: Resource being accessed
            
        Returns:
            Result indicating whether access is authorized
        """
        with self.stats_lock:
            self.authz_stats['authorization_checks'] += 1
        
        try:
            # Check if principal is explicitly denied
            if self._is_denied(principal, resource):
                with self.stats_lock:
                    self.authz_stats['access_denied'] += 1
                    self.authz_stats['policy_violations'] += 1
                
                return Result.ok(False)
            
            # Get principal's permissions
            principal_permissions = self._get_principal_permissions(principal)
            
            # Check if principal has required permission for action
            required_permission = self._action_to_permission(action)
            
            if required_permission in principal_permissions or "admin" in principal_permissions:
                # Check resource-specific policies
                if self._check_resource_policies(principal, required_permission, resource):
                    with self.stats_lock:
                        self.authz_stats['access_granted'] += 1
                    return Result.ok(True)
            
            with self.stats_lock:
                self.authz_stats['access_denied'] += 1
            
            return Result.ok(False)
            
        except Exception as e:
            return Result.err({
                'errorType': 'AUTHORIZATION_ERROR',
                'message': f'Authorization check failed: {str(e)}',
                'details': {
                    'principal': principal,
                    'action': action,
                    'resource': resource
                }
            })
    
    def authorize_message(self, message) -> Result[bool, Dict[str, Any]]:
        """
        Authorize a message for sending/receiving.
        
        Args:
            message: Message to authorize
            
        Returns:
            Result indicating authorization status
        """
        if not hasattr(message, 'sender') or not message.sender:
            return Result.err({
                'errorType': 'MISSING_SENDER',
                'message': 'Message has no sender specified'
            })
        
        # Check if sender can send messages
        send_result = self.authorize(
            principal=message.sender,
            action="send_message",
            resource=f"message:{message.message_type}"
        )
        
        if send_result.is_err() or not send_result.unwrap():
            return Result.ok(False)
        
        # Check if receiver can receive messages (if specified)
        if hasattr(message, 'receiver') and message.receiver:
            receive_result = self.authorize(
                principal=message.receiver,
                action="receive_message",
                resource=f"message:{message.message_type}"
            )
            
            if receive_result.is_err() or not receive_result.unwrap():
                return Result.ok(False)
        
        return Result.ok(True)
    
    def add_policy(self, policy: AccessPolicy) -> None:
        """
        Add an access control policy.
        
        Args:
            policy: Access policy to add
        """
        with self.policies_lock:
            self.policies.append(policy)
        
        logger.info(f"Added access policy for resource pattern: {policy.resource_pattern}")
    
    def remove_policy(self, resource_pattern: str) -> bool:
        """
        Remove access control policies for a resource pattern.
        
        Args:
            resource_pattern: Resource pattern to remove policies for
            
        Returns:
            True if any policies were removed
        """
        with self.policies_lock:
            original_count = len(self.policies)
            self.policies = [p for p in self.policies if p.resource_pattern != resource_pattern]
            removed = len(self.policies) < original_count
        
        if removed:
            logger.info(f"Removed access policies for resource pattern: {resource_pattern}")
        
        return removed
    
    def _get_principal_permissions(self, principal: str) -> Set[str]:
        """Get all permissions for a principal."""
        permissions = set()
        
        with self.roles_lock:
            principal_role_names = self.principal_roles.get(principal, set())
            
            for role_name in principal_role_names:
                if role_name in self.roles:
                    role = self.roles[role_name]
                    permissions.update(role.permissions)
        
        return permissions
    
    def _action_to_permission(self, action: str) -> str:
        """Map an action to a required permission."""
        action_map = {
            'read': Permission.READ.value,
            'write': Permission.WRITE.value,
            'delete': Permission.DELETE.value,
            'send_message': Permission.SEND_MESSAGE.value,
            'receive_message': Permission.RECEIVE_MESSAGE.value,
            'create_link': Permission.CREATE_LINK.value,
            'manage_resources': Permission.MANAGE_RESOURCES.value,
            'view_stats': Permission.VIEW_STATS.value,
            'admin': Permission.ADMIN.value
        }
        
        return action_map.get(action, action)  # Return action as-is if not mapped
    
    def _check_resource_policies(self, principal: str, permission: str, resource: str) -> bool:
        """Check resource-specific policies."""
        with self.policies_lock:
            for policy in self.policies:
                if policy.matches_resource(resource):
                    # Check if permission is required
                    if permission in policy.required_permissions:
                        # Check role restrictions
                        if policy.allowed_roles:
                            principal_roles = self.principal_roles.get(principal, set())
                            if not principal_roles.intersection(policy.allowed_roles):
                                return False
                        
                        # Check explicit denials
                        if policy.denied_principals and principal in policy.denied_principals:
                            return False
        
        return True
    
    def _is_denied(self, principal: str, resource: str) -> bool:
        """Check if principal is explicitly denied access to resource."""
        with self.policies_lock:
            for policy in self.policies:
                if (policy.matches_resource(resource) and 
                    policy.denied_principals and 
                    principal in policy.denied_principals):
                    return True
        
        return False
    
    def get_principal_roles(self, principal: str) -> List[str]:
        """Get roles assigned to a principal."""
        with self.roles_lock:
            return list(self.principal_roles.get(principal, set()))
    
    def get_principal_permissions(self, principal: str) -> List[str]:
        """Get all permissions for a principal."""
        return list(self._get_principal_permissions(principal))
    
    def list_roles(self) -> List[Dict[str, Any]]:
        """List all available roles."""
        with self.roles_lock:
            return [role.to_dict() for role in self.roles.values()]
    
    def list_policies(self) -> List[Dict[str, Any]]:
        """List all access control policies."""
        with self.policies_lock:
            return [policy.to_dict() for policy in self.policies]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get authorization statistics."""
        with self.stats_lock:
            stats = self.authz_stats.copy()
        
        with self.roles_lock:
            stats['total_roles'] = len(self.roles)
            stats['total_principals'] = len(self.principal_roles)
        
        with self.policies_lock:
            stats['total_policies'] = len(self.policies)
        
        return stats
