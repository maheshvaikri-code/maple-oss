# Best Practices for MAPLE

**Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)**

Guidelines for building reliable multi-agent systems with MAPLE.

## Agent Design Patterns

### 1. Resource-Aware Agent Design

Design agents that declare resource requirements up front:

```python
from maple import Agent, Message, Priority, Config
from maple.resources.specification import ResourceRequest, ResourceRange, TimeConstraint

config = Config(agent_id="compute_agent", broker_url="memory://local")
agent = Agent(config)
agent.start()

# Include resource requirements in messages
message = Message(
    message_type="HEAVY_TASK",
    receiver="worker_agent",
    priority=Priority.HIGH,
    payload={
        "task": "model_training",
        "data_path": "/data/training_set",
        "resources": ResourceRequest(
            compute=ResourceRange(min=8, preferred=16),
            memory=ResourceRange(min="16GB", preferred="32GB"),
            time=TimeConstraint(timeout="3600s"),
            priority="HIGH"
        ).to_dict()
    }
)

result = agent.send(message)
if result.is_err():
    error = result.unwrap_err()
    print(f"Send failed: {error['message']}")
```

### 2. Always Use Result\<T,E\> Pattern

Never ignore Result values. Always check success or failure:

```python
from maple import Result

# Good: check result
result = agent.send(message)
if result.is_ok():
    message_id = result.unwrap()
    print(f"Sent: {message_id}")
else:
    error = result.unwrap_err()
    handle_error(error)

# Good: chain operations
result = (
    agent.send(message)
    .map(lambda mid: f"processed_{mid}")
    .map_err(lambda err: log_error(err))
)

# Good: use unwrap_or for non-critical operations
message_id = agent.send(message).unwrap_or("unknown")

# Bad: ignoring the result
agent.send(message)  # Don't do this - errors go unnoticed
```

### 3. Secure Communication with Links

Use Link Identification for sensitive communication:

```python
from maple import Agent, Message, Config, SecurityConfig

config = Config(
    agent_id="secure_agent",
    broker_url="memory://local",
    security=SecurityConfig(
        auth_type="token",
        credentials="secure_token",
        require_links=True
    )
)

agent = Agent(config)
agent.start()

# Establish link before sending sensitive data
link_result = agent.establish_link("partner_agent", lifetime_seconds=7200)

if link_result.is_ok():
    link_id = link_result.unwrap()

    # Associate link with message
    secure_message = Message(
        message_type="SENSITIVE_DATA",
        receiver="partner_agent",
        payload={"data": "confidential_content"}
    ).with_link(link_id)

    send_result = agent.send_with_link(secure_message, "partner_agent")
    if send_result.is_err():
        print(f"Secure send failed: {send_result.unwrap_err()}")
else:
    print(f"Link establishment failed: {link_result.unwrap_err()}")
```

## Error Handling Patterns

### 1. Structured Error Responses

Return structured errors from handlers so callers can take informed action:

```python
@agent.handler("PROCESS_DATA")
def handle_process(message):
    data = message.payload.get("data")

    if not data:
        return Message.error(
            error_type="VALIDATION_ERROR",
            message="Missing 'data' field in payload",
            details={"required_fields": ["data"]},
            recoverable=True,
            receiver=message.sender
        )

    try:
        processed = process(data)
        return Message(
            message_type="PROCESS_RESULT",
            receiver=message.sender,
            payload={"result": processed}
        )
    except Exception as e:
        return Message.error(
            error_type="PROCESSING_ERROR",
            message=str(e),
            recoverable=False,
            receiver=message.sender
        )
```

### 2. Retry with Circuit Breaker

Use MAPLE's built-in circuit breaker for resilient communication:

```python
from maple.error.circuit_breaker import CircuitBreaker
from maple.error.recovery import retry, RetryOptions, exponential_backoff

# Configure circuit breaker
breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60.0,
    half_open_max_calls=3
)

# Retry with backoff
options = RetryOptions(max_attempts=3, backoff_fn=exponential_backoff)
result = retry(lambda: agent.send(message), options)
```

