"""
Copyright (C) 2025 Mahesh Vaijainthymala Krishnamoorthy
(Mahesh Vaikri)

This file is part of MAPLE - Multi Agent Protocol Language Engine.

MAPLE - Multi Agent Protocol Language Engine is free software: you can
redistribute it and/or modify it under the terms of the GNU Affero General
Public License as published by the Free Software Foundation, either version 3
of the License, or (at your option) any later version.
MAPLE - Multi Agent Protocol Language Engine is distributed in the hope that
it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty
of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero
General Public License for more details. You should have received a copy of
the GNU Affero General Public License along with MAPLE - Multi Agent Protocol
Language Engine. If not, see <https://www.gnu.org/licenses/>.
"""

# mapl/agent/config.py
# Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..error.types import ConfigurationError


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
    # Optional SeparationOfDutiesPolicy (maple.security.separation). Typed as
    # Any to keep this module free of a security-layer import. When set, the
    # broker enforces its sender allowlist + artifact-ref-only payload policy.
    separation_policy: Optional[Any] = None


@dataclass
class PerformanceConfig:
    """Performance configuration for an agent."""

    connection_pool_size: int = 10
    max_concurrent_requests: int = 50
    # Broker admission limits (ADR-159). Process-wide: the in-memory broker is
    # a process-wide singleton, so these bound the process, not one agent.
    max_queue_size: int = 10000
    max_message_bytes: int = 1_048_576  # matches core/serialization.py limits
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
    capabilities: List[str] = field(default_factory=list)
    security: Optional[SecurityConfig] = None
    performance: Optional[PerformanceConfig] = None
    metrics: Optional[MetricsConfig] = None
    tracing: Optional[TracingConfig] = None

    #: Transports MAPLE can actually build, lowercased. Kept beside the
    #: validation that uses it; a test pins it against the schemes
    #: ``Agent._create_broker`` dispatches on, so the two cannot drift.
    KNOWN_SCHEMES = ("memory", "nats", "s2")

    #: Bounds that must be positive integers. A non-positive value here does
    #: not degrade behaviour, it removes it: max_queue_size=-5 makes every
    #: send fail QUEUE_FULL (ADR-164).
    _POSITIVE_INTS = (
        "connection_pool_size",
        "max_concurrent_requests",
        "max_queue_size",
        "max_message_bytes",
        "batch_size",
    )

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Refuse configuration that cannot produce a working agent.

        Raises ``ConfigurationError`` (a ``ValueError``) at construction, so
        the mistake is reported where it was made rather than surfacing later
        as an unrelated symptom — an ``Ok`` send that never arrives, or a
        ``QUEUE_FULL`` with no full queue (ADR-164).
        """
        self._validate_agent_id()
        self._validate_broker_url()
        self._validate_performance()

    def _validate_agent_id(self) -> None:
        if not isinstance(self.agent_id, str):
            raise ConfigurationError(
                "agent_id",
                "agent_id must be a string, not " f"{type(self.agent_id).__name__}.",
                received=repr(self.agent_id),
            )
        if not self.agent_id.strip():
            raise ConfigurationError(
                "agent_id",
                "agent_id must not be empty: an agent with no id is "
                "unroutable, so every send to it returns Ok and delivers "
                "nothing.",
                received=repr(self.agent_id),
            )

    def _validate_broker_url(self) -> None:
        if not isinstance(self.broker_url, str):
            raise ConfigurationError(
                "broker_url",
                "broker_url must be a string, not "
                f"{type(self.broker_url).__name__}.",
                received=repr(self.broker_url),
            )
        url = self.broker_url.strip()
        if not url:
            raise ConfigurationError(
                "broker_url",
                "broker_url must not be empty. Use 'memory://<scope>' for the "
                "in-process broker.",
                supportedSchemes=list(self.KNOWN_SCHEMES),
            )

        prefix = url.split(":", 1)[0].lower() if ":" in url else ""

        # 1. A name MAPLE recognises must be spelled as a URL. Matching is
        #    case-insensitive because _create_broker's startswith("nats://")
        #    misses NATS:// entirely and falls back to in-process - which is
        #    precisely the silent downgrade ADR-157 refuses.
        if prefix in self.KNOWN_SCHEMES:
            if not url.lower().startswith(prefix + "://"):
                raise ConfigurationError(
                    "broker_url",
                    f"broker_url names the {prefix!r} transport but is not a "
                    f"URL. Use '{prefix}://<host>'. As written it would fall "
                    "back to the in-process broker and every message would "
                    "stay local.",
                    received=self.broker_url,
                )
            return

        # 2. Scheme-shaped, but not a transport MAPLE has.
        if "://" in url:
            raise ConfigurationError(
                "broker_url",
                f"Unsupported broker scheme {prefix!r}. MAPLE would fall back "
                "to the in-process broker and every message would stay local.",
                received=self.broker_url,
                supportedSchemes=list(self.KNOWN_SCHEMES),
            )

        # 3. No scheme at all - in-process, exactly as before. 'localhost:8080'
        #    and bare names keep working; nobody types those believing they
        #    configured a cluster.

    def _validate_performance(self) -> None:
        if self.performance is None:
            return
        for name in self._POSITIVE_INTS:
            value = getattr(self.performance, name, None)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, int):
                raise ConfigurationError(
                    f"performance.{name}",
                    f"{name} must be an integer, not " f"{type(value).__name__}.",
                    received=repr(value),
                )
            if value < 1:
                raise ConfigurationError(
                    f"performance.{name}",
                    f"{name} must be at least 1; {value} does not limit "
                    "anything, it disables it.",
                    received=value,
                )
