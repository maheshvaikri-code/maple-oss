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


# maple/__init__.py
# Creator: Mahesh Vaikri

"""
MAPLE: Multi Agent Protocol Language Engine

A comprehensive framework for communication between autonomous agents in complex AI systems.
Creator: Mahesh Vaikri
"""

__version__ = "1.0.0"
__author__ = "Mahesh Vaikri"
__email__ = "mahesh.vaikri@example.com"
__license__ = "AGPL 3.0"

# Core imports - always available
try:
    from .core.types import Priority, Size, Duration, Boolean, Integer, String, AgentID, MessageID
    from .core.message import Message
    from .core.result import Result
    CORE_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Core modules not available: {e}")
    CORE_AVAILABLE = False

# Serialization (optional)
try:
    from .core.serialization import Serializer
    SERIALIZATION_AVAILABLE = True
except ImportError:
    SERIALIZATION_AVAILABLE = False
    Serializer = None

# Agent and configuration
try:
    from .agent.config import Config, SecurityConfig, PerformanceConfig, MetricsConfig, TracingConfig, LinkConfig
    from .agent.agent import Agent
    AGENT_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Agent modules not available: {e}")
    AGENT_AVAILABLE = False

# Broker systems
try:
    from .broker.broker import MessageBroker
    from .broker.production_broker import ProductionBrokerManager, BrokerType, create_production_broker
    BROKER_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Broker modules not available: {e}")
    BROKER_AVAILABLE = False

# Error handling
try:
    from .error.types import Error, Severity, ErrorType
    from .error.recovery import retry, RetryOptions, exponential_backoff
    from .error.circuit_breaker import CircuitBreaker, CircuitState
    ERROR_HANDLING_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Error handling modules not available: {e}")
    ERROR_HANDLING_AVAILABLE = False

# Resource management
try:
    from .resources.specification import ResourceRequest, ResourceRange, TimeConstraint
    from .resources.manager import ResourceManager, ResourceAllocation
    from .resources.negotiation import ResourceNegotiator
    RESOURCE_MANAGEMENT_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Resource management modules not available: {e}")
    RESOURCE_MANAGEMENT_AVAILABLE = False

# Communication patterns (optional)
try:
    from .communication.streaming import Stream, StreamOptions
    STREAMING_AVAILABLE = True
except ImportError:
    STREAMING_AVAILABLE = False
    Stream = None
    StreamOptions = None

try:
    from .communication.request_response import RequestResponsePattern
    REQUEST_RESPONSE_AVAILABLE = True
except ImportError:
    REQUEST_RESPONSE_AVAILABLE = False
    RequestResponsePattern = None

try:
    from .communication.pubsub import PublishSubscribePattern
    PUBSUB_AVAILABLE = True
except ImportError:
    PUBSUB_AVAILABLE = False
    PublishSubscribePattern = None

# Security (with fallbacks from our __init__.py)
try:
    from .security import (
        AuthenticationManager, AuthMethod, AuthCredentials, AuthToken,
        AuthorizationManager, LinkManager, Link, LinkState
    )
    SECURITY_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Security modules not fully available: {e}")
    SECURITY_AVAILABLE = False

# Security audit (optional)
try:
    from .security.audit import AuditLogger, AuditEvent, AuditEventType, AuditSeverity, get_audit_logger
    AUDIT_AVAILABLE = True
except ImportError:
    AUDIT_AVAILABLE = False
    AuditLogger = None
    AuditEvent = None
    AuditEventType = None
    AuditSeverity = None
    get_audit_logger = None

# Optional imports with graceful fallbacks

# NATS broker (optional)
try:
    from .broker.nats_broker import NATSBroker, NATSBrokerSync, NATSConfig
    _NATS_AVAILABLE = True
except ImportError:
    _NATS_AVAILABLE = False
    NATSBroker = None
    NATSBrokerSync = None
    NATSConfig = None

# Cryptography features (optional)
try:
    from .security.cryptography_impl import CryptographyManager, CryptoSuite, KeyPair
    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False
    CryptographyManager = None
    CryptoSuite = None
    KeyPair = None

# State management (optional)
try:
    from .state.store import StateStore
    from .state.synchronization import StateSynchronizer
    from .state.consistency import ConsistencyManager
    STATE_MANAGEMENT_AVAILABLE = True
except ImportError:
    STATE_MANAGEMENT_AVAILABLE = False
    StateStore = None
    StateSynchronizer = None
    ConsistencyManager = None

# Monitoring and observability (optional)
try:
    from .monitoring.health_monitor import HealthMonitor, HealthMetrics
    MONITORING_AVAILABLE = True
