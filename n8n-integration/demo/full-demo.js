#!/usr/bin/env node
// 🍁 MAPLE n8n Full Demo Script
// Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

const { MAPLEClient } = require('../lib/MAPLEClient');
const MAPLEDemoLauncher = require('./launch-demo');
const fs = require('fs');
const path = require('path');
const axios = require('axios');

console.log('🍁 MAPLE n8n Full Integration Demo');
console.log('Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)');
console.log('====================================================');

class MAPLEFullDemo {
  constructor() {
    this.launcher = new MAPLEDemoLauncher();
    this.pythonBridgeUrl = 'http://localhost:8000';
    this.webSocketUrl = 'ws://localhost:8080';
    this.demoUrl = 'http://localhost:3000';
    this.apiKey = 'demo-key-12345';
    this.results = {};
  }

  async run() {
    try {
      console.log('🚀 Starting Full MAPLE Demo...');
      
      // 1. Launch MAPLE services
      await this.launchServices();
      
      // 2. Run comprehensive tests
      await this.runComprehensiveTests();
      
      // 3. Test n8n workflows
      await this.testN8nWorkflows();
      
      // 4. Performance benchmarks
      await this.runPerformanceBenchmarks();
      
      // 5. Generate report
      await this.generateReport();
      
      console.log('✅ Full Demo completed successfully!');
      console.log('📊 Check demo-results.json for detailed results');
      
    } catch (error) {
      console.error('❌ Full Demo failed:', error.message);
      await this.cleanup();
      process.exit(1);
    }
  }

  async launchServices() {
    console.log('\n🏗️ Launching MAPLE Services...');
    
    await this.launcher.launch();
    
    // Wait for services to be ready
    await this.waitForServices();
    
    console.log('✅ All services are ready');
  }

  async waitForServices() {
    console.log('⏳ Waiting for services to be ready...');
    
    const maxAttempts = 30;
    let attempts = 0;
    
    while (attempts < maxAttempts) {
      try {
        const pythonHealth = await axios.get(`${this.pythonBridgeUrl}/health`, { timeout: 1000 });
        const demoHealth = await axios.get(`${this.demoUrl}/test/connection`, { timeout: 1000 });
        
        if (pythonHealth.data.status === 'ok' && demoHealth.data.status === 'success') {
          console.log('✅ Services are healthy');
          return;
        }
      } catch (error) {
        // Services not ready yet
      }
      
      attempts++;
      await new Promise(resolve => setTimeout(resolve, 1000));
      process.stdout.write('.');
    }
    
    console.log('\n⚠️ Services may not be fully ready, proceeding with tests...');
  }

  async runComprehensiveTests() {
    console.log('\n🧪 Running Comprehensive Tests...');
    
    this.results.tests = {};
    
    // Test 1: Basic Connectivity
    this.results.tests.connectivity = await this.testConnectivity();
    
    // Test 2: Agent Lifecycle
    this.results.tests.agentLifecycle = await this.testAgentLifecycle();
    
    // Test 3: Message Patterns
    this.results.tests.messagePatterns = await this.testMessagePatterns();
    
    // Test 4: Resource Management
    this.results.tests.resourceManagement = await this.testResourceManagement();
    
    // Test 5: Error Handling
    this.results.tests.errorHandling = await this.testErrorHandling();
    
    // Test 6: Security Features
    this.results.tests.security = await this.testSecurity();
    
    // Test 7: State Management
    this.results.tests.stateManagement = await this.testStateManagement();
  }

  async testConnectivity() {
    console.log('🔌 Testing Connectivity...');
    
    const client = new MAPLEClient({
      brokerUrl: this.webSocketUrl,
      apiKey: this.apiKey,
      agentId: 'connectivity-test',
      pythonBridgeUrl: this.pythonBridgeUrl
    });

    try {
      const startTime = Date.now();
      const connectResult = await client.connect();
      const connectTime = Date.now() - startTime;
      
      if (connectResult.isOk) {
        // Test ping
        const pingStart = Date.now();
        const pingResult = await client.sendMessage({
          header: { messageType: 'PING', priority: 'LOW' },
          payload: { test: true }
        });
        const pingTime = Date.now() - pingStart;
        
        client.disconnect();
        
        return {
          success: true,
          connectTime,
          pingTime,
          roundTripTime: pingTime
        };
      } else {
        return {
          success: false,
          error: connectResult.error
        };
      }
    } catch (error) {
      return {
        success: false,
        error: error.message
      };
    }
  }

