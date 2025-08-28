# Best Practices for MAPLE

**Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)**

This guide outlines best practices for implementing MAPLE (Multi Agent Protocol Language Extensible) in production systems, leveraging its revolutionary capabilities that are impossible with Google A2A, FIPA ACL, MCP, AGENTCY, or any other protocol.

## Agent Design Patterns

### 1. Resource-Aware Agent Architecture (UNIQUE TO MAPLE)

Always design agents with explicit resource consciousness:

```python
# ✅ EXCELLENT: Resource-aware agent design
class IntelligentAgent(Agent):
    def __init__(self, config: Config):
        super().__init__(config)
        self.resource_profile = self._analyze_system_capabilities()
        self.optimization_strategy = "performance_cost_balanced"
        
    def send_intelligent_message(self, message: Message) -> Result[str, Dict[str, Any]]:
        # MAPLE's unique resource optimization
        optimized_resources = self.calculate_optimal_resources(
            message_complexity=self._analyze_message_complexity(message),
            deadline=message.payload.get('deadline'),
            quality_requirements=message.payload.get('quality', {})
        )
        
        enhanced_message = message.with_resource_requirements(optimized_resources)
        return self.send_with_resource_awareness(enhanced_message, optimized_resources)
    
    def _analyze_message_complexity(self, message: Message) -> Dict[str, float]:
        """Analyze computational complexity of message processing"""
        payload = message.payload
        complexity_factors = {
            "data_size": len(str(payload.get('data', ''))),
            "algorithm_complexity": self._get_algorithm_complexity(payload.get('algorithm')),
            "expected_processing_time": payload.get('estimated_duration', 60)
        }
        return complexity_factors

# ❌ AVOID: Generic agent without resource awareness (like other protocols)
class GenericAgent:
    def send_message(self, message):
        # No resource considerations - system can't optimize
        return self.send(message)  # Silent failures possible
```

### 2. Revolutionary Error Handling with Result<T,E>

Always use MAPLE's comprehensive error handling:

```python
# ✅ EXCELLENT: MAPLE's bulletproof error handling
async def process_critical_task(self, task_data: Dict) -> Result[ProcessingResult, ProcessingError]:
    """Process task with comprehensive error handling and recovery"""
    
    # Validate input with detailed error information
    validation_result = self.validate_task_input(task_data)
    if validation_result.is_err():
        validation_error = validation_result.unwrap_err()
        return Result.err({
            "errorType": "INPUT_VALIDATION_FAILED",
            "message": "Task input validation failed",
            "details": {
                "validation_errors": validation_error,
                "input_size": len(str(task_data)),
                "expected_format": "TaskInputSchema_v2.1"
            },
            "severity": "HIGH",
            "recoverable": True,
            "suggestion": {
                "action": "REFORMAT_INPUT",
                "parameters": {
                    "auto_correction": True,
                    "schema_migration": "v2.0_to_v2.1",
                    "fallback_processing": True
                }
            }
        })
    
    # Process with resource monitoring
    processing_result = await self.execute_task_with_monitoring(
        validated_data=validation_result.unwrap(),
        resource_limits=self.get_resource_limits(),
        performance_targets=self.get_performance_targets()
    )
    
    if processing_result.is_ok():
        result_data = processing_result.unwrap()
        
        # Verify result quality
        quality_check = self.verify_result_quality(result_data)
        if quality_check.is_err():
            return Result.err({
                "errorType": "QUALITY_VERIFICATION_FAILED",
                "message": "Processing completed but quality check failed",
                "details": quality_check.unwrap_err(),
                "recoverable": True,
                "suggestion": {
                    "action": "REPROCESS_WITH_HIGHER_PRECISION",
                    "parameters": {
                        "precision_increase": 1.5,
                        "additional_validation": True
                    }
                }
            })
        
        return Result.ok({
            "data": result_data,
            "quality_metrics": quality_check.unwrap(),
            "performance_metrics": {
                "processing_time": processing_result.processing_time,
                "resource_utilization": processing_result.resource_usage,
                "efficiency_score": processing_result.efficiency
            }
        })
    else:
        processing_error = processing_result.unwrap_err()
        
        # Determine recovery strategy based on error type
        recovery_strategy = self.determine_recovery_strategy(processing_error)
        
        return Result.err({
            "errorType": "TASK_PROCESSING_FAILED",
            "message": processing_error.get('message', 'Unknown processing error'),
            "details": {
                "original_error": processing_error,
                "resource_state": self.get_current_resource_state(),
                "system_load": self.get_system_load_metrics()
            },
            "severity": processing_error.get('severity', 'MEDIUM'),
            "recoverable": recovery_strategy['possible'],
            "suggestion": recovery_strategy.get('strategy', {})
        })

# ❌ AVOID: Primitive error handling (like other protocols)
def process_task_primitively(self, task):
    try:
        result = self.process(task)  # May fail silently
        return result  # No error context, no recovery suggestions
    except Exception as e:
        # Generic exception with no structured recovery
        return {"error": str(e)}  # Useless for automated recovery
```

