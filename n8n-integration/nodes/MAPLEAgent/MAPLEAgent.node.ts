import {
  IExecuteFunctions,
  INodeExecutionData,
  INodeType,
  INodeTypeDescription,
  NodeOperationError,
} from 'n8n-workflow';

import { MAPLEClient } from '../../lib/MAPLEClient';

// Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

export class MAPLEAgent implements INodeType {
  description: INodeTypeDescription = {
    displayName: 'MAPLE Agent',
    name: 'mapleAgent',
    icon: 'file:maple.svg',
    group: ['ai'],
    version: 1,
    subtitle: '={{$parameter["operation"] + ": " + $parameter["agentId"]}}',
    description: 'Interact with MAPLE agents for multi-agent AI workflows. Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)',
    defaults: {
      name: 'MAPLE Agent',
    },
    inputs: ['main'],
    outputs: ['main'],
    credentials: [
      {
        name: 'mapleApi',
        required: true,
      },
    ],
    properties: [
      {
        displayName: 'Operation',
        name: 'operation',
        type: 'options',
        options: [
          {
            name: 'Send Message',
            value: 'sendMessage',
            description: 'Send a message to an agent',
          },
          {
            name: 'Create Agent',
            value: 'createAgent',
            description: 'Create a new MAPLE agent',
          },
          {
            name: 'Execute Task',
            value: 'executeTask',
            description: 'Execute a task on an agent',
          },
          {
            name: 'Get Status',
            value: 'getStatus',
            description: 'Get agent status information',
          },
          {
            name: 'Allocate Resources',
            value: 'allocateResources',
            description: 'Allocate resources for tasks',
          },
        ],
        default: 'sendMessage',
        noDataExpression: true,
      },
      {
        displayName: 'Agent ID',
        name: 'agentId',
        type: 'string',
        default: '',
        placeholder: 'e.g., research-agent-001',
        description: 'Unique identifier for the MAPLE agent',
        required: true,
      },
      {
        displayName: 'Message Type',
        name: 'messageType',
        type: 'options',
        options: [
          { name: 'Task Request', value: 'TASK_REQUEST' },
          { name: 'Data Query', value: 'DATA_QUERY' },
          { name: 'Analysis Request', value: 'ANALYSIS_REQUEST' },
          { name: 'Generate Content', value: 'GENERATE_CONTENT' },
          { name: 'Process Data', value: 'PROCESS_DATA' },
          { name: 'Search Web', value: 'SEARCH_WEB' },
          { name: 'Analyze Content', value: 'ANALYZE_CONTENT' },
          { name: 'Generate Summary', value: 'GENERATE_SUMMARY' },
          { name: 'Custom', value: 'CUSTOM' },
        ],
        default: 'TASK_REQUEST',
        displayOptions: {
          show: {
            operation: ['sendMessage'],
          },
        },
      },
      {
        displayName: 'Custom Message Type',
        name: 'customMessageType',
        type: 'string',
        default: '',
        placeholder: 'e.g., CUSTOM_ANALYSIS',
        displayOptions: {
          show: {
            operation: ['sendMessage'],
            messageType: ['CUSTOM'],
          },
        },
      },
      {
        displayName: 'Priority',
        name: 'priority',
        type: 'options',
        options: [
          { name: 'High', value: 'HIGH' },
          { name: 'Medium', value: 'MEDIUM' },
          { name: 'Low', value: 'LOW' },
        ],
        default: 'MEDIUM',
        displayOptions: {
          show: {
            operation: ['sendMessage', 'executeTask'],
          },
        },
      },
      {
        displayName: 'Capabilities',
        name: 'capabilities',
        type: 'fixedCollection',
        placeholder: 'Add Capability',
        typeOptions: {
          multipleValues: true,
        },
        default: { capability: [] },
        displayOptions: {
          show: {
            operation: ['createAgent'],
          },
        },
        options: [
          {
            name: 'capability',
            displayName: 'Capability',
            values: [
              {
                displayName: 'Name',
                name: 'name',
                type: 'string',
                default: '',
                placeholder: 'e.g., text-analysis, web-search, content-generation',
              },
              {
                displayName: 'Description',
                name: 'description',
                type: 'string',
                default: '',
                placeholder: 'e.g., Analyze text content for insights',
              },
            ],
          },
        ],
      },
      {
        displayName: 'Task Configuration',
        name: 'taskConfig',
        type: 'json',
        default: '{"task": "analyze", "data": "input data"}',
        placeholder: '{"task": "analyze", "data": "..."}',
        description: 'JSON object containing task parameters',
        displayOptions: {
          show: {
            operation: ['executeTask'],
          },
        },
      },
      {
        displayName: 'Resource Requirements',
        name: 'resources',
        type: 'fixedCollection',
        placeholder: 'Add Resource',
        typeOptions: {
          multipleValues: false,
        },
        default: {},
        displayOptions: {
          show: {
            operation: ['createAgent', 'executeTask', 'allocateResources'],
          },
        },
        options: [
          {
            name: 'resourceRequirement',
            displayName: 'Resource Requirement',
            values: [
              {
                displayName: 'Compute Cores',
                name: 'compute',
                type: 'number',
                default: 1,
                description: 'Number of CPU cores required',
              },
              {
                displayName: 'Memory',
                name: 'memory',
                type: 'string',
                default: '1GB',
                placeholder: 'e.g., 4GB, 512MB',
                description: 'Memory requirement (e.g., 4GB, 512MB)',
              },
              {
                displayName: 'Storage',
                name: 'storage',
                type: 'string',
                default: '1GB',
                placeholder: 'e.g., 10GB, 1TB',
                description: 'Storage requirement (e.g., 10GB, 1TB)',
              },
              {
                displayName: 'Bandwidth',
                name: 'bandwidth',
                type: 'string',
                default: '100Mbps',
                placeholder: 'e.g., 1Gbps, 100Mbps',
                description: 'Bandwidth requirement',
              },
              {
                displayName: 'Deadline',
                name: 'deadline',
                type: 'string',
                default: '',
                placeholder: 'e.g., 2024-12-31T23:59:59Z',
                description: 'ISO datetime when resources must be available',
              },
              {
                displayName: 'Timeout',
                name: 'timeout',
                type: 'string',
                default: '30s',
                placeholder: 'e.g., 30s, 5m, 1h',
                description: 'Maximum time to wait for resources',
              },
            ],
          },
        ],
      },
      {
        displayName: 'Agent Configuration',
        name: 'agentConfig',
        type: 'json',
        default: '{"maxConcurrency": 5, "timeout": "30s"}',
        placeholder: '{"maxConcurrency": 5, "timeout": "30s"}',
        description: 'JSON configuration for the agent',
        displayOptions: {
          show: {
            operation: ['createAgent'],
          },
        },
      },
      {
        displayName: 'Enable Error Recovery',
        name: 'enableErrorRecovery',
        type: 'boolean',
        default: true,
        description: 'Whether to enable automatic error recovery',
      },
      {
        displayName: 'Max Retry Attempts',
        name: 'maxRetryAttempts',
        type: 'number',
        default: 3,
        description: 'Maximum number of retry attempts on failure',
        displayOptions: {
          show: {
            enableErrorRecovery: [true],
          },
        },
      },
    ],
  };

