# Getting Started with MAPLE

**Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)**

MAPLE (Multi Agent Protocol Language Engine) is a Python framework for multi-agent communication with built-in resource management, type-safe error handling, and secure link identification.

## Installation

```bash
# Install MAPLE
pip install maple-oss

# Or install from source
git clone https://github.com/maheshvaikri-code/maple-oss.git
cd maple-oss
pip install -e .

# Verify installation
python -c "from maple import Agent, Message, Config; print('MAPLE ready')"

# Run the local, network-free readiness check
maple doctor --json
```

`maple doctor` checks the installed core, trusted execution, retrieval, event,
evaluation, and interop surfaces locally. It does not call an LLM provider or
cloud service; a successful doctor report is a preflight signal, not a release
or security audit.

## Your First MAPLE Agent

```python
from maple import Agent, Message, Priority, Config

# Create an agent
config = Config(
    agent_id="my_agent",
    broker_url="memory://local"
)

agent = Agent(config)
agent.start()

# Send a message with Result<T,E> error handling
message = Message(
    message_type="GREETING",
    receiver="other_agent",
    priority=Priority.HIGH,
    payload={"text": "Hello from MAPLE"}
)

result = agent.send(message)

if result.is_ok():
    message_id = result.unwrap()
    print(f"Sent: {message_id}")
else:
    error = result.unwrap_err()
    print(f"Failed: {error['message']}")

agent.stop()
```

## When a send fails

`send()` returns a `Result`, and since 2.1.0 it genuinely can fail. The failure
carries a machine-readable `errorType` so you can branch on the cause rather
than parse a message string.

```python
result = agent.send(message)

if result.is_err():
    error = result.unwrap_err()

    if error["errorType"] == "QUEUE_FULL":
        # Backpressure. The consumer is behind and the broker is refusing
        # rather than buffering without a limit. Slow down, shed, or retry.
        ...
    elif error["errorType"] == "MESSAGE_TOO_LARGE":
        # Payload exceeded max_message_bytes. Split it or raise the limit.
        ...
    elif error["errorType"] == "UNROUTABLE":
        # Only when you passed require_routable=True: nobody is subscribed.
        ...
```

| `errorType` | Meaning |
| --- | --- |
| `QUEUE_FULL` | The broker is at capacity and refused the message |
| `MESSAGE_TOO_LARGE` | The payload exceeded the configured limit |
| `UNROUTABLE` | No live subscription for the receiver (opt-in check) |
| `SEND_ERROR` | Anything else, with the cause in `message` |

**Ignoring the `Result` loses messages.** That was true before 2.1.0 as well;
the difference is that the loss is now reported rather than silent.

### Messages nobody receives

By default, sending to an agent that has not started is *accepted*. This is
deliberate — you often send to a peer that starts moments later — so it is not
an error. It is no longer invisible either:

```python
stats = agent.broker.get_statistics()
print(stats["undeliverable"])   # messages that reached zero handlers
print(stats["refused"])         # messages the broker declined

# Or be told as it happens
agent.broker.set_undeliverable_handler(
    lambda receiver, message: audit.record(receiver, message.message_id)
)
```

If you would rather fail fast than send into the void, ask for a routability
check at send time:

```python
result = agent.send(message, require_routable=True)
```

## Isolating agents in one process

`broker_url` names an isolation boundary. Agents sharing a URL share a bus and
a discovery registry; agents on different URLs share nothing.

```python
tenant_a = Agent(Config(agent_id="worker", broker_url="memory://tenant-a"))
tenant_b = Agent(Config(agent_id="worker", broker_url="memory://tenant-b"))
# separate buses, separate registries, no cross-visibility
```

Leaving `broker_url` unset resolves to a single default scope, so simple
programs need not think about this at all.

Before 2.1.0 every URL returned the same process-wide bus. If you relied on
agents with *different* URLs talking to each other, give them the same URL.

## Key Features

### Resource-Aware Communication

Include resource requirements in your messages:

```python
from maple.resources.specification import ResourceRequest, ResourceRange, TimeConstraint

message = Message(
    message_type="HEAVY_COMPUTATION",
    receiver="compute_agent",
    priority=Priority.HIGH,
    payload={
        "task": "model_training",
        "resources": ResourceRequest(
            compute=ResourceRange(min=4, preferred=8, max=16),
            memory=ResourceRange(min="8GB", preferred="16GB"),
            time=TimeConstraint(timeout="120s"),
            priority="HIGH"
        ).to_dict()
    }
)
```

### Result\<T,E\> Error Handling

Type-safe results that prevent silent failures:

```python
from maple import Result

result = agent.send(message)

if result.is_ok():
    message_id = result.unwrap()
    print(f"Success: {message_id}")
else:
    error = result.unwrap_err()
    print(f"Error: {error['message']}")

# Chain operations
processed = (
    agent.send(message)
    .map(lambda mid: f"processed_{mid}")
    .map_err(lambda err: log_error(err))
)
```

### Secure Links (LIM)

Establish cryptographically verified channels:

```python
from maple import Config, SecurityConfig

config = Config(
    agent_id="secure_agent",
    broker_url="memory://local",
    security=SecurityConfig(
        auth_type="token",
        credentials="my_token",
        require_links=True
    )
)

agent = Agent(config)
agent.start()

# Establish secure link
link_result = agent.establish_link("partner_agent", lifetime_seconds=3600)

if link_result.is_ok():
    link_id = link_result.unwrap()
    secure_msg = Message(
        message_type="SENSITIVE_DATA",
        receiver="partner_agent",
        payload={"data": "confidential"}
    ).with_link(link_id)

    agent.send_with_link(secure_msg, "partner_agent")
```

`require_links=True` is enforced, and it fails closed. A send with no valid
link raises `SecurityError` when `strict_link_policy` is set, and a broker
that cannot build a link manager at all refuses every link-enforced send
rather than passing the message through. Catch it from the package root:

```python
from maple import SecurityError

try:
    agent.send(secure_msg)
except SecurityError as exc:
    ...  # no link: the message was not enqueued
```

## Next Steps

1. **Explore Examples**:
   ```bash
   python demo_package/examples/comprehensive_feature_demo.py
   ```

2. **Run Tests**:
   ```bash
   python -m pytest tests/ -v
   ```

3. **Read the Docs**:
   - [Type System](type-system.md)
   - [Protocol Comparison](protocol-comparison.md)
   - [Best Practices](best-practices.md)
   - [API Reference](api-reference.md)

## Support

**Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)**

- [Documentation](../README.md)
- [Issues](https://github.com/maheshvaikri-code/maple-oss/issues)
- [Discussions](https://github.com/maheshvaikri-code/maple-oss/discussions)
- [Contact](mailto:mahesh@mapleagent.org)

```text
Copyright (C) 2025 Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)
Licensed under the GNU Affero General Public License v3.0 (AGPL-3.0)
See LICENSE for details.
```
