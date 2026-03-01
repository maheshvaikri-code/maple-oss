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
```

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
