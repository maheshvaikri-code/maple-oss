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

# maple/security/__init__.py
# Creator: Mahesh Vaikri

"""
Security module for MAPLE providing authentication, authorization, and encryption.
"""

import time
from typing import Any, Dict, List, Optional

from ..core.result import Result

try:
    from .authentication import (
        AuthCredentials,
        AuthenticationManager,
        AuthMethod,
        AuthToken,
    )

    AUTH_AVAILABLE = True
except ImportError as e:  # pragma: no cover
    print(f"Warning: Authentication not fully available: {e}")
    AUTH_AVAILABLE = False

    # Provide fallback classes for testing
    class AuthMethod:  # type: ignore[no-redef]
        JWT = "jwt"

    class AuthToken:  # type: ignore[no-redef]
        def __init__(
            self,
            token: str,
            principal: str,
            method: Any,
            issued_at: float,
            expires_at: Optional[float] = None,
            permissions: Optional[List[str]] = None,
        ) -> None:
            self.token = token
            self.principal = principal
            self.method = method
            self.issued_at = issued_at
            self.expires_at = expires_at
            self.permissions = permissions or []

        def is_valid(self) -> bool:
            if self.expires_at is None:
                return True
            return time.time() < self.expires_at

    class AuthCredentials:  # type: ignore[no-redef]
        def __init__(
            self,
            method: Any,
            principal: str,
            credentials: Any,
            expires_at: Optional[float] = None,
            metadata: Optional[Dict[str, Any]] = None,
        ) -> None:
            self.method = method
            self.principal = principal
            self.credentials = credentials
            self.expires_at = expires_at
            self.metadata = metadata or {}

        def is_expired(self) -> bool:
            if self.expires_at is None:
                return False
            return time.time() > self.expires_at

    class AuthenticationManager:  # type: ignore[no-redef]
        def __init__(self, config: Any = None) -> None:
            self.active_tokens: Dict[str, AuthToken] = {}
            self.jwt_secret = "test-secret"
            self.jwt_expiry = 3600

        def generate_jwt(
            self,
            principal: str,
            permissions: Optional[List[str]] = None,
            expires_in: Optional[float] = None,
        ) -> Result[str, Dict[str, Any]]:
            token = f"test-jwt-{principal}-{int(time.time())}"
            expires_in = expires_in or self.jwt_expiry

            auth_token = AuthToken(
                token=token,
                principal=principal,
                method=AuthMethod.JWT,
                issued_at=time.time(),
                expires_at=time.time() + expires_in,
                permissions=permissions or [],
            )

            self.active_tokens[token] = auth_token
            return Result.ok(token)

        def verify_token(self, token: str) -> Result[Any, Dict[str, Any]]:
            if token in self.active_tokens:
                auth_token = self.active_tokens[token]
                if auth_token.is_valid():
                    return Result.ok(auth_token)
                else:
                    del self.active_tokens[token]
                    return Result.err(
                        {"errorType": "TOKEN_EXPIRED", "message": "Token has expired"}
                    )
            else:
                return Result.err(
                    {"errorType": "INVALID_TOKEN", "message": "Token not found"}
                )

        def revoke_token(self, token: str) -> Result[None, Dict[str, Any]]:
            if token in self.active_tokens:
                del self.active_tokens[token]
                return Result.ok(None)
            else:
                return Result.err(
                    {"errorType": "TOKEN_NOT_FOUND", "message": "Token not found"}
                )


try:
    from .authorization import AuthorizationManager

    AUTHZ_AVAILABLE = True
except ImportError:  # pragma: no cover
    AUTHZ_AVAILABLE = False

    class AuthorizationManager:  # type: ignore[no-redef]
        def authorize_message(self, message: Any) -> Result[bool, Dict[str, Any]]:
            return Result.ok(True)


try:
    from .link import Link, LinkManager, LinkState

    LINK_AVAILABLE = True
except ImportError:  # pragma: no cover
    LINK_AVAILABLE = False

    class LinkState:  # type: ignore[no-redef]
        INITIATING = "INITIATING"
        ESTABLISHED = "ESTABLISHED"
        TERMINATED = "TERMINATED"

    class Link:  # type: ignore[no-redef]
        def __init__(
            self, agent_a: str, agent_b: str, link_id: Optional[str] = None
        ) -> None:
            import uuid

            self.agent_a = agent_a
            self.agent_b = agent_b
            self.link_id = link_id or str(uuid.uuid4())
            self.state = LinkState.INITIATING

        def establish(self, lifetime_seconds: int = 3600) -> None:
            self.state = LinkState.ESTABLISHED

        def is_expired(self) -> bool:
            return False

    class LinkManager:  # type: ignore[no-redef]
        def __init__(self) -> None:
            self.links: Dict[str, Link] = {}

        def initiate_link(self, agent_a: str, agent_b: str) -> Link:
            link = Link(agent_a, agent_b)
            self.links[link.link_id] = link
            return link

        def establish_link(
            self, link_id: str, lifetime_seconds: int = 3600
        ) -> Result[Link, Dict[str, Any]]:
            if link_id in self.links:
                link = self.links[link_id]
                link.establish(lifetime_seconds)
                return Result.ok(link)
            else:
                return Result.err(
                    {"errorType": "UNKNOWN_LINK", "message": "Link not found"}
                )

        def validate_link(
            self, link_id: str, sender: str, receiver: str
        ) -> Result[Link, Dict[str, Any]]:
            if link_id in self.links:
                link = self.links[link_id]
                if link.state == LinkState.ESTABLISHED:
                    return Result.ok(link)

            return Result.err(
                {"errorType": "INVALID_LINK", "message": "Link validation failed"}
            )


try:
    from .separation import (
        GATE_RESULT,
        WORK_PACKAGE,
        ArtifactRef,
        SeparationOfDutiesPolicy,
        attach_to_config,
        fresh_context_verifier_preset,
        is_artifact_ref,
    )

    SEPARATION_AVAILABLE = True
except ImportError:  # pragma: no cover
    # No permissive fallback: separation of duties is a security guarantee,
    # so a failed import must surface loudly rather than silently allow sends.
    SEPARATION_AVAILABLE = False

__all__ = [
    "AuthenticationManager",
    "AuthMethod",
    "AuthCredentials",
    "AuthToken",
    "AuthorizationManager",
    "LinkManager",
    "Link",
    "LinkState",
    "SeparationOfDutiesPolicy",
    "ArtifactRef",
    "is_artifact_ref",
    "fresh_context_verifier_preset",
    "attach_to_config",
    "WORK_PACKAGE",
    "GATE_RESULT",
    "AUTH_AVAILABLE",
    "AUTHZ_AVAILABLE",
    "LINK_AVAILABLE",
    "SEPARATION_AVAILABLE",
]
