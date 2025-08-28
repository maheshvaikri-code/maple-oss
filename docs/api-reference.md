# API Reference - MAPLE

**Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)**

Complete API reference for MAPLE (Multi Agent Protocol Language Extensible), the world's most advanced agent communication protocol.

## Core Classes

### Agent Class

The central class for creating and managing intelligent agents with MAPLE's revolutionary capabilities.

```python
class Agent:
    """
    MAPLE Agent with resource awareness, type safety, and security features
    
    Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)
    """
    
    def __init__(self, config: Config):
        """
        Initialize agent with configuration
        
        Args:
            config (Config): Agent configuration including security and resources
        """
```

#### Methods

##### Core Communication

```python
async def start(self) -> None:
    """Start the agent and establish broker connections"""
    
def send(self, message: Message) -> Result[str, Dict[str, Any]]:
    """
    Send message with MAPLE's Result<T,E> error handling
    
    Args:
        message (Message): Message to send
        
    Returns:
        Result[str, Dict]: Success with message_id or detailed error
    """
    
def request(self, message: Message, timeout: str = "30s") -> Result[Message, Dict[str, Any]]:
    """
    Send message and wait for response with timeout
    
    Args:
        message (Message): Request message
        timeout (str): Timeout duration (e.g., "30s", "5m")
        
    Returns:
        Result[Message, Dict]: Response message or timeout error
    """
```

##### Resource-Aware Communication (UNIQUE TO MAPLE)

```python
def send_with_resource_awareness(
    self, 
    message: Message, 
    resources: ResourceRequest
) -> Result[str, Dict[str, Any]]:
    """
    Send message with explicit resource requirements
    
    Args:
        message (Message): Message to send
        resources (ResourceRequest): Resource requirements and preferences
        
    Returns:
        Result with allocation details or resource constraint errors
    """
    
def negotiate_resources(
    self, 
    target_agent: str, 
    requirements: ResourceRequest
) -> Result[ResourceAllocation, Dict[str, Any]]:
    """
    Negotiate optimal resource allocation with target agent
    
    Args:
        target_agent (str): Agent to negotiate with
        requirements (ResourceRequest): Desired resources
        
    Returns:
        Result with negotiated allocation or negotiation failure
    """
```

##### Secure Communication (UNIQUE TO MAPLE)

```python
def establish_link(
    self, 
    agent_id: str, 
    security_level: str = "HIGH",
    lifetime_seconds: int = 3600
) -> Result[str, Dict[str, Any]]:
    """
    Establish cryptographically verified secure communication link
    
    Args:
        agent_id (str): Target agent identifier
        security_level (str): Security level ("LOW", "MEDIUM", "HIGH", "MAXIMUM")
        lifetime_seconds (int): Link validity duration
        
    Returns:
        Result with link_id or establishment failure details
    """
    
def send_with_link(
    self, 
    message: Message, 
    link_id: str
) -> Result[str, Dict[str, Any]]:
    """
    Send message through established secure link
    
    Args:
        message (Message): Message to send securely
        link_id (str): Established link identifier
        
    Returns:
        Result with transmission confirmation or link validation error
    """
```

##### State Management (UNIQUE TO MAPLE)

```python
def synchronize_state(
    self, 
    state_id: str, 
    state_data: Dict[str, Any],
    consistency_level: ConsistencyLevel = ConsistencyLevel.STRONG
) -> Result[None, Dict[str, Any]]:
    """
    Synchronize distributed state across agent network
    
    Args:
        state_id (str): Unique state identifier
        state_data (Dict): State data to synchronize
        consistency_level (ConsistencyLevel): Desired consistency level
        
    Returns:
        Result with synchronization confirmation or conflict details
    """
    
def get_shared_state(
    self, 
    state_id: str
) -> Result[Dict[str, Any], Dict[str, Any]]:
    """
    Retrieve current shared state
    
    Args:
        state_id (str): State identifier
        
    Returns:
        Result with current state data or access error
    """
```

##### Handler Registration

```python
def register_handler(
    self, 
    message_type: str, 
    handler: Callable[[Message], Optional[Message]]
) -> None:
    """
    Register handler for specific message type
    
    Args:
        message_type (str): Message type to handle
        handler (Callable): Handler function
    """
    
@agent.handler("MESSAGE_TYPE")
def handle_message_type(message: Message) -> Optional[Message]:
    """Decorator for registering message handlers"""
```

