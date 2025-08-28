#!/usr/bin/env node
// 🍁 MAPLE n8n Quick Demo Script
// Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

const { MAPLEClient } = require('../lib/MAPLEClient');
const axios = require('axios');

console.log('🍁 MAPLE n8n Quick Demo');
console.log('Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)');
console.log('===================================================');

class MAPLEQuickDemo {
  constructor() {
    this.pythonBridgeUrl = 'http://localhost:8000';
    this.webSocketUrl = 'ws://localhost:8080';
    this.apiKey = 'demo-key-12345';
  }

  async run() {
    try {
      console.log('🚀 Starting MAPLE Quick Demo...');
      
      // Test connection to services
      await this.testConnections();
      
      // Test MAPLE Client
      await this.testMAPLEClient();
      
      // Test Agent Operations
      await this.testAgentOperations();
      
      // Test Resource Management
      await this.testResourceManagement();
      
      // Test Workflow Coordination
      await this.testWorkflowCoordination();
      
      console.log('✅ Quick Demo completed successfully!');
      console.log('🎯 Ready for n8n integration');
      
    } catch (error) {
      console.error('❌ Quick Demo failed:', error.message);
      console.log('💡 Make sure to run: npm run start:broker first');
      process.exit(1);
    }
  }

  async testConnections() {
    console.log('\n📡 Testing Service Connections...');
    
    try {
      // Test Python Bridge
      const pythonResponse = await axios.get(`${this.pythonBridgeUrl}/health`, {
        timeout: 3000
      });
      console.log('✅ Python Bridge:', pythonResponse.data.status);
    } catch (error) {
      console.log('⚠️ Python Bridge: Not available (will use mock data)');
    }
    
    try {
      // Test Demo Server
      const demoResponse = await axios.get('http://localhost:3000/test/connection', {
        timeout: 3000
      });
      console.log('✅ Demo Server:', demoResponse.data.status);
    } catch (error) {
      console.log('⚠️ Demo Server: Not available');
    }
  }

  async testMAPLEClient() {
    console.log('\n🔧 Testing MAPLE Client...');
    
    const client = new MAPLEClient({
      brokerUrl: this.webSocketUrl,
      apiKey: this.apiKey,
      agentId: 'quick-demo-client',
      pythonBridgeUrl: this.pythonBridgeUrl,
      requestTimeout: 5000
    });

    try {
      const connectResult = await client.connect();
      if (connectResult.isOk) {
        console.log('✅ MAPLE Client connected successfully');
        
        // Test message sending
        const messageResult = await client.sendMessage({
          header: {
            messageType: 'PING',
            priority: 'LOW'
          },
          payload: { test: 'hello from quick demo' }
        });
        
        if (messageResult.isOk) {
          console.log('✅ Message exchange working');
        } else {
          console.log('⚠️ Message exchange failed:', messageResult.error);
        }
        
        client.disconnect();
      } else {
        console.log('⚠️ MAPLE Client connection failed:', connectResult.error);
      }
    } catch (error) {
      console.log('⚠️ MAPLE Client test failed:', error.message);
    }
  }

  async testAgentOperations() {
    console.log('\n🤖 Testing Agent Operations...');
    
    const client = new MAPLEClient({
      brokerUrl: this.webSocketUrl,
      apiKey: this.apiKey,
      agentId: 'agent-test-client',
      pythonBridgeUrl: this.pythonBridgeUrl,
      requestTimeout: 10000
    });

    try {
      await client.connect();
      
      // Test agent creation
      console.log('📝 Creating test agent...');
      const createResult = await client.createAgent({
        agentId: 'demo-test-agent',
        capabilities: ['demo-task', 'mock-processing'],
        config: {
          maxConcurrency: 3,
          timeout: '30s'
        }
      });
      
      if (createResult.isOk) {
        console.log('✅ Agent created:', createResult.value.agentId);
        
        // Test task execution
        console.log('⚡ Executing test task...');
        const taskResult = await client.executeTask({
          agentId: 'demo-test-agent',
          task: {
            type: 'demo-task',
            data: 'Quick demo test data',
            parameters: { format: 'json' }
          },
          priority: 'MEDIUM'
        });
        
        if (taskResult.isOk) {
          console.log('✅ Task executed successfully');
          console.log('📊 Result:', JSON.stringify(taskResult.value, null, 2));
        } else {
          console.log('⚠️ Task execution failed:', taskResult.error);
        }
        
        // Test agent status
        console.log('📊 Checking agent status...');
        const statusResult = await client.getAgentStatus('demo-test-agent');
        
        if (statusResult.isOk) {
          console.log('✅ Agent status retrieved');
          console.log('🔍 Status:', statusResult.value.status);
        } else {
          console.log('⚠️ Status check failed:', statusResult.error);
        }
      } else {
        console.log('⚠️ Agent creation failed:', createResult.error);
      }
      
      client.disconnect();
    } catch (error) {
      console.log('⚠️ Agent operations test failed:', error.message);
    }
  }