except ImportError:
    MONITORING_AVAILABLE = False
    HealthMonitor = None
    HealthMetrics = None

# Convenience functions
def create_agent(agent_id: str, broker_url: str = "localhost:8080", **kwargs):
    """Create a MAPLE agent with sensible defaults."""
    if not AGENT_AVAILABLE:
        raise ImportError("Agent components not available")
    
    security_config = SecurityConfig(
        auth_type=kwargs.get('auth_type', 'demo'),
        credentials=kwargs.get('credentials', 'demo_token'),
        public_key=kwargs.get('public_key', 'demo_key'),
        require_links=kwargs.get('require_links', False)
    )
    
    config = Config(
        agent_id=agent_id,
        broker_url=broker_url,
        security=security_config
    )
    
    return Agent(config)

def create_secure_agent(agent_id: str, broker_url: str = "localhost:8080", **kwargs):
    """Create a MAPLE agent with security enabled."""
    if not AGENT_AVAILABLE:
        raise ImportError("Agent components not available")
    
    security_config = SecurityConfig(
        auth_type=kwargs.get('auth_type', 'jwt'),
        credentials=kwargs.get('credentials'),
        public_key=kwargs.get('public_key'),
        require_links=kwargs.get('require_links', True),
        strict_link_policy=kwargs.get('strict_link_policy', False)
    )
    
    if kwargs.get('link_enabled', True):
        security_config.link_config = LinkConfig(
            enabled=True,
            default_lifetime=kwargs.get('link_lifetime', 3600),
            auto_establish=kwargs.get('auto_establish_links', True)
        )
    
    config = Config(
        agent_id=agent_id,
        broker_url=broker_url,
        security=security_config
    )
    
    return Agent(config)

def get_version_info() -> dict:
    """Get comprehensive version and feature information."""
    return {
        "version": __version__,
        "creator": __author__,
        "license": __license__,
        "features": {
            "core": CORE_AVAILABLE,
            "agent": AGENT_AVAILABLE,
            "broker": BROKER_AVAILABLE,
            "error_handling": ERROR_HANDLING_AVAILABLE,
            "resource_management": RESOURCE_MANAGEMENT_AVAILABLE,
            "security": SECURITY_AVAILABLE,
            "nats_broker": _NATS_AVAILABLE,
            "cryptography": _CRYPTO_AVAILABLE,
            "state_management": STATE_MANAGEMENT_AVAILABLE,
            "monitoring": MONITORING_AVAILABLE,
            "streaming": STREAMING_AVAILABLE,
            "audit": AUDIT_AVAILABLE,
            # Additional aliases for test compatibility
            "link_identification": SECURITY_AVAILABLE,
            "distributed_state": STATE_MANAGEMENT_AVAILABLE,
            "circuit_breaker": ERROR_HANDLING_AVAILABLE,
            "type_safety": CORE_AVAILABLE
        },
        "comparison": {
            "google_a2a": {
                "resource_management": "MAPLE has built-in, A2A platform-level",
                "type_system": "MAPLE rich types, A2A JSON Schema",
                "error_handling": "MAPLE Result<T,E>, A2A conventional",
                "security": "MAPLE end-to-end, A2A OAuth platform",
                "architecture": "MAPLE open, A2A Google-locked"
            },
            "fipa_acl": {
                "type_system": "MAPLE modern types, ACL basic",
                "resource_management": "MAPLE built-in, ACL none",
                "error_handling": "MAPLE advanced, ACL basic",
                "security": "MAPLE comprehensive, ACL minimal",
                "scalability": "MAPLE 10K+ agents, ACL medium scale"
            },
            "agentcy": {
                "production_readiness": "MAPLE enterprise-ready, AGENTCY academic",
                "error_handling": "MAPLE sophisticated, AGENTCY basic",
                "scalability": "MAPLE production scale, AGENTCY limited",
                "security": "MAPLE enterprise features, AGENTCY basic"
            },
            "mcp": {
                "scope": "MAPLE multi-agent systems, MCP sequential chains",
                "resource_optimization": "MAPLE built-in, MCP none",
                "state_management": "MAPLE distributed, MCP external",
                "coordination": "MAPLE complex workflows, MCP linear chains"
            }
        }
    }

