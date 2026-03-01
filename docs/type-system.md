# MAPLE Type System

**Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)**

MAPLE uses a type system designed to prevent common errors in agent communication through structured types and the Result\<T,E\> pattern.

## Result\<T,E\> Pattern

The Result type is the core of MAPLE's error handling. Every operation that can fail returns a `Result` instead of raising exceptions, ensuring that errors are always handled explicitly.

### Core Concept

```python
from maple.core.result import Result

# Every operation returns Result - success or structured error
def process_data(data) -> Result:
    if not data:
        return Result.err({
            "errorType": "VALIDATION_ERROR",
            "message": "Empty data provided",
            "recoverable": True
        })

    try:
        processed = transform(data)
        return Result.ok({"data": processed, "count": len(data)})
    except Exception as e:
        return Result.err({
            "errorType": "PROCESSING_ERROR",
            "message": str(e),
            "recoverable": False
        })
```

### Result Operations

```python
# Chain operations safely
result = (
    load_data(source)
    .and_then(lambda data: validate(data))
    .map(lambda valid: process(valid))
    .map_err(lambda err: log_error(err))
)

if result.is_ok():
    output = result.unwrap()
else:
    error = result.unwrap_err()
    if error.get('recoverable'):
        # Handle recoverable error
        pass
```

### Available Methods

| Method | Description |
| ------ | ----------- |
| `Result.ok(value)` | Create a success result |
| `Result.err(error)` | Create an error result |
| `is_ok()` | Check if successful |
| `is_err()` | Check if error |
| `unwrap()` | Get success value (raises on error) |
| `unwrap_or(default)` | Get success value or default |
| `unwrap_err()` | Get error value (raises on success) |
| `map(fn)` | Transform success value |
| `map_err(fn)` | Transform error value |
| `and_then(fn)` | Chain fallible operations |
| `or_else(fn)` | Provide recovery alternative |
| `to_dict()` | Serialize to dictionary |

## Core Types

### Priority

```python
from maple.core.types import Priority

class Priority(Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
```

### Size

Parse human-readable size strings:

```python
from maple.core.types import Size

bytes_val = Size.parse("4GB")     # 4294967296
bytes_val = Size.parse("1KB")     # 1024
bytes_val = Size.parse("2MB")     # 2097152
bytes_val = Size.parse("100B")    # 100
bytes_val = Size.parse("1024")    # 1024 (plain number)
```

### Duration

Parse human-readable duration strings:

```python
from maple.core.types import Duration

seconds = Duration.parse("30s")   # 30.0
seconds = Duration.parse("5m")    # 300.0
seconds = Duration.parse("1h")    # 3600.0
```

### AgentID and MessageID

Type aliases for agent and message identifiers:

```python
from maple.core.types import AgentID, MessageID

agent_id: AgentID = "agent_001"
msg_id: MessageID = "msg_abc123"
```

## Message Types

### Message Construction

```python
from maple.core.message import Message
from maple.core.types import Priority

message = Message(
    message_type="TASK_ASSIGNMENT",
    receiver="worker_agent",
    priority=Priority.HIGH,
    payload={
        "task_id": "TASK_001",
        "task_type": "DATA_ANALYSIS",
        "parameters": {
            "algorithm": "clustering",
            "dataset": "sales_data"
        }
    },
    metadata={"correlation_id": "req_123"}
)

# Fluent methods
message = message.with_receiver("other_agent")
message = message.with_link("link_id_abc")

# Serialization
msg_dict = message.to_dict()
msg_json = message.to_json()

# Deserialization
restored = Message.from_dict(msg_dict)
restored = Message.from_json(msg_json)
```

### Error Messages

```python
error_msg = Message.error(
    error_type="VALIDATION_ERROR",
    message="Invalid input format",
    details={"missing_fields": ["timestamp"]},
    severity="HIGH",
    recoverable=True,
    receiver="sender_agent"
)
```

## Resource Types

### ResourceRequest

Define resource requirements for tasks:

```python
from maple.resources.specification import ResourceRequest, ResourceRange, TimeConstraint

request = ResourceRequest(
    compute=ResourceRange(min=4, preferred=8, max=16),
    memory=ResourceRange(min="8GB", preferred="16GB", max="32GB"),
    bandwidth=ResourceRange(min="100Mbps"),
    time=TimeConstraint(timeout="120s"),
    priority="HIGH"
)

# Serialize for inclusion in message payloads
resource_dict = request.to_dict()

# Deserialize
restored = ResourceRequest.from_dict(resource_dict)
```

### ResourceRange

Specify minimum, preferred, and maximum resource values:

```python
from maple.resources.specification import ResourceRange

cpu_range = ResourceRange(min=4, preferred=8, max=16)
memory_range = ResourceRange(min="8GB", preferred="16GB", max="32GB")
```

## Error Types

### ErrorType Enum

```python
from maple.error.types import ErrorType, Severity

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

class Severity(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
```

## State Types

### StateStore and ConsistencyLevel

```python
from maple.state import StateStore, ConsistencyLevel, StorageBackend

class ConsistencyLevel(Enum):
    EVENTUAL = "eventual"
    STRONG = "strong"
    CAUSAL = "causal"

class StorageBackend(Enum):
    MEMORY = "memory"
    FILE = "file"
    REDIS = "redis"
    DATABASE = "database"

# Usage
store = StateStore(
    backend=StorageBackend.MEMORY,
    consistency=ConsistencyLevel.STRONG
)

# Set with version tracking
store.set("key", {"value": 42})

# Get returns Result
result = store.get("key")
if result.is_ok():
    value = result.unwrap()
```

## Type Safety in Practice

### Example: Type-Safe Agent Communication

```python
from maple import Agent, Message, Priority, Config, Result

config = Config(agent_id="typed_agent", broker_url="memory://local")
agent = Agent(config)
agent.start()

# All operations return Result - no silent failures
send_result: Result = agent.send(Message(
    message_type="TYPED_TASK",
    receiver="worker",
    priority=Priority.HIGH,
    payload={"data": [1, 2, 3]}
))

# Must handle both cases
if send_result.is_ok():
    msg_id = send_result.unwrap()
    print(f"Sent successfully: {msg_id}")
elif send_result.is_err():
    error = send_result.unwrap_err()
    print(f"Error type: {error.get('errorType')}")
    print(f"Message: {error.get('message')}")

# Chain operations
processed = (
    send_result
    .map(lambda mid: {"message_id": mid, "status": "sent"})
    .map_err(lambda err: {"error": err, "action": "retry"})
)

agent.stop()
```

---

**Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)**

```text
Copyright (C) 2025 Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)
Licensed under the GNU Affero General Public License v3.0 (AGPL-3.0)
See LICENSE for details.
```
