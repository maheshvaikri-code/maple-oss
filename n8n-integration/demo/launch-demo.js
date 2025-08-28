#!/usr/bin/env node
// 🍁 MAPLE n8n Demo Launch Script
// Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

const express = require('express');
const WebSocket = require('ws');
const cors = require('cors');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

console.log('🍁 MAPLE n8n Integration Demo Launcher');
console.log('Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)');
console.log('=========================================================');

class MAPLEDemoLauncher {
  constructor() {
    this.pythonBridgePort = 8000;
    this.webSocketPort = 8080;
    this.demoPort = 3000;
    this.pythonProcess = null;
    this.webSocketServer = null;
    this.demoServer = null;
  }

  async launch() {
    try {
      console.log('🚀 Starting MAPLE Demo Components...');
      
      // 1. Start Python MAPLE Bridge
      await this.startPythonBridge();
      
      // 2. Start WebSocket Server
      await this.startWebSocketServer();
      
      // 3. Start Demo Web Server
      await this.startDemoWebServer();
      
      // 4. Display connection info
      this.displayConnectionInfo();
      
      // 5. Set up cleanup
      this.setupCleanup();
      
      console.log('✅ All MAPLE Demo components are running!');
      console.log('🎯 Ready for n8n integration testing');
      
    } catch (error) {
      console.error('❌ Failed to launch MAPLE demo:', error.message);
      await this.cleanup();
      process.exit(1);
    }
  }

  async startPythonBridge() {
    console.log('🐍 Starting Python MAPLE Bridge...');
    
    return new Promise((resolve, reject) => {
      // Check if Python MAPLE is available
      const pythonScript = path.join(__dirname, '..', '..', 'quick_start.py');
      
      if (!fs.existsSync(pythonScript)) {
        console.log('⚠️ Python MAPLE not found, starting mock bridge...');
        this.startMockPythonBridge();
        resolve();
        return;
      }
      
      // Start the actual Python MAPLE bridge
      this.pythonProcess = spawn('python', [pythonScript, '--bridge-mode', '--port', this.pythonBridgePort], {
        stdio: ['pipe', 'pipe', 'pipe'],
        env: { ...process.env, MAPLE_BRIDGE_MODE: 'true' }
      });
      
      this.pythonProcess.stdout.on('data', (data) => {
        const output = data.toString();
        if (output.includes('Bridge server running')) {
          console.log('✅ Python MAPLE Bridge started on port', this.pythonBridgePort);
          resolve();
        }
        console.log('🐍 Python Bridge:', output.trim());
      });
      
      this.pythonProcess.stderr.on('data', (data) => {
        console.log('🐍 Python Bridge Error:', data.toString().trim());
      });
      
      this.pythonProcess.on('error', (error) => {
        console.log('⚠️ Python Bridge failed, starting mock bridge...');
        this.startMockPythonBridge();
        resolve();
      });
      
      // Timeout fallback
      setTimeout(() => {
        if (this.pythonProcess && this.pythonProcess.exitCode === null) {
          console.log('✅ Python MAPLE Bridge started (assumed)');
          resolve();
        }
      }, 3000);
    });
  }