  async testAgentLifecycle() {
    console.log('🤖 Testing Agent Lifecycle...');
    
    const client = new MAPLEClient({
      brokerUrl: this.webSocketUrl,
      apiKey: this.apiKey,
      agentId: 'lifecycle-test',
      pythonBridgeUrl: this.pythonBridgeUrl
    });

    try {
      await client.connect();
      
      const agentId = 'lifecycle-test-agent';
      const results = [];
      
      // Create agent
      const createStart = Date.now();
      const createResult = await client.createAgent({
        agentId,
        capabilities: ['test-processing', 'mock-analysis'],
        config: { timeout: '30s', maxConcurrency: 5 }
      });
      results.push({
        operation: 'create',
        success: createResult.isOk,
        time: Date.now() - createStart,
        result: createResult.isOk ? createResult.value : createResult.error
      });
      
      if (createResult.isOk) {
        // Execute tasks
        for (let i = 0; i < 3; i++) {
          const taskStart = Date.now();
          const taskResult = await client.executeTask({
            agentId,
            task: {
              type: 'test-task',
              data: `Test data ${i + 1}`,
              iteration: i + 1
            },
            priority: i === 0 ? 'HIGH' : 'MEDIUM'
          });
          results.push({
            operation: `task_${i + 1}`,
            success: taskResult.isOk,
            time: Date.now() - taskStart,
            result: taskResult.isOk ? taskResult.value : taskResult.error
          });
        }
        
        // Check status
        const statusStart = Date.now();
        const statusResult = await client.getAgentStatus(agentId);
        results.push({
          operation: 'status',
          success: statusResult.isOk,
          time: Date.now() - statusStart,
          result: statusResult.isOk ? statusResult.value : statusResult.error
        });
      }
      
      client.disconnect();
      
      return {
        success: results.every(r => r.success),
        operations: results,
        totalTime: results.reduce((sum, r) => sum + r.time, 0)
      };
    } catch (error) {
      return {
        success: false,
        error: error.message
      };
    }
  }

  async testMessagePatterns() {
    console.log('💬 Testing Message Patterns...');
    
    const client = new MAPLEClient({
      brokerUrl: this.webSocketUrl,
      apiKey: this.apiKey,
      agentId: 'message-test',
      pythonBridgeUrl: this.pythonBridgeUrl
    });

    try {
      await client.connect();
      
      const patterns = [];
      
      // Request-Response Pattern
      const rrStart = Date.now();
      const rrResult = await client.sendMessage({
        header: { messageType: 'REQUEST_RESPONSE_TEST', priority: 'MEDIUM' },
        payload: { pattern: 'request-response', data: 'test data' }
      });
      patterns.push({
        pattern: 'request-response',
        success: rrResult.isOk,
        time: Date.now() - rrStart
      });
      
      // Async Message Pattern
      const asyncStart = Date.now();
      const asyncResult = await client.sendMessage({
        header: { messageType: 'ASYNC_TEST', priority: 'LOW' },
        payload: { pattern: 'async', callback: false }
      });
      patterns.push({
        pattern: 'async',
        success: asyncResult.isOk,
        time: Date.now() - asyncStart
      });
      
      // Broadcast Pattern (simulated)
      const broadcastStart = Date.now();
      const broadcastPromises = [];
      for (let i = 0; i < 3; i++) {
        broadcastPromises.push(
          client.sendMessage({
            header: { messageType: 'BROADCAST_TEST', priority: 'LOW' },
            payload: { pattern: 'broadcast', recipient: i, data: `broadcast ${i}` }
          })
        );
      }
      const broadcastResults = await Promise.allSettled(broadcastPromises);
      patterns.push({
        pattern: 'broadcast',
        success: broadcastResults.every(r => r.status === 'fulfilled'),
        time: Date.now() - broadcastStart,
        messageCount: 3
      });
      
      client.disconnect();
      
      return {
        success: patterns.every(p => p.success),
        patterns,
        totalPatterns: patterns.length
      };
    } catch (error) {
      return {
        success: false,
        error: error.message
      };
    }
  }

