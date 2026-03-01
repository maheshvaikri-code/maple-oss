# API Reference - MAPLE

**Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)**

API reference for MAPLE (Multi Agent Protocol Language Engine).

## Core Classes

### Agent Class

The central class for creating and managing agents.

```python
class Agent:
    def __init__(self, config: Config, broker: Optional[MessageBroker] = None):
        """
        Initialize agent with configuration.

        Args:
            config (Config): Agent configuration including security and resources
            broker (MessageBroker, optional): Custom broker instance
        """
```

#### Methods

##### Core Communication

```python
def start(self) -> None:
    """Start the agent and establish broker connections."""

def stop(self) -> None:
    """Stop the agent and clean up connections."""

def send(self, message: Message) -> Result[str, Dict[str, Any]]:
    """
    Send a message with Result<T,E> error handling.

    Args:
        message (Message): Message to send

    Returns:
        Result[str, Dict]: Success with message_id or detailed error
    """

def request(self, message: Message, timeout: str = "30s") -> Result[Message, Dict[str, Any]]:
    """
    Send message and wait for response with timeout.

    Args:
        message (Message): Request message
        timeout (str): Timeout duration (e.g., "30s", "5m")

    Returns:
        Result[Message, Dict]: Response message or timeout error
    """

def receive(self, timeout: Optional[str] = None) -> Result[Message, Dict[str, Any]]:
    """
    Receive a message from the agent's queue.

    Args:
        timeout (str, optional): Timeout duration

    Returns:
        Result[Message, Dict]: Received message or timeout/error
    """

def broadcast(self, recipients: List[str], message: Message) -> Dict[str, Result[str, Dict[str, Any]]]:
    """
    Send a message to multiple recipients.

    Args:
        recipients: List of agent IDs
        message: Message to broadcast

    Returns:
        Dict mapping agent_id to send Result
    """
```

##### Pub/Sub Communication

```python
def publish(self, topic: str, message: Message) -> Result[str, Dict[str, Any]]:
    """Publish a message to a topic."""

def subscribe(self, topic: str) -> Result[None, Dict[str, Any]]:
    """Subscribe to a topic."""
```

##### Secure Communication (Link Identification)

```python
def establish_link(
    self,
    agent_id: str,
    lifetime_seconds: int = 3600
) -> Result[str, Dict[str, Any]]:
    """
    Establish a cryptographically verified secure communication link.

    Args:
        agent_id (str): Target agent identifier
        lifetime_seconds (int): Link validity duration

    Returns:
        Result with link_id or establishment failure details
    """

def send_with_link(
    self,
    message: Message,
    agent_id: str
) -> Result[str, Dict[str, Any]]:
    """
    Send message through an established secure link.

    Args:
        message (Message): Message to send (should have link via .with_link())
        agent_id (str): Target agent identifier

    Returns:
        Result with message_id or link validation error
    """
```

##### Handler Registration

```python
def register_handler(
    self,
    message_type: str,
    handler: Callable[[Message], Optional[Message]]
) -> None:
    """Register handler for a specific message type."""

def register_topic_handler(
    self,
    topic: str,
    handler: Callable[[Message], Optional[Message]]
) -> None:
    """Register handler for a topic."""

# Decorator forms
@agent.handler("MESSAGE_TYPE")
def handle_message(message: Message) -> Optional[Message]:
    """Decorator for registering message handlers."""

@agent.topic_handler("topic_name")
def handle_topic(message: Message) -> Optional[Message]:
    """Decorator for registering topic handlers."""
```

##### Streaming

```python
def create_stream(self, name: str) -> Result[Stream, Dict[str, Any]]:
    """Create a new message stream."""

def connect_stream(self, name: str) -> Result[Stream, Dict[str, Any]]:
    """Connect to an existing message stream."""

@agent.stream_handler("stream_name")
def handle_stream(message: Message) -> None:
    """Decorator for registering stream handlers."""
```

### Message Class

