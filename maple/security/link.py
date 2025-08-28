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


# mapl/security/link.py

from typing import Dict, Any, Optional, Tuple
import time
import uuid
import logging
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from ..core.result import Result
from ..core.message import Message

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
        """Terminate the link."""
        self.state = LinkState.TERMINATED

class LinkManager:
    """Manages secure communication links between agents."""
    
    def __init__(self):
        self.links = {}  # Dictionary of link_id -> Link
        self.agent_links = {}  # Dictionary of agent_id -> set of link_ids
    
    def initiate_link(self, agent_a: str, agent_b: str) -> Link:
        """Initiate a new link between two agents."""
        link = Link(agent_a, agent_b)
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
        """Establish a link after successful handshake."""
        if link_id not in self.links:
            return Result.err({
                "errorType": "UNKNOWN_LINK",
                "message": f"Link {link_id} does not exist",
            })
        
        link = self.links[link_id]
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
        """Terminate a link."""
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
        """Get all links for an agent."""
        if agent_id not in self.agent_links:
            return Result.ok([])
        
        links = [self.links[link_id] for link_id in self.agent_links[agent_id] 
                if link_id in self.links and self.links[link_id].state == LinkState.ESTABLISHED]
        
        return Result.ok(links)