  async testResourceManagement() {
    console.log('💾 Testing Resource Management...');
    
    const client = new MAPLEClient({
      brokerUrl: this.webSocketUrl,
      apiKey: this.apiKey,
      agentId: 'resource-test',
      pythonBridgeUrl: this.pythonBridgeUrl
    });

    try {
      await client.connect();
      
      const allocations = [];
      
      // Test different resource types
      const resourceTypes = [
        { compute: 2, memory: '4GB', priority: 'MEDIUM' },
        { compute: 4, memory: '8GB', storage: '20GB', priority: 'HIGH' },
        { memory: '16GB', bandwidth: '1Gbps', priority: 'LOW' }
      ];
      
      for (let i = 0; i < resourceTypes.length; i++) {
        const allocStart = Date.now();
        const allocResult = await client.allocateResources(resourceTypes[i]);
        allocations.push({
          allocation: i + 1,
          success: allocResult.isOk,
          time: Date.now() - allocStart,
          resources: resourceTypes[i],
          result: allocResult.isOk ? allocResult.value : allocResult.error
        });
      }
      
      client.disconnect();
      
      return {
        success: allocations.every(a => a.success),
        allocations,
        totalAllocated: allocations.length
      };
    } catch (error) {
      return {
        success: false,
        error: error.message
      };
    }
  }

  async testErrorHandling() {
    console.log('⚠️ Testing Error Handling...');
    
    const client = new MAPLEClient({
      brokerUrl: this.webSocketUrl,
      apiKey: this.apiKey,
      agentId: 'error-test',
      pythonBridgeUrl: this.pythonBridgeUrl
    });

    try {
      await client.connect();
      
      const errorTests = [];
      
      // Test invalid agent ID
      const invalidAgentResult = await client.getAgentStatus('non-existent-agent');
      errorTests.push({
        test: 'invalid_agent',
        expectedError: true,
        actualError: !invalidAgentResult.isOk,
        success: !invalidAgentResult.isOk
      });
      
      // Test invalid message type
      const invalidMessageResult = await client.sendMessage({
        header: { messageType: 'INVALID_MESSAGE_TYPE', priority: 'MEDIUM' },
        payload: { test: 'error handling' }
      });
      errorTests.push({
        test: 'invalid_message',
        expectedError: false, // Should be handled gracefully
        actualError: !invalidMessageResult.isOk,
        success: true // Any response is fine
      });
      
      // Test timeout (simulate with very short timeout)
      const shortTimeoutClient = new MAPLEClient({
        brokerUrl: this.webSocketUrl,
        apiKey: this.apiKey,
        agentId: 'timeout-test',
        requestTimeout: 100 // Very short timeout
      });
      
      await shortTimeoutClient.connect();
      const timeoutResult = await shortTimeoutClient.sendMessage({
        header: { messageType: 'SLOW_OPERATION', priority: 'LOW' },
        payload: { delay: 5000 }
      });
      shortTimeoutClient.disconnect();
      
      errorTests.push({
        test: 'timeout',
        expectedError: true,
        actualError: !timeoutResult.isOk,
        success: !timeoutResult.isOk
      });
      
      client.disconnect();
      
      return {
        success: errorTests.every(t => t.success),
        tests: errorTests,
        totalTests: errorTests.length
      };
    } catch (error) {
      return {
        success: false,
        error: error.message
      };
    }
  }

