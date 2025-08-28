# Getting Started with MAPLE

**Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)**

MAPLE (Multi Agent Protocol Language Extensible) revolutionizes multi-agent communication with unprecedented capabilities that are impossible with Google A2A, FIPA ACL, MCP, AGENTCY, or any existing protocol.

## Quick Installation

### Python
```bash
# Install MAPLE
pip install maple-oss

# Verify installation
python -c "import maple; print('🍁 MAPLE ready!')"
```

### Node.js
```bash
# Install MAPLE for Node.js
npm install maple-protocol

# Verify installation
node -e "const maple = require('maple-protocol'); console.log('🍁 MAPLE ready!');"
```

### Java
```xml
<!-- Maven dependency -->
<dependency>
    <groupId>org.maple</groupId>
    <artifactId>maple-core</artifactId>
    <version>1.0.0</version>
</dependency>
```

## Your First MAPLE Agent

Experience MAPLE's revolutionary capabilities in minutes:

```python
#!/usr/bin/env python3
"""
MAPLE Quick Start - Revolutionary Agent Communication
Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)
"""

from maple import Agent, Message, Priority, Config
from maple.resources import ResourceRequest, ResourceRange
import asyncio

async def create_revolutionary_agents():
    print("🍁 MAPLE Revolutionary Multi-Agent System")
    print("Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)")
    print("=" * 60)
    
    # Create agent with MAPLE's advanced configuration
    config = Config(
        agent_id="intelligent_agent",
        broker_url="memory://localhost"
    )
    
    agent = Agent(config)
    await agent.start()
    
    # Demonstrate MAPLE's resource-aware messaging
    message = Message(
        message_type="INTELLIGENT_TASK",
        receiver="worker_agent",
        priority=Priority.HIGH,
        payload={
            "task": "complex_analysis",
            "data": list(range(10000)),
            "resources": ResourceRequest(
                memory=ResourceRange(min="4GB", preferred="8GB", max="16GB"),
                compute=ResourceRange(min=4, preferred=8, max=16),
                deadline="2024-12-25T18:00:00Z"
            ).to_dict()
        }
    )
    
    # Send with MAPLE's Result<T,E> error handling
    result = agent.send(message)
    
    if result.is_ok():
        message_id = result.unwrap()
        print(f"✅ Message sent successfully: {message_id}")
        print("🔍 Features demonstrated:")
        print("   - Resource-aware communication")
        print("   - Type-safe error handling")
        print("   - Priority-based routing")
    else:
        error = result.unwrap_err()
        print(f"❌ Send failed: {error['message']}")
        # MAPLE's intelligent error recovery
        if error.get('recoverable', False):
            suggestion = error.get('suggestion', {})
            print(f"💡 Recovery suggestion: {suggestion}")
    
    await agent.stop()
    print("🎉 MAPLE demonstration complete!")

# Run the demonstration
if __name__ == "__main__":
    asyncio.run(create_revolutionary_agents())
```

## Revolutionary Features

### 🔧 Resource-Aware Communication (INDUSTRY FIRST)
```python
# Specify resource requirements directly in messages
resource_message = Message(
    message_type="HEAVY_COMPUTATION",
    payload={
        "data": large_dataset,
        "resources": ResourceRequest(
            memory=ResourceRange(min="16GB", preferred="32GB", max="64GB"),
            compute=ResourceRange(min=16, preferred=32, max=64),
            gpu_memory=ResourceRange(min="8GB", preferred="24GB"),
            network_bandwidth=ResourceRange(min="1Gbps", preferred="10Gbps"),
            deadline="2024-12-25T15:30:00Z"
        ).to_dict()
    }
)
```

### 🛡️ Result<T,E> Error Handling (ELIMINATES SILENT FAILURES)
```python
# Type-safe communication that prevents all silent failures
result = agent.send(message)

if result.is_ok():
    message_id = result.unwrap()
    print(f"Success: {message_id}")
else:
    error = result.unwrap_err()
    print(f"Error: {error['message']}")
    
    # Automatic recovery suggestions
    if error.get('recoverable'):
        recovery = error.get('suggestion', {})
        print(f"Recovery: {recovery}")
```

### 🔒 Link Identification Mechanism (PATENT-WORTHY SECURITY)
```python
# Establish cryptographically verified communication channels
link_result = agent.establish_link(
    target_agent="secure_processor",
    security_level="MAXIMUM",
    encryption="AES-256-GCM"
)

if link_result.is_ok():
    link_id = link_result.unwrap()
    
    # Send sensitive data through secure channel
    secure_message = Message(
        message_type="CONFIDENTIAL_DATA",
        payload={"sensitive_info": classified_data}
    ).with_link(link_id)  # EXCLUSIVE MAPLE FEATURE
    
    agent.send(secure_message)
```

## Next Steps

1. **Explore Examples**: Run the comprehensive demo
   ```bash
   python demo_package/examples/comprehensive_feature_demo.py
   ```

2. **Compare Performance**: See MAPLE's superiority
   ```bash
   python demo_package/examples/performance_comparison_example_fixed.py
   ```

3. **Production Setup**: Deploy enterprise-grade systems
   ```bash
   python maple/broker/production_broker.py --port 8080
   ```

4. **Learn Advanced Features**: 
   - [Type System](type-system.md)
   - [Resource Management](resource-management.md) 
   - [Security Model](security-model.md)
   - [API Reference](api-reference.md)

## Support

**Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)**

- 📚 [Documentation](../README.md)
- 🐛 [Issues](https://github.com/maheshvaikri-code/maple-oss/issues)
- 💬 [Discussions](https://github.com/maheshvaikri-code/maple-oss/discussions)
- 📧 [Contact Creator](mailto:mahesh@mapleagent.org)

**MAPLE: The Protocol That Changes Everything 🚀**