### 3. Secure Communication with Link Identification Mechanism

Always use MAPLE's revolutionary security features for sensitive communications:

```python
# ✅ REVOLUTIONARY: MAPLE's secure communication
class SecureAgent(Agent):
    def __init__(self, config: Config):
        super().__init__(config)
        self.secure_links = {}
        self.security_policies = SecurityPolicyManager()
        
    async def establish_secure_communications(self, target_agents: List[str]) -> Dict[str, Result[str, Dict]]:
        """Establish secure links with multiple agents"""
        link_results = {}
        
        for agent_id in target_agents:
            # Determine appropriate security level
            security_level = self.security_policies.get_required_level(agent_id)
            
            # Establish cryptographically verified link
            link_result = await self.establish_link(
                agent_id=agent_id,
                security_level=security_level,
                encryption="AES-256-GCM",
                authentication="MUTUAL_CERTIFICATE",
                lifetime_seconds=7200
            )
            
            if link_result.is_ok():
                link_id = link_result.unwrap()
                self.secure_links[agent_id] = {
                    "link_id": link_id,
                    "established_at": datetime.utcnow(),
                    "security_level": security_level,
                    "message_count": 0
                }
                logger.info(f"🔒 Secure link established with {agent_id}: {link_id}")
            else:
                logger.error(f"❌ Failed to establish link with {agent_id}: {link_result.unwrap_err()}")
            
            link_results[agent_id] = link_result
        
        return link_results
    
    async def send_classified_data(
        self, 
        target_agent: str, 
        classified_payload: Dict,
        classification_level: str = "CONFIDENTIAL"
    ) -> Result[str, Dict[str, Any]]:
        """Send classified data through verified secure channel"""
        
        # Ensure secure link exists
        if target_agent not in self.secure_links:
            link_result = await self.establish_link(
                agent_id=target_agent,
                security_level="MAXIMUM"
            )
            if link_result.is_err():
                return Result.err({
                    "errorType": "SECURE_LINK_REQUIRED",
                    "message": f"Cannot send classified data without secure link to {target_agent}",
                    "details": link_result.unwrap_err()
                })
        
        link_info = self.secure_links[target_agent]
        
        # Create classified message
        classified_message = Message(
            message_type="CLASSIFIED_COMMUNICATION",
            receiver=target_agent,
            priority=Priority.CRITICAL,
            payload={
                "classification": classification_level,
                "data": classified_payload,
                "security_metadata": {
                    "clearance_required": classification_level,
                    "handling_instructions": "AUTHORIZED_PERSONNEL_ONLY",
                    "retention_policy": "DESTROY_AFTER_PROCESSING"
                }
            }
        ).with_link(link_info['link_id'])  # EXCLUSIVE MAPLE FEATURE
        
        # Send through secure channel with verification
        send_result = await self.send_with_link_verification(classified_message)
        
        if send_result.is_ok():
            # Update link usage statistics
            self.secure_links[target_agent]["message_count"] += 1
            self.audit_log.record_classified_transmission(
                target_agent, classification_level, send_result.unwrap()
            )
        
        return send_result

# ❌ IMPOSSIBLE with other protocols - no secure link mechanism
# Google A2A: Only basic OAuth
# FIPA ACL: No security at all
# MCP: Platform security only  
# AGENTCY: No security framework
```

## Performance Optimization Patterns

### 1. Resource-Aware Message Batching

Optimize throughput with intelligent batching based on resource constraints:

```python
# ✅ MAPLE's intelligent resource-aware batching
class ResourceOptimizedAgent(Agent):
    def __init__(self, config: Config):
        super().__init__(config)
        self.batch_optimizer = BatchOptimizer(
            target_throughput="250K_messages_per_second",
            resource_constraints=self.get_system_resource_limits(),
            optimization_strategy="throughput_efficiency_balanced"
        )
        
    async def send_optimized_batch(
        self, 
        messages: List[Message],
        optimization_goal: str = "maximize_throughput"
    ) -> Dict[str, Result[str, Dict[str, Any]]]:
        """Send messages with optimal batching and resource utilization"""
        
        # Analyze message complexity and resource requirements
        batch_analysis = self.batch_optimizer.analyze_message_batch(messages)
        
        # Group messages by resource similarity and priority
        optimized_batches = self.batch_optimizer.create_optimal_batches(
            messages=messages,
            batch_analysis=batch_analysis,
            optimization_goal=optimization_goal
        )
        
        results = {}
        
        for batch in optimized_batches:
            # Allocate optimal resources for this batch
            resource_allocation = await self.allocate_batch_resources(
                batch_info=batch,
                priority_level=batch.max_priority,
                deadline=batch.earliest_deadline
            )
            
            if resource_allocation.is_ok():
                allocation = resource_allocation.unwrap()
                
                # Process batch with allocated resources
                batch_results = await self.process_message_batch(
                    messages=batch.messages,
                    allocated_resources=allocation,
                    optimization_params=batch.optimization_params
                )
                
                # Merge results
                results.update(batch_results)
                
                # Release resources
                await self.release_batch_resources(allocation)
            else:
                # Handle resource allocation failure
                allocation_error = resource_allocation.unwrap_err()
                for message in batch.messages:
                    results[message.message_id] = Result.err({
                        "errorType": "BATCH_RESOURCE_ALLOCATION_FAILED",
                        "message": "Could not allocate resources for batch processing",
                        "details": allocation_error
                    })
        
        return results
```

### 2. Adaptive Load Balancing

Implement intelligent load balancing based on agent capabilities and current load:

```python
# ✅ MAPLE's adaptive load balancing
class LoadBalancedCoordinator(Agent):
    def __init__(self, config: Config):
        super().__init__(config)
        self.agent_registry = AgentCapabilityRegistry()
        self.load_monitor = RealTimeLoadMonitor()
        self.performance_tracker = PerformanceTracker()
        
    async def distribute_workload(
        self, 
        tasks: List[Dict],
        optimization_strategy: str = "minimize_response_time"
    ) -> Dict[str, Result[str, Dict[str, Any]]]:
        """Distribute tasks across agents with optimal load balancing"""
        
        # Get current agent capabilities and load
        available_agents = await self.agent_registry.get_available_agents()
        current_loads = await self.load_monitor.get_current_loads(available_agents)
        
        # Analyze task requirements
        task_analysis = []
        for task in tasks:
            analysis = {
                "task_id": task.get('task_id'),
                "complexity": self._calculate_task_complexity(task),
                "resource_requirements": task.get('resources', {}),
                "deadline": task.get('deadline'),
                "specialized_capabilities": task.get('required_capabilities', [])
            }
            task_analysis.append(analysis)
        
        # Create optimal distribution plan
        distribution_plan = self._create_distribution_plan(
            tasks=task_analysis,
            agents=available_agents,
            current_loads=current_loads,
            strategy=optimization_strategy
        )
        
        # Execute distribution
        distribution_results = {}
        
        for allocation in distribution_plan:
            agent_id = allocation['agent_id']
            assigned_tasks = allocation['tasks']
            expected_completion = allocation['estimated_completion_time']
            
            # Create work assignment message
            work_assignment = Message(
                message_type="WORK_ASSIGNMENT",
                receiver=agent_id,
                priority=Priority.HIGH,
                payload={
                    "assignment_id": allocation['assignment_id'],
                    "tasks": assigned_tasks,
                    "resources": allocation['allocated_resources'],
                    "performance_targets": {
                        "max_response_time": expected_completion,
                        "quality_threshold": 0.95,
                        "efficiency_target": 0.90
                    },
                    "load_balancing_metadata": {
                        "total_system_load": self.load_monitor.get_system_load(),
                        "agent_current_load": current_loads.get(agent_id, 0),
                        "priority_level": allocation['priority'],
                        "fallback_agents": allocation.get('fallback_agents', [])
                    }
                }
            )
            
            # Send with resource awareness and monitoring
            send_result = await self.send_with_performance_monitoring(
                message=work_assignment,
                performance_callback=lambda metrics: self.performance_tracker.record_metrics(
                    agent_id, metrics
                )
            )
            
            for task in assigned_tasks:
                distribution_results[task['task_id']] = send_result
        
        return distribution_results
    
    def _create_distribution_plan(
        self, 
        tasks: List[Dict], 
        agents: List[Dict], 
        current_loads: Dict[str, float],
        strategy: str
    ) -> List[Dict]:
        """Create optimal task distribution plan"""
        
        if strategy == "minimize_response_time":
            return self._optimize_for_response_time(tasks, agents, current_loads)
        elif strategy == "maximize_throughput":
            return self._optimize_for_throughput(tasks, agents, current_loads)
        elif strategy == "balance_load":
            return self._optimize_for_load_balance(tasks, agents, current_loads)
        else:
            return self._optimize_mixed_strategy(tasks, agents, current_loads, strategy)
```