## State Management Patterns

### 1. Use Appropriate Consistency Level

Choose consistency based on your requirements:

```python
from maple.state import StateStore, ConsistencyLevel

# Strong consistency: critical data that must be consistent
critical_store = StateStore(consistency=ConsistencyLevel.STRONG)
critical_store.set("account_balance", {"amount": 1000.00})

# Eventual consistency: data where slight staleness is acceptable
cache_store = StateStore(consistency=ConsistencyLevel.EVENTUAL)
cache_store.set("agent_status", {"status": "active", "load": 0.5})
```

### 2. Use Version Checking for Concurrent Updates

Prevent lost updates with optimistic concurrency:

```python
store = StateStore(consistency=ConsistencyLevel.STRONG)

# Read current version
result = store.get("counter")
if result.is_ok():
    current = result.unwrap()

    # Update with expected version
    entry = store.set(
        "counter",
        {"value": current["value"] + 1},
        expected_version=current.get("version", 0)
    )

    if entry.is_err():
        print("Concurrent modification detected, retry")
```

### 3. Listen for State Changes

React to state changes across agents:

```python
store = StateStore()

def on_state_change(key, entry):
    print(f"State '{key}' updated to version {entry.version}")
    # React to change

store.add_listener(on_state_change)
```

## Performance Patterns

### 1. Use Appropriate Priority Levels

Route messages efficiently with priority:

```python
from maple import Priority

# High priority: time-sensitive operations
urgent = Message(
    message_type="ALERT",
    priority=Priority.HIGH,
    payload={"alert": "system_warning"}
)

# Medium priority: standard operations (default)
normal = Message(
    message_type="TASK",
    payload={"task": "process_batch"}
)

# Low priority: background operations
background = Message(
    message_type="CLEANUP",
    priority=Priority.LOW,
    payload={"action": "archive_old_data"}
)
```

### 2. Use Pub/Sub for Broadcast Communication

Prefer pub/sub over individual sends for one-to-many:

```python
# Good: pub/sub for broadcasting
agent.publish("system_alerts", Message(
    message_type="ALERT",
    payload={"message": "Maintenance in 10 minutes"}
))

# Less efficient: sending individually
for agent_id in all_agents:
    agent.send(Message(
        message_type="ALERT",
        receiver=agent_id,
        payload={"message": "Maintenance in 10 minutes"}
    ))
```

## Testing Patterns

### 1. Use In-Memory Broker for Tests

```python
import unittest
from maple import Agent, Message, Config

class TestMyAgent(unittest.TestCase):
    def setUp(self):
        # Use memory broker for testing
        config = Config(agent_id="test_agent", broker_url="memory://test")
        self.agent = Agent(config)
        self.agent.start()

    def tearDown(self):
        self.agent.stop()

    def test_send_message(self):
        result = self.agent.send(Message(
            message_type="TEST",
            receiver="other",
            payload={"data": "test"}
        ))
        self.assertTrue(result.is_ok())

    def test_handler_registration(self):
        received = []

        @self.agent.handler("TASK")
        def handle(msg):
            received.append(msg)

        # Handler is registered
        self.assertIsNotNone(self.agent._handlers.get("TASK"))
```

### 2. Test Result Handling

```python
def test_result_chaining(self):
    result = Result.ok(42)

    chained = (
        result
        .map(lambda x: x * 2)
        .and_then(lambda x: Result.ok(x + 1) if x < 100 else Result.err("too large"))
    )

    self.assertTrue(chained.is_ok())
    self.assertEqual(chained.unwrap(), 85)

def test_error_handling(self):
    result = Result.err({"errorType": "TIMEOUT", "message": "Request timed out"})

    self.assertTrue(result.is_err())
    error = result.unwrap_err()
    self.assertEqual(error["errorType"], "TIMEOUT")
```

---

**Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)**

```text
Copyright (C) 2025 Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)
Licensed under the GNU Affero General Public License v3.0 (AGPL-3.0)
See LICENSE for details.
```