  async testResourceManagement() {
    console.log('\n💾 Testing Resource Management...');
    
    const client = new MAPLEClient({
      brokerUrl: this.webSocketUrl,
      apiKey: this.apiKey,
      agentId: 'resource-test-client',
      pythonBridgeUrl: this.pythonBridgeUrl,
      requestTimeout: 10000
    });

    try {
      await client.connect();
      
      // Test resource allocation
      console.log('🔧 Allocating resources...');
      const allocateResult = await client.allocateResources({
        compute: 2,
        memory: '4GB',
        storage: '10GB',
        priority: 'MEDIUM',
        timeout: '30s'
      });
      
      if (allocateResult.isOk) {
        console.log('✅ Resources allocated successfully');
        console.log('📊 Allocation:', JSON.stringify(allocateResult.value, null, 2));
      } else {
        console.log('⚠️ Resource allocation failed:', allocateResult.error);
      }
      
      client.disconnect();
    } catch (error) {
      console.log('⚠️ Resource management test failed:', error.message);
    }
  }

  async testWorkflowCoordination() {
    console.log('\n🎼 Testing Workflow Coordination...');
    
    const client = new MAPLEClient({
      brokerUrl: this.webSocketUrl,
      apiKey: this.apiKey,
      agentId: 'workflow-test-client',
      pythonBridgeUrl: this.pythonBridgeUrl,
      requestTimeout: 15000
    });

    try {
      await client.connect();
      
      // Test workflow creation
      console.log('📋 Creating test workflow...');
      const workflowResult = await client.createWorkflow({
        name: 'Quick Demo Workflow',
        description: 'Simple workflow for testing',
        agents: ['agent-1', 'agent-2'],
        steps: [
          {
            stepId: 'step_1',
            name: 'Initial Processing',
            agentId: 'agent-1',
            operation: 'process',
            parameters: { input: 'demo data' },
            dependencies: []
          },
          {
            stepId: 'step_2',
            name: 'Final Output',
            agentId: 'agent-2',
            operation: 'finalize',
            parameters: { format: 'summary' },
            dependencies: ['step_1']
          }
        ],
        resources: {
          compute: 4,
          memory: '8GB',
          timeout: '2m'
        },
        metadata: {
          creator: 'quick-demo',
          version: '1.0'
        }
      });
      
      if (workflowResult.isOk) {
        console.log('✅ Workflow created:', workflowResult.value);
        
        // Test workflow execution
        console.log('▶️ Executing workflow...');
        const executeResult = await client.executeWorkflow(workflowResult.value, {
          input: 'Quick demo input data',
          parameters: { priority: 'high' }
        });
        
        if (executeResult.isOk) {
          console.log('✅ Workflow executed successfully');
          console.log('📊 Result:', JSON.stringify(executeResult.value, null, 2));
        } else {
          console.log('⚠️ Workflow execution failed:', executeResult.error);
        }
      } else {
        console.log('⚠️ Workflow creation failed:', workflowResult.error);
      }
      
      client.disconnect();
    } catch (error) {
      console.log('⚠️ Workflow coordination test failed:', error.message);
    }
  }
}

// Performance test
async function performanceTest() {
  console.log('\n⚡ Performance Test...');
  
  const client = new MAPLEClient({
    brokerUrl: 'ws://localhost:8080',
    apiKey: 'demo-key-12345',
    agentId: 'perf-test-client',
    pythonBridgeUrl: 'http://localhost:8000'
  });

  try {
    await client.connect();
    
    const startTime = Date.now();
    const messageCount = 50;
    const promises = [];
    
    console.log(`📊 Sending ${messageCount} messages...`);
    
    for (let i = 0; i < messageCount; i++) {
      const promise = client.sendMessage({
        header: {
          messageType: 'PERF_TEST',
          priority: 'LOW'
        },
        payload: {
          messageNumber: i,
          timestamp: Date.now(),
          data: `Performance test message ${i}`
        }
      });
      promises.push(promise);
    }
    
    const results = await Promise.allSettled(promises);
    const endTime = Date.now();
    const duration = endTime - startTime;
    const successful = results.filter(r => r.status === 'fulfilled').length;
    
    console.log(`✅ Performance Results:`);
    console.log(`   Messages: ${successful}/${messageCount} successful`);
    console.log(`   Duration: ${duration}ms`);
    console.log(`   Rate: ${(successful * 1000 / duration).toFixed(2)} msg/sec`);
    console.log(`   Avg Latency: ${(duration / successful).toFixed(2)}ms`);
    
    client.disconnect();
  } catch (error) {
    console.log('⚠️ Performance test failed:', error.message);
  }
}

// Run demo
if (require.main === module) {
  const demo = new MAPLEQuickDemo();
  
  demo.run()
    .then(() => performanceTest())
    .then(() => {
      console.log('\n🎉 All tests completed!');
      console.log('👨‍💻 Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)');
      console.log('🔗 Ready to integrate with n8n!');
    })
    .catch(error => {
      console.error('❌ Demo failed:', error);
      process.exit(1);
    });
}

module.exports = MAPLEQuickDemo;