  async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
    const items = this.getInputData();
    const operation = this.getNodeParameter('operation', 0) as string;
    const agentId = this.getNodeParameter('agentId', 0) as string;
    const enableErrorRecovery = this.getNodeParameter('enableErrorRecovery', 0, true) as boolean;
    const maxRetryAttempts = this.getNodeParameter('maxRetryAttempts', 0, 3) as number;

    const credentials = await this.getCredentials('mapleApi');
    const client = new MAPLEClient({
      brokerUrl: credentials.brokerUrl as string,
      apiKey: credentials.apiKey as string,
      agentId: credentials.agentId as string,
      pythonBridgeUrl: credentials.pythonBridgeUrl as string,
      requestTimeout: credentials.requestTimeout as number || 30000,
      reconnect: credentials.enableReconnect as boolean || true,
      maxReconnectAttempts: credentials.maxReconnectAttempts as number || 5,
    });

    try {
      const connectResult = await client.connect();
      if (!connectResult.isOk) {
        throw new NodeOperationError(
          this.getNode(),
          `Failed to connect to MAPLE: ${connectResult.error}`
        );
      }
    } catch (error: any) {
      throw new NodeOperationError(
        this.getNode(),
        `Failed to connect to MAPLE broker: ${error.message}`
      );
    }

    const returnData: INodeExecutionData[] = [];