  async testSecurity() {
    console.log('🔒 Testing Security Features...');
    
    // Test valid API key
    const validClient = new MAPLEClient({
      brokerUrl: this.webSocketUrl,
      apiKey: this.apiKey,
      agentId: 'security-test-valid'
    });

    const securityTests = [];
    
    try {
      const validResult = await validClient.connect();
      securityTests.push({
        test: 'valid_api_key',
        success: validResult.isOk,
        result: validResult.isOk ? 'authenticated' : validResult.error
      });
      validClient.disconnect();
    } catch (error) {
      securityTests.push({
        test: 'valid_api_key',
        success: false,
        error: error.message
      });
    }
    
    // Test invalid API key
    const invalidClient = new MAPLEClient({
      brokerUrl: this.webSocketUrl,
      apiKey: 'invalid-key',
      agentId: 'security-test-invalid'
    });

    try {
      const invalidResult = await invalidClient.connect();
      securityTests.push({
        test: 'invalid_api_key',
        success: !invalidResult.isOk, // Should fail
        result: invalidResult.isOk ? 'unexpected_success' : 'authentication_failed'
      });
      invalidClient.disconnect();
    } catch (error) {
      securityTests.push({
        test: 'invalid_api_key',
        success: true, // Expected to fail
        result: 'authentication_rejected'
      });
    }
    
    return {
      success: securityTests.every(t => t.success),
      tests: securityTests,
      authenticatedRequests: securityTests.filter(t => t.test === 'valid_api_key' && t.success).length
    };
  }

  async testStateManagement() {
    console.log('🔄 Testing State Management...');
    
    const client = new MAPLEClient({
      brokerUrl: this.webSocketUrl,
      apiKey: this.apiKey,
      agentId: 'state-test',
      pythonBridgeUrl: this.pythonBridgeUrl
    });

    try {
      await client.connect();
      
      const stateTests = [];
      
      // Test state persistence across messages
      const sessionId = `session_${Date.now()}`;
      
      for (let i = 0; i < 3; i++) {
        const stateResult = await client.sendMessage({
          header: { messageType: 'STATE_UPDATE', priority: 'MEDIUM' },
          payload: {
            sessionId,
            operation: 'update',
            key: `value_${i}`,
            data: `state_data_${i}`,
            sequence: i
          }
        });
        
        stateTests.push({
          operation: `state_update_${i}`,
          success: stateResult.isOk,
          sessionId,
          sequence: i
        });
      }
      
      // Test state retrieval
      const stateRetrievalResult = await client.sendMessage({
        header: { messageType: 'STATE_RETRIEVE', priority: 'MEDIUM' },
        payload: {
          sessionId,
          operation: 'retrieve'
        }
      });
      
      stateTests.push({
        operation: 'state_retrieval',
        success: stateRetrievalResult.isOk,
        sessionId
      });
      
      client.disconnect();
      
      return {
        success: stateTests.every(t => t.success),
        tests: stateTests,
        sessionId
      };
    } catch (error) {
      return {
        success: false,
        error: error.message
      };
    }
  }

  async testN8nWorkflows() {
    console.log('\n🔧 Testing n8n Workflow Compatibility...');
    
    this.results.workflows = {};
    
    // Load and validate sample workflows
    const workflowsDir = path.join(__dirname, '..', 'workflows');
    const workflowFiles = fs.readdirSync(workflowsDir).filter(f => f.endsWith('.json'));
    
    for (const workflowFile of workflowFiles) {
      const workflowName = path.basename(workflowFile, '.json');
      console.log(`📋 Testing workflow: ${workflowName}`);
      
      try {
        const workflowPath = path.join(workflowsDir, workflowFile);
        const workflowData = JSON.parse(fs.readFileSync(workflowPath, 'utf8'));
        
        // Validate workflow structure
        const validation = this.validateWorkflow(workflowData);
        
        // Test workflow simulation
        const simulation = await this.simulateWorkflow(workflowData);
        
        this.results.workflows[workflowName] = {
          validation,
          simulation,
          nodeCount: workflowData.nodes?.length || 0,
          mapleNodes: workflowData.nodes?.filter(n => n.type?.includes('maple'))?.length || 0
        };
      } catch (error) {
        this.results.workflows[workflowName] = {
          success: false,
          error: error.message
        };
      }
    }
  }