  startMockPythonBridge() {
    console.log('🎭 Starting Mock Python Bridge...');
    
    const app = express();
    app.use(cors());
    app.use(express.json());
    
    // Health check endpoint
    app.get('/health', (req, res) => {
      res.json({ status: 'ok', service: 'maple-python-bridge', mock: true });
    });
    
    // Create agent endpoint
    app.post('/agents', (req, res) => {
      const { agentId, capabilities, configuration } = req.body;
      res.json({
        agentId,
        capabilities,
        status: 'ACTIVE',
        resources: { allocated: {}, available: {}, utilization: {} },
        performance: {
          messagesProcessed: 0,
          averageResponseTime: 0,
          errorRate: 0,
          lastActivity: new Date().toISOString()
        },
        config: configuration || {}
      });
    });
    
    // Execute task endpoint
    app.post('/tasks/execute', (req, res) => {
      const { agentId, task } = req.body;
      
      // Simulate task execution with mock results
      setTimeout(() => {
        let mockResult;
        
        if (task.task?.includes?.('search') || task.query) {
          mockResult = {
            query: task.query || task.task,
            results: [
              {
                title: 'AI Research Breakthrough in Multi-Agent Systems',
                summary: 'Recent developments in MAPLE protocol show significant improvements...',
                source: 'https://example.com/ai-research',
                relevance: 0.95
              },
              {
                title: 'Multi-Agent Coordination Protocols Comparison',
                summary: 'MAPLE outperforms traditional protocols by 300%...',
                source: 'https://example.com/protocol-comparison',
                relevance: 0.87
              }
            ],
            searchTime: '1.2s',
            totalResults: 2
          };
        } else if (task.task?.includes?.('analy') || task.content) {
          mockResult = {
            analysis: {
              keyInsights: [
                'MAPLE protocol demonstrates superior performance',
                'Multi-agent coordination shows 400% improvement',
                'Resource management is highly optimized'
              ],
              sentiment: 'positive',
              confidence: 0.92,
              topics: ['multi-agent systems', 'MAPLE protocol', 'AI coordination']
            },
            processingTime: '0.8s'
          };
        } else if (task.task?.includes?.('summar') || task.format === 'executive_summary') {
          mockResult = {
            summary: {
              title: 'Executive Summary: MAPLE Protocol Research',
              keyPoints: [
                'MAPLE (Mahesh\\'s Agent Protocol Language Engine) represents a breakthrough in multi-agent communication',
                'Performance benchmarks show 300-400% improvement over existing protocols',
                'Resource-aware communication and advanced error handling are key differentiators',
                'Ready for production deployment with 93.75% test success rate'
              ],
              conclusion: 'MAPLE protocol is ready for enterprise adoption and sets new industry standards.',
              wordCount: 150,
              readingTime: '1 minute'
            },
            generationTime: '0.5s'
          };
        } else {
          mockResult = {
            status: 'completed',
            result: 'Task executed successfully',
            data: task,
            executionTime: '0.3s'
          };
        }
        
        res.json(mockResult);
      }, Math.random() * 1000 + 500); // 0.5-1.5s delay
    });
    
    // Get agent status endpoint
    app.get('/agents/:agentId/status', (req, res) => {
      const { agentId } = req.params;
      res.json({
        agentId,
        capabilities: ['mock-capability'],
        status: 'ACTIVE',
        resources: {
          allocated: { cpu: 2, memory: '4GB' },
          available: { cpu: 4, memory: '8GB' },
          utilization: { cpu: 0.3, memory: 0.5 }
        },
        performance: {
          messagesProcessed: Math.floor(Math.random() * 100) + 50,
          averageResponseTime: Math.random() * 100 + 50,
          errorRate: Math.random() * 0.05,
          lastActivity: new Date().toISOString()
        },
        config: {}
      });
    });
    
    // Resource allocation endpoint
    app.post('/resources/allocate', (req, res) => {
      const request = req.body;
      res.json({
        allocationId: 'alloc_' + Math.random().toString(36).substr(2, 9),
        allocated: request,
        status: 'allocated',
        availableUntil: new Date(Date.now() + 3600000).toISOString(), // 1 hour
        cost: Math.random() * 10 + 5
      });
    });
    