### Message Class

```python
class Message:
    """
    MAPLE Message with comprehensive metadata and type safety
    
    Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)
    """
    
    def __init__(
        self,
        message_type: str,
        receiver: Optional[str] = None,
        priority: Priority = Priority.MEDIUM,
        payload: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        message_id: Optional[str] = None,
        sender: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ):
```

#### Message Methods

```python
def with_resource_requirements(
    self, 
    resources: ResourceRequest
) -> 'Message':
    """Add resource requirements to message (UNIQUE TO MAPLE)"""
    
def with_link(self, link_id: str) -> 'Message':
    """Associate message with secure link (UNIQUE TO MAPLE)"""
    
def with_priority(self, priority: Priority) -> 'Message':
    """Set message priority for intelligent routing"""
    
@classmethod
def error(
    cls,
    error_type: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    severity: str = "HIGH",
    recoverable: bool = False,
    suggestion: Optional[Dict[str, Any]] = None
) -> 'Message':
    """Create structured error message with recovery suggestions"""
```

### Result<T,E> Type (REVOLUTIONARY)

```python
class Result[T, E]:
    """
    Type-safe error handling that eliminates silent failures
    
    Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)
    
    This revolutionary pattern ensures NO operation can fail silently
    """
    
    @classmethod
    def ok(cls, value: T) -> 'Result[T, E]':
        """Create successful result"""
        
    @classmethod
    def err(cls, error: E) -> 'Result[T, E]':
        """Create error result with detailed information"""
        
    def is_ok(self) -> bool:
        """Check if result is successful"""
        
    def is_err(self) -> bool:
        """Check if result contains error"""
        
    def unwrap(self) -> T:
        """Extract success value or raise exception"""
        
    def unwrap_or(self, default: T) -> T:
        """Extract success value or return default"""
        
    def unwrap_err(self) -> E:
        """Extract error value"""
        
    def map(self, f: Callable[[T], U]) -> 'Result[U, E]':
        """Transform success value"""
        
    def and_then(self, f: Callable[[T], 'Result[U, E]']) -> 'Result[U, E]':
        """Chain operations with automatic error propagation"""
        
    def or_else(self, f: Callable[[E], 'Result[T, F]']) -> 'Result[T, F]':
        """Provide error recovery alternative"""
```

## Resource Management (UNIQUE TO MAPLE)

### ResourceRequest Class

```python
class ResourceRequest:
    """
    Specify resource requirements with precision
    
    NO OTHER PROTOCOL HAS THIS CAPABILITY
    """
    
    def __init__(
        self,
        compute: Optional[ResourceRange] = None,
        memory: Optional[ResourceRange] = None,
        gpu_memory: Optional[ResourceRange] = None,
        network_bandwidth: Optional[ResourceRange] = None,
        storage: Optional[ResourceRange] = None,
        deadline: Optional[str] = None,
        timeout: Optional[str] = None,
        priority: str = "MEDIUM"
    ):
```

### ResourceRange Class

```python
class ResourceRange:
    """
    Define resource range with min, preferred, and max values
    """
    
    def __init__(self, min: Any, preferred: Any = None, max: Any = None):
        """
        Args:
            min: Minimum acceptable resource amount
            preferred: Optimal resource amount
            max: Maximum usable resource amount
        """
```

### ResourceManager Class

```python
class ResourceManager:
    """
    Manage resource allocation and optimization across agents
    """
    
    def allocate_resources(
        self, 
        request: ResourceRequest
    ) -> Result[ResourceAllocation, Dict[str, Any]]:
        """
        Allocate resources based on request and availability
        
        Returns:
            Result with allocation details or constraint violations
        """
        
    def optimize_allocation(
        self, 
        requests: List[ResourceRequest],
        optimization_goal: str = "efficiency"
    ) -> Result[Dict[str, ResourceAllocation], Dict[str, Any]]:
        """
        Optimize multiple resource allocations simultaneously
        
        Args:
            requests: List of resource requests to optimize
            optimization_goal: "efficiency", "performance", "cost", or "fairness"
            
        Returns:
            Result with optimized allocations or optimization failure
        """
```

## Security Framework (UNIQUE TO MAPLE)

### LinkManager Class

