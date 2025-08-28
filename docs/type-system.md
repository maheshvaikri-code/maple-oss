# MAPLE Type System

**Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)**

MAPLE features the most comprehensive type system in agent communication, providing unprecedented type safety and validation capabilities that are impossible with Google A2A, FIPA ACL, MCP, AGENTCY, or any other protocol.

## Revolutionary Result<T,E> Pattern

The Result<T,E> type is MAPLE's breakthrough innovation that **eliminates ALL silent failures** in agent communication.

### Core Concept

```python
from maple.core import Result

# Every operation returns Result<T,E> - success or structured error
def process_data(data) -> Result[ProcessedData, ProcessingError]:
    if not validate_input(data):
        return Result.err({
            "errorType": "VALIDATION_ERROR",
            "message": "Invalid input format",
            "details": {
                "expected": "JSON with timestamp",
                "received": type(data).__name__,
                "missing_fields": ["timestamp", "agent_id"]
            },
            "severity": "HIGH",
            "recoverable": True,
            "suggestion": {
                "action": "REFORMAT_DATA",
                "parameters": {
                    "add_timestamp": True,
                    "validate_schema": True
                }
            }
        })
    
    try:
        processed = advanced_processing(data)
        return Result.ok({
            "data": processed,
            "confidence": 0.98,
            "processing_time": "1.2s",
            "resource_usage": {
                "cpu": "45%",
                "memory": "2.1GB"
            }
        })
    except Exception as e:
        return Result.err({
            "errorType": "PROCESSING_ERROR", 
            "message": str(e),
            "recoverable": False
        })
```

### Result Operations

```python
# Chain operations safely - NO SILENT FAILURES
result = (
    load_data(source)
    .and_then(lambda data: validate_schema(data))
    .map(lambda valid_data: process_ai_analysis(valid_data))
    .and_then(lambda analysis: generate_insights(analysis))
    .map(lambda insights: format_output(insights))
)

if result.is_ok():
    final_output = result.unwrap()
    print(f"Success: {final_output}")
else:
    error = result.unwrap_err()
    print(f"Pipeline failed: {error['message']}")
    
    # Intelligent error recovery
    if error.get('recoverable'):
        recovery_strategy = error.get('suggestion', {})
        apply_recovery_strategy(recovery_strategy)
```

## Comprehensive Type System

### Primitive Types

```python
from maple.core.types import (
    Boolean, Integer, Float, String, 
    Timestamp, UUID, Byte, Size, Duration
)

# Type validation with detailed error information
try:
    memory_size = Size.validate("16GB")  # Returns bytes
    duration = Duration.validate("30s")  # Returns seconds
    agent_id = UUID.validate("550e8400-e29b-41d4-a716-446655440000")
except ValueError as e:
    print(f"Type validation failed: {e}")
```

### Collection Types

```python
from maple.core.types import Array, Map, Set, Option

# Strongly typed collections
AgentList = Array(String)
ResourceMap = Map(String, Integer) 
CapabilitySet = Set(String)
OptionalConfig = Option(Map(String, String))

# Validation ensures type safety
agent_list = AgentList.validate(["agent_1", "agent_2", "agent_3"])
resources = ResourceMap.validate({"cpu": 8, "memory": 16, "gpu": 2})
```

### Protocol-Specific Types

```python
from maple.core.types import Priority, AgentID, MessageID

class Priority(Enum):
    CRITICAL = "CRITICAL"      # Life-critical systems
    HIGH = "HIGH"              # High-priority tasks  
    MEDIUM = "MEDIUM"          # Standard priority
    LOW = "LOW"                # Background tasks
    BATCH = "BATCH"            # Batch processing

# Usage in messages
message = Message(
    message_type="EMERGENCY_ALERT",
    priority=Priority.CRITICAL,  # Type-safe priority
    payload={
        "alert_type": "SYSTEM_FAILURE",
        "affected_agents": AgentList.validate([...]),
        "response_time": Duration.validate("30s")
    }
)
```

## Resource Types (UNIQUE TO MAPLE)

### Resource Specifications

