"""Tests for maple.security.authentication - AuthenticationManager."""

import pytest
import time
from maple.security.authentication import (
    AuthenticationManager, AuthMethod, AuthCredentials, AuthToken
)


@pytest.fixture
def auth():
    return AuthenticationManager()


class TestJWTAuthentication:
    """Test JWT token generation, verification, and revocation."""

    def test_generate_jwt(self, auth):
        result = auth.generate_jwt("agent_001", permissions=["read", "write"])
        assert result.is_ok()
        token = result.unwrap()
        assert isinstance(token, str)
        assert len(token) > 0

    def test_verify_jwt(self, auth):
        gen_result = auth.generate_jwt("agent_001")
        assert gen_result.is_ok()
        token = gen_result.unwrap()

        verify_result = auth.verify_token(token)
        assert verify_result.is_ok()
        auth_token = verify_result.unwrap()
        assert auth_token.principal == "agent_001"
        assert auth_token.method == AuthMethod.JWT

    def test_jwt_with_permissions(self, auth):
        perms = ["send", "receive", "admin"]
        gen_result = auth.generate_jwt("admin_agent", permissions=perms)
        token = gen_result.unwrap()

        verify_result = auth.verify_token(token)
        auth_token = verify_result.unwrap()
        assert auth_token.permissions == perms

    def test_jwt_expiry(self, auth):
        # Generate a token that expires in 1 second
        gen_result = auth.generate_jwt("agent_001", expires_in=1)
        assert gen_result.is_ok()
        token = gen_result.unwrap()

        # Should be valid immediately
        assert auth.verify_token(token).is_ok()

        # Wait for expiry
        time.sleep(1.5)

        # Should now fail
        result = auth.verify_token(token)
        assert result.is_err()

    def test_revoke_token(self, auth):
        gen_result = auth.generate_jwt("agent_001")
        token = gen_result.unwrap()

        # Should be valid
        assert auth.verify_token(token).is_ok()

        # Revoke
        revoke_result = auth.revoke_token(token)
        assert revoke_result.is_ok()

        # Should now fail
        result = auth.verify_token(token)
        assert result.is_err()
        assert result.unwrap_err()['errorType'] == 'TOKEN_REVOKED'

    def test_authenticate_with_jwt_dict(self, auth):
        gen_result = auth.generate_jwt("agent_001")
        token = gen_result.unwrap()

        creds = {
            'method': 'jwt',
            'principal': 'agent_001',
            'token': token
        }
        result = auth.authenticate(creds)
        assert result.is_ok()
        assert result.unwrap().principal == 'agent_001'

    def test_authenticate_invalid_jwt(self, auth):
        creds = {
            'method': 'jwt',
            'principal': 'agent_001',
            'token': 'invalid.jwt.token'
        }
        result = auth.authenticate(creds)
        assert result.is_err()

    def test_authenticate_missing_token(self, auth):
        creds = {'method': 'jwt', 'principal': 'agent_001'}
        result = auth.authenticate(creds)
        assert result.is_err()
        assert result.unwrap_err()['errorType'] == 'MISSING_JWT_TOKEN'


class TestAPIKeyAuthentication:
    """Test API key authentication."""

    def test_add_and_authenticate_api_key(self, auth):
        auth.add_api_key("test-key-123", principal="api_agent", permissions=["read"])

        creds = {
            'method': 'api_key',
            'principal': 'api_agent',
            'api_key': 'test-key-123'
        }
        result = auth.authenticate(creds)
        assert result.is_ok()
        assert result.unwrap().principal == 'api_agent'

    def test_invalid_api_key(self, auth):
        creds = {
            'method': 'api_key',
            'principal': 'agent',
            'api_key': 'nonexistent-key'
        }
        result = auth.authenticate(creds)
        assert result.is_err()
        assert result.unwrap_err()['errorType'] == 'INVALID_API_KEY'

    def test_missing_api_key(self, auth):
        creds = {'method': 'api_key', 'principal': 'agent'}
        result = auth.authenticate(creds)
        assert result.is_err()

    def test_expired_api_key(self, auth):
        auth.add_api_key("expired-key", principal="agent", expires_at=time.time() - 100)

        creds = {'method': 'api_key', 'principal': 'agent', 'api_key': 'expired-key'}
        result = auth.authenticate(creds)
        assert result.is_err()
        assert result.unwrap_err()['errorType'] == 'API_KEY_EXPIRED'


class TestAuthCredentials:
    """Test AuthCredentials dataclass."""

    def test_not_expired(self):
        creds = AuthCredentials(
            method=AuthMethod.JWT,
            principal="agent",
            credentials={},
            expires_at=time.time() + 3600
        )
        assert creds.is_expired() is False

    def test_expired(self):
        creds = AuthCredentials(
            method=AuthMethod.JWT,
            principal="agent",
            credentials={},
            expires_at=time.time() - 100
        )
        assert creds.is_expired() is True

    def test_no_expiry(self):
        creds = AuthCredentials(
            method=AuthMethod.JWT,
            principal="agent",
            credentials={}
        )
        assert creds.is_expired() is False


class TestAuthToken:
    """Test AuthToken dataclass."""

    def test_valid_token(self):
        token = AuthToken(
            token="abc",
            principal="agent",
            method=AuthMethod.JWT,
            issued_at=time.time(),
            expires_at=time.time() + 3600
        )
        assert token.is_valid() is True

    def test_expired_token(self):
        token = AuthToken(
            token="abc",
            principal="agent",
            method=AuthMethod.JWT,
            issued_at=time.time() - 7200,
            expires_at=time.time() - 3600
        )
        assert token.is_valid() is False

    def test_to_dict(self):
        token = AuthToken(
            token="abc",
            principal="agent",
            method=AuthMethod.JWT,
            issued_at=100.0,
            permissions=["read"]
        )
        d = token.to_dict()
        assert d['token'] == 'abc'
        assert d['principal'] == 'agent'
        assert d['method'] == 'jwt'
        assert d['permissions'] == ['read']


class TestAuthStatistics:
    """Test authentication statistics and cleanup."""

    def test_statistics(self, auth):
        auth.generate_jwt("agent1")
        auth.generate_jwt("agent2")
        auth.add_api_key("key1", "agent3")

        stats = auth.get_statistics()
        assert stats['active_tokens'] >= 2
        assert stats['api_keys'] == 1
        assert 'jwt' in stats['supported_methods']

    def test_cleanup_expired_tokens(self, auth):
        auth.generate_jwt("agent1", expires_in=1)
        time.sleep(1.5)
        cleaned = auth.cleanup_expired_tokens()
        assert cleaned >= 1

    def test_unsupported_auth_method(self, auth):
        creds = {'method': 'unknown_method', 'principal': 'agent'}
        result = auth.authenticate(creds)
        assert result.is_err()