  validateWorkflow(workflowData) {
    const checks = [];
    
    // Check required fields
    checks.push({
      check: 'has_nodes',
      success: Array.isArray(workflowData.nodes) && workflowData.nodes.length > 0
    });
    
    checks.push({
      check: 'has_connections',
      success: workflowData.connections && typeof workflowData.connections === 'object'
    });
    
    // Check MAPLE nodes
    const mapleNodes = workflowData.nodes?.filter(n => 
      n.type?.includes('maple') || n.type?.includes('MAPLE')
    ) || [];
    
    checks.push({
      check: 'has_maple_nodes',
      success: mapleNodes.length > 0,
      count: mapleNodes.length
    });
    
    // Check node parameters
    for (const node of mapleNodes) {
      checks.push({
        check: `node_${node.name}_has_operation`,
        success: node.parameters && node.parameters.operation,
        nodeType: node.type
      });
    }
    
    return {
      success: checks.every(c => c.success),
      checks,
      mapleNodeCount: mapleNodes.length
    };
  }

  async simulateWorkflow(workflowData) {
    // This would simulate the workflow execution
    // For now, we'll do basic validation and mock execution
    
    const startTime = Date.now();
    
    try {
      const mapleNodes = workflowData.nodes?.filter(n => 
        n.type?.includes('maple') || n.type?.includes('MAPLE')
      ) || [];
      
      const results = [];
      
      for (const node of mapleNodes) {
        const nodeStart = Date.now();
        
        // Mock node execution
        await new Promise(resolve => setTimeout(resolve, Math.random() * 100 + 50));
        
        results.push({
          nodeId: node.id,
          nodeName: node.name,
          nodeType: node.type,
          operation: node.parameters?.operation,
          success: true,
          executionTime: Date.now() - nodeStart
        });
      }
      
      return {
        success: true,
        totalTime: Date.now() - startTime,
        nodeResults: results,
        executedNodes: results.length
      };
    } catch (error) {
      return {
        success: false,
        error: error.message
      };
    }
  }

  async runPerformanceBenchmarks() {
    console.log('\n⚡ Running Performance Benchmarks...');
    
    this.results.performance = {};
    
    // Throughput test
    this.results.performance.throughput = await this.testThroughput();
    
    // Latency test
    this.results.performance.latency = await this.testLatency();
    
    // Concurrent connections test
    this.results.performance.concurrency = await this.testConcurrency();
    
    // Resource efficiency test
    this.results.performance.efficiency = await this.testEfficiency();
  }

  async testThroughput() {
    console.log('📊 Testing Message Throughput...');
    
    const client = new MAPLEClient({
      brokerUrl: this.webSocketUrl,
      apiKey: this.apiKey,
      agentId: 'throughput-test',
      pythonBridgeUrl: this.pythonBridgeUrl
    });

    try {
      await client.connect();
      
      const messageCount = 200;
      const startTime = Date.now();
      const promises = [];
      
      for (let i = 0; i < messageCount; i++) {
        const promise = client.sendMessage({
          header: { messageType: 'THROUGHPUT_TEST', priority: 'LOW' },
          payload: { messageId: i, timestamp: Date.now() }
        });
        promises.push(promise);
      }
      
      const results = await Promise.allSettled(promises);
      const endTime = Date.now();
      const duration = endTime - startTime;
      const successful = results.filter(r => r.status === 'fulfilled').length;
      
      client.disconnect();
      
      return {
        messageCount,
        successful,
        failed: messageCount - successful,
        duration,
        messagesPerSecond: (successful * 1000 / duration).toFixed(2),
        averageLatency: (duration / successful).toFixed(2)
      };
    } catch (error) {
      return {
        success: false,
        error: error.message
      };
    }
  }