```python
from maple.resources import ResourceRequest, ResourceRange

# Define resource requirements with precision
resource_spec = ResourceRequest(
    # Computational resources
    compute=ResourceRange(min=4, preferred=8, max=16),
    memory=ResourceRange(min="8GB", preferred="16GB", max="32GB"),
    gpu_memory=ResourceRange(min="4GB", preferred="8GB", max="24GB"),
    
    # Network resources  
    network_bandwidth=ResourceRange(min="100Mbps", preferred="1Gbps", max="10Gbps"),
    network_latency=ResourceRange(max="10ms", preferred="1ms"),
    
    # Storage resources
    storage=ResourceRange(min="100GB", preferred="1TB", max="10TB"),
    iops=ResourceRange(min=1000, preferred=10000, max=100000),
    
    # Time constraints
    deadline="2024-12-25T18:00:00Z",
    timeout="30s",
    
    # Optimization preferences
    priority="HIGH",
    cost_optimization=False,
    energy_efficiency=True
)
```

### Resource Negotiation Types

```python
from maple.resources import ResourceOffer, ResourceAllocation

# Structured resource negotiation
class ResourceOffer:
    def __init__(self, resources, conditions, alternatives):
        self.resources = resources          # What's being offered
        self.conditions = conditions        # Requirements/constraints
        self.alternatives = alternatives    # Fallback options
        self.expiry = "2024-12-13T16:00:00Z"
        
# Resource allocation tracking
class ResourceAllocation:
    def __init__(self, allocation_id, resources, duration):
        self.allocation_id = allocation_id
        self.resources = resources
        self.allocated_at = datetime.utcnow()
        self.expires_at = allocated_at + duration
        self.usage_tracking = ResourceUsageTracker()
```

## Message Type System

### Structured Message Types

```python
from maple.core.message import Message
from maple.core.types import MessageType, Payload

# Type-safe message construction
class TaskAssignment:
    @staticmethod
    def validate(payload):
        required_fields = ["task_id", "task_type", "parameters", "deadline"]
        for field in required_fields:
            if field not in payload:
                raise ValueError(f"Missing required field: {field}")
        return payload

# Usage with type validation
assignment_message = Message(
    message_type="TASK_ASSIGNMENT",
    payload=TaskAssignment.validate({
        "task_id": "TASK_001",
        "task_type": "DATA_ANALYSIS",
        "parameters": {
            "algorithm": "deep_learning",
            "dataset_size": "1TB",
            "accuracy_threshold": 0.95
        },
        "deadline": "2024-12-20T10:00:00Z",
        "resources": resource_spec.to_dict()
    })
)
```

### Error Type Hierarchy

```python
from maple.error.types import ErrorType, Severity

class MAPLEError:
    def __init__(self, error_type, message, details=None, severity=Severity.MEDIUM):
        self.error_type = error_type
        self.message = message
        self.details = details or {}
        self.severity = severity
        self.timestamp = datetime.utcnow()
        self.recoverable = self._determine_recoverability()
        self.suggestion = self._generate_recovery_suggestion()

# Hierarchical error types
class ErrorType(Enum):
    # Communication errors
    NETWORK_ERROR = "NETWORK_ERROR"
    TIMEOUT = "TIMEOUT"
    ROUTING_ERROR = "ROUTING_ERROR"
    
    # Processing errors
    VALIDATION_ERROR = "VALIDATION_ERROR"
    RESOURCE_ERROR = "RESOURCE_ERROR" 
    LOGIC_ERROR = "LOGIC_ERROR"
    
    # Security errors
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"
    ENCRYPTION_ERROR = "ENCRYPTION_ERROR"
    LINK_VERIFICATION_FAILED = "LINK_VERIFICATION_FAILED"
    
    # System errors
    AGENT_UNAVAILABLE = "AGENT_UNAVAILABLE"
    SERVICE_DEGRADED = "SERVICE_DEGRADED"
    RESOURCE_EXHAUSTED = "RESOURCE_EXHAUSTED"
```

## State Types (REVOLUTIONARY DISTRIBUTED STATE)

### State Management Types

