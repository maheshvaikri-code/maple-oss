"""Tests for maple.security.authorization - AuthorizationManager."""

import pytest
from unittest.mock import MagicMock
from maple.security.authorization import (
    AuthorizationManager, Permission, Role, AccessPolicy
)


@pytest.fixture
def authz():
    return AuthorizationManager()


class TestPermissionEnum:
    """Test Permission enum values."""

    def test_all_permissions_exist(self):
        assert Permission.READ.value == "read"
        assert Permission.WRITE.value == "write"
        assert Permission.DELETE.value == "delete"
        assert Permission.ADMIN.value == "admin"
        assert Permission.SEND_MESSAGE.value == "send_message"
        assert Permission.RECEIVE_MESSAGE.value == "receive_message"
        assert Permission.CREATE_LINK.value == "create_link"
        assert Permission.MANAGE_RESOURCES.value == "manage_resources"
        assert Permission.VIEW_STATS.value == "view_stats"


class TestRole:
    """Test Role dataclass."""

    def test_create_role(self):
        role = Role(name="test", permissions={"read", "write"}, description="Test role")
        assert role.name == "test"
        assert "read" in role.permissions
        assert role.description == "Test role"

    def test_has_permission(self):
        role = Role(name="test", permissions={"read", "write"})
        assert role.has_permission("read") is True
        assert role.has_permission("delete") is False

    def test_admin_has_all_permissions(self):
        role = Role(name="admin", permissions={"admin"})
        assert role.has_permission("read") is True
        assert role.has_permission("write") is True
        assert role.has_permission("anything") is True

    def test_to_dict(self):
        role = Role(name="test", permissions={"read"}, description="desc")
        d = role.to_dict()
        assert d['name'] == "test"
        assert "read" in d['permissions']
        assert d['description'] == "desc"

    def test_from_dict(self):
        data = {'name': 'test', 'permissions': ['read', 'write'], 'description': 'desc'}
        role = Role.from_dict(data)
        assert role.name == "test"
        assert "read" in role.permissions
        assert "write" in role.permissions

    def test_from_dict_no_description(self):
        data = {'name': 'test', 'permissions': ['read']}
        role = Role.from_dict(data)
        assert role.description is None

    def test_roundtrip(self):
        original = Role(name="dev", permissions={"read", "write", "send_message"}, description="Developer")
        restored = Role.from_dict(original.to_dict())
        assert restored.name == original.name
        assert restored.permissions == original.permissions
        assert restored.description == original.description


class TestAccessPolicy:
    """Test AccessPolicy dataclass."""

    def test_exact_match(self):
        policy = AccessPolicy(resource_pattern="messages:alerts", required_permissions={"read"})
        assert policy.matches_resource("messages:alerts") is True
        assert policy.matches_resource("messages:other") is False

    def test_wildcard_match(self):
        policy = AccessPolicy(resource_pattern="*", required_permissions={"read"})
        assert policy.matches_resource("anything") is True

    def test_prefix_wildcard(self):
        policy = AccessPolicy(resource_pattern="messages:*", required_permissions={"read"})
        assert policy.matches_resource("messages:alerts") is True
        assert policy.matches_resource("messages:other") is True
        assert policy.matches_resource("tasks:other") is False

    def test_to_dict(self):
        policy = AccessPolicy(
            resource_pattern="test:*",
            required_permissions={"read"},
            allowed_roles={"admin"},
            denied_principals={"bad_agent"}
        )
        d = policy.to_dict()
        assert d['resource_pattern'] == "test:*"
        assert "read" in d['required_permissions']
        assert "admin" in d['allowed_roles']
        assert "bad_agent" in d['denied_principals']

    def test_to_dict_none_optionals(self):
        policy = AccessPolicy(resource_pattern="test", required_permissions={"read"})
        d = policy.to_dict()
        assert d['allowed_roles'] is None
        assert d['denied_principals'] is None