```python
class Message:
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
def with_link(self, link_id: str) -> 'Message':
    """Associate message with a secure link."""

def with_receiver(self, receiver: str) -> 'Message':
    """Set the message receiver."""

def get_link_id(self) -> Optional[str]:
    """Get the associated link ID, if any."""

def add_metadata(self, key: str, value: Any) -> None:
    """Add metadata to the message."""

def get_metadata(self, key: str, default: Any = None) -> Any:
    """Get metadata by key."""

def to_dict(self) -> Dict[str, Any]:
    """Serialize to dictionary."""

def to_json(self) -> str:
    """Serialize to JSON string."""

@classmethod
def from_dict(cls, data: Dict[str, Any]) -> 'Message':
    """Deserialize from dictionary."""

@classmethod
def from_json(cls, json_str: str) -> 'Message':
    """Deserialize from JSON string."""

@classmethod
def error(
    cls,
    error_type: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    severity: str = "HIGH",
    recoverable: bool = False,
    receiver: Optional[str] = None,
    correlation_id: Optional[str] = None
) -> 'Message':
    """Create a structured error message."""

@classmethod
def ack(cls, correlation_id: str, receiver: Optional[str] = None) -> 'Message':
    """Create an acknowledgement message."""

def builder() -> 'Message.Builder':
    """Get a builder for fluent message construction."""
```

### Result\<T,E\> Type

Rust-inspired type-safe error handling.

```python
class Result[T, E]:
    @classmethod
    def ok(cls, value: T) -> 'Result[T, E]':
        """Create successful result."""

    @classmethod
    def err(cls, error: E) -> 'Result[T, E]':
        """Create error result."""

    def is_ok(self) -> bool:
        """Check if result is successful."""

    def is_err(self) -> bool:
        """Check if result contains error."""

    def unwrap(self) -> T:
        """Extract success value. Raises if Err."""

    def unwrap_or(self, default: T) -> T:
        """Extract success value or return default."""

    def unwrap_err(self) -> E:
        """Extract error value. Raises if Ok."""

    def map(self, f: Callable[[T], U]) -> 'Result[U, E]':
        """Transform success value."""

    def map_err(self, f: Callable[[E], F]) -> 'Result[T, F]':
        """Transform error value."""

    def and_then(self, f: Callable[[T], 'Result[U, E]']) -> 'Result[U, E]':
        """Chain operations with automatic error propagation."""

    def or_else(self, f: Callable[[E], 'Result[T, F]']) -> 'Result[T, F]':
        """Provide error recovery alternative."""

    def to_dict(self) -> dict:
        """Serialize to dictionary."""

    @classmethod
    def from_dict(cls, data: dict) -> 'Result[Any, Any]':
        """Deserialize from dictionary."""
```

## Resource Management

### ResourceRequest Class

```python
@dataclass
class ResourceRequest:
    compute: Optional[ResourceRange] = None
    memory: Optional[ResourceRange] = None
    bandwidth: Optional[ResourceRange] = None
    time: Optional[TimeConstraint] = None
    priority: str = "MEDIUM"

    def to_dict(self) -> Dict[str, Any]: ...

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ResourceRequest': ...
```

### ResourceRange Class

```python
@dataclass
class ResourceRange:
    min: Any
    preferred: Optional[Any] = None
    max: Optional[Any] = None
```

### ResourceManager Class

```python
class ResourceManager:
    def allocate_resources(
        self,
        request: ResourceRequest
    ) -> Result[ResourceAllocation, Dict[str, Any]]:
        """Allocate resources based on request and availability."""

    def release_resources(self, allocation_id: str) -> Result[None, Dict[str, Any]]:
        """Release a previous allocation."""
```

## Security Framework

### LinkManager Class

```python
class LinkManager:
    def initiate_link(self, agent_a: str, agent_b: str) -> Link:
        """Initiate a new link between two agents."""

    def establish_link(
        self,
        link_id: str,
        lifetime_seconds: int = 3600
    ) -> Result[Link, Dict[str, Any]]:
        """Establish a previously initiated link."""

    def validate_link(
        self,
        link_id: str,
        sender: str,
        receiver: str
    ) -> Result[Link, Dict[str, Any]]:
        """Validate link authenticity and authorization."""

    def terminate_link(self, link_id: str) -> Result[None, Dict[str, Any]]:
        """Terminate an established link."""

    def get_links_for_agent(self, agent_id: str) -> Result[list, Dict[str, Any]]:
        """Get all links for a specific agent."""
```

### SecurityConfig Class

```python
@dataclass
class SecurityConfig:
    auth_type: str
    credentials: str
    public_key: Optional[str] = None
    private_key: Optional[str] = None
    permissions: Optional[List[Dict[str, Any]]] = None
    require_links: bool = False
    strict_link_policy: bool = False
    link_config: Optional[LinkConfig] = None
```

## State Management

### StateStore Class