```python
from maple.state import StateManager, ConsistencyLevel, ConflictResolution

# Distributed state with type safety
class DistributedState:
    def __init__(self, state_id, initial_value, consistency_level):
        self.state_id = state_id
        self.value = initial_value
        self.version = 0
        self.consistency_level = consistency_level
        self.last_updated = datetime.utcnow()
        self.replicas = {}
        
# Complex state operations
global_mission_state = StateManager.create_distributed_state(
    state_id="mission_control",
    initial_value={
        "mission_status": "ACTIVE",
        "agent_assignments": {},
        "resource_allocation": {},
        "security_status": "GREEN"
    },
    consistency_level=ConsistencyLevel.STRONG,
    conflict_resolution=ConflictResolution.LAST_WRITER_WINS
)
```

## Validation and Error Reporting

### Comprehensive Validation

```python
from maple.core.types import TypeValidator

class ComprehensiveValidator:
    @staticmethod
    def validate_complex_message(message_data):
        """Validate complex multi-layered message structure"""
        errors = []
        
        # Header validation
        if 'header' not in message_data:
            errors.append(ValidationError("Missing header"))
        else:
            header_errors = validate_header(message_data['header'])
            errors.extend(header_errors)
            
        # Payload validation  
        if 'payload' not in message_data:
            errors.append(ValidationError("Missing payload"))
        else:
            payload_errors = validate_payload_by_type(
                message_data.get('messageType'), 
                message_data['payload']
            )
            errors.extend(payload_errors)
            
        # Resource validation
        if 'resources' in message_data['payload']:
            resource_errors = ResourceRequest.validate(
                message_data['payload']['resources']
            )
            errors.extend(resource_errors)
        
        if errors:
            return Result.err({
                "errorType": "VALIDATION_ERROR",
                "message": "Message validation failed",
                "details": {
                    "validation_errors": [e.to_dict() for e in errors],
                    "error_count": len(errors),
                    "message_id": message_data.get('messageId', 'unknown')
                },
                "suggestion": {
                    "action": "FIX_VALIDATION_ERRORS",
                    "fix_suggestions": generate_fix_suggestions(errors)
                }
            })
        
        return Result.ok(message_data)
```

## Type System Advantages Over Competitors

### MAPLE vs Other Protocols

| Feature | **MAPLE** | Google A2A | FIPA ACL | MCP | AGENTCY |
|---------|-----------|------------|----------|-----|---------|
| **Result<T,E> Pattern** | ✅ **REVOLUTIONARY** | ❌ None | ❌ None | ❌ None | ❌ None |
| **Resource Types** | ✅ **FIRST-IN-INDUSTRY** | ❌ None | ❌ None | ❌ None | ❌ None |
| **Error Hierarchy** | ✅ **COMPREHENSIVE** | ⚠️ Basic | ❌ None | ⚠️ Limited | ❌ None |
| **Type Validation** | ✅ **RUNTIME + COMPILE** | ⚠️ JSON Schema | ❌ Legacy | ⚠️ Interface | ❌ None |
| **State Types** | ✅ **DISTRIBUTED** | ❌ External | ❌ None | ❌ None | ❌ Academic |
| **Generic Types** | ✅ **FULL SUPPORT** | ⚠️ Limited | ❌ None | ⚠️ Basic | ❌ None |

**MAPLE's type system is literally years ahead of any competitor.**

## API Reference

### Core Type Classes

```python
# Import all type system components
from maple.core.types import (
    # Primitive types
    Boolean, Integer, Float, String, Timestamp, UUID, Byte,
    
    # Size and duration types
    Size, Duration,
    
    # Collection types  
    Array, Map, Set, Option,
    
    # Protocol types
    Priority, AgentID, MessageID,
    
    # Validation utilities
    TypeValidator
)

# Import resource types
from maple.resources import (
    ResourceRequest, ResourceRange, ResourceOffer, 
    ResourceAllocation, TimeConstraint
)

# Import error types
from maple.error.types import (
    ErrorType, Severity, MAPLEError
)

# Import state types
from maple.state import (
    StateManager, DistributedState, ConsistencyLevel, 
    ConflictResolution
)
```

**Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)**

MAPLE's type system represents the most significant advancement in agent communication since the field began. No other protocol provides this level of type safety, error prevention, and structured validation.

**🚀 MAPLE: The Protocol That Changes Everything 🚀**