class TestDefaultRoles:
    """Test that default roles are created."""

    def test_admin_role_exists(self, authz):
        roles = authz.list_roles()
        names = [r['name'] for r in roles]
        assert "admin" in names

    def test_agent_role_exists(self, authz):
        roles = authz.list_roles()
        names = [r['name'] for r in roles]
        assert "agent" in names

    def test_readonly_role_exists(self, authz):
        roles = authz.list_roles()
        names = [r['name'] for r in roles]
        assert "readonly" in names

    def test_guest_role_exists(self, authz):
        roles = authz.list_roles()
        names = [r['name'] for r in roles]
        assert "guest" in names

    def test_admin_has_all_permissions(self, authz):
        roles = {r['name']: r for r in authz.list_roles()}
        admin_perms = set(roles['admin']['permissions'])
        all_perms = {p.value for p in Permission}
        assert admin_perms == all_perms


class TestCreateRole:
    """Test role creation."""

    def test_create_role(self, authz):
        result = authz.create_role("developer", ["read", "write", "send_message"], "Dev role")
        assert result.is_ok()
        role = result.unwrap()
        assert role.name == "developer"

    def test_create_duplicate_role(self, authz):
        authz.create_role("custom", ["read"])
        result = authz.create_role("custom", ["write"])
        assert result.is_err()
        assert result.unwrap_err()['errorType'] == 'ROLE_EXISTS'

    def test_create_role_invalid_permissions(self, authz):
        result = authz.create_role("bad", ["nonexistent_perm"])
        assert result.is_err()
        assert result.unwrap_err()['errorType'] == 'INVALID_PERMISSIONS'

    def test_create_existing_default_role_fails(self, authz):
        result = authz.create_role("admin", ["read"])
        assert result.is_err()
        assert result.unwrap_err()['errorType'] == 'ROLE_EXISTS'


class TestRoleAssignment:
    """Test role assignment and revocation."""

    def test_assign_role(self, authz):
        result = authz.assign_role("agent_1", "agent")
        assert result.is_ok()
        roles = authz.get_principal_roles("agent_1")
        assert "agent" in roles

    def test_assign_nonexistent_role(self, authz):
        result = authz.assign_role("agent_1", "nonexistent")
        assert result.is_err()
        assert result.unwrap_err()['errorType'] == 'ROLE_NOT_FOUND'

    def test_assign_multiple_roles(self, authz):
        authz.assign_role("agent_1", "agent")
        authz.assign_role("agent_1", "readonly")
        roles = authz.get_principal_roles("agent_1")
        assert "agent" in roles
        assert "readonly" in roles

    def test_revoke_role(self, authz):
        authz.assign_role("agent_1", "agent")
        result = authz.revoke_role("agent_1", "agent")
        assert result.is_ok()
        roles = authz.get_principal_roles("agent_1")
        assert "agent" not in roles

    def test_revoke_cleans_up_empty_principal(self, authz):
        authz.assign_role("agent_1", "agent")
        authz.revoke_role("agent_1", "agent")
        assert "agent_1" not in authz.principal_roles

    def test_revoke_nonexistent_principal(self, authz):
        result = authz.revoke_role("nobody", "agent")
        assert result.is_ok()  # No error, just a no-op


class TestGetPrincipalPermissions:
    """Test permission retrieval."""

    def test_no_roles_no_permissions(self, authz):
        perms = authz.get_principal_permissions("unknown")
        assert perms == []

    def test_agent_permissions(self, authz):
        authz.assign_role("agent_1", "agent")
        perms = authz.get_principal_permissions("agent_1")
        assert "read" in perms
        assert "write" in perms
        assert "send_message" in perms
        assert "delete" not in perms

    def test_admin_permissions(self, authz):
        authz.assign_role("admin_1", "admin")
        perms = authz.get_principal_permissions("admin_1")
        assert "admin" in perms
        assert "read" in perms