## Production Deployment Patterns

### 1. High-Availability Configuration

```python
# ✅ Production-grade high-availability setup
class ProductionMAPLECluster:
    def __init__(self):
        self.cluster_config = self._create_ha_configuration()
        self.health_monitor = ClusterHealthMonitor()
        self.failover_manager = AutomaticFailoverManager()
        
    def _create_ha_configuration(self) -> ClusterConfig:
        """Create high-availability cluster configuration"""
        return ClusterConfig(
            broker_nodes=[
                "nats://primary-broker:4222",
                "nats://secondary-broker:4222", 
                "nats://tertiary-broker:4222"
            ],
            replication_factor=3,
            consistency_level=ConsistencyLevel.STRONG,
            automatic_failover=True,
            health_check_interval="5s",
            performance_monitoring=True,
            
            # MAPLE-specific HA features
            resource_replication=True,
            state_synchronization=True,
            link_failover=True,
            
            # Security configuration
            security=SecurityConfig(
                auth_type="mutual_tls_jwt",
                require_links=True,
                strict_link_policy=True,
                certificate_rotation="24h",
                audit_logging=True
            ),
            
            # Performance configuration
            performance=PerformanceConfig(
                target_throughput="300K_messages_per_second",
                max_latency="1ms",
                connection_pool_size=100,
                adaptive_routing=True,
                load_balancing=True,
                auto_scaling=True
            )
        )
    
    async def deploy_production_agents(
        self, 
        agent_specifications: List[AgentSpec]
    ) -> Dict[str, Result[Agent, Dict[str, Any]]]:
        """Deploy agents with production-grade configuration"""
        
        deployment_results = {}
        
        for spec in agent_specifications:
            # Create production configuration
            prod_config = Config(
                agent_id=spec.agent_id,
                broker_url=self.cluster_config.get_primary_broker(),
                security=self.cluster_config.security,
                performance=self.cluster_config.performance,
                resources=spec.resource_requirements,
                monitoring=MonitoringConfig(
                    metrics_enabled=True,
                    health_checks=True,
                    performance_profiling=True,
                    distributed_tracing=True
                )
            )
            
            try:
                # Create and configure agent
                agent = Agent(prod_config)
                
                # Register health checks
                await self.health_monitor.register_agent(agent)
                
                # Configure automatic failover
                await self.failover_manager.configure_agent_failover(agent, spec.failover_config)
                
                # Start agent with production monitoring
                await agent.start_with_monitoring()
                
                deployment_results[spec.agent_id] = Result.ok(agent)
                
                logger.info(f"✅ Production agent deployed: {spec.agent_id}")
                
            except Exception as e:
                deployment_results[spec.agent_id] = Result.err({
                    "errorType": "AGENT_DEPLOYMENT_FAILED",
                    "message": f"Failed to deploy agent {spec.agent_id}",
                    "details": {
                        "exception": str(e),
                        "configuration": prod_config.to_dict(),
                        "system_state": self.get_system_state()
                    }
                })
                
                logger.error(f"❌ Agent deployment failed: {spec.agent_id}")
        
        return deployment_results
```

### 2. Monitoring and Observability

