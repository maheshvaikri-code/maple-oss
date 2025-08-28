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


# maple/security/authentication.py
# Creator: Mahesh Vaikri

"""
Production Authentication Manager for MAPLE
Provides enterprise-grade authentication with multiple methods
"""

import time
import jwt
import base64
import hashlib
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass
from enum import Enum
import logging

from ..core.result import Result
from .cryptography_impl import CryptographyManager, CRYPTO_AVAILABLE

logger = logging.getLogger(__name__)

class AuthMethod(Enum):
    """Supported authentication methods."""
    JWT = "jwt"
    CERTIFICATE = "certificate"
    API_KEY = "api_key"
    MUTUAL_TLS = "mutual_tls"
    OAUTH2 = "oauth2"

@dataclass
class AuthCredentials:
    """Authentication credentials."""
    method: AuthMethod
    principal: str  # Agent ID or username
    credentials: Dict[str, Any]
    expires_at: Optional[float] = None
    metadata: Dict[str, Any] = None
    
    def is_expired(self) -> bool:
        """Check if credentials have expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

@dataclass
class AuthToken:
    """Authentication token."""
    token: str
    principal: str
    method: AuthMethod
    issued_at: float
    expires_at: Optional[float] = None
    permissions: list = None
    
    def is_valid(self) -> bool:
        """Check if token is still valid."""
        if self.expires_at is None:
            return True
        return time.time() < self.expires_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'token': self.token,
            'principal': self.principal,
            'method': self.method.value,
            'issued_at': self.issued_at,
            'expires_at': self.expires_at,
            'permissions': self.permissions or []
        }

class AuthenticationManager:
    """
    Production authentication manager for MAPLE agents.
    
    Features:
    - Multiple authentication methods (JWT, certificates, API keys)
    - Token lifecycle management
    - Credential validation and verification
    - Integration with cryptographic backend
    """
    
    def __init__(self, config=None):
        self.config = config
        self.crypto_manager = None
        self.active_tokens: Dict[str, AuthToken] = {}
        self.revoked_tokens: set = set()  # Track revoked tokens
        self.trusted_certificates: Dict[str, Any] = {}
        self.api_keys: Dict[str, Dict[str, Any]] = {}
        
        # Initialize cryptographic manager if available
        if CRYPTO_AVAILABLE:
            self.crypto_manager = CryptographyManager()
        
        # JWT configuration
        self.jwt_secret = getattr(config, 'jwt_secret', 'maple-default-secret-change-in-production')
        self.jwt_algorithm = getattr(config, 'jwt_algorithm', 'HS256')
        self.jwt_expiry = getattr(config, 'jwt_expiry_seconds', 3600)  # 1 hour default
        
        logger.info("Authentication manager initialized")
    
    def authenticate(self, credentials: Union[Dict[str, Any], AuthCredentials]) -> Result[AuthToken, Dict[str, Any]]:
        """
        Authenticate using provided credentials.
        
        Args:
            credentials: Authentication credentials
            
        Returns:
            Result containing AuthToken or error
        """
        try:
            # Convert dict to AuthCredentials if needed
            if isinstance(credentials, dict):
                method_str = credentials.get('method', 'jwt')
                try:
                    method = AuthMethod(method_str)
                except ValueError:
                    return Result.err({
                        'errorType': 'UNSUPPORTED_AUTH_METHOD',
                        'message': f'Unsupported authentication method: {method_str}'
                    })
                
                auth_creds = AuthCredentials(
                    method=method,
                    principal=credentials.get('principal', ''),
                    credentials=credentials,
                    expires_at=credentials.get('expires_at'),
                    metadata=credentials.get('metadata', {})
                )
            else:
                auth_creds = credentials
            
            # Check if credentials have expired
            if auth_creds.is_expired():
                return Result.err({
                    'errorType': 'CREDENTIALS_EXPIRED',
                    'message': 'Authentication credentials have expired'
                })
            
            # Route to appropriate authentication method
            if auth_creds.method == AuthMethod.JWT:
                return self._authenticate_jwt(auth_creds)
            elif auth_creds.method == AuthMethod.CERTIFICATE:
                return self._authenticate_certificate(auth_creds)
            elif auth_creds.method == AuthMethod.API_KEY:
                return self._authenticate_api_key(auth_creds)
            elif auth_creds.method == AuthMethod.MUTUAL_TLS:
                return self._authenticate_mutual_tls(auth_creds)
            elif auth_creds.method == AuthMethod.OAUTH2:
                return self._authenticate_oauth2(auth_creds)
            else:
                return Result.err({
                    'errorType': 'UNSUPPORTED_AUTH_METHOD',
                    'message': f'Authentication method not implemented: {auth_creds.method.value}'
                })
                
        except Exception as e:
            error = {
                'errorType': 'AUTHENTICATION_ERROR',
                'message': f'Authentication failed: {str(e)}'
            }
            logger.error(f"Authentication error: {error}")
            return Result.err(error)
    
    def _authenticate_jwt(self, creds: AuthCredentials) -> Result[AuthToken, Dict[str, Any]]:
        """Authenticate using JWT token."""
        try:
            token = creds.credentials.get('token')
            if not token:
                return Result.err({
                    'errorType': 'MISSING_JWT_TOKEN',
                    'message': 'JWT token is required'
                })
            
            # Verify and decode JWT
            try:
                payload = jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
            except jwt.ExpiredSignatureError:
                return Result.err({
                    'errorType': 'JWT_EXPIRED',
                    'message': 'JWT token has expired'
                })
            except jwt.InvalidTokenError as e:
                return Result.err({
                    'errorType': 'INVALID_JWT',
                    'message': f'Invalid JWT token: {str(e)}'
                })
            
            # Extract information from payload
            principal = payload.get('sub', creds.principal)
            permissions = payload.get('permissions', [])
            issued_at = payload.get('iat', time.time())
            expires_at = payload.get('exp')
            
            # Create auth token
            auth_token = AuthToken(
                token=token,
                principal=principal,
                method=AuthMethod.JWT,
                issued_at=issued_at,
                expires_at=expires_at,
                permissions=permissions
            )
            
            # Store active token
            self.active_tokens[token] = auth_token
            
            logger.info(f"JWT authentication successful for principal: {principal}")
            return Result.ok(auth_token)
            
        except Exception as e:
            return Result.err({
                'errorType': 'JWT_AUTHENTICATION_ERROR',
                'message': f'JWT authentication failed: {str(e)}'
            })
    
    def _authenticate_certificate(self, creds: AuthCredentials) -> Result[AuthToken, Dict[str, Any]]:
        """Authenticate using X.509 certificate."""
        if not self.crypto_manager:
            return Result.err({
                'errorType': 'CRYPTO_UNAVAILABLE',
                'message': 'Cryptographic functions not available'
            })
        
        try:
            certificate_pem = creds.credentials.get('certificate')
            if not certificate_pem:
                return Result.err({
                    'errorType': 'MISSING_CERTIFICATE',
                    'message': 'Certificate is required'
                })
            
            # In a real implementation, you would:
            # 1. Parse the certificate
            # 2. Verify it against trusted CA certificates
            # 3. Check validity dates
            # 4. Extract subject information
            
            # For now, simplified implementation
            # Parse certificate (this would be more complex in production)
            if certificate_pem in self.trusted_certificates:
                cert_info = self.trusted_certificates[certificate_pem]
                principal = cert_info.get('subject', creds.principal)
                permissions = cert_info.get('permissions', [])
                
                # Generate a session token
                session_token = base64.b64encode(
                    hashlib.sha256(f"{principal}:{time.time()}".encode()).digest()
                ).decode('utf-8')
                
                auth_token = AuthToken(
                    token=session_token,
                    principal=principal,
                    method=AuthMethod.CERTIFICATE,
                    issued_at=time.time(),
                    expires_at=time.time() + self.jwt_expiry,
                    permissions=permissions
                )
                
                self.active_tokens[session_token] = auth_token
                
                logger.info(f"Certificate authentication successful for principal: {principal}")
                return Result.ok(auth_token)
            else:
                return Result.err({
                    'errorType': 'UNTRUSTED_CERTIFICATE',
                    'message': 'Certificate is not trusted'
                })
                
        except Exception as e:
            return Result.err({
                'errorType': 'CERTIFICATE_AUTHENTICATION_ERROR',
                'message': f'Certificate authentication failed: {str(e)}'
            })
    
    def _authenticate_api_key(self, creds: AuthCredentials) -> Result[AuthToken, Dict[str, Any]]:
        """Authenticate using API key."""
        try:
            api_key = creds.credentials.get('api_key')
            if not api_key:
                return Result.err({
                    'errorType': 'MISSING_API_KEY',
                    'message': 'API key is required'
                })
            
            # Check if API key exists and is valid
            if api_key in self.api_keys:
                key_info = self.api_keys[api_key]
                
                # Check if key has expired
                if 'expires_at' in key_info and time.time() > key_info['expires_at']:
                    return Result.err({
                        'errorType': 'API_KEY_EXPIRED',
                        'message': 'API key has expired'
                    })
                
                principal = key_info.get('principal', creds.principal)
                permissions = key_info.get('permissions', [])
                
                # Generate session token
                session_token = base64.b64encode(
                    hashlib.sha256(f"{principal}:{api_key}:{time.time()}".encode()).digest()
                ).decode('utf-8')
                
                auth_token = AuthToken(
                    token=session_token,
                    principal=principal,
                    method=AuthMethod.API_KEY,
                    issued_at=time.time(),
                    expires_at=time.time() + self.jwt_expiry,
                    permissions=permissions
                )
                
                self.active_tokens[session_token] = auth_token
                
                logger.info(f"API key authentication successful for principal: {principal}")
                return Result.ok(auth_token)
            else:
                return Result.err({
                    'errorType': 'INVALID_API_KEY',
                    'message': 'API key is not valid'
                })
                
        except Exception as e:
            return Result.err({
                'errorType': 'API_KEY_AUTHENTICATION_ERROR',
                'message': f'API key authentication failed: {str(e)}'
            })
    
    def _authenticate_mutual_tls(self, creds: AuthCredentials) -> Result[AuthToken, Dict[str, Any]]:
        """Authenticate using mutual TLS."""
        return Result.err({
            'errorType': 'NOT_IMPLEMENTED',
            'message': 'Mutual TLS authentication not yet implemented'
        })
    
    def _authenticate_oauth2(self, creds: AuthCredentials) -> Result[AuthToken, Dict[str, Any]]:
        """Authenticate using OAuth2."""
        return Result.err({
            'errorType': 'NOT_IMPLEMENTED',
            'message': 'OAuth2 authentication not yet implemented'
        })
    
    def verify_token(self, token: str) -> Result[AuthToken, Dict[str, Any]]:
        """
        Verify an authentication token.
        
        Args:
            token: Token to verify
            
        Returns:
            Result containing AuthToken if valid or error
        """
        # Check if token has been revoked
        if token in self.revoked_tokens:
            return Result.err({
                'errorType': 'TOKEN_REVOKED',
                'message': 'Authentication token has been revoked'
            })
        
        # Check if token is in active tokens
        if token in self.active_tokens:
            auth_token = self.active_tokens[token]
            
            if auth_token.is_valid():
                return Result.ok(auth_token)
            else:
                # Remove expired token
                del self.active_tokens[token]
                return Result.err({
                    'errorType': 'TOKEN_EXPIRED',
                    'message': 'Authentication token has expired'
                })
        
        # Try to verify as JWT if not in active tokens
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
            
            auth_token = AuthToken(
                token=token,
                principal=payload.get('sub', ''),
                method=AuthMethod.JWT,
                issued_at=payload.get('iat', time.time()),
                expires_at=payload.get('exp'),
                permissions=payload.get('permissions', [])
            )
            
            if auth_token.is_valid():
                self.active_tokens[token] = auth_token
                return Result.ok(auth_token)
            else:
                return Result.err({
                    'errorType': 'TOKEN_EXPIRED',
                    'message': 'Authentication token has expired'
                })
                
        except jwt.InvalidTokenError:
            return Result.err({
                'errorType': 'INVALID_TOKEN',
                'message': 'Authentication token is not valid'
            })
    
    def verify_message_sender(self, message) -> Result[AuthToken, Dict[str, Any]]:
        """
        Verify that a message sender is authenticated.
        
        Args:
            message: The message to verify
            
        Returns:
            Result containing AuthToken or error
        """
        if not hasattr(message, 'metadata') or 'authToken' not in message.metadata:
            return Result.err({
                'errorType': 'MISSING_AUTH_TOKEN',
                'message': 'Message does not contain authentication token'
            })
        
        token = message.metadata['authToken']
        token_result = self.verify_token(token)
        
        if token_result.is_err():
            return token_result
        
        auth_token = token_result.unwrap()
        
        # Verify that the token principal matches the message sender
        if hasattr(message, 'sender') and message.sender != auth_token.principal:
            return Result.err({
                'errorType': 'SENDER_MISMATCH',
                'message': f'Message sender {message.sender} does not match token principal {auth_token.principal}'
            })
        
        return Result.ok(auth_token)
    
    def revoke_token(self, token: str) -> Result[None, Dict[str, Any]]:
        """Revoke an authentication token."""
        # Add to revocation list
        self.revoked_tokens.add(token)
        
        # Remove from active tokens if present
        if token in self.active_tokens:
            del self.active_tokens[token]
        
        logger.info(f"Token revoked: {token[:16]}...")
        return Result.ok(None)
    
    def generate_jwt(self, principal: str, permissions: list = None, expires_in: int = None) -> Result[str, Dict[str, Any]]:
        """
        Generate a JWT token for a principal.
        
        Args:
            principal: Principal (agent ID or username)
            permissions: List of permissions
            expires_in: Expiry time in seconds (uses default if None)
            
        Returns:
            Result containing JWT token or error
        """
        try:
            now = time.time()
            expires_in = expires_in or self.jwt_expiry
            
            payload = {
                'sub': principal,
                'iat': now,
                'exp': now + expires_in,
                'permissions': permissions or []
            }
            
            token = jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)
            
            # Store in active tokens
            auth_token = AuthToken(
                token=token,
                principal=principal,
                method=AuthMethod.JWT,
                issued_at=now,
                expires_at=now + expires_in,
                permissions=permissions
            )
            
            self.active_tokens[token] = auth_token
            
            logger.info(f"Generated JWT for principal: {principal}")
            return Result.ok(token)
            
        except Exception as e:
            error = {
                'errorType': 'JWT_GENERATION_ERROR',
                'message': f'Failed to generate JWT: {str(e)}'
            }
            logger.error(f"JWT generation error: {error}")
            return Result.err(error)
    
    def add_trusted_certificate(self, certificate_pem: str, principal: str, permissions: list = None) -> None:
        """Add a trusted certificate."""
        self.trusted_certificates[certificate_pem] = {
            'subject': principal,
            'permissions': permissions or [],
            'added_at': time.time()
        }
        logger.info(f"Added trusted certificate for principal: {principal}")
    
    def add_api_key(self, api_key: str, principal: str, permissions: list = None, expires_at: float = None) -> None:
        """Add an API key."""
        self.api_keys[api_key] = {
            'principal': principal,
            'permissions': permissions or [],
            'created_at': time.time(),
            'expires_at': expires_at
        }
        logger.info(f"Added API key for principal: {principal}")
    
    def cleanup_expired_tokens(self) -> int:
        """Remove expired tokens from active tokens."""
        expired_tokens = [
            token for token, auth_token in self.active_tokens.items()
            if not auth_token.is_valid()
        ]
        
        for token in expired_tokens:
            del self.active_tokens[token]
        
        if expired_tokens:
            logger.info(f"Cleaned up {len(expired_tokens)} expired tokens")
        
        return len(expired_tokens)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get authentication statistics."""
        active_count = len(self.active_tokens)
        expired_count = sum(1 for token in self.active_tokens.values() if not token.is_valid())
        
        return {
            'active_tokens': active_count,
            'expired_tokens': expired_count,
            'revoked_tokens': len(self.revoked_tokens),
            'trusted_certificates': len(self.trusted_certificates),
            'api_keys': len(self.api_keys),
            'supported_methods': [method.value for method in AuthMethod]
        }
