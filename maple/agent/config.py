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


# mapl/agent/config.py
# Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from ..core.types import Priority

@dataclass
class LinkConfig:
    """Configuration for link management."""
    enabled: bool = True
    default_lifetime: int = 3600  # Default link lifetime in seconds
    auto_establish: bool = True  # Automatically establish links when needed
    rekey_interval: int = 3600  # How often to refresh link keys (seconds)

@dataclass
class SecurityConfig:
    """Security configuration for an agent."""
    auth_type: str
    credentials: str
    public_key: Optional[str] = None  # Public key for link establishment
    private_key: Optional[str] = None  # Private key for link establishment
    permissions: Optional[List[Dict[str, Any]]] = None
    require_links: bool = False  # Whether links are required for communication
    strict_link_policy: bool = False  # Whether to reject messages without links
    link_config: Optional[LinkConfig] = None  # Link configuration

@dataclass
class PerformanceConfig:
    """Performance configuration for an agent."""
    connection_pool_size: int = 10
    max_concurrent_requests: int = 50
    serialization_format: str = "json"
    batch_size: int = 10
    batch_timeout: str = "100ms"

@dataclass
class MetricsConfig:
    """Metrics configuration for an agent."""
    enabled: bool = False
    exporter: Optional[str] = None
    endpoint: Optional[str] = None

@dataclass
class TracingConfig:
    """Tracing configuration for an agent."""
    enabled: bool = False
    sampling_rate: float = 0.1
    exporter: Optional[str] = None
    endpoint: Optional[str] = None

@dataclass
class Config:
    """Configuration for an agent."""
    agent_id: str
    broker_url: str
    security: Optional[SecurityConfig] = None
    performance: Optional[PerformanceConfig] = None
    metrics: Optional[MetricsConfig] = None
    tracing: Optional[TracingConfig] = None