```python
class LinkManager:
    """
    Manage cryptographically verified communication links
    
    PATENT-WORTHY INNOVATION - NO COMPETITOR HAS THIS
    """
    
    def establish_link(
        self, 
        agent_a: str, 
        agent_b: str,
        security_level: str = "HIGH",
        encryption: str = "AES-256-GCM"
    ) -> Result[str, Dict[str, Any]]:
        """
        Establish secure link with cryptographic verification
        
        Args:
            agent_a: First agent identifier
            agent_b: Second agent identifier  
            security_level: Required security level
            encryption: Encryption algorithm
            
        Returns:
            Result with link_id or establishment failure
        """
        
    def validate_link(
        self, 
        link_id: str, 
        sender: str, 
        receiver: str
    ) -> Result[bool, Dict[str, Any]]:
        """
        Validate link authenticity and authorization
        
        Returns:
            Result with validation status or security violation details
        """
```

### SecurityConfig Class

```python
class SecurityConfig:
    """
    Configure comprehensive security settings
    """
    
    def __init__(
        self,
        auth_type: str = "jwt",
        credentials: str = "",
        require_links: bool = False,
        strict_link_policy: bool = False,
        encryption: str = "AES-256-GCM",
        key_rotation_interval: str = "1h"
    ):
```

## State Management (REVOLUTIONARY)

### StateManager Class

```python
class StateManager:
    """
    Manage distributed state across agent networks
    
    FIRST-IN-INDUSTRY DISTRIBUTED STATE FOR AGENT COMMUNICATION
    """
    
    def create_distributed_state(
        self,
        state_id: str,
        initial_value: Dict[str, Any],
        consistency_level: ConsistencyLevel = ConsistencyLevel.STRONG
    ) -> Result[DistributedState, Dict[str, Any]]:
        """
        Create new distributed state with consistency guarantees
        """
        
    def atomic_update(
        self,
        state_id: str,
        update_function: Callable[[Dict], Dict],
        retry_count: int = 3
    ) -> Result[Dict[str, Any], Dict[str, Any]]:
        """
        Perform atomic update across all replicas
        
        Args:
            state_id: State identifier
            update_function: Pure function to transform state
            retry_count: Number of retry attempts on conflicts
            
        Returns:
            Result with updated state or conflict resolution failure
        """
```

### ConsistencyLevel Enum

```python
class ConsistencyLevel(Enum):
    """
    Distributed consistency levels
    """
    STRONG = "STRONG"          # All replicas consistent immediately
    EVENTUAL = "EVENTUAL"      # Eventual consistency with conflict resolution
    CAUSAL = "CAUSAL"          # Causally consistent ordering
    WEAK = "WEAK"              # Best-effort consistency
```

## Configuration Classes

### Config Class

```python
class Config:
    """
    Agent configuration with comprehensive options
    """
    
    def __init__(
        self,
        agent_id: str,
        broker_url: str,
        security: Optional[SecurityConfig] = None,
        performance: Optional[PerformanceConfig] = None,
        resources: Optional[ResourceConfig] = None,
        monitoring: Optional[MonitoringConfig] = None
    ):
```

### PerformanceConfig Class

```python
class PerformanceConfig:
    """
    Performance optimization settings
    """
    
    def __init__(
        self,
        target_throughput: str = "100K_messages_per_second",
        max_latency: str = "10ms",
        connection_pool_size: int = 50,
        message_compression: bool = True,
        adaptive_routing: bool = True,
        load_balancing: bool = True
    ):
```

## Error Handling

### Error Types

```python
class ErrorType(Enum):
    """
    Comprehensive error type hierarchy
    """
    # Communication errors
    NETWORK_ERROR = "NETWORK_ERROR"
    TIMEOUT = "TIMEOUT"
    ROUTING_ERROR = "ROUTING_ERROR"
    MESSAGE_VALIDATION_ERROR = "MESSAGE_VALIDATION_ERROR"
    
    # Resource errors
    RESOURCE_UNAVAILABLE = "RESOURCE_UNAVAILABLE"
    RESOURCE_EXHAUSTED = "RESOURCE_EXHAUSTED"
    RESOURCE_NEGOTIATION_FAILED = "RESOURCE_NEGOTIATION_FAILED"
    
    # Security errors
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"
    LINK_VERIFICATION_FAILED = "LINK_VERIFICATION_FAILED"
    ENCRYPTION_ERROR = "ENCRYPTION_ERROR"
    
    # State errors
    STATE_CONFLICT = "STATE_CONFLICT"
    STATE_SYNCHRONIZATION_FAILED = "STATE_SYNCHRONIZATION_FAILED"
    CONSISTENCY_VIOLATION = "CONSISTENCY_VIOLATION"
```

