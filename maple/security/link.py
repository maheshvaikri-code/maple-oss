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


# maple/security/link.py

from typing import Dict, Any, Optional
import time
import uuid
import logging

from ..core.result import Result
from ..core.message import Message

try:
    from .cryptography_impl import CryptographyManager, CRYPTO_AVAILABLE
except ImportError:
    CRYPTO_AVAILABLE = False

logger = logging.getLogger(__name__)


class LinkState:
    """Possible states for a communication link."""
    INITIATING = "INITIATING"
    ESTABLISHED = "ESTABLISHED"
    DEGRADED = "DEGRADED"
    TERMINATED = "TERMINATED"


class Link:
    """Represents a secure communication link between two agents."""

    def __init__(self, agent_a: str, agent_b: str, link_id: str = None):
        self.agent_a = agent_a
        self.agent_b = agent_b
        self.link_id = link_id or f"link_{uuid.uuid4()}"
        self.state = LinkState.INITIATING
        self.established_at = None
        self.expires_at = None
        self.encryption_params = {}
        self.last_activity = time.time()

        # Cryptographic key material (populated during establish)
        self.shared_key: Optional[bytes] = None
        self._local_private_key = None
        self._local_public_key = None
        self._peer_public_key = None

    def establish(self, lifetime_seconds: int = 3600) -> None:
        """Mark the link as established."""
        self.state = LinkState.ESTABLISHED
        self.established_at = time.time()
        self.expires_at = self.established_at + lifetime_seconds

    def is_expired(self) -> bool:
        """Check if the link has expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    def terminate(self) -> None:
        """Terminate the link and wipe key material."""
        self.state = LinkState.TERMINATED
        self.shared_key = None
        self._local_private_key = None
        self._local_public_key = None
        self._peer_public_key = None


class LinkManager:
    """
    Manages secure communication links between agents.

    When the `cryptography` library is available, performs real ECDH key
    exchange to derive a shared secret for each link. Otherwise operates
    as a state-machine-only link manager.
    """

    def __init__(self):
        self.links: Dict[str, Link] = {}
        self.agent_links: Dict[str, set] = {}

        # Initialize crypto manager if available
        self._crypto: Optional[CryptographyManager] = None
        if CRYPTO_AVAILABLE:
            try:
                self._crypto = CryptographyManager()
                logger.info("LinkManager initialized with real ECDH key exchange")
            except Exception as e:
                logger.warning(f"CryptographyManager init failed: {e}")

    @property
    def has_real_crypto(self) -> bool:
        """Whether real cryptographic key exchange is available."""
        return self._crypto is not None

    def initiate_link(self, agent_a: str, agent_b: str) -> Link:
        """Initiate a new link between two agents."""
        link = Link(agent_a, agent_b)

        # Generate ephemeral ECDH key pair for this link
        if self._crypto:
            kp_result = self._crypto.generate_key_pair("ECDSA_P256")
            if kp_result.is_ok():
                kp = kp_result.unwrap()
                link._local_private_key = kp.private_key
                link._local_public_key = kp.public_key
                link.encryption_params['key_type'] = 'ECDH_P256'

        self.links[link.link_id] = link

        # Track which links each agent participates in
        if agent_a not in self.agent_links:
            self.agent_links[agent_a] = set()
        if agent_b not in self.agent_links:
            self.agent_links[agent_b] = set()

        self.agent_links[agent_a].add(link.link_id)
        self.agent_links[agent_b].add(link.link_id)

        logger.info(f"Initiated link {link.link_id} between {agent_a} and {agent_b}")
        return link

    def establish_link(self, link_id: str, lifetime_seconds: int = 3600) -> Result[Link, Dict[str, Any]]:
        """
        Establish a link after successful handshake.

        When crypto is available, generates a peer ECDH key pair and derives
        a shared secret via HKDF so that messages over this link can be
        encrypted with a symmetric key.
        """
        if link_id not in self.links:
            return Result.err({
                "errorType": "UNKNOWN_LINK",
                "message": f"Link {link_id} does not exist",
            })

        link = self.links[link_id]

        # Perform ECDH key exchange if crypto is available
        if self._crypto and link._local_private_key is not None:
            # In a real distributed system, the peer public key would come
            # from the other agent over the wire. Here we simulate the full
            # handshake by generating the peer side locally.
            peer_kp_result = self._crypto.generate_key_pair("ECDSA_P256")
            if peer_kp_result.is_ok():
                peer_kp = peer_kp_result.unwrap()
                link._peer_public_key = peer_kp.public_key

                # Derive shared secret
                secret_result = self._crypto.derive_shared_secret(
                    link._local_private_key, peer_kp.public_key
                )
                if secret_result.is_ok():
                    link.shared_key = secret_result.unwrap()
                    link.encryption_params['has_shared_key'] = True
                    logger.info(f"ECDH key exchange completed for link {link_id}")
                else:
                    logger.warning(f"Key derivation failed for link {link_id}: {secret_result.unwrap_err()}")

        link.establish(lifetime_seconds)

        logger.info(f"Established link {link_id} between {link.agent_a} and {link.agent_b}")
        return Result.ok(link)

    def validate_link(self, link_id: str, sender: str, receiver: str) -> Result[Link, Dict[str, Any]]:
        """Validate a link for a message exchange."""
        if link_id not in self.links:
            return Result.err({
                "errorType": "INVALID_LINK",
                "message": f"Link {link_id} does not exist",
            })

        link = self.links[link_id]

        # Check if link is in correct state
        if link.state != LinkState.ESTABLISHED:
            return Result.err({
                "errorType": "LINK_NOT_ESTABLISHED",
                "message": f"Link {link_id} is in state {link.state}, not ESTABLISHED",
            })

        # Check if link has expired
        if link.is_expired():
            link.state = LinkState.TERMINATED
            return Result.err({
                "errorType": "EXPIRED_LINK",
                "message": f"Link {link_id} has expired",
            })

        # Check if sender and receiver are part of this link
        if (sender != link.agent_a and sender != link.agent_b) or \
           (receiver != link.agent_a and receiver != link.agent_b):
            return Result.err({
                "errorType": "UNAUTHORIZED_LINK_USAGE",
                "message": f"Agents {sender} and {receiver} are not authorized to use link {link_id}",
            })

        # Update last activity
        link.last_activity = time.time()

        return Result.ok(link)

    def terminate_link(self, link_id: str) -> Result[None, Dict[str, Any]]:
        """Terminate a link and wipe its key material."""
        if link_id not in self.links:
            return Result.err({
                "errorType": "UNKNOWN_LINK",
                "message": f"Link {link_id} does not exist",
            })

        link = self.links[link_id]
        link.terminate()

        logger.info(f"Terminated link {link_id} between {link.agent_a} and {link.agent_b}")
        return Result.ok(None)

    def get_links_for_agent(self, agent_id: str) -> Result[list, Dict[str, Any]]:
        """Get all established links for an agent."""
        if agent_id not in self.agent_links:
            return Result.ok([])

        links = [
            self.links[link_id]
            for link_id in self.agent_links[agent_id]
            if link_id in self.links and self.links[link_id].state == LinkState.ESTABLISHED
        ]

        return Result.ok(links)