```python
# ✅ Comprehensive production monitoring
class MAPLEObservabilityStack:
    def __init__(self):
        self.metrics_collector = MetricsCollector()
        self.trace_collector = DistributedTraceCollector()
        self.log_aggregator = LogAggregator()
        self.alert_manager = AlertManager()
        
    async def setup_comprehensive_monitoring(self, agents: List[Agent]):
        """Setup complete observability for MAPLE agents"""
        
        for agent in agents:
            # Performance metrics
            await self.metrics_collector.instrument_agent(
                agent=agent,
                metrics=[
                    "message_throughput",
                    "message_latency", 
                    "resource_utilization",
                    "error_rates",
                    "link_establishment_time",
                    "state_synchronization_latency"
                ]
            )
            
            # Distributed tracing
            await self.trace_collector.enable_agent_tracing(
                agent=agent,
                trace_sampling_rate=0.1,  # 10% sampling
                include_payloads=False,   # Security
                trace_context_propagation=True
            )
            
            # Log aggregation
            await self.log_aggregator.configure_agent_logging(
                agent=agent,
                log_levels=["ERROR", "WARN", "INFO"],
                structured_logging=True,
                include_security_events=True
            )
            
            # Alerting rules
            await self.alert_manager.configure_agent_alerts(
                agent=agent,
                alert_rules=[
                    {
                        "condition": "message_error_rate > 0.01",
                        "severity": "WARNING",
                        "action": "investigate_error_spike"
                    },
                    {
                        "condition": "resource_utilization > 0.90",
                        "severity": "CRITICAL", 
                        "action": "auto_scale_resources"
                    },
                    {
                        "condition": "link_establishment_failures > 5",
                        "severity": "HIGH",
                        "action": "check_security_infrastructure"
                    }
                ]
            )
```

## Security Best Practices

### 1. Zero-Trust Security Model

```python
# ✅ MAPLE's zero-trust security implementation
class ZeroTrustMAPLEAgent(Agent):
    def __init__(self, config: Config):
        super().__init__(config)
        self.security_policy = ZeroTrustSecurityPolicy()
        self.identity_verifier = ContinuousIdentityVerifier()
        self.behavior_monitor = BehaviorAnomalyMonitor()
        
    async def send_with_zero_trust(
        self, 
        message: Message,
        trust_level: TrustLevel = TrustLevel.VERIFY
    ) -> Result[str, Dict[str, Any]]:
        """Send message with zero-trust security verification"""
        
        # 1. Verify sender identity continuously
        identity_verification = await self.identity_verifier.verify_current_identity()
        if identity_verification.is_err():
            return Result.err({
                "errorType": "IDENTITY_VERIFICATION_FAILED",
                "message": "Sender identity could not be verified",
                "details": identity_verification.unwrap_err()
            })
        
        # 2. Verify receiver identity and authorization
        receiver_verification = await self.verify_receiver_authorization(
            receiver_id=message.receiver,
            message_type=message.message_type,
            payload_classification=self.classify_payload_sensitivity(message.payload)
        )
        if receiver_verification.is_err():
            return Result.err({
                "errorType": "RECEIVER_AUTHORIZATION_FAILED",
                "message": f"Receiver {message.receiver} not authorized for this message type",
                "details": receiver_verification.unwrap_err()
            })
        
        # 3. Establish or verify secure link based on trust level
        if trust_level in [TrustLevel.VERIFY, TrustLevel.MAXIMUM]:
            link_result = await self.ensure_secure_link(
                target=message.receiver,
                required_security_level=trust_level.to_security_level()
            )
            if link_result.is_err():
                return Result.err({
                    "errorType": "SECURE_LINK_REQUIRED", 
                    "message": "Cannot send message without verified secure link",
                    "details": link_result.unwrap_err()
                })
            
            message = message.with_link(link_result.unwrap())
        
        # 4. Monitor behavior for anomalies
        behavior_analysis = await self.behavior_monitor.analyze_send_request(
            message=message,
            historical_patterns=self.get_historical_communication_patterns(),
            current_context=self.get_current_security_context()
        )
        
        if behavior_analysis.indicates_anomaly():
            # Flag for security review but allow with additional monitoring
            await self.security_policy.flag_for_review(
                agent_id=self.agent_id,
                anomaly_details=behavior_analysis.get_anomaly_details(),
                message_metadata=message.get_security_metadata()
            )
        
        # 5. Send with enhanced monitoring
        send_result = await self.send_with_enhanced_monitoring(
            message=message,
            monitoring_level=MonitoringLevel.HIGH,
            audit_trail=True
        )
        
        # 6. Verify delivery and log security event
        if send_result.is_ok():
            await self.security_policy.log_secure_transmission(
                sender=self.agent_id,
                receiver=message.receiver,
                message_id=send_result.unwrap(),
                security_metadata={
                    "trust_level": trust_level.value,
                    "link_used": message.get_link_id(),
                    "identity_verified": True,
                    "behavior_normal": not behavior_analysis.indicates_anomaly()
                }
            )
        
        return send_result
```

## Testing Strategies