### Recovery Utilities

```python
def retry_with_backoff(
    operation: Callable[[], Result[T, E]],
    max_attempts: int = 3,
    backoff_factor: float = 2.0,
    retryable_errors: Optional[List[str]] = None
) -> Result[T, E]:
    """
    Retry operation with exponential backoff
    
    Args:
        operation: Function to retry
        max_attempts: Maximum retry attempts
        backoff_factor: Backoff multiplication factor
        retryable_errors: List of retryable error types
        
    Returns:
        Result of final attempt or accumulated error information
    """

class CircuitBreaker:
    """
    Circuit breaker pattern for preventing cascading failures
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: str = "60s",
        half_open_max_calls: int = 3
    ):
```

## Usage Examples

### Complete Agent Setup

```python
from maple import Agent, Message, Priority, Config, SecurityConfig, PerformanceConfig
from maple.resources import ResourceRequest, ResourceRange

# Configure high-performance secure agent
config = Config(
    agent_id="production_agent_001",
    broker_url="nats://prod-cluster:4222",
    security=SecurityConfig(
        auth_type="mutual_tls_jwt",
        require_links=True,
        strict_link_policy=True,
        encryption="AES-256-GCM"
    ),
    performance=PerformanceConfig(
        target_throughput="300K_messages_per_second",
        max_latency="1ms",
        adaptive_routing=True,
        load_balancing=True
    )
)

# Create and start agent
agent = Agent(config)
await agent.start()

# Register intelligent message handler
@agent.handler("COMPLEX_ANALYSIS")
def handle_complex_analysis(message: Message) -> Optional[Message]:
    # Extract resource requirements
    resources = message.payload.get('resources', {})
    data = message.payload.get('data')
    
    # Process with resource awareness
    processing_result = analyze_with_resources(data, resources)
    
    if processing_result.is_ok():
        result_data = processing_result.unwrap()
        return Message(
            message_type="ANALYSIS_COMPLETE",
            payload={
                "results": result_data,
                "performance_metrics": {
                    "processing_time": "2.3s",
                    "resource_efficiency": 0.95,
                    "accuracy": 0.98
                }
            }
        )
    else:
        error = processing_result.unwrap_err()
        return Message.error(
            error_type="ANALYSIS_FAILED",
            message=error['message'],
            details=error.get('details', {}),
            recoverable=error.get('recoverable', False),
            suggestion=error.get('suggestion', {})
        )

# Send resource-aware message
message = Message(
    message_type="COMPLEX_ANALYSIS",
    receiver="analysis_worker",
    priority=Priority.HIGH,
    payload={
        "data": large_dataset,
        "algorithm": "deep_learning",
        "resources": ResourceRequest(
            compute=ResourceRange(min=16, preferred=32, max=64),
            memory=ResourceRange(min="32GB", preferred="64GB", max="128GB"),
            gpu_memory=ResourceRange(min="16GB", preferred="48GB"),
            deadline="2024-12-25T15:00:00Z"
        ).to_dict()
    }
)

# Send with comprehensive error handling
result = agent.send_with_resource_awareness(message, message.payload['resources'])

if result.is_ok():
    message_id = result.unwrap()
    print(f"✅ Analysis request sent: {message_id}")
else:
    error = result.unwrap_err()
    print(f"❌ Request failed: {error['message']}")
    
    # Apply intelligent recovery
    if error.get('recoverable'):
        recovery = error.get('suggestion', {})
        if recovery.get('action') == 'REDUCE_RESOURCE_REQUIREMENTS':
            # Automatically retry with reduced resources
            reduced_resources = optimize_resource_requirements(
                original_resources, 
                constraints=error['details']
            )
            retry_result = agent.send_with_resource_awareness(
                message.with_resource_requirements(reduced_resources),
                reduced_resources
            )
```

**Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)**

**This API reference covers MAPLE's revolutionary capabilities that are literally impossible with any other agent communication protocol. MAPLE sets a new standard for intelligent, secure, and efficient agent coordination.**

**🚀 MAPLE: The Protocol That Changes Everything 🚀**