```python
class StateStore:
    def __init__(
        self,
        backend: StorageBackend = StorageBackend.MEMORY,
        consistency: ConsistencyLevel = ConsistencyLevel.EVENTUAL,
        config: Optional[Dict[str, Any]] = None
    ):

    def get(self, key: str) -> Result[Optional[Any], Dict[str, Any]]:
        """Get state value by key."""

    def set(
        self,
        key: str,
        value: Any,
        metadata: Optional[Dict[str, Any]] = None,
        expected_version: Optional[int] = None
    ) -> Result[StateEntry, Dict[str, Any]]:
        """Set state value with optional version checking."""

    def delete(
        self,
        key: str,
        expected_version: Optional[int] = None
    ) -> Result[bool, Dict[str, Any]]:
        """Delete a state entry."""

    def list_keys(self, prefix: Optional[str] = None) -> Result[List[str], Dict[str, Any]]:
        """List state keys, optionally filtered by prefix."""

    def add_listener(self, listener: Callable[[str, StateEntry], None]) -> None:
        """Register a listener for state changes."""

    def remove_listener(self, listener: Callable[[str, StateEntry], None]) -> None:
        """Remove a state change listener."""

    def get_statistics(self) -> Dict[str, Any]:
        """Get store statistics."""
```

### Enums

```python
class StorageBackend(Enum):
    MEMORY = "memory"
    FILE = "file"
    REDIS = "redis"
    DATABASE = "database"

class ConsistencyLevel(Enum):
    EVENTUAL = "eventual"
    STRONG = "strong"
    CAUSAL = "causal"

class Priority(Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
```

## Configuration Classes

### Config Class

```python
@dataclass
class Config:
    agent_id: str
    broker_url: str
    security: Optional[SecurityConfig] = None
    performance: Optional[PerformanceConfig] = None
    metrics: Optional[MetricsConfig] = None
    tracing: Optional[TracingConfig] = None
```

## Error Handling

### Error Types

```python
class ErrorType(Enum):
    NETWORK_ERROR = "NETWORK_ERROR"
    TIMEOUT = "TIMEOUT"
    ROUTING_ERROR = "ROUTING_ERROR"
    MESSAGE_VALIDATION_ERROR = "MESSAGE_VALIDATION_ERROR"
    RESOURCE_UNAVAILABLE = "RESOURCE_UNAVAILABLE"
    RESOURCE_EXHAUSTED = "RESOURCE_EXHAUSTED"
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"
    LINK_VERIFICATION_FAILED = "LINK_VERIFICATION_FAILED"
    ENCRYPTION_ERROR = "ENCRYPTION_ERROR"
    STATE_CONFLICT = "STATE_CONFLICT"
```

### Recovery Utilities

```python
def retry(
    operation: Callable,
    options: RetryOptions
) -> Result:
    """Retry an operation with configurable backoff."""

def exponential_backoff(attempt: int, base_delay: float = 1.0) -> float:
    """Calculate exponential backoff delay."""

class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 3
    ):
        """Circuit breaker pattern for preventing cascading failures."""
```

## Usage Example

```python
from maple import Agent, Message, Priority, Config, SecurityConfig, Result

# Configure agent
config = Config(
    agent_id="my_agent",
    broker_url="memory://local",
    security=SecurityConfig(
        auth_type="token",
        credentials="my_token",
        require_links=True
    )
)

# Create and start agent
agent = Agent(config)
agent.start()

# Register handler
@agent.handler("TASK")
def handle_task(message):
    data = message.payload.get("data")
    return Message(
        message_type="TASK_RESULT",
        receiver=message.sender,
        payload={"result": f"processed {data}"}
    )

# Send a message
result = agent.send(Message(
    message_type="TASK",
    receiver="other_agent",
    priority=Priority.HIGH,
    payload={"data": "input"}
))

if result.is_ok():
    print(f"Sent: {result.unwrap()}")
else:
    print(f"Error: {result.unwrap_err()}")

# Establish secure link
link_result = agent.establish_link("other_agent", lifetime_seconds=3600)
if link_result.is_ok():
    link_id = link_result.unwrap()
    secure_msg = Message(
        message_type="SECURE_TASK",
        receiver="other_agent",
        payload={"sensitive": "data"}
    ).with_link(link_id)
    agent.send_with_link(secure_msg, "other_agent")

agent.stop()
```

---

**Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)**

```text
Copyright (C) 2025 Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)
Licensed under the GNU Affero General Public License v3.0 (AGPL-3.0)
See LICENSE for details.
```