### 1. Comprehensive Testing Framework

```python
# ✅ MAPLE testing best practices
class MAPLETestSuite:
    def __init__(self):
        self.test_broker = TestBroker()
        self.mock_agents = MockAgentFactory()
        self.resource_simulator = ResourceSimulator()
        self.security_tester = SecurityTestSuite()
        
    async def test_resource_aware_communication(self):
        """Test MAPLE's unique resource-aware capabilities"""
        
        # Create test agents with different resource profiles
        high_performance_agent = self.mock_agents.create_agent(
            agent_id="high_perf_agent",
            resource_profile="high_performance",
            capabilities=["gpu_computing", "large_memory_processing"]
        )
        
        constrained_agent = self.mock_agents.create_agent(
            agent_id="constrained_agent", 
            resource_profile="resource_constrained",
            capabilities=["basic_processing"]
        )
        
        # Test resource negotiation
        resource_request = ResourceRequest(
            compute=ResourceRange(min=16, preferred=32, max=64),
            memory=ResourceRange(min="32GB", preferred="64GB", max="128GB"),
            gpu_memory=ResourceRange(min="16GB", preferred="32GB"),
            deadline="2024-12-25T15:00:00Z"
        )
        
        # Send resource-intensive message
        message = Message(
            message_type="RESOURCE_INTENSIVE_TASK",
            receiver="high_perf_agent",
            payload={
                "task": "complex_ai_processing",
                "data_size": "10GB",
                "resources": resource_request.to_dict()
            }
        )
        
        # Test with high-performance agent (should succeed)
        result_hp = await constrained_agent.send_with_resource_awareness(message, resource_request)
        assert result_hp.is_ok(), "High-performance agent should handle resource request"
        
        # Test with constrained agent (should provide alternatives)
        message_constrained = message.with_receiver("constrained_agent")
        result_constrained = await constrained_agent.send_with_resource_awareness(
            message_constrained, resource_request
        )
        
        if result_constrained.is_err():
            error = result_constrained.unwrap_err()
            assert error['errorType'] == 'RESOURCE_UNAVAILABLE'
            assert 'suggestion' in error
            assert error['recoverable'] == True
            
            # Test recovery strategy
            recovery = error['suggestion']
            if recovery.get('action') == 'REDUCE_RESOURCE_REQUIREMENTS':
                reduced_request = self.resource_simulator.apply_reduction_strategy(
                    original_request=resource_request,
                    reduction_strategy=recovery
                )
                
                retry_result = await constrained_agent.send_with_resource_awareness(
                    message_constrained, reduced_request
                )
                assert retry_result.is_ok(), "Reduced resource request should succeed"
    
    async def test_result_type_error_handling(self):
        """Test MAPLE's revolutionary Result<T,E> pattern"""
        
        agent = self.mock_agents.create_agent("test_agent")
        
        # Test successful operation
        success_message = Message(
            message_type="SIMPLE_TASK",
            payload={"data": "valid_data"}
        )
        
        result = await agent.send(success_message)
        assert result.is_ok(), "Valid message should succeed"
        
        message_id = result.unwrap()
        assert isinstance(message_id, str), "Success should return message ID"
        
        # Test error operation  
        error_message = Message(
            message_type="INVALID_TASK",
            payload={"data": "invalid_data"}
        )
        
        error_result = await agent.send(error_message)
        assert error_result.is_err(), "Invalid message should fail"
        
        error = error_result.unwrap_err()
        assert 'errorType' in error, "Error should have type"
        assert 'message' in error, "Error should have message"
        assert 'details' in error, "Error should have details"
        
        # Test error recovery
        if error.get('recoverable'):
            suggestion = error.get('suggestion', {})
            assert 'action' in suggestion, "Recoverable error should have suggestion"
        
        # Test Result operations
        chained_result = (
            agent.send(success_message)
            .map(lambda mid: f"processed_{mid}")
            .and_then(lambda processed: Result.ok(f"final_{processed}"))
        )
        
        assert chained_result.is_ok(), "Result chaining should work"
        final_value = chained_result.unwrap()
        assert final_value.startswith("final_processed_"), "Result chaining should transform value"
```

**Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)**

These best practices leverage MAPLE's revolutionary capabilities that are literally impossible with Google A2A, FIPA ACL, MCP, AGENTCY, or any other protocol. Following these patterns ensures optimal performance, security, and reliability in production systems.

**🚀 MAPLE: The Protocol That Changes Everything 🚀**