def print_comparison() -> None:
    """Print a comparison of MAPLE with other protocols."""
    print("MAPLE MAPLE vs Other Agent Communication Protocols")
    print("Creator: Mahesh Vaikri")
    print("=" * 60)
    
    comparison = [
        ("Feature", "MAPLE", "Google A2A", "FIPA ACL", "AGENTCY", "MCP"),
        ("Resource Mgmt", "[PASS] Built-in", "[FAIL] Platform", "[FAIL] None", "[FAIL] None", "[FAIL] None"),
        ("Type Safety", "[PASS] Rich", "[WARN] JSON", "[FAIL] Basic", "[FAIL] Basic", "[WARN] Basic"),
        ("Error Handling", "[PASS] Result<T,E>", "[WARN] Basic", "[FAIL] Poor", "[FAIL] Poor", "[WARN] Basic"),
        ("Security", "[PASS] End-to-end", "[WARN] OAuth", "[FAIL] None", "[FAIL] None", "[WARN] Basic"),
        ("Scalability", "[PASS] 10K+ agents", "[PASS] High", "[WARN] Medium", "[FAIL] Low", "[WARN] Limited"),
        ("State Mgmt", "[PASS] Distributed", "[FAIL] External", "[FAIL] None", "[FAIL] None", "[FAIL] External"),
        ("Open Source", "[PASS] AGPL 3.0", "[FAIL] Closed", "[PASS] Open", "[WARN] Academic", "[WARN] Limited")
    ]
    
    for row in comparison:
        print(f"{row[0]:<15} | {row[1]:<18} | {row[2]:<12} | {row[3]:<10} | {row[4]:<10} | {row[5]:<10}")
    
    print("\n[TARGET] MAPLE Key Advantages:")
    print("  [ADVANTAGE] Only protocol with built-in resource management")
    print("  [ADVANTAGE] Type-safe error handling with Result<T,E> pattern")
    print("  [ADVANTAGE] Link Identification Mechanism for security")
    print("  [ADVANTAGE] Open architecture vs. Google's closed ecosystem")
    print("  [ADVANTAGE] Production-ready vs. academic frameworks")
    print("  [ADVANTAGE] Created by Mahesh Vaikri for enterprise use")

# Build exports dynamically based on what's available
__all__ = [
    # Version and info
    "__version__", "__author__", "__email__", "__license__",
    "get_version_info", "print_comparison",
]

# Add available components to exports
if CORE_AVAILABLE:
    __all__.extend([
        "Priority", "Size", "Duration", "Boolean", "Integer", "String", 
        "AgentID", "MessageID", "Message", "Result"
    ])

if SERIALIZATION_AVAILABLE:
    __all__.append("Serializer")

if AGENT_AVAILABLE:
    __all__.extend([
        "Agent", "Config", "SecurityConfig", "PerformanceConfig", 
        "MetricsConfig", "TracingConfig", "LinkConfig",
        "create_agent", "create_secure_agent"
    ])

if BROKER_AVAILABLE:
    __all__.extend([
        "MessageBroker", "ProductionBrokerManager", "BrokerType", 
        "create_production_broker"
    ])

if ERROR_HANDLING_AVAILABLE:
    __all__.extend([
        "Error", "Severity", "ErrorType", "retry", "RetryOptions", 
        "exponential_backoff", "CircuitBreaker", "CircuitState"
    ])

if RESOURCE_MANAGEMENT_AVAILABLE:
    __all__.extend([
        "ResourceRequest", "ResourceRange", "TimeConstraint",
        "ResourceManager", "ResourceAllocation", "ResourceNegotiator"
    ])

if STREAMING_AVAILABLE:
    __all__.extend(["Stream", "StreamOptions"])

if REQUEST_RESPONSE_AVAILABLE:
    __all__.append("RequestResponsePattern")

if PUBSUB_AVAILABLE:
    __all__.append("PublishSubscribePattern")

if SECURITY_AVAILABLE:
    __all__.extend([
        "AuthenticationManager", "AuthCredentials", "AuthToken", "AuthMethod",
        "AuthorizationManager", "LinkManager", "Link", "LinkState"
    ])

if AUDIT_AVAILABLE:
    __all__.extend([
        "AuditLogger", "AuditEvent", "AuditEventType", "AuditSeverity", "get_audit_logger"
    ])

# Print attribution on import
print("MAPLE MAPLE: Multi Agent Protocol Language Engine")
print("Creator: Mahesh Vaikri | Version: 1.0.0 | License: AGPL 3.0")

# Feature availability summary
available_features = sum([
    CORE_AVAILABLE, AGENT_AVAILABLE, BROKER_AVAILABLE, 
    ERROR_HANDLING_AVAILABLE, RESOURCE_MANAGEMENT_AVAILABLE, SECURITY_AVAILABLE
])
total_features = 6
print(f"[FEATURES] Features available: {available_features}/{total_features}")

if available_features < total_features:
    print("[WARN]  Some features may be limited due to missing dependencies")