    for (let i = 0; i < items.length; i++) {
      let attempts = 0;
      let lastError: any = null;

      while (attempts <= maxRetryAttempts) {
        try {
          let result: any;

          switch (operation) {
            case 'sendMessage':
              const messageType = this.getNodeParameter('messageType', i) as string;
              const customMessageType = this.getNodeParameter('customMessageType', i, '') as string;
              const priority = this.getNodeParameter('priority', i) as 'HIGH' | 'MEDIUM' | 'LOW';
              
              const finalMessageType = messageType === 'CUSTOM' ? customMessageType : messageType;
              
              const sendResult = await client.sendMessage({
                header: {
                  messageType: finalMessageType,
                  receiver: agentId,
                  priority,
                },
                payload: items[i].json,
                metadata: {
                  correlationId: items[i].json.correlationId || undefined,
                  source: 'n8n-workflow',
                  operation: 'sendMessage',
                },
              });

              if (sendResult.isOk) {
                result = sendResult.value;
              } else {
                throw new Error(sendResult.error);
              }
              break;

            case 'createAgent':
              const capabilities = this.getNodeParameter('capabilities', i, { capability: [] }) as any;
              const agentConfigStr = this.getNodeParameter('agentConfig', i, '{}') as string;
              const resourceReq = this.getNodeParameter('resources', i, {}) as any;
              
              let agentConfig;
              try {
                agentConfig = JSON.parse(agentConfigStr);
              } catch (error: any) {
                throw new NodeOperationError(
                  this.getNode(),
                  `Invalid JSON in agent configuration: ${error.message}`
                );
              }

              const agentCapabilities = capabilities.capability?.map((cap: any) => cap.name) || [];
              
              const createResult = await client.createAgent({
                agentId,
                capabilities: agentCapabilities,
                config: {
                  ...agentConfig,
                  resources: resourceReq.resourceRequirement || {},
                  ...items[i].json.config || {},
                },
              });

              if (createResult.isOk) {
                result = createResult.value;
              } else {
                throw new Error(createResult.error);
              }
              break;

            case 'executeTask':
              const taskConfigStr = this.getNodeParameter('taskConfig', i) as string;
              const taskResources = this.getNodeParameter('resources', i, {}) as any;
              const taskPriority = this.getNodeParameter('priority', i) as 'HIGH' | 'MEDIUM' | 'LOW';
              
              let taskConfig;
              try {
                taskConfig = JSON.parse(taskConfigStr);
              } catch (error: any) {
                throw new NodeOperationError(
                  this.getNode(),
                  `Invalid JSON in task configuration: ${error.message}`
                );
              }

              const executeResult = await client.executeTask({
                agentId,
                task: { ...taskConfig, ...items[i].json },
                resources: taskResources.resourceRequirement || {},
                priority: taskPriority,
              });

              if (executeResult.isOk) {
                result = executeResult.value;
              } else {
                throw new Error(executeResult.error);
              }
              break;

            case 'getStatus':
              const statusResult = await client.getAgentStatus(agentId);
              
              if (statusResult.isOk) {
                result = statusResult.value;
              } else {
                throw new Error(statusResult.error);
              }
              break;

            case 'allocateResources':
              const allocateResources = this.getNodeParameter('resources', i, {}) as any;
              const resourceRequest = allocateResources.resourceRequirement || {};

              const allocateResult = await client.allocateResources(resourceRequest);
              
              if (allocateResult.isOk) {
                result = allocateResult.value;
              } else {
                throw new Error(allocateResult.error);
              }
              break;

            default:
              throw new NodeOperationError(
                this.getNode(),
                `Unknown operation: ${operation}`
              );
          }

          // Success - add result and break retry loop
          returnData.push({
            json: {
              success: true,
              operation,
              agentId,
              result,
              timestamp: new Date().toISOString(),
              attempts: attempts + 1,
              creator: 'Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)',
              ...result,
            },
          });
          break;

        } catch (error: any) {
          attempts++;
          lastError = error;

          if (!enableErrorRecovery || attempts > maxRetryAttempts) {
            if (this.continueOnFail()) {
              returnData.push({
                json: {
                  success: false,
                  operation,
                  agentId,
                  error: error.message,
                  timestamp: new Date().toISOString(),
                  attempts,
                  creator: 'Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)',
                },
              });
              break;
            } else {
              throw new NodeOperationError(this.getNode(), error.message);
            }
          }

          // Wait before retrying (exponential backoff)
          const delay = Math.min(1000 * Math.pow(2, attempts - 1), 5000);
          await new Promise(resolve => setTimeout(resolve, delay));
        }
      }
    }

    client.disconnect();
    return [returnData];
  }
}