class TestAuthorize:
    """Test authorization checks."""

    def test_authorized_with_role(self, authz):
        authz.assign_role("agent_1", "agent")
        result = authz.authorize("agent_1", "read", "data:test")
        assert result.is_ok()
        assert result.unwrap() is True

    def test_unauthorized_no_role(self, authz):
        result = authz.authorize("nobody", "read", "data:test")
        assert result.is_ok()
        assert result.unwrap() is False

    def test_unauthorized_wrong_permission(self, authz):
        authz.assign_role("agent_1", "guest")
        result = authz.authorize("agent_1", "delete", "data:test")
        assert result.is_ok()
        assert result.unwrap() is False

    def test_admin_authorized_for_anything(self, authz):
        authz.assign_role("admin_1", "admin")
        result = authz.authorize("admin_1", "delete", "any:resource")
        assert result.is_ok()
        assert result.unwrap() is True

    def test_denied_principal(self, authz):
        authz.assign_role("bad_agent", "agent")
        policy = AccessPolicy(
            resource_pattern="*",
            required_permissions={"read"},
            denied_principals={"bad_agent"}
        )
        authz.add_policy(policy)
        result = authz.authorize("bad_agent", "read", "data:test")
        assert result.is_ok()
        assert result.unwrap() is False

    def test_policy_role_restriction(self, authz):
        authz.assign_role("agent_1", "agent")
        policy = AccessPolicy(
            resource_pattern="admin:*",
            required_permissions={"read"},
            allowed_roles={"admin"}
        )
        authz.add_policy(policy)
        result = authz.authorize("agent_1", "read", "admin:settings")
        assert result.is_ok()
        assert result.unwrap() is False


class TestAuthorizeMessage:
    """Test message authorization."""

    def test_no_sender_fails(self, authz):
        msg = MagicMock()
        msg.sender = None
        result = authz.authorize_message(msg)
        assert result.is_err()
        assert result.unwrap_err()['errorType'] == 'MISSING_SENDER'

    def test_authorized_sender(self, authz):
        authz.assign_role("agent_1", "agent")
        authz.assign_role("agent_2", "agent")
        msg = MagicMock()
        msg.sender = "agent_1"
        msg.receiver = "agent_2"
        msg.message_type = "TASK"
        result = authz.authorize_message(msg)
        assert result.is_ok()
        assert result.unwrap() is True

    def test_unauthorized_sender(self, authz):
        msg = MagicMock()
        msg.sender = "nobody"
        msg.receiver = "agent_2"
        msg.message_type = "TASK"
        result = authz.authorize_message(msg)
        assert result.is_ok()
        assert result.unwrap() is False


class TestPolicyManagement:
    """Test policy add/remove/list."""

    def test_add_policy(self, authz):
        policy = AccessPolicy(resource_pattern="test:*", required_permissions={"read"})
        authz.add_policy(policy)
        policies = authz.list_policies()
        assert len(policies) == 1

    def test_remove_policy(self, authz):
        policy = AccessPolicy(resource_pattern="test:*", required_permissions={"read"})
        authz.add_policy(policy)
        removed = authz.remove_policy("test:*")
        assert removed is True
        assert len(authz.list_policies()) == 0

    def test_remove_nonexistent_policy(self, authz):
        removed = authz.remove_policy("nonexistent")
        assert removed is False

    def test_list_policies(self, authz):
        authz.add_policy(AccessPolicy(resource_pattern="a:*", required_permissions={"read"}))
        authz.add_policy(AccessPolicy(resource_pattern="b:*", required_permissions={"write"}))
        policies = authz.list_policies()
        assert len(policies) == 2


class TestStatistics:
    """Test authorization statistics."""

    def test_initial_stats(self, authz):
        stats = authz.get_statistics()
        assert stats['authorization_checks'] == 0
        assert stats['access_granted'] == 0
        assert stats['access_denied'] == 0
        assert stats['total_roles'] >= 4  # default roles

    def test_stats_after_checks(self, authz):
        authz.assign_role("agent_1", "agent")
        authz.authorize("agent_1", "read", "data:test")
        authz.authorize("nobody", "read", "data:test")
        stats = authz.get_statistics()
        assert stats['authorization_checks'] == 2
        assert stats['access_granted'] >= 1
        assert stats['access_denied'] >= 1

    def test_stats_counts_principals(self, authz):
        authz.assign_role("a1", "agent")
        authz.assign_role("a2", "agent")
        stats = authz.get_statistics()
        assert stats['total_principals'] == 2

    def test_stats_counts_policies(self, authz):
        authz.add_policy(AccessPolicy(resource_pattern="*", required_permissions={"read"}))
        stats = authz.get_statistics()
        assert stats['total_policies'] == 1