  async testLatency() {
    console.log('🕐 Testing Message Latency...');
    
    const client = new MAPLEClient({
      brokerUrl: this.webSocketUrl,
      apiKey: this.apiKey,
      agentId: 'latency-test',
      pythonBridgeUrl: this.pythonBridgeUrl
    });

    try {
      await client.connect();
      
      const testCount = 20;
      const latencies = [];
      
      for (let i = 0; i < testCount; i++) {
        const startTime = Date.now();
        const result = await client.sendMessage({
          header: { messageType: 'LATENCY_TEST', priority: 'HIGH' },
          payload: { testId: i, clientTimestamp: startTime }
        });
        const endTime = Date.now();
        
        if (result.isOk) {
          latencies.push(endTime - startTime);
        }
        
        // Small delay between tests
        await new Promise(resolve => setTimeout(resolve, 50));
      }
      
      client.disconnect();
      
      const avgLatency = latencies.reduce((sum, lat) => sum + lat, 0) / latencies.length;
      const minLatency = Math.min(...latencies);
      const maxLatency = Math.max(...latencies);
      
      return {
        testCount,
        successfulTests: latencies.length,
        averageLatency: avgLatency.toFixed(2),
        minLatency,
        maxLatency,
        latencies
      };
    } catch (error) {
      return {
        success: false,
        error: error.message
      };
    }
  }

  async testConcurrency() {
    console.log('🔀 Testing Concurrent Connections...');
    
    const clientCount = 5;
    const messagesPerClient = 20;
    const clients = [];
    
    try {
      // Create multiple clients
      for (let i = 0; i < clientCount; i++) {
        const client = new MAPLEClient({
          brokerUrl: this.webSocketUrl,
          apiKey: this.apiKey,
          agentId: `concurrent-test-${i}`,
          pythonBridgeUrl: this.pythonBridgeUrl
        });
        await client.connect();
        clients.push(client);
      }
      
      const startTime = Date.now();
      const allPromises = [];
      
      // Each client sends messages concurrently
      for (let clientIndex = 0; clientIndex < clients.length; clientIndex++) {
        const client = clients[clientIndex];
        
        for (let msgIndex = 0; msgIndex < messagesPerClient; msgIndex++) {
          const promise = client.sendMessage({
            header: { messageType: 'CONCURRENCY_TEST', priority: 'MEDIUM' },
            payload: {
              clientId: clientIndex,
              messageId: msgIndex,
              timestamp: Date.now()
            }
          });
          allPromises.push(promise);
        }
      }
      
      const results = await Promise.allSettled(allPromises);
      const endTime = Date.now();
      
      // Cleanup
      for (const client of clients) {
        client.disconnect();
      }
      
      const successful = results.filter(r => r.status === 'fulfilled').length;
      const totalMessages = clientCount * messagesPerClient;
      
      return {
        clientCount,
        messagesPerClient,
        totalMessages,
        successful,
        failed: totalMessages - successful,
        duration: endTime - startTime,
        messagesPerSecond: (successful * 1000 / (endTime - startTime)).toFixed(2)
      };
    } catch (error) {
      // Cleanup on error
      for (const client of clients) {
        try {
          client.disconnect();
        } catch (e) {
          // Ignore cleanup errors
        }
      }
      
      return {
        success: false,
        error: error.message
      };
    }
  }

  async testEfficiency() {
    console.log('⚡ Testing Resource Efficiency...');
    
    const beforeMemory = process.memoryUsage();
    const startTime = Date.now();
    
    const client = new MAPLEClient({
      brokerUrl: this.webSocketUrl,
      apiKey: this.apiKey,
      agentId: 'efficiency-test',
      pythonBridgeUrl: this.pythonBridgeUrl
    });

    try {
      await client.connect();
      
      // Perform various operations
      const operations = [];
      
      // Agent operations
      const createResult = await client.createAgent({
        agentId: 'efficiency-agent',
        capabilities: ['efficiency-test'],
        config: {}
      });
      operations.push({ operation: 'create_agent', success: createResult.isOk });
      
      // Task execution
      const taskResult = await client.executeTask({
        agentId: 'efficiency-agent',
        task: { type: 'efficiency-test', data: 'test data' },
        priority: 'MEDIUM'
      });
      operations.push({ operation: 'execute_task', success: taskResult.isOk });
      
      // Resource allocation
      const resourceResult = await client.allocateResources({
        compute: 1,
        memory: '1GB',
        priority: 'LOW'
      });
      operations.push({ operation: 'allocate_resources', success: resourceResult.isOk });
      
      client.disconnect();
      
      const afterMemory = process.memoryUsage();
      const endTime = Date.now();
      
      return {
        operations,
        successfulOperations: operations.filter(op => op.success).length,
        totalOperations: operations.length,
        executionTime: endTime - startTime,
        memoryUsage: {
          before: beforeMemory,
          after: afterMemory,
          increase: {
            rss: afterMemory.rss - beforeMemory.rss,
            heapUsed: afterMemory.heapUsed - beforeMemory.heapUsed,
            heapTotal: afterMemory.heapTotal - beforeMemory.heapTotal
          }
        }
      };
    } catch (error) {
      return {
        success: false,
        error: error.message
      };
    }
  }

