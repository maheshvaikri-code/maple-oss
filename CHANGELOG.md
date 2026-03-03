<img width="358" height="358" alt="maple358" src="https://github.com/user-attachments/assets/299615b3-7c74-4344-9aff-5346b8f62c24" />

<img width="358" height="358" alt="mapleagents-358" src="https://github.com/user-attachments/assets/e78a2d4f-837a-4f72-919a-366cbe4c3eb5" />

# MAPLE Changelog

**Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)**

## Version 1.1.1 - S2.dev Integration (March 2026)

### Additions

- **S2.dev Durable Streaming**: `S2Broker` and `S2StateBackend` for durable message transport and state persistence via [s2.dev](https://s2.dev)
- **S2 Broker Type**: `BrokerType.S2` registered in `ProductionBrokerManager` with auto-detection from `s2://` broker URLs
- **Adapters Package**: New `maple/adapters/__init__.py` with conditional S2 exports
- **834 tests passing**, 16 new S2 adapter tests

### New Dependencies (optional)

```toml
[project.optional-dependencies]
s2 = ["streamstore>=5.0.0"]
```

---

## Version 1.1.0 - Autonomous Agentic AI (March 2026)

### Major Additions

- **LLM Provider Layer**: Pluggable provider system supporting OpenAI, Anthropic, and compatible APIs (vLLM, Ollama, Together)
- **Autonomous Agent**: ReAct-loop powered `AutonomousAgent` with goal pursuit, multi-step reasoning, reflection, and backtracking
- **Tool Framework**: Extensible `Tool` and `ToolRegistry` with built-in MAPLE tools (send_message, query_agents, read/write state, check resources, establish links)
- **Memory System**: Three-tier memory — `WorkingMemory` (context window), `EpisodicMemory` (task history), `SemanticMemory` (learned facts) — backed by existing `StateStore`
- **Multi-Agent Orchestrator**: `AgentOrchestrator` with supervisor and consensus execution patterns, capability-based team formation
- **MCP Tool Discovery**: Discover and register external MCP server tools as native MAPLE tools via `MCPAdapter`
- **Observability**: `DecisionLogger` and `AgentSnapshot` for full decision tracing and agent state inspection

### Infrastructure Improvements

- **Broker Wiring**: NATS broker auto-detection from `broker_url`, `ProductionBrokerManager` integration
- **Authorization Enforcement**: `AuthorizationManager` auto-initialized in `MessageBroker` when security config present
- **Message Queue & Router**: `MessageQueue` (priority ordering) and `MessageRouter` integrated into broker delivery loop
- **Agent Auto-Registration**: Agents auto-register/deregister in `AgentRegistry` on start/stop
- **Cryptographic Handshake**: Agent handshake uses real `CryptographyManager` (AES-256-GCM) with graceful fallback
- **Circuit Breaker Consolidation**: `TaskScheduler` and `FailureDetector` now use shared `error.circuit_breaker.CircuitBreaker`
- **Agent Metrics**: Built-in counters for messages sent/received/failed, handler errors, processing time
- **S2.dev Integration**: `S2Broker` and `S2StateBackend` for durable streaming via [s2.dev](https://s2.dev), auto-detected from `s2://` broker URLs

### Testing & Quality

- **818 tests passing**, 0 failures
- **80% code coverage** across all modules
- New test suites: LLM providers, autonomous agent, tools, memory, orchestrator, observability, performance optimizer, scheduler, result collector, security init

### New Dependencies (optional)

```toml
[project.optional-dependencies]
llm = ["openai>=1.0.0", "anthropic>=0.20.0"]
s2 = ["streamstore>=5.0.0"]
```

---

## Version 1.0.0 - Initial Release (December 2024)

### Major Changes
- **Protocol**: MAPLE (Multi Agent Protocol Language Engine) Multi Agent Communication Protocol
- **Attribution**: Added comprehensive attribution to Mahesh Vaikri throughout codebase
- **Enhanced Comparisons**: Updated all documentation to compare with major protocols:
  - Google A2A (Agent-to-Agent)
  - FIPA ACL (Foundation for Intelligent Physical Agents - Agent Communication Language)
  - AGENTCY
  - Model Context Protocol (MCP)

### Core Features
- **Rich Type System**: Comprehensive type validation with primitive, collection, and special types
- **Result<T,E> Pattern**: Advanced error handling with explicit success/error types
- **Resource Management**: Built-in resource specification, allocation, and negotiation
- **Link Identification Mechanism**: Secure communication channel establishment
- **Distributed State Management**: Consistency models for large-scale agent systems
- **Message Structure**: Standardized header, payload, and metadata format
- **Communication Patterns**: Request-response, publish-subscribe, streaming, and broadcast

### Security Features
- **Authentication**: JWT-based agent authentication
- **Authorization**: Role-based access control
- **Encryption**: End-to-end message encryption
- **Link Security**: Link Identification Mechanism for secure channels

### Documentation Updates
- **Comprehensive API Documentation**: Complete reference for all MAPLE components
- **Protocol Comparison**: Detailed comparison with competing protocols
- **Usage Examples**: Practical examples for common use cases
- **Best Practices**: Guidelines for effective MAPLE implementation

### Performance Characteristics
- **Scalability**: Support for 10,000+ agents
- **Latency**: 5-15ms message delivery
- **Throughput**: 10,000+ messages per second
- **Reliability**: 99.99% uptime with fault tolerance

### Use Cases
- **Manufacturing Systems**: Industrial automation and robotics coordination
- **Financial Trading**: High-frequency trading agent coordination
- **Smart Cities**: IoT and infrastructure management
- **Autonomous Vehicles**: Vehicle-to-vehicle communication
- **Healthcare**: Medical device and information system coordination

### Technical Improvements
- **Memory Optimization**: Efficient message serialization and processing
- **Network Efficiency**: Optimized protocol overhead
- **Error Recovery**: Circuit breaker pattern and retry mechanisms
- **Resource Optimization**: Dynamic allocation based on agent requirements

### Attribution
All files now include proper attribution:
```
# Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)
```

### Repository Structure
```
maple-oss/
├── maple/                 # Core MAPLE implementation
│   ├── core/             # Type system, messages, result handling
│   ├── agent/            # Agent implementation and configuration
│   ├── broker/           # Message routing and delivery
│   ├── security/         # Authentication, authorization, encryption
│   ├── resources/        # Resource management and negotiation
│   ├── communication/    # Communication patterns
│   ├── error/            # Error handling and recovery
│   └── state/            # Distributed state management
├── docs/                 # Comprehensive documentation
├── html_documentation/   # Interactive web documentation
├── sample/               # Usage examples and demos
└── tests/                # Test suite
```

### Breaking Changes
- Package name changed from `mapl` to `maple-oss`
- Import statements updated: `from maple import ...`
- Protocol name changed throughout documentation

### Future Roadmap
- **Formal Verification**: Mathematical verification of protocol correctness
- **Adaptive Protocols**: Self-optimizing communication patterns
- **Cross-Organization**: Multi-tenant agent coordination
- **Quantum Integration**: Quantum-safe cryptography support

**Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)**