    app.listen(this.pythonBridgePort, () => {
      console.log(\`✅ Mock Python Bridge started on port \${this.pythonBridgePort}\`);
    });
  }

  async startWebSocketServer() {
    console.log('🌐 Starting WebSocket Server...');
    
    return new Promise((resolve) => {
      this.webSocketServer = new WebSocket.Server({ 
        port: this.webSocketPort,
        verifyClient: (info) => {
          // Verify API key in headers
          const authHeader = info.req.headers.authorization;
          return authHeader && authHeader.startsWith('Bearer ');
        }
      });
      
      this.webSocketServer.on('connection', (ws, req) => {
        const agentId = req.headers['x-maple-agent-id'] || 'unknown';
        console.log(\`🔗 Agent connected: \${agentId}\`);
        
        ws.on('message', (data) => {
          try {
            const message = JSON.parse(data.toString());
            console.log(\`📨 Message from \${agentId}:\`, message.header?.messageType);
            
            // Echo back with modified response
            const response = {
              ...message,
              header: {
                ...message.header,
                messageId: require('crypto').randomUUID(),
                timestamp: new Date().toISOString(),
                messageType: this.getResponseMessageType(message.header.messageType)
              },
              payload: this.generateMockResponse(message),
              metadata: {
                ...message.metadata,
                correlationId: message.header.messageId,
                responseFrom: 'maple-websocket-server'
              }
            };
            
            // Simulate processing delay
            setTimeout(() => {
              ws.send(JSON.stringify(response));
            }, Math.random() * 500 + 100);
            
          } catch (error) {
            console.error('❌ WebSocket message error:', error.message);
          }
        });
        
        ws.on('close', () => {
          console.log(\`👋 Agent disconnected: \${agentId}\`);
        });
        
        ws.on('error', (error) => {
          console.error(\`❌ WebSocket error for \${agentId}:\`, error.message);
        });
        
        // Send welcome message
        ws.send(JSON.stringify({
          header: {
            messageId: require('crypto').randomUUID(),
            timestamp: new Date().toISOString(),
            messageType: 'WELCOME',
            priority: 'LOW'
          },
          payload: {
            message: 'Welcome to MAPLE WebSocket Server',
            serverId: 'maple-ws-demo',
            capabilities: ['message-routing', 'agent-coordination', 'resource-management']
          },
          metadata: {
            source: 'maple-websocket-server',
            agentId
          }
        }));
      });
      
      console.log(\`✅ WebSocket Server started on port \${this.webSocketPort}\`);
      resolve();
    });
  }

  getResponseMessageType(requestType) {
    const responses = {
      'AGENT_CREATE': 'AGENT_CREATED',
      'TASK_EXECUTE': 'TASK_RESULT',
      'AGENT_STATUS_REQUEST': 'AGENT_STATUS_RESPONSE',
      'RESOURCE_REQUEST': 'RESOURCE_ALLOCATED',
      'WORKFLOW_CREATE': 'WORKFLOW_CREATED',
      'WORKFLOW_EXECUTE': 'WORKFLOW_RESULT',
      'HEARTBEAT': 'HEARTBEAT_RESPONSE'
    };
    return responses[requestType] || 'RESPONSE';
  }

  generateMockResponse(message) {
    const messageType = message.header.messageType;
    
    switch (messageType) {
      case 'AGENT_CREATE':
        return {
          agentId: message.payload.agentId,
          status: 'ACTIVE',
          capabilities: message.payload.capabilities || [],
          resources: { allocated: {}, available: {}, utilization: {} },
          performance: {
            messagesProcessed: 0,
            averageResponseTime: 0,
            errorRate: 0,
            lastActivity: new Date().toISOString()
          }
        };
        
      case 'TASK_EXECUTE':
        return {
          result: {
            status: 'completed',
            output: 'Mock task execution result',
            executionTime: Math.random() * 1000 + 200,
            resourcesUsed: { cpu: Math.random() * 2, memory: Math.random() * 1000 + 500 }
          }
        };
        
      case 'RESOURCE_REQUEST':
        return {
          allocationId: 'alloc_' + Math.random().toString(36).substr(2, 9),
          allocated: message.payload.resourceRequest,
          status: 'allocated'
        };
        
      default:
        return { status: 'acknowledged', originalMessage: message.payload };
    }
  }

  async startDemoWebServer() {
    console.log('🌟 Starting Demo Web Server...');
    
    const app = express();
    app.use(cors());
    app.use(express.json());
    app.use(express.static(path.join(__dirname, '..', 'docs')));
    
    // Demo dashboard
    app.get('/', (req, res) => {
      res.send(\`
        <!DOCTYPE html>
        <html>
        <head>
          <title>MAPLE n8n Integration Demo</title>
          <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            .header { text-align: center; margin-bottom: 30px; }
            .title { color: #2c3e50; margin-bottom: 10px; }
            .creator { color: #7f8c8d; font-style: italic; }
            .section { margin: 20px 0; padding: 20px; border: 1px solid #ecf0f1; border-radius: 5px; }
            .status { padding: 10px; border-radius: 5px; margin: 10px 0; }
            .status.running { background: #d5f4e6; color: #27ae60; }
            .status.error { background: #fadad7; color: #e74c3c; }
            .endpoints { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
            .endpoint { background: #ecf0f1; padding: 15px; border-radius: 5px; }
            .code { background: #2c3e50; color: #ecf0f1; padding: 15px; border-radius: 5px; font-family: monospace; overflow-x: auto; }
            .btn { background: #3498db; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; text-decoration: none; display: inline-block; margin: 5px; }
            .btn:hover { background: #2980b9; }
          </style>
        </head>
        <body>
          <div class="container">
            <div class="header">
              <h1 class="title">🍁 MAPLE n8n Integration Demo</h1>
              <p class="creator">Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)</p>
              <p>Multi-Agent Protocol Language Engine - Visual AI Workflows</p>
            </div>
            
            <div class="section">
              <h2>🚀 System Status</h2>
              <div class="status running">✅ Python Bridge: Running on port \${this.pythonBridgePort}</div>
              <div class="status running">✅ WebSocket Server: Running on port \${this.webSocketPort}</div>
              <div class="status running">✅ Demo Server: Running on port \${this.demoPort}</div>
            </div>
            
            <div class="section">
              <h2>🔧 n8n Configuration</h2>
              <p>Use these connection details in your n8n MAPLE credentials:</p>
              <div class="code">
{
  "connectionType": "hybrid",
  "brokerUrl": "ws://localhost:\${this.webSocketPort}",
  "pythonBridgeUrl": "http://localhost:\${this.pythonBridgePort}",
  "apiKey": "demo-key-12345",
  "agentId": "n8n-demo-agent"
}
              </div>
            </div>
            
            <div class="section">
              <h2>🛠️ Available Endpoints</h2>
              <div class="endpoints">
                <div class="endpoint">
                  <h3>WebSocket</h3>
                  <strong>URL:</strong> ws://localhost:\${this.webSocketPort}<br>
                  <strong>Protocol:</strong> MAPLE v1.0<br>
                  <strong>Auth:</strong> Bearer token required
                </div>
                <div class="endpoint">
                  <h3>Python Bridge</h3>
                  <strong>URL:</strong> http://localhost:\${this.pythonBridgePort}<br>
                  <strong>Health:</strong> GET /health<br>
                  <strong>Agents:</strong> POST /agents
                </div>
                <div class="endpoint">
                  <h3>Demo Dashboard</h3>
                  <strong>URL:</strong> http://localhost:\${this.demoPort}<br>
                  <strong>Status:</strong> This page<br>
                  <strong>Test:</strong> /test endpoints
                </div>
              </div>
            </div>
            
            <div class="section">
              <h2>🎯 Quick Actions</h2>
              <a href="/test/connection" class="btn">Test Connection</a>
              <a href="/test/agents" class="btn">Test Agent Creation</a>
              <a href="/test/workflow" class="btn">Test Workflow</a>
              <a href="/workflows/ai-research-assistant.json" class="btn">Download Sample Workflow</a>
              <a href="https://github.com/mahesh-vaikri/maple-n8n-nodes" class="btn" target="_blank">GitHub Repository</a>
            </div>
            
            <div class="section">
              <h2>📚 Documentation</h2>
              <ul>
                <li><a href="/docs/setup.html">Setup Guide</a></li>
                <li><a href="/docs/nodes.html">Node Reference</a></li>
                <li><a href="/docs/examples.html">Examples</a></li>
                <li><a href="/docs/api.html">API Documentation</a></li>
              </ul>
            </div>
            
            <div class="section">
              <h2>🏆 About MAPLE</h2>
              <p><strong>MAPLE (Multi Agent Protocol Language Engine)</strong> is a cutting-edge protocol for multi-agent AI coordination.</p>
              <ul>
                <li>🚀 <strong>Performance:</strong> 332K+ messages/second</li>
                <li>🧠 <strong>Intelligence:</strong> Resource-aware communication</li>
                <li>🔒 <strong>Security:</strong> Advanced link identification</li>
                <li>⚡ <strong>Recovery:</strong> Sophisticated error handling</li>
                <li>📊 <strong>Monitoring:</strong> Real-time state management</li>
              </ul>
            </div>
          </div>
          
          <script>
            // Auto-refresh status every 30 seconds
            setTimeout(() => location.reload(), 30000);
          </script>
        </body>
        </html>
      \`);
    });
    
    // Test endpoints
    app.get('/test/connection', (req, res) => {
      res.json({
        status: 'success',
        message: 'MAPLE Demo Server is running',
        services: {
          pythonBridge: \`http://localhost:\${this.pythonBridgePort}\`,
          webSocket: \`ws://localhost:\${this.webSocketPort}\`,
          demoServer: \`http://localhost:\${this.demoPort}\`
        },
        timestamp: new Date().toISOString(),
        creator: 'Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)'
      });
    });
    
    app.get('/test/agents', (req, res) => {
      res.json({
        availableAgents: [
          { id: 'search-agent-001', type: 'web-search', status: 'active' },
          { id: 'analysis-agent-001', type: 'content-analysis', status: 'active' },
          { id: 'summary-agent-001', type: 'text-summary', status: 'active' },
          { id: 'coordinator-001', type: 'workflow-coordination', status: 'active' }
        ],
        capabilities: ['search', 'analysis', 'summary', 'coordination'],
        timestamp: new Date().toISOString()
      });
    });
    
    app.get('/test/workflow', (req, res) => {
      res.json({
        sampleWorkflows: [
          'ai-research-assistant',
          'content-creation-pipeline',
          'data-analysis-workflow',
          'customer-service-bot'
        ],
        recommendedFlow: 'webhook -> coordinator -> agents -> response',
        timestamp: new Date().toISOString()
      });
    });
    
    this.demoServer = app.listen(this.demoPort, () => {
      console.log(\`✅ Demo Web Server started on port \${this.demoPort}\`);
    });
  }

  displayConnectionInfo() {
    console.log('\\n🎯 MAPLE Demo Connection Information:');
    console.log('==========================================');
    console.log(\`📊 Demo Dashboard: http://localhost:\${this.demoPort}\`);
    console.log(\`🐍 Python Bridge:  http://localhost:\${this.pythonBridgePort}\`);
    console.log(\`🌐 WebSocket:      ws://localhost:\${this.webSocketPort}\`);
    console.log('\\n🔧 n8n Credentials Configuration:');
    console.log(\`   Connection Type: hybrid\`);
    console.log(\`   Broker URL:      ws://localhost:\${this.webSocketPort}\`);
    console.log(\`   Python Bridge:   http://localhost:\${this.pythonBridgePort}\`);
    console.log(\`   API Key:         demo-key-12345\`);
    console.log(\`   Agent ID:        n8n-demo-agent\`);
    console.log('\\n🎉 Ready for n8n integration!');
    console.log('👨‍💻 Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)');
  }

  setupCleanup() {
    const cleanup = async () => {
      console.log('\\n🧹 Cleaning up MAPLE Demo...');
      await this.cleanup();
      process.exit(0);
    };
    
    process.on('SIGINT', cleanup);
    process.on('SIGTERM', cleanup);
    process.on('SIGUSR1', cleanup);
    process.on('SIGUSR2', cleanup);
  }

  async cleanup() {
    if (this.pythonProcess) {
      console.log('🛑 Stopping Python Bridge...');
      this.pythonProcess.kill();
      this.pythonProcess = null;
    }
    
    if (this.webSocketServer) {
      console.log('🛑 Stopping WebSocket Server...');
      this.webSocketServer.close();
      this.webSocketServer = null;
    }
    
    if (this.demoServer) {
      console.log('🛑 Stopping Demo Web Server...');
      this.demoServer.close();
      this.demoServer = null;
    }
    
    console.log('✅ Cleanup complete');
  }
}

// Launch the demo if this script is run directly
if (require.main === module) {
  const launcher = new MAPLEDemoLauncher();
  launcher.launch().catch(error => {
    console.error('❌ Launch failed:', error);
    process.exit(1);
  });
}

module.exports = MAPLEDemoLauncher;