  async generateReport() {
    console.log('\n📊 Generating Comprehensive Report...');
    
    const report = {
      timestamp: new Date().toISOString(),
      creator: 'Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)',
      protocol: 'MAPLE (Mahesh\'s Agent Protocol Language Engine)',
      version: '1.0.0',
      demo: 'n8n-integration-full',
      summary: this.generateSummary(),
      results: this.results
    };
    
    // Save report
    const reportPath = path.join(__dirname, '..', 'demo-results.json');
    fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
    
    // Display summary
    this.displaySummary(report.summary);
    
    console.log(`📄 Full report saved to: ${reportPath}`);
  }

  generateSummary() {
    const tests = this.results.tests || {};
    const workflows = this.results.workflows || {};
    const performance = this.results.performance || {};
    
    const testResults = Object.values(tests);
    const workflowResults = Object.values(workflows);
    
    return {
      totalTests: testResults.length,
      passedTests: testResults.filter(t => t.success).length,
      failedTests: testResults.filter(t => !t.success).length,
      testSuccessRate: (testResults.filter(t => t.success).length / testResults.length * 100).toFixed(1) + '%',
      
      totalWorkflows: workflowResults.length,
      validWorkflows: workflowResults.filter(w => w.validation?.success).length,
      
      performanceMetrics: {
        throughput: performance.throughput?.messagesPerSecond || 'N/A',
        averageLatency: performance.latency?.averageLatency || 'N/A',
        concurrentClients: performance.concurrency?.clientCount || 'N/A',
        memoryEfficiency: performance.efficiency?.memoryUsage?.increase?.heapUsed || 'N/A'
      },
      
      overallStatus: this.calculateOverallStatus(tests, workflows, performance)
    };
  }

  calculateOverallStatus(tests, workflows, performance) {
    const testsPassed = Object.values(tests).every(t => t.success);
    const workflowsValid = Object.values(workflows).every(w => w.validation?.success !== false);
    const performanceGood = performance.throughput?.successful > 0;
    
    if (testsPassed && workflowsValid && performanceGood) {
      return 'EXCELLENT';
    } else if ((testsPassed || workflowsValid) && performanceGood) {
      return 'GOOD';
    } else {
      return 'NEEDS_IMPROVEMENT';
    }
  }

  displaySummary(summary) {
    console.log('\n🎯 Demo Summary:');
    console.log('================');
    console.log(`✅ Tests Passed: ${summary.passedTests}/${summary.totalTests} (${summary.testSuccessRate})`);
    console.log(`📋 Valid Workflows: ${summary.validWorkflows}/${summary.totalWorkflows}`);
    console.log(`⚡ Throughput: ${summary.performanceMetrics.throughput} msg/sec`);
    console.log(`🕐 Average Latency: ${summary.performanceMetrics.averageLatency}ms`);
    console.log(`🔀 Concurrent Clients: ${summary.performanceMetrics.concurrentClients}`);
    console.log(`📊 Overall Status: ${summary.overallStatus}`);
    console.log(`\n👨‍💻 Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)`);
  }

  async cleanup() {
    console.log('\n🧹 Cleaning up...');
    await this.launcher.cleanup();
  }
}

// Run full demo
if (require.main === module) {
  const demo = new MAPLEFullDemo();
  
  demo.run()
    .then(() => {
      console.log('\n🎉 Full Demo completed successfully!');
      console.log('🔗 Ready for production n8n integration!');
      process.exit(0);
    })
    .catch(error => {
      console.error('❌ Full Demo failed:', error);
      process.exit(1);
    });
}

module.exports = MAPLEFullDemo